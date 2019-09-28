#!/usr/bin/python3
#-*- coding: utf-8 -*-

# emr_diff.py - finding diffs between visits at NCKUH

# Author: Chang-Yi Yen
# License: coffeeware
# Initially created in May 2019

import argparse
import difflib
import datetime
import os
import pathlib
import re
import sys
import urllib.request

import bs4

from lib import session

if __name__ == '__main__':
    # Change working directory to location of this script
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
    except OSError:
        print("[Error] Couldn't change working directory to location of this script", file=sys.stderr)
    parser = argparse.ArgumentParser(description="Comparing notes from the NCKUH EMR",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    # TODO: add mechanism to compare whole notes, diagnoses, or SOAP only
    # Whole note: Diagnosis (including ICD codes), Subjective, Objective, Assessment & Plan (in a unified block)
    # SOAP: Subjective, Objective, Assessment (actually Diagnosis but without ICD codes), Assessment & Plan
    # TODO: add ability to parse inpatient records?
    #parser.add_argument("--mode", choices=["PN", "OPD"], default="OPD", help="Specify parts of records to compare; 'OPD' for outpatient, 'PN' for progress")
    parser.add_argument("-u", "--uid", type=str, required=True, help="User ID")
    parser.add_argument("-p", "--passwd", type=str, required=True, help="Password")
    parser.add_argument("-c", "--chartno", type=str, required=True, help="Chart number")
    parser.add_argument("-s", "--startdate", type=str, help="Starting date in ISO8601 format", default="2019-01-01")
    parser.add_argument("-o", "--outputdir", type=str, help="Set output directory", default=pathlib.Path.cwd().parent / 'cache')
    parser.add_argument("-e", "--enddate", type=str, help="Ending date in ISO8601 format (defaults to today)", default=datetime.date.today().isoformat())
    parser.add_argument("-r", "--reverse", action="store_true", help="Reverse output chronology")
    parser.add_argument("-w", "--wraplen", type=int, help="Set table wrap length", default=50)
    parser.add_argument("--version", action="version", version="%(prog)s 0.2.1 'Annihilation'")
    args = parser.parse_args()

    if args.debug:
        print("[DEBUG] UID: ", args.uid, file=sys.stderr)
        print("[DEBUG] Chart number: ", args.chartno, file=sys.stderr)
        print("[DEBUG] Start date: ", args.startdate, file=sys.stderr)
        print("[DEBUG] End date: ", args.enddate, file=sys.stderr)

    ROOTURL = "http://hisweb.hosp.ncku/EmrQuery/" + "(S(" + session.get_sessionid(args) + "))/" + "tree/"

    # Get list of visits

    visit_list_url = "list2.aspx?" + "chartno=" + args.chartno + "&start=" + args.startdate + "&stop=" + args.enddate + "&query=0"
    with urllib.request.urlopen(ROOTURL + visit_list_url) as f:
        visit_list = f.read().decode("utf-8")

    # Parse visit list: get IDs of each visit ("medicalsn") and put each into bins based on name of attending
    d = dict()
    ## build regex
    ## 'O' prefix for outpatient, 'I' prefix for inpatient
    o_regex = re.compile("^((?!type).)*medicalsn=(O.+)$")
    ## Regex for name of attending. The spaces on either end are '\xa0' symbols (non-breaking spaces), as parsed from the HTML "&nbsp;".
    n_regex = re.compile("[0-9]\xa0(.+)\xa0.+$")
    visit_list_soup = bs4.BeautifulSoup(visit_list, "html.parser")
    visits = visit_list_soup.find_all("a", href=o_regex)
    for i in visits:
        name = re.search(n_regex, i.text).groups()[0]
        ## No autovivification in Python...
        if name not in d.keys():
            d[name] = []
        d[name].append(re.search(o_regex, i["href"]).groups()[1])
    for i in d.keys():
        d[i] = set(d[i])
        d[i] = list(d[i])
        d[i].sort()
    # Retrieve OPD notes of each attending and calculate unified diffs
    # (assuming that each attending uses his own notes as a base)
    # TODO: Build a mechanism for selecting which parts to calculate a delta on
    segment_names = ("Subjective", "Objective", "Diagnosis", "Assessment & Plan")
    # List of diagnoses
    diagnoses = []
    date_regex = re.compile("\d{4}/\d{2}/\d{2} \d{2}:\d{2}")
    # HTML output, generated as a string. Double curly braces are used for the stylesheet since single ones trigger string formatting (and hence errors). Stylesheet copied from difflib.HtmlDiff.make_file output.
    # TODO: consider reworking this to use normal text output from difflib
    # along with Jinja2 templates, since the difflib.HtmlDiff output kind of
    # sucks.
    html_out = "<html lang='en'>\n<head>\n  <meta charset='utf-8'>\n  <title>OPD Visit Diff Report for {patient}</title>\n  <style type='text/css'>\n    table.diff {{font-family:Courier; border:medium;}}\n    .diff_header {{background-color:#e0e0e0}}\n    td.diff_header {{text-align:right}}\n    .diff_next {{background-color:#c0c0c0}}\n    .diff_add {{background-color:#aaffaa}}\n    .diff_chg {{background-color:#ffff77}}\n    .diff_sub {{background-color:#ffaaaa}}\n    #toc_container {{border: 1px solid #aaa; padding: 20px; width: auto;}}\n    .toc_title {{text-align: center;}}\n  </style>\n</head>\n<body>\n".format(patient=args.chartno)

    toc = "  <div id='toc_container'>\n    <ul>\n"
    for name in d.keys():
        toc = toc + "      <li><a href='#" + name + "'>" + name + "</a></li>\n"
    html_out = html_out + toc + "    </ul>\n  </div>\n"

    for name in d.keys():
        print(("### Notes for Dr. " + name + " ###").encode('utf-8'))
        html_out += "  <hr/>\n  <p><h2 id='{doctor}'>Notes for Dr. {doctor}</h2></p>\n".format(doctor=name)
        d[name].sort()
        # Comparing all components
        cache = [[],[],[],[]] # cache for note
        total_diffs = ""
        for v in range(0,len(d[name])):
            n = urllib.request.urlopen(ROOTURL+"viewer.aspx?type=soap"+"&chartno="+args.chartno+"&medicalsn="+d[name][v]).read().decode("utf-8")# fetch note
            note = bs4.BeautifulSoup(n, "html.parser")
            # Get time of visit from header
            header = note.find(attrs={"class":"portlet-header"})
            date = re.search(date_regex, header.text).group()
            main_text = note.find(attrs={"class":"portlet-content"}).findChildren(attrs={"class":"small"})
            print("=== Visit at " + date + " (medicalsn", d[name][v], ") ===")
            diff = "\n  <p><h3>Visit at {date} (medicalsn {medicalsn})</h3></p>\n".format(date=date, medicalsn=d[name][v])
            # Subjective: main_text[0], objective: main_text[1], assessment: main_text[2], plan: main_text[3]
            # (main_text[4] contains lab tests but this is more clearly expressed and worked on with the relevant LIS tools)
            # Skip note if there are less than 4 segments (e.g. when the visit is just for vaccination)
            if len(main_text) < 4:
                continue
            # Pseudocode:
            #if d not in [i[0] for i in diagnosis]:
            #    diagnosis.append([d, name, date])
            for i in (2,0,1,3):
                segment = [x for x in main_text[i].stripped_strings]
                #print("=== ", segment_names[i], " ===")
                #for j in difflib.ndiff(cache[i], segment):
                #    print(j)
                u = difflib.HtmlDiff(tabsize=4, wrapcolumn=args.wraplen)
                diff += "  <p><h4>{s}</h4></p>\n".format(s=segment_names[i])
                diff += u.make_table(cache[i], segment, context=True, numlines=3)
                cache[i] = segment
            if args.reverse:
                total_diffs = diff + total_diffs
            else:
                total_diffs += diff
        html_out += total_diffs
    html_out += "\n</body>\n</html>"

    outpath = pathlib.Path(args.outputdir) / (args.chartno + "_diff_" + args.startdate + "_" + args.enddate + ".html") 
    with open(outpath, mode="w", encoding="utf-8") as fh:
        print(html_out, file=fh)

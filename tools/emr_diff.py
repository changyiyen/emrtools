#!/usr/bin/python3
#-*- coding: utf-8 -*-

# emr_diff.py - finding diffs between visits at NCKUH

# Author: Chang-Yi Yen
# License: coffeeware
# Initially created in May 2019

import argparse
import difflib
import datetime
import http.cookiejar
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request

import bs4

def get_sessionid(args):
    # Get session ID from EMR server using credentials
    ## POST to http://hisweb.hosp.ncku/WebsiteSSO/PCS/default.aspx
    ## ID: TextBoxId
    ## password: TextBoxPwd
    ## example inputs:
    ##   <input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="/wEPDwUKMjEyMTE0NTgwOA9kFgICAw9kFgICAQ8PFgIeBFRleHQFHuaIkOWkp+e4vemZouihjOWLleafpeaIv+ezu+e1sWRkZB6p3RfEPfN0hx7RbZxTBsfMwyzg" />
    ##   <input type="hidden" name="__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="10DD8462" />
    ##   <input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="/wEWBAL688C9DAL904ynDgLw08jWBgKM54rGBhfM2hnGG474WVqlhp014eAAKM18" />
    ##   <input type="submit" name="Button1" value="登入系統" id="Button1" />
    # Cookie storage is required
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    login = opener.open("http://hisweb.hosp.ncku/WebsiteSSO/PCS/").read().decode()
    login_soup = bs4.BeautifulSoup(login, "html.parser")
    VIEWSTATE = login_soup.find("input", attrs={"name":"__VIEWSTATE"})["value"]
    VIEWSTATEGENERATOR = login_soup.find("input", attrs={"name":"__VIEWSTATEGENERATOR"})["value"]
    EVENTVALIDATION = login_soup.find("input", attrs={"name":"__EVENTVALIDATION"})["value"]

    if args.debug:
        print("[DEBUG] VIEWSTATE: ", VIEWSTATE, file=sys.stderr)
        print("[DEBUG] VIEWSTATEGENERATOR: ", VIEWSTATEGENERATOR, file=sys.stderr)
        print("[DEBUG] EVENTVALIDATION: ", EVENTVALIDATION, file=sys.stderr)

    post_url = "http://hisweb.hosp.ncku/WebsiteSSO/PCS/default.aspx"

    post_fields = {
        "TextBoxId": args.uid,
        "TextBoxPwd": args.passwd,
        "__VIEWSTATE": VIEWSTATE,
        "__VIEWSTATEGENERATOR": VIEWSTATEGENERATOR,
        "__EVENTVALIDATION": EVENTVALIDATION,
        "Button1": "登入系統"
    }
    post_request = urllib.request.Request(post_url, urllib.parse.urlencode(post_fields).encode())
    post_reply = opener.open(post_request).read().decode()
    ## Redirects to a location that looks like: http://hisweb.hosp.ncku/WebSiteSSO/wLogin.aspx?ReturnUrl=http://hisweb.hosp.ncku/WebsiteSSO/PCS/PCSPatList.aspx&ci=POjCkPFiJ3DqylhccRv0oxVzYYPLlhEaaZ9cMO3Iv%2bM2w9kJ2EalG0BQ7KPPm1Qv
    ## Redirects to http://hisweb.hosp.ncku/WebsiteSSO/PCS/PCSPatList.aspx which contains a table of patients with id=GridView1

    ## Requesting http://hisweb.hosp.ncku/WebsiteSSO/PCS/showchart.aspx?chartno=01641893 gets:
    ## http://hisweb.hosp.ncku/EmrQuery/autologin.aspx?chartno=01641893&systems=0 then
    ## http://hisweb.hosp.ncku/EmrQuery/(S(l3wcfyew4iwb2155gpb2mb55))/autologin.aspx?chartno=01641893&systems=0
    ## Apparently requesting "http://hisweb.hosp.ncku/WebsiteSSO/PCS/showchart.aspx?chartno=..." does *not* work (a 500 Internal Error is returned)
    emr_reply = opener.open("http://hisweb.hosp.ncku/EmrQuery/autologin.aspx?chartno=" + args.chartno + "&systems=0")

    if args.debug:
        print("[DEBUG] EMR reply:", emr_reply, file=sys.stderr)

    session_id = re.search("S\(([a-z0-9]+)\)", emr_reply.geturl()).groups()[0]

    return session_id

if __name__ == '__main__':
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
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.1 'Annihilation'")
    args = parser.parse_args()

    CHARTNO = args.chartno
    STARTDATE = args.startdate
    ENDDATE = args.enddate

    if args.debug:
        print("[DEBUG] UID: ", args.uid, file=sys.stderr)
        print("[DEBUG] Chart number: ", CHARTNO, file=sys.stderr)
        print("[DEBUG] Start date: ", STARTDATE, file=sys.stderr)
        print("[DEBUG] End date: ", ENDDATE, file=sys.stderr)

    ROOTURL = "http://hisweb.hosp.ncku/EmrQuery/" + "(S(" + get_sessionid(args) + "))/" + "tree/"

    # Get list of visits

    visit_list_url = "list2.aspx?" + "chartno=" + CHARTNO + "&start=" + STARTDATE + "&stop=" + ENDDATE + "&query=0"
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
    html_out = "<html lang='en'>\n<head>\n  <meta charset='utf-8'>\n  <title>OPD Visit Diff Report for {patient}</title>\n  <style type='text/css'>\n    table.diff {{font-family:Courier; border:medium;}}\n    .diff_header {{background-color:#e0e0e0}}\n    td.diff_header {{text-align:right}}\n    .diff_next {{background-color:#c0c0c0}}\n    .diff_add {{background-color:#aaffaa}}\n    .diff_chg {{background-color:#ffff77}}\n    .diff_sub {{background-color:#ffaaaa}}\n    #toc_container {{border: 1px solid #aaa; padding: 20px; width: auto;}}\n    .toc_title {{text-align: center;}}\n  </style>\n</head>\n<body>\n".format(patient=CHARTNO)

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
            n = urllib.request.urlopen(ROOTURL+"viewer.aspx?type=soap"+"&chartno="+CHARTNO+"&medicalsn="+d[name][v]).read().decode("utf-8")# fetch note
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

    outpath = pathlib.Path(args.outputdir) / (CHARTNO + "_diff_" + args.startdate + "_" + args.enddate + ".html") 
    with open(outpath, mode="w", encoding="utf-8") as fh:
        print(html_out, file=fh)

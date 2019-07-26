#!/usr/bin/env python3
#-*- coding: utf-8 -*-

# emr_diagnosis.py - listing of diagnoses made at NCKUH

# Author: Chang-Yi Yen
# License: coffeeware
# Initially created in May 2019

import argparse
import datetime
import http.cookiejar
import pathlib
import re
import sys
import urllib.parse
import urllib.request

import bs4

def get_sessionid(args):
    # Get session ID from EMR server using credentials
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
    ## Apparently requesting "http://hisweb.hosp.ncku/WebsiteSSO/PCS/showchart.aspx?chartno=..." does *not* work (a 500 Internal Error is returned)
    emr_reply = opener.open("http://hisweb.hosp.ncku/EmrQuery/autologin.aspx?chartno=" + args.chartno + "&systems=0")

    if args.debug:
        print("[DEBUG] EMR reply:", emr_reply, file=sys.stderr)

    session_id = re.search("S\(([a-z0-9]+)\)", emr_reply.geturl()).groups()[0]

    return session_id

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Retrieval of diagnoses from NCKUH EMR, sorted by date of first appearance in note",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    parser.add_argument("-u", "--uid", type=str, required=True, help="User ID")
    parser.add_argument("-p", "--passwd", type=str, required=True, help="Password")
    parser.add_argument("-c", "--chartno", type=str, required=True, help="Chart number")
    parser.add_argument("-s", "--startdate", type=str, help="Starting date in ISO8601 format", default="2019-01-01")
    parser.add_argument("-e", "--enddate", type=str, help="Ending date in ISO8601 format (defaults to today)", default=datetime.date.today().isoformat())
    ## TODO: modify HTML output to include sorting within page
    #parser.add_argument("-r", "--reverse", action="store_true", help="Reverse output chronology")
    parser.add_argument("-o", "--outputdir", type=str, help="Set output directory", default=pathlib.Path.cwd().parent / 'cache')
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.1 'Annihilation'")
    args = parser.parse_args()

    CHARTNO = args.chartno
    STARTDATE = args.startdate
    ENDDATE = args.enddate
    
    # Input validation
    assert re.match('\d{6}', CHARTNO), "ID number malformed (less than 6 digits)"
    assert re.match('\d{8}', CHARTNO), "Chart number malformed (less than 8 digits)"
    try:
        datetime.datetime.strptime(STARTDATE, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Incorrect start date format (should be YYYY-MM-DD)")
    try:
        datetime.datetime.strptime(ENDDATE, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Incorrect end date format (should be YYYY-MM-DD)")

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

    # Build regexes
    date_regex = re.compile("\d{4}/\d{2}/\d{2} \d{2}:\d{2}")
    ## 'O' prefix for outpatient, 'I' prefix for inpatient, 'E' prefix for ED
    o_regex = re.compile("^((?!type).)*medicalsn=(O.+)$") # TODO: consider changing this to grab the diagnosis subpage only
    i_regex = re.compile("type=PL.+medicalsn=(I.+)$") # TODO: design better regex here?
    #e_regex = re.compile("^((?!type).)*medicalsn=(E.+)$") # ED records of limited utility due to being based on (possibly improper) ICD-10 codes
    ## Regex for name of attending. The spaces on either end are '\xa0' symbols (non-breaking spaces), as parsed from the HTML "&nbsp;". Digit on the front is from the date.
    n_regex = re.compile("[0-9]\xa0(.+)\xa0.+$")
    
    visit_list_soup = bs4.BeautifulSoup(visit_list, "html.parser")
    o_visits = visit_list_soup.find_all("a", href=o_regex)
    i_visits = visit_list_soup.find_all("a", href=i_regex)
    #e_visits = visit_list_soup.find_all("a", href=e_regex)

    diagnoses = dict()

    # Outpatient visits #
    for i in o_visits:
        v = urllib.request.urlopen(ROOTURL+i.attrs['href']).read().decode('utf-8')
        date = re.search(date_regex, v).group()
        d = bs4.BeautifulSoup(v, 'html.parser').findChildren('p')[1]
        #o_diagnoses = [re.search('\W?\d+[.](.+)$',i).groups()[0] for i in d.strings if re.search('\W?\d+[.](.+)$', i) != None]
        o_diagnoses = [i for i in d.strings]
        o_diagnoses.pop(0)
        attending = re.search('醫師 : (.+?)\W', v).groups()[0]
        for j in o_diagnoses:
            if j in diagnoses.keys() and diagnoses[j][0] < date:
                continue
            else:
                diagnoses[j] = (date, attending)

    # Inpatient visits #
    ## Worth noting that 'viewer_v2' seems to be for a past inpatient stay while 'iviewer' is for a current stay
    ## Also worth noting: problem list can actually be empty (!) for certain old visits
    for i in i_visits:
        v = urllib.request.urlopen(ROOTURL+i.attrs['href']).read().decode('utf-8')
        try:
            date = re.search(date_regex, v).group()
        except AttributeError:
            print(v)
            print("[Error] ISO8601-formatted date not found", file=sys.stderr)
            continue
        i_diagnoses = [i.text for i in bs4.BeautifulSoup(v, 'html.parser').findChildren('td',attrs={'width':''})[4:]]
        attending = re.search('醫師 : (.+?)\W', v).groups()[0]
        for j in i_diagnoses:
            if j in diagnoses.keys() and diagnoses[j][0] < date:
                continue
            else:
                diagnoses[j] = (date, attending)

    # Emergency department visits #
    ## Doubts about finishing this part since it is of limited utility
    #for i in e_visits:
        # ...

    # Change diagnoses from dict to list; list of tuples of the form (diagnosis, date, attending)
    diagnoses = [(i, diagnoses[i][0], diagnoses[i][1]) for i in diagnoses.keys()]

    # Sort by date
    diagnoses.sort(key=lambda x: x[1])

    html_out = "<html lang='en'>\n<head>\n  <meta charset='utf-8'>\n  <title>Diagnosis log for {patient}</title>\n</head>\n<body>\n".format(patient=CHARTNO)
    js = ""
    table_head = "  <table>\n    <tr>\n      <th>Diagnosis</th><th>Date</th><th>Attending physician</th>\n"
    table_content = ""
    table_footer = "  </table>\n</body>\n</html>"
    for i in diagnoses:
        table_content = table_content + "      <tr><td>" + i[0] + "</td><td>" + i[1] + "</td><td>" + i[2] + "</td></tr>\n"
    html_out = html_out + table_head + table_content + table_footer 

    # Note that the default encoding on other OSs may not be UTF-8
    outpath = pathlib.Path(args.outputdir) / (CHARTNO + "_diag_" + args.startdate + "_" + args.enddate + ".html")
    with open(outpath, mode="w", encoding="utf-8") as fh:
        print(html_out, file=fh)

#!/usr/bin/python3
#-*- coding: utf-8 -*-

# emr_encounters.py - listing of encounter IDs at NCKUH

# Author: Chang-Yi Yen
# License: coffeeware
# Initially created in July 2019

import argparse
import csv
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
    parser = argparse.ArgumentParser(description="Retrieval of encounter IDs ('medicalsn') from NCKUH EMR",
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
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0 'Annihilation'")
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
    o_regex = re.compile("medicalsn=(O\d+)")
    i_regex = re.compile("medicalsn=(I\d+)")
    e_regex = re.compile("medicalsn=(E\d+)")
    
    visit_list_soup = bs4.BeautifulSoup(visit_list, "html.parser")
    o_visits = visit_list_soup.find_all("a", href=o_regex)
    i_visits = visit_list_soup.find_all("a", href=i_regex)
    e_visits = visit_list_soup.find_all("a", href=e_regex)

    o_set = set()
    i_set = set()
    e_set = set()

    # Outpatient visits #
    for i in o_visits:
        o_set.add(re.search(o_regex, i['href']).groups(0)[0])

    # Inpatient visits #
    ## Worth noting that 'viewer_v2' seems to be for a past inpatient stay while 'iviewer' is for a current stay
    for i in i_visits:
        i_set.add(re.search(i_regex, i['href']).groups(0)[0])

    # Emergency department visits #
    for i in e_visits:
        e_set.add(re.search(e_regex, i['href']).groups(0)[0])
        
    out_list = list()
    out_list.extend(sorted(list(o_set)))
    out_list.extend(sorted(list(i_set)))
    out_list.extend(sorted(list(e_set)))

    # Note that the default encoding on other OSs may not be UTF-8
    outpath = pathlib.Path(args.outputdir) / (CHARTNO + "_enct_" + args.startdate + "_" + args.enddate + ".csv")
    with open(outpath, mode="w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Chart number", "Encounter ID"])
        for i in out_list:
            writer.writerow([args.chartno, i])
#!/usr/bin/python3
#-*- coding: utf-8 -*-

# emr_encounters.py - listing of encounter IDs at NCKUH

# Author: Chang-Yi Yen
# License: coffeeware
# Initially created in July 2019

import argparse
import csv
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
    parser = argparse.ArgumentParser(description="Retrieval of encounter IDs ('medicalsn') from NCKUH EMR",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    parser.add_argument("-u", "--uid", type=str, required=True, help="User ID")
    parser.add_argument("-p", "--passwd", type=str, required=True, help="Password")
    parser.add_argument("-c", "--chartno", type=str, required=True, help="Chart number")
    parser.add_argument("-s", "--startdate", type=str, help="Starting date in ISO8601 format", default="2019-01-01")
    parser.add_argument("-e", "--enddate", type=str, help="Ending date in ISO8601 format (defaults to today)", default=datetime.date.today().isoformat())
    #parser.add_argument("-r", "--reverse", action="store_true", help="Reverse output chronology")
    parser.add_argument("-l", "--latest", action="store_true", help="Print the patient's latest inpatient encounter ID to standard output")
    parser.add_argument("-o", "--outputdir", type=str, help="Set output directory", default=pathlib.Path.cwd().parent / 'cache')
    parser.add_argument("--version", action="version", version="%(prog)s 0.2.1 'Annihilation'")
    args = parser.parse_args()

    # Input validation
    assert re.match('\d{6}', args.uid), "ID number malformed (less than 6 digits)"
    assert re.match('\d{8}', args.chartno), "Chart number malformed (less than 8 digits)"
    try:
        datetime.datetime.strptime(args.startdate, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Incorrect start date format (should be YYYY-MM-DD)")
    try:
        datetime.datetime.strptime(args.enddate, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Incorrect end date format (should be YYYY-MM-DD)")

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

    if args.latest:
        print(sorted(list(i_set))[-1], end='', file=sys.stdout)
        #outpath = pathlib.Path(args.outputdir) / (args.chartno + "_enct_adm_latest_" + datetime.date.today().isoformat() + ".csv")
        #with open(outpath, mode="w", encoding="utf-8", newline="") as csvfile:
        #    writer = csv.writer(csvfile)
        #    #writer.writerow(["Chart number", "Encounter ID"])
        #    #writer.writerow([args.chartno, latest_admission])
        #    writer.writerow([latest_admission])
        exit(0)

    # Note that the default encoding on other OSs may not be UTF-8
    outpath = pathlib.Path(args.outputdir) / (args.chartno + "_enct_" + args.startdate + "_" + args.enddate + ".csv")
    with open(outpath, mode="w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Chart number", "Encounter ID"])
        for i in out_list:
            writer.writerow([args.chartno, i])

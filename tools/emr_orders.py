#!/usr/bin/python3
#-*- coding: utf-8 -*-

# emr_orders.py - listing of orders from EMR at NCKUH

# Author: Chang-Yi Yen
# License: coffeeware
# Initially created in August 2019

import argparse
import csv
import datetime
import os
import pathlib
import re
import sys
import urllib.request

import bs4

if __name__ == '__main__':
    # Change working directory to location of this script
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
    except OSError:
        print("[Error] Couldn't change working directory to location of this script", file=sys.stderr)
    parser = argparse.ArgumentParser(description="Retrieval of orders from NCKUH EMR",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    parser.add_argument("-u", "--uid", type=str, required=True, help="User ID")
    parser.add_argument("-p", "--passwd", type=str, required=True, help="Password")
    # TODO: add shortcut so that giving the chart number would retrieve the latest applicable encounter ID
    parser.add_argument("-c", "--chartno", type=str, required=True, help="Chart number")
    parser.add_argument("-e", "--encounterid", type=str, help="Encounter ID ('medicalsn')")
    parser.add_argument("-o", "--outputdir", type=str, help="Set output directory", default=pathlib.Path.cwd().parent / 'cache')
    parser.add_argument("--version", action="version", version="%(prog)s 0.2.1 'Annihilation'")
    args = parser.parse_args()

    # Input validation
    assert re.match('\d{6}', args.uid), "ID number malformed (less than 6 digits)"
    assert re.match('\d{8}', args.chartno), "Chart number malformed (less than 8 digits)"

    if args.debug:
        print("[DEBUG] UID: ", args.uid, file=sys.stderr)
        print("[DEBUG] Chart number: ", args.chartno, file=sys.stderr)

    ROOTURL = "http://hisweb.hosp.ncku/WebsiteSSO/PCS/"

    with urllib.request.urlopen(ROOTURL + "showShift.aspx?type=1&caseno=" + args.encounterid) as f:
        ordersheet = f.read().decode("utf-8")
    ordersoup = bs4.BeautifulSoup(ordersheet, "html.parser")

    # After consideration, it seems better to leave the filtering by date to the summary generator
    ## Here we're assuming that this script is run on the '2nd day' of duty
    #dutystart = datetime.datetime.combine(datetime.date.today() - datetime.timedelta(1), datetime.time(17))
    #dutyend = datetime.datetime.combine(datetime.date.today(), datetime.time(8))

    # Regular orders
    regular = ordersoup.find('table', {'id':'GridView6'})
    if regular:
        regular_new = list()
        ## Get order's start dates and contents
        regular_dates = regular.findAll('td',text=re.compile('^\d{4}-\d{2}-\d{2}'))
        for i in regular_dates:
            m = re.search('^(\d{4}-\d{2}-\d{2} \d{4})(?: -- (\d{4}-\d{2}-\d{2}))?', i.text)
            starttime = datetime.datetime.strptime(m.groups()[0], '%Y-%m-%d %H%M')
            #if starttime > dutystart and starttime < dutyend:
            #    regular_new.append((starttime, i.find_previous_sibling().text.strip(), i.find_previous_sibling().find_previous_sibling().text.strip()))
            regular_new.append((starttime, i.find_previous_sibling().text.strip(), i.find_previous_sibling().find_previous_sibling().text.strip()))

    # Stat orders
    stat = ordersoup.find('table', {'id': 'GridView7'})
    if stat:
        stat_new = list()
        ## Get order's start dates and contents
        stat_dates = stat.findAll('td',text=re.compile('^\d{4}-\d{2}-\d{2}'))
        for i in stat_dates:
            m = re.search('^(\d{4}-\d{2}-\d{2} \d{4})(?: -- (\d{4}-\d{2}-\d{2}))?', i.text)
            starttime = datetime.datetime.strptime(m.groups()[0], '%Y-%m-%d %H%M')
            #if starttime > dutystart and starttime < dutyend:
            #    stat_new.append((starttime, i.find_previous_sibling().text.strip(), i.find_previous_sibling().find_previous_sibling().text.strip()))
            stat_new.append((starttime, i.find_previous_sibling().text.strip(), i.find_previous_sibling().find_previous_sibling().text.strip()))

    out_list = list()
    if regular:
        out_list.extend(regular_new)
    if stat:
        out_list.extend(stat_new)

    if args.debug:
        print(out_list, file=sys.stderr)
    # Note that the default encoding on other OSs may not be UTF-8
    outpath = pathlib.Path(args.outputdir) / (args.chartno + "_orders_" + datetime.datetime.now().strftime("%Y-%m-%dT%H%M") + ".csv")
    with open(outpath, mode="w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Time", "Order", "Type"])
        for i in out_list:
            writer.writerow(i)

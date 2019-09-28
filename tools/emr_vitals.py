#!/usr/bin/python3
#-*- coding: utf-8 -*-

# emr_vitals.py - listing of vital signs from EMR at NCKUH

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

from lib import session

if __name__ == '__main__':
    # Change working directory to location of this script
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
    except OSError:
        print("[Error] Couldn't change working directory to location of this script", file=sys.stderr)
    parser = argparse.ArgumentParser(description="Retrieval of vital signs from NCKUH EMR (within the past week)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    parser.add_argument("-u", "--uid", type=str, required=True, help="User ID")
    parser.add_argument("-p", "--passwd", type=str, required=True, help="Password")
    parser.add_argument("-c", "--chartno", type=str, required=True, help="Chart number")
    parser.add_argument("-o", "--outputdir", type=str, help="Set output directory", default=pathlib.Path.cwd().parent / 'cache')
    parser.add_argument("--version", action="version", version="%(prog)s 0.2.1 'Annihilation'")
    args = parser.parse_args()

    # Input validation
    assert re.match('\d{6}', args.uid), "ID number malformed (less than 6 digits)"
    assert re.match('\d{8}', args.chartno), "Chart number malformed (less than 8 digits)"

    if args.debug:
        print("[DEBUG] UID: ", args.uid, file=sys.stderr)
        print("[DEBUG] Chart number: ", args.chartno, file=sys.stderr)

    ROOTURL = "http://hisweb.hosp.ncku/EmrQuery/" + "(S(" + session.get_sessionid(args) + "))/" + "tree/"

    with urllib.request.urlopen(ROOTURL + "tprm3.aspx?type=tpri&chartno=" + args.chartno) as f:
        tprsheet = f.read().decode("utf-8")
    tprsoup = bs4.BeautifulSoup(tprsheet, "html.parser")
    measurements = sorted(set([i["title"] for i in tprsoup.findAll("area")]))
    if args.debug:
        print(measurements, file=sys.stderr)
    out_list = []
    for datapoint in measurements:
        i = list(re.search('(\d{4}/\d{2}/\d{2}  \d{2}:\d{2})\n(?:.+體溫 : (\d{2}\.?\d?)\n)?(?:.+脈搏 : (\d{2,3})\n)?(?:.+呼吸 : (\d{2})\n)?(?:.+收縮壓 : (\d{2,3})\n)?(?:.+舒張壓 : (\d{2,3}))?', datapoint).groups())
        i[0] = datetime.datetime.strptime(i[0], "%Y/%m/%d  %H:%M").strftime("%Y-%m-%dT%H:%M")
        out_list.append(i)
    if args.debug:
        print(out_list, file=sys.stderr)
    # Note that the default encoding on other OSs may not be UTF-8
    outpath = pathlib.Path(args.outputdir) / (args.chartno + "_vitals_" + datetime.datetime.now().strftime("%Y-%m-%dT%H%M") + ".csv")
    with open(outpath, mode="w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Time", "Temperature", "Pulse", "Respiration", "Systolic_BP", "Diastolic_BP"])
        for i in out_list:
            writer.writerow(i)

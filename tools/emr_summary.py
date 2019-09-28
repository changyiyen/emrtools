#!/usr/bin/python3
#-*- coding: utf-8 -*-

# emr_summary.py - generates a summary of patient events last night at NCKUH

# Author: Chang-Yi Yen
# License: coffeeware
# Initially created in September 2019

# Notes on the use of old asyncio syntax:
# I wrote this script using an older version of Python 3 (specifically version
# 3.6.8), whose asyncio module has not yet implemented the run() function.
# I'll probably get around to changing this once the version of Python 3 for
# Xubuntu has been bumped up.to 3.7 or later. --cyyen 2019-09-13

# Note on the range of time to summarize:
# Initially I assumed that the time range to summarize would be from the evening
# the day before to this morning, but that's assuming the previous day was a
# workday as well. We could try to account for weekends, but then there's the
# problem of national holidays. A compromise is probably to just summarize the
# last 24 hours. --cyyen 2019-09-15

import argparse
import asyncio
import csv
import datetime
import glob
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

import jinja2

def generate_summary(args):
    with open(args.chartnofile, 'r') as f:
        chartnolist = f.readlines()
    if args.debug:
        print('[DEBUG] chartnolist: ', chartnolist, file=sys.stderr)
    patient_data = dict()
    for chartno in chartnolist:
        chartno = chartno.strip()
        if args.debug:
            print('[DEBUG] Working on ID number: ', chartno, file=sys.stderr)
        ### Call emr_encounters to get latest encounter code
        medicalsn = subprocess.run([sys.executable, 'emr_encounters.py', '-u', args.uid, '-p', args.passwd, '-c', chartno, '-l'], stdout=subprocess.PIPE).stdout.decode('utf-8')
        if args.debug:
            print('[DEBUG] medicalsn: ', medicalsn, file=sys.stderr)
        ## Create directory for each patient ID and output there
        try:
            if args.debug:
                print('[DEBUG] Creating subdirectory for {}'.format(chartno), file=sys.stderr)
            os.mkdir(pathlib.Path(args.outputdir) / chartno)
        except FileExistsError:
            if args.debug:
                print('[INFO] Subdirectory for {} exists, will write into that directory'.format(chartno), file=sys.stderr)
        outsubdir = (pathlib.Path(args.outputdir) / chartno).resolve()
        ## emr_vitals
        ### Needs UID, passwd, chartno
        @asyncio.coroutine
        def vitals():
            proc = asyncio.create_subprocess_exec(sys.executable, 'emr_vitals.py', '-u', args.uid, '-p', args.passwd, '-c', chartno, '-o', str(outsubdir))
            p = yield from proc
            yield from p.wait()
        ## emr_nursing
        ### Needs UID, passwd, chartno, encounter ID
        @asyncio.coroutine
        def nursing():
            proc = asyncio.create_subprocess_exec(sys.executable, 'emr_nursing.py', '-u', args.uid, '-p', args.passwd, '-c', chartno, '-e', medicalsn, '-o', str(outsubdir))
            p = yield from proc
            yield from p.wait()
        ## emr_orders
        ### Needs UID, passwd, chartno, encounter ID
        @asyncio.coroutine
        def orders():
            proc = asyncio.create_subprocess_exec(sys.executable, 'emr_orders.py', '-u', args.uid, '-p', args.passwd, '-c', chartno, '-e', medicalsn, '-o', str(outsubdir))
            p = yield from proc
            yield from p.wait()
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
        else:
            loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(nursing(),orders(),vitals()))
        loop.close()
        ## Generate report webpage using Jinja2
        #vitals_out = next(outsubdir.glob(chartno + "_vitals_" + "*.csv"))
        vitals_out = max(glob.glob(str(outsubdir / (chartno + "_vitals_*.csv"))), key=os.path.getctime)
        #nursing_out = outsubdir / (chartno + "_nurs_" + medicalsn + ".csv")
        #print(str(outsubdir / (chartno + "_nurs_" + str(medicalsn) + "*.csv")))
        nursing_out = max(glob.glob(str(outsubdir / (chartno + "_nurs_" + medicalsn + "*.csv"))), key=os.path.getctime)
        #orders_out = next(outsubdir.glob(chartno + "_orders_" + "*.csv"))
        orders_out = max(glob.glob(str(outsubdir / (chartno + "_orders_*.csv"))), key=os.path.getctime)

        patient_data[chartno] = dict()
        # Patient's name here
        #patient_data[chartno]['name'] = ...
        patient_data[chartno]['vitals'] = list()
        patient_data[chartno]['nursing'] = list()
        patient_data[chartno]['orders'] = list()

        # Default off-service time: 5PM (today (before midnight) or the day before (after midnight))
        if datetime.datetime.now().time() > datetime.time(17):
            LASTOFFSERVICETIME = datetime.datetime.now().replace(hour=17, minute=0, second=0, microsecond=0)
        else:
            LASTOFFSERVICETIME = (datetime.datetime.now() - datetime.timedelta(1)).replace(hour=17, minute=0, second=0, microsecond=0)
        if args.debug:
            print('[DEBUG] LASTOFFSERVICETIME: ', LASTOFFSERVICETIME, file=sys.stderr)

        with open(vitals_out, 'r') as f:
            r = csv.DictReader(f)
            for l in r:
                if datetime.datetime.strptime(l['Time'], '%Y-%m-%dT%H:%M') < LASTOFFSERVICETIME:
                    if args.debug:
                        print('[DEBUG] vitals time: ', l['Time'], file=sys.stderr)
                    continue
                patient_data[chartno]['vitals'].append(l)
        with open(nursing_out, 'r') as f:
            r = csv.DictReader(f)
            for l in r:
                # Note the slightly different time specs (TODO: unify time specs)
                if datetime.datetime.strptime(l['Time'], '%Y-%m-%d %H:%M') < LASTOFFSERVICETIME:
                    if args.debug:
                        print('[DEBUG] nursing time: ', l['Time'], file=sys.stderr)
                    continue
                patient_data[chartno]['nursing'].append(l)
        with open(orders_out, 'r') as f:
            r = csv.DictReader(f)
            for l in r:
                # Note the slightly different time specs (TODO: unify time specs)
                if datetime.datetime.strptime(l['Time'], '%Y-%m-%d %H:%M:%S') < LASTOFFSERVICETIME:
                    if args.debug:
                        print('[DEBUG] vitals time: ', l['Time'], file=sys.stderr)
                    continue
                patient_data[chartno]['orders'].append(l)
    templateloader = jinja2.FileSystemLoader(searchpath="./")
    templateenv = jinja2.Environment(loader=templateloader, autoescape=True)
    template = templateenv.get_template('summary.html')

    outpath = pathlib.Path(args.outputdir) / ('summary_' + time.strftime('%Y-%m-%dT%H%M') + '.html')
    with open(outpath, mode="w", encoding="utf-8") as fh:
        print(template.render(patient_data=patient_data, date=time.strftime('%Y-%m-%dT%H%M')), file=fh)

if __name__ == '__main__':
    # Change working directory to location of this script
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
    except OSError:
        print("[Error] Couldn't change working directory to location of this script", file=sys.stderr)
    parser = argparse.ArgumentParser(description="Generates a summary of patient events last night at NCKUH",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    parser.add_argument("-u", "--uid", type=str, required=True, help="User ID")
    parser.add_argument("-p", "--passwd", type=str, required=True, help="Password")
    parser.add_argument("-f", "--chartnofile", type=str, help="File containing chart numbers, one on each line", default=pathlib.Path.cwd().parent / 'config' / 'chartno.txt')
    parser.add_argument("-o", "--outputdir", type=str, help="Set output directory", default=pathlib.Path.cwd().parent / 'cache')
    parser.add_argument("-d", "--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("-t", "--time", type=str, help="Time of day to run (applies to daemon mode only), written as hourminute, e.g., 0630", default="0630")
    parser.add_argument("--version", action="version", version="%(prog)s 0.2.1 'Annihilation'")
    args = parser.parse_args()

    if args.daemon:
        run_time = time.strptime(args.time, '%H%M')
        while(True):
            if time.localtime().tm_hour == run_time.tm_hour and time.localtime().tm_minute == run_time.tm_minute:
                generate_summary(args)
            time.sleep(60)
    else:
        generate_summary(args)
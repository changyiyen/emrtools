#!/usr/bin/python3
#-*- coding: utf-8 -*-

# emr_nursing.py - prints inpatient nursing records at NCKUH

# Author: Chang-Yi Yen
# License: coffeeware
# Initially created in July 2019

import argparse
import csv
import datetime
import json
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
    parser = argparse.ArgumentParser(description="Retrieval of inpatient nursing records from NCKUH EMR",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    parser.add_argument("-u", "--uid", type=str, required=True, help="User ID (required)")
    parser.add_argument("-p", "--passwd", type=str, required=True, help="Password (required)")
    parser.add_argument("-c", "--chartno", type=str, required=True, help="Chart number (required)")
    parser.add_argument("-d", "--date", type=str, required=False, help="Date in ISO8601 format (gets all)")
    parser.add_argument("-e", "--encounterid", type=str, required=True, help="Encounter ID (medicalsn) (required)")
    parser.add_argument("-m", "--mode", type=str, choices=["admission", "other"], help="Type of nursing record to retrieve ('other' includes normal ward and ICU)", default="other")
    parser.add_argument("-o", "--outputdir", type=str, help="Set output directory", default=pathlib.Path.cwd().parent / 'cache')
    parser.add_argument("--version", action="version", version="%(prog)s 0.2.1 'Annihilation'")
    args = parser.parse_args()
    
    # Input validation
    assert re.match('\d{6}', args.uid), "ID number malformed (less than 6 digits)"
    assert re.match('[01]\d{7}', args.chartno), "Chart number malformed (less than 8 digits)"
    try:
        if args.date:
            datetime.datetime.strptime(args.date, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Incorrect date format (should be YYYY-MM-DD)")

    if args.debug:
        print("[DEBUG] UID: ", args.uid, file=sys.stderr)
        print("[DEBUG] Chart number: ", args.chartno, file=sys.stderr)
        print("[DEBUG] Encounter ID: ", args.encounterid, file=sys.stderr)
        print("[DEBUG] Mode: ", args.mode, file=sys.stderr)

    ROOTURL = "http://hisweb.hosp.ncku/EmrQuery/" + "(S(" + session.get_sessionid(args) + "))/" + "tree/"

    if args.date:
        notedate = [datetime.datetime.strptime(args.date, '%Y-%m-%d').strftime('%Y/%m/%d')]
    else:
        # Extract valid dates for nursing records
        nursing_record_rooturl = ROOTURL + "NISlist.aspx?ChartNo=" + args.chartno + "&CaseNo="+ args.encounterid + "&GTYPE=2"
        with urllib.request.urlopen(nursing_record_rooturl) as f:
            nursing_record_root = f.read().decode("utf-8")
        nursing_record_root_soup = bs4.BeautifulSoup(nursing_record_root, 'lxml')
        notedate = [x.text for x in nursing_record_root_soup.findAll('a', text=re.compile('\d{4}/\d{2}/\d{2}'))]

    if args.mode == 'admission':
        noteurl = [ROOTURL + "viewReport.aspx?medicalsn=" + args.encounterid + "&GTYPE=2_1&CHARTNO=" + args.chartno]
    elif args.mode == 'other':
        # It's certainly bad form to use forward slashes in a date...
        noteurl = [ROOTURL + "viewReport.aspx?medicalsn=" + args.encounterid + "&NDATE=" + x + "&CHARTNO=" + args.chartno for x in notedate]
    else:
        print("Error: incorrect mode", file=sys.stderr)
        exit(1)

    out_list = list()
    out_dict = dict()

    for x in zip(notedate, noteurl):
        if args.debug:
            print('[DEBUG] Getting note on', x[0], '(url: ', x[1], ')', file=sys.stderr)
        with urllib.request.urlopen(x[1]) as f:
            nursing_sheet = f.read().decode("utf-8")
        if args.mode == 'admission':
            nursing_sheet_soup = bs4.BeautifulSoup(nursing_sheet, 'html.parser')
            # TODO: Pending code for parsing the admission datasheet
            tables_all = nursing_sheet_soup.findAll('table')
            # Administrative info
            admin_table = tables_all[7]
            out_dict['pid'] = admin_table.find('td',text='病歷號').next_sibling.text.strip()
            out_dict['name'] = admin_table.find('td',text='病患姓名').next_sibling.text.strip()
            out_dict['dob'] = admin_table.find('td',text='生日').next_sibling.text.strip()
            out_dict['gender'] = admin_table.find('td',text='性別').next_sibling.text.strip()
            # Basic info
            basic_info_table = tables_all[9]
            out_dict['diagnosis'] = basic_info_table.find('td',text='入院診斷').next_sibling.text.strip()
            out_dict['height'] = basic_info_table.find('td',text='身高').next_sibling.text.strip()
            out_dict['weight'] = basic_info_table.find('td',text='體重').next_sibling.text.strip()
            out_dict['vitals'] = basic_info_table.find('td',text='生命徵象').next_sibling.text.strip()
            # ...
            # History
            history_table = tables_all[11]
            out_dict['family_history'] = history_table.find('td',text='家族病史').next_sibling.text.strip()
            out_dict['medical_history'] = history_table.find('td',text='過去病史').next_sibling.text.strip()
            out_dict['longterm_drugs'] = history_table.find('td',text='長期用藥').next_sibling.text.strip()
            out_dict['medication_allergies'] = history_table.find('td',text='藥物過敏史').next_sibling.text.strip()
            out_dict['food_allergies'] = history_table.find('td',text='食物過敏史').next_sibling.text.strip()
            out_dict['other_allergies'] = history_table.find('td',text='其他過敏史').next_sibling.text.strip()
            out_dict['present_illness'] = history_table.find('td',text='此次發病經過').next_sibling.text.strip()
            # Evaluation
            evaluation_table = tables_all[13]
            out_dict['religion'] = evaluation_table.find('td',text='靈性').next_sibling.text.strip()
            out_dict['personal_history'] = evaluation_table.find('td',text='個人史').next_sibling.text.strip()
            out_dict['family_history_eval'] = evaluation_table.find('td',text='家族史').next_sibling.text.strip()
            out_dict['neuro'] = evaluation_table.find('td',text='神經').next_sibling.text.strip()
            out_dict['sensory'] = evaluation_table.find('td',text='感官').next_sibling.text.strip()
            out_dict['respiration'] = evaluation_table.find('td',text='呼吸').next_sibling.text.strip()
            out_dict['cardiovascular'] = evaluation_table.find('td',text='心血管').next_sibling.text.strip()
            out_dict['digestion'] = evaluation_table.find('td',text='消化').next_sibling.text.strip()
            out_dict['urogenital'] = evaluation_table.find('td',text='泌尿/生殖').next_sibling.text.strip()
            out_dict['musculoskeletal'] = evaluation_table.find('td',text='肌肉骨骼').next_sibling.text.strip()
            out_dict['skin'] = evaluation_table.find('td',text='皮膚').next_sibling.text.strip()
            out_dict['bloodtype'] = evaluation_table.find('td',text='血型').next_sibling.text.strip()
            # At the Pediatrics department the 'routine' row contains the circumference of the head, chest and abdomen
            out_dict['routine'] = evaluation_table.find('td',text='常規').next_sibling.text.strip()
        if args.mode == 'other':
            nursing_sheet_soup = bs4.BeautifulSoup(nursing_sheet, 'html.parser')
            event_num = nursing_sheet_soup.findAll('div', text=re.compile('^\d+\.$'))
            for e in event_num:
                # Consider creating full ISO8601-compliant time instead of only %H:%M
                #date = e.findParent().find_previous('td', attrs={'id':re.compile('c0$')}).text
                #time = e.findParent().find_previous('td', attrs={'id':re.compile('c1$')}).text
                time = datetime.datetime.strptime(x[0], '%Y/%m/%d').strftime('%Y-%m-%d') + ' ' + e.findParent().find_previous('td', attrs={'id':re.compile('c1$')}).text
                event_type = e.findParent().find_previous('td', attrs={'id':re.compile('c2$')}).text
                assessment_type = e.findParent().find_previous('td', attrs={'id':re.compile('c3$')}).text
                action = e.findParent().find_next_sibling().text
                out_list.append([time, event_type, assessment_type, action])

    # Note that the default encoding on other OSs may not be UTF-8
    if args.mode == 'admission':
        outpath = pathlib.Path(args.outputdir) / (args.chartno + "_nurs_" + args.encounterid + "_adm" + ".json")
        with open(outpath, mode="w", encoding="utf-8", newline="") as jsonfile:
            json.dump(out_dict, jsonfile)
    if args.mode == 'other':
        outpath = pathlib.Path(args.outputdir) / (args.chartno + "_nurs_" + args.encounterid + "_" + datetime.datetime.now().strftime("%Y-%m-%dT%H%M") + ".csv")
        with open(outpath, mode="w", encoding="utf-8", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Time", "Event_Type", "Assessment_Type", "Action"])
            for i in out_list:
                writer.writerow(i)
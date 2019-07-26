#!/usr/bin/python
# -*- coding: utf-8 -*-

# ivue_scraper.py - simple scraper for Philips iVue server at NCKUH

# Note: This script was originally written for the Philips iVue server
# installed at the Pediatrics ICU at NCKUH, which I suspect has been
# customised; be advised that it has not been tested on other iVue servers.
#    --cyyen (20190719)

# Author: Chang-Yi Yen
# License: coffeeware
# Initially created on 2019-07-15

# Changelog:
# 0.1.0 (2019-07-15): initial release
# 0.1.1 (2019-07-19): added ability to traverse earlier pages; added more informative docstrings

import argparse
import csv
import datetime
import os
import pathlib
import re
import sys
import time
import urllib.request

import bs4

def get_ivue_data(baseurl, chartno, encounterid, mode):
#def get_ivue_data(baseurl, chartno, encounterid, args):
    """Get tables from the iVue pages, parse them, pass them for further processing, and collect results.

    Args:
        baseurl (str): Base URL of the iVue interface, e.g. "http://192.168.202.9/iVue/".
        chartno (str): Chart number, e.g., "12345678".
        encounterid (str): Encounter ID, e.g., "I20190014727".
        mode (str): Type of data to retrieve, e.g., 'hr' (heart rate)

    Returns:
        results (dict): Dict of results. Keys are datetime.datetime objects while values are strings.

    """
    page = urllib.request.urlopen(baseurl + 'patient.aspx?ChartNo=' + chartno + '&CaseNo=' + encounterid).read().decode()
    soup = bs4.BeautifulSoup(page, 'lxml')
    id = re.search('patientEncounter.aspx\?Page=1\-(\d+)\-1', str(soup)).groups()[0]

    # Basic info: probably one page only
    # TPR sheet: many pages
    # ICU monitor: many pages
    # ICU handover: probably one page only


    if mode == 'temp':
    #if args.mode == 'temp':
        if args.allrecords:
            results = dict()
            for i in map(lambda x: temp(x), get_page_soup(baseurl, id, 2)):
                results.update(i)
        else:
            results = temp(next(get_page_soup(baseurl, id, 2)))
    if mode == 'hr':
    #if args.mode == 'hr':
        if args.allrecords:
            results = dict()
            for i in map(lambda x: hr(x), get_page_soup(baseurl, id, 2)):
                results.update(i)
        else:
            results = hr(next(get_page_soup(baseurl, id, 2)))
    if mode == 'rr':
    #if args.mode == 'rr':
        if args.allrecords:
            results = dict()
            for i in map(lambda x: rr(x), get_page_soup(baseurl, id, 2)):
                results.update(i)
        else:
            results = rr(next(get_page_soup(baseurl, id, 2)))
    if mode == 'surgery':
    #if args.mode == 'surgery':
        # '--allrecords' argument silently ignored
        results = surgery(next(get_page_soup(baseurl, id, 1)), next(get_page_soup(baseurl, id, 8)))
    if mode == 'respiration':
    #if args.mode == 'respiration':
        # '--allrecords' argument silently ignored
        results = respiration(next(get_page_soup(baseurl, id, 1)), next(get_page_soup(baseurl, id, 8)))
    if mode == 'cxr':
    #if args.mode == 'cxr':
        # '--allrecords' argument silently ignored
        results = cxr(next(get_page_soup(baseurl, id, 1)), next(get_page_soup(baseurl, id, 8)))
    if mode == 'vaccine':
    #if args.mode == 'vaccine':
        # '--allrecords' argument silently ignored
        results = vaccine(next(get_page_soup(baseurl, id, 8)))
    return results

## Modes of data-fetching

def temp(tprsheet_soup):
    """Parses TPR sheet for temperature records.

    Args:
        tprsheet_soup (bs4.BeautifulSoup): BeautifulSoup object created from page containing the TPR sheet.

    Returns:
        t (dict): Dictionary of measured temperatures. Keys are datetime.datetime objects while values are
            strings containing measured temperature.

    """
    # TODO: consider modifying this function to output the raw numbers only (as strings) to facilitate easier data importation
    # TODO: consider adding a strict mode (where both the temperature and site of measurement have to be present to count)
    #   and a relaxed mode (where only the temperature is needed). Current behavior is in strict mode.
    # Time: mainTBL > tbody > tr starting with "time"
    times = tprsheet_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('time')).parent.find_all('td')
    # Temp: mainTBL > tbody > tr starting with "- B. T.(C)"
    temps = tprsheet_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('\W*- B\. T\.\(C\)')).parent.find_all('td')
    # Site: mainTBL > tbody > tr starting with "- 體溫部位"
    sites = tprsheet_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('- 體溫部位')).parent.find_all('td')
    # Get index of cell containing temp/site and index into time
    t = dict()
    for i in range(1, len(temps)):
        # Only print if both temp and site present
        if temps[i].text and sites[i].text:
            t[datetime.datetime.strptime(times[i].text, "%d-%m-%Y %H:%M")] = temps[i].text + "(" + sites[i].text + ")"    
    return t

def hr(tprsheet_soup):
    """Parses TPR sheet for heart rate records.

    Args:
        tprsheet_soup (bs4.BeautifulSoup): BeautifulSoup object created from page containing the TPR sheet.

    Returns:
        h (dict): Dictionary of measured heart rates. Keys are datetime.datetime objects while values are
            strings containing heart rate.

    """
    # TODO: consider modifying this function to output the raw numbers only (as strings) to facilitate easier data importation
    # Time: mainTBL > tbody > tr starting with "time"
    times = tprsheet_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('time')).parent.find_all('td')
    # HR: mainTBL > tbody > tr starting with "Heart Rate"
    rate = tprsheet_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('Heart Rate')).parent.find_all('td')
    h = dict()
    for i in range(1, len(rate)):
        if rate[i].text:
            h[datetime.datetime.strptime(times[i].text, "%d-%m-%Y %H:%M")] = rate[i].text
    return h

def rr(tprsheet_soup):
    """Parses TPR sheet for respiratory rate records.

    Args:
        tprsheet_soup (bs4.BeautifulSoup): BeautifulSoup object created from page containing the TPR sheet.

    Returns:
        r (dict): Dictionary of measured respiratory rates. Keys are datetime.datetime objects while values are
            strings containing respiratory rate.

    """
    # TODO: consider modifying this function to output the raw numbers only (as strings) to facilitate easier data importation
    # Time: mainTBL > tbody > tr starting with "time"
    times = tprsheet_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('time')).parent.find_all('td')
    # RR: mainTBL > tbody > tr starting with "Respiration"
    rate = tprsheet_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('Respiration')).parent.find_all('td')
    r = dict()
    for i in range(1, len(rate)):
        if rate[i].text:
            r[datetime.datetime.strptime(times[i].text, "%d-%m-%Y %H:%M")] = rate[i].text
    return r

def surgery(basicinfo_soup, icuhandover_soup):
    """Parses ICU handover sheet for surgical history.

    Args:
        basicinfo_soup (bs4.BeautifulSoup): BeautifulSoup object created from page containing basic patient info.
        icuhandover_soup (bs4.BeautifulSoup): BeautifulSoup object created from page containing ICU handover sheet.

    Returns:
        resp_entries (dict): Dictionary of surgeries. Keys are datetime.datetime objects while values are
            strings containing description of surgery.

    """
    admission_date = datetime.datetime.strptime(basicinfo_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('轉入本單位日期時間')).next_sibling.string, '%Y/%m/%d %H:%M')
    surgery_hx = icuhandover_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('手術 - 手術')).next_sibling.stripped_strings
    surgery_entries = dict()
    for e in parse_entries(surgery_hx, admission_date):
        if e[0] not in surgery_entries.keys():
            surgery_entries[e[0]] = e[1]
        else:
            surgery_entries[e[0]] = '; '.join([surgery_entries[e[0]], e[1]])
    return surgery_entries

def respiration(basicinfo_soup, icuhandover_soup):
    """Parses ICU handover sheet for respiration-related events.

    Args:
        basicinfo_soup (bs4.BeautifulSoup): BeautifulSoup object created from page containing basic patient info.
        icuhandover_soup (bs4.BeautifulSoup): BeautifulSoup object created from page containing ICU handover sheet.

    Returns:
        resp_entries (dict): Dictionary of respiration-related treatments. Keys are datetime.datetime objects while values are
            strings containing type of respiration treatment.

    """
    admission_date = datetime.datetime.strptime(basicinfo_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('轉入本單位日期時間')).next_sibling.string, '%Y/%m/%d %H:%M')
    resp_hx = icuhandover_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('呼吸歷程 - 呼吸歷程')).next_sibling.stripped_strings
    resp_entries = dict()
    for e in parse_entries(resp_hx, admission_date):
        if e[0] not in resp_entries.keys():
            resp_entries[e[0]] = e[1]
        else:
            resp_entries[e[0]] = '; '.join([resp_entries[e[0]], e[1]])
    return resp_entries

def cxr(basicinfo_soup, icuhandover_soup):
    """Parses ICU handover sheet for CXR interpretation results.

    Args:
        basicinfo_soup (bs4.BeautifulSoup): BeautifulSoup object created from page containing basic patient info.
        icuhandover_soup (bs4.BeautifulSoup): BeautifulSoup object created from page containing ICU handover sheet.

    Returns:
        cxr_entries (dict): Dictionary of CXR interpretations. Keys are datetime.datetime objects while values are
            strings containing interpretation results.

    """
    admission_date = datetime.datetime.strptime(basicinfo_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('轉入本單位日期時間')).next_sibling.string, '%Y/%m/%d %H:%M')
    cxr_hx = icuhandover_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('CXR/檢查 - 呼吸系統')).next_sibling.stripped_strings
    cxr_entries = dict()
    for e in parse_entries(cxr_hx, admission_date):
        if e[0] not in cxr_entries.keys():
            cxr_entries[e[0]] = e[1]
        else:
            cxr_entries[e[0]] = '; '.join([cxr_entries[e[0]], e[1]])
    return cxr_entries 

def vaccine(icuhandover_soup):
    """Parses ICU handover sheet for vaccination history.

    Args:
        icuhandover_soup (bs4.BeautifulSoup): BeautifulSoup object created from page containing ICU handover sheet.

    Returns:
        vax_entries (dict): Dictionary of injection dates. Keys are datetime.datetime objects while values are strings containing vaccine type.

    """
    vax_hx = icuhandover_soup.find('table', {'class': 'mainTBL'}).find('td', string=re.compile('疫苗')).next_sibling.stripped_strings
    vax_entries = dict()
    for i in vax_hx:
        # position 0: vaccine type; position 1: date
        shot = re.search('[◎](.+)[ ]+.{4}:(.+)', i)
        d = datetime.datetime.strptime(shot.groups()[1], '%Y/%m/%d')
        if d not in vax_entries.keys():
            vax_entries[d] = shot.groups()[0]
        else:
            # Join shots together if on same day
            vax_entries[d] = '; '.join([vax_entries[d], shot.groups()[0]])
    return vax_entries

## Housekeeping functions

def parse_entries(hx, admission_date):
    """Parses history and yields entries. *Critical assumption is that year rollover will occur only once at most.*

    Args:
        hx (generator): Generator producing line to parse. Each line should start with a date of the form YYYY/MM/DD;
            fallback is to use MM/DD, assuming the year to be the year of admission. Whitespace can precede the date.
        admission_date (datetime.datetime): Datetime object containing the date of admission to ICU.

    Yields:
        list: List of 2 elements, date (datetime.datetime object) and contents (str)

    """
    # Using a generator for this function since the state of last_entry_date and new_year needs to be maintained.
    last_entry_date = admission_date
    new_year = False

    while True:
        try:
            entry = next(hx)
        except StopIteration:
            break

        missing_year = False
        raw_date = re.search('^[ \t]*(\d{4})/(\d{1,2})/(\d{1,2})', entry)
        # Prefer date of the type YYYY/MM/DD; fall back to MM/DD if unavailable
        if not raw_date:
            missing_year = True
            raw_date = re.search('^[ \t]*(\d{1,2})/(\d{1,2})', entry)
        if raw_date:
            contents = re.search('(?:\d{1,2}/)?\d{1,2}/\d{1,2}[ \t]*(.+)$', entry).groups()[0]
            if missing_year:
                # Assume initial year is same as that of admission date
                date = datetime.datetime(admission_date.year, int(raw_date.groups()[-2]), int(raw_date.groups()[-1]))
            else:
                date = datetime.datetime(int(raw_date.groups()[0]), int(raw_date.groups()[1]), int(raw_date.groups()[2]))
            # If we appear to be jumping back in time, and we're crossing from Dec to Jan, set new year and reparse
            if date < last_entry_date and date.month == 1 and last_entry_date.month == 12 and not new_year:
                new_year = True
                date = datetime.datetime(last_entry_date.year + 1, int(raw_date.groups()[-2]), int(raw_date.groups()[-1]))
            last_entry_date = date
        else:
            # Skip line if no date found (better way to do this?)
            continue
        yield list([date, contents])

def get_page_soup(baseurl, id, sheetno):
    """Returns a generator yielding parsed pages; each call returns the previous page.

    Args:
        baseurl (str): Base URL of the iVue interface, e.g. "http://192.168.202.9/iVue/"
        id (str or int): ID code used by the iVue server, unique to every encounter, e.g. "59829"
        sheetno (int or str): Number corresponding to patient's datasheet.
            Known values:
            1: Basic info
            2: TPR sheet
            3: ICU monitoring sheet
            4: Pharmacologist evaluation
            6: Pressure sore nursing records
            7: Wound nursing records
            8: Pediatric ICU / Newborn ICU handover sheet
            9998: Nursing handover sheet (links to physician notes on another server; each note identified with UUID)

    Yields:
        page_soup (bs4.BeautifulSoup): a BeautifulSoup object created by parsing the page

    Examples:

        >>> print([type(soup) for soup in get_page_soup("http://192.168.202.9/iVue/", "59829", 2)])
        [<class 'bs4.BeautifulSoup'>, <class 'bs4.BeautifulSoup'>, ...]

    """
    count = 1
    while True:
        page = urllib.request.urlopen(baseurl + 'patientEncounter.aspx?Page=' + str(sheetno) + '-' + str(id) + '-' + str(count)).read().decode()
        page_soup = bs4.BeautifulSoup(page, 'lxml')
        yield page_soup
        # For debugging
        if args.debug and count > 100:
            print("[DEBUG] Halting after count > 100.", file=sys.stderr)
            break
        # Search for link to previous page and stop if no link found
        count += 12
        page_prev = page_soup.find('a', {'href': re.compile('patientEncounter.aspx\?Page='+str(sheetno)+'\-.+\-'+str(count)+'$')})
        if not page_prev:
            break

def writeout(output, outputdir, chartno, encounterid, mode):
#def writeout(output, chartno, encounterid, args):
    """Write retrieved iVue data to CSV output (UTF-8 encoding).

    Args:
        output (dict): Dictionary containing retrieved data. Keys are datetime.datetime objects, while values are strings.
        outputdir (str): Output directory, e.g., '/home/user/output'.
        chartno (str): Chart number, e.g., "12345678".
        encounterid (str): Encounter ID, e.g., "I20190014727".
        mode (str): Type of data to retrieve, e.g., 'hr' (heart rate)

    Returns:
        No return value.

    Raises:
        Does not raise errors itself but called functions (open, csv.writer.writerow, etc.) can raise relevant errors.

    """
    # TODO: consider changing interface to replace outputdir and mode with program args
    # Note that the default encoding on certain OSs may not be UTF-8
    outpath = pathlib.Path(outputdir) / (chartno + '_' + encounterid + '_icu_' + mode + '.csv')
    #outpath = pathlib.Path(args.outputdir) / (chartno + '_' + encounterid + '_icu_' + args.mode + '.csv')
    with open(outpath, mode='w', encoding='utf-8', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Date', 'Event'])
        for i in sorted(output.keys()):
            writer.writerow([i, output[i]])

def run_scraper(baseurl, args):
    """Runs scraper for all provided chart numbers and encounter IDs, then writes data by calling writeout().

    Args:
        baseurl (str): Base URL of the iVue interface, e.g. "http://192.168.202.9/iVue/"
        args (argparse.Namespace): Arguments passed to the main program

    Returns:
        bool: True for sucess, false otherwise

    """
    if args.file:
        if args.debug:
            print('[DEBUG] Reading file: ', args.file, file=sys.stderr)
        with open(args.file, 'r') as fh:
            reader = csv.DictReader(fh)
            # ICU data is only extracted if the patient is admitted
            encounters = [r for r in reader if r['Encounter_ID'][0] == 'I']
        for e in encounters:
            out = get_ivue_data(baseurl, e['Chart_number'], e['Encounter_ID'], args.mode)
            writeout(out, args.outputdir, e['Chart_number'], e['Encounter_ID'], args.mode)
    elif args.chartno and args.encounterid:
        if args.debug:
            print('[DEBUG] Fetching data for chart number ', args.chartno, ', encounter ID ', args.encounterid, file=sys.stderr)
        out = get_ivue_data(baseurl, args.chartno, args.encounterid, args.mode)
        writeout(out, args.outputdir, args.chartno, args.encounterid, args.mode)
    else:
        print("[ERROR] Missing chart number(s) and encounter ID(s)", file=sys.stderr)
        return False
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Scraping of data from Philips iVue server web interface at NCKUH",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    #parser.add_argument("-u", "--uid", type=str, required=True, help="User ID")
    #parser.add_argument("-p", "--passwd", type=str, required=True, help="Password")
    parser.add_argument("-a", "--allrecords", action="store_true", help="Retrieve requested records from all pages for this encounter. *Note: This option will hammer the server hard and is IGNORED if running as daemon.*")
    parser.add_argument("-d", "--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("-i", "--interval", type=int, help="Interval between checks (in seconds)", default=1800)
    parser.add_argument("-s", "--server", type=str, help="IP of iVue server", default="192.168.202.9")
    parser.add_argument("-f", "--file", type=str, help="CSV file containing chart number and encounter ID, with header line ('Chart_number','Encounter_ID')")
    parser.add_argument("-c", "--chartno", type=str, required=('-f' not in sys.argv) and ('--file' not in sys.argv), help="Chart number")
    parser.add_argument("-e", "--encounterid", type=str, required=('-f' not in sys.argv) and ('--file' not in sys.argv), help="Encounter ID")
    parser.add_argument("-m", "--mode", type=str, choices=["temp", "hr", "rr", "surgery", "respiration", "cxr", "vaccine"], help="Type of record to output", default="respiration")
    #parser.add_argument("-n", "--nounits", action="store_true", help="Do not output measurement units")
    parser.add_argument("-o", "--outputdir", type=str, help="Set output directory", default=pathlib.Path.cwd())
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.1 'Bicycle Repair Man'")
    args = parser.parse_args()

    # Input validation
    if args.chartno:
        assert re.match('\d{8}', args.chartno), 'Chart number malformed (less than 8 digits)'

    # Example URL: http://192.168.202.9/iVue/patient.aspx?ChartNo=19314023&CaseNo=I20190014727
    # Potential for URL injection here...
    BASEURL = 'http://' + args.server + '/iVue/'

    if args.debug:
        print('[DEBUG] BASEURL is: ', BASEURL, file=sys.stderr)

    # Run forever if daemonized
    if args.daemon:
        if args.debug:
            print('[DEBUG] Running as daemon with process ID ', os.getpid(), ' and an update interval of ', args.interval, ' seconds.', file=sys.stderr)
        # Ignore switch to get all records since most of the returned data is the same and static
        if args.allrecords:
            args.allrecords = False
        while True:
            print(time.ctime(), "Getting data...")
            run_scraper(BASEURL, args)
            print(time.ctime(), "Finished writing to file.")
            time.sleep(args.interval)
    else:
        run_scraper(BASEURL, args)
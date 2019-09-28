#!/usr/bin/env python3
#-*- coding: utf-8 -*-

# session.py - functions for working with the NCKUH EMR

import http.cookiejar
import urllib.parse
import urllib.request
import re
import sys

import bs4

def login(args):
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
    # post_reply contains the user's list of patients
    return opener, post_reply

def get_sessionid(args):
    # Get session ID from EMR server using credentials
    opener, reply = login(args)
    ## Apparently requesting "http://hisweb.hosp.ncku/WebsiteSSO/PCS/showchart.aspx?chartno=..." does *not* work (a 500 Internal Error is returned)
    emr_reply = opener.open("http://hisweb.hosp.ncku/EmrQuery/autologin.aspx?chartno=" + args.chartno + "&systems=0")
    if args.debug:
        print("[DEBUG] EMR reply:", emr_reply, file=sys.stderr)
    session_id = re.search("S\(([a-z0-9]+)\)", emr_reply.geturl()).groups()[0]
    return session_id

def get_patientlist(args):
    opener, post_reply = login(args)
    patientlist_soup = bs4.BeautifulSoup(post_reply, "html.parser")
    patientlist_table = patientlist_soup.find("table", attrs={"id":"GridView1"})
    patientlist_tr = patientlist_table.findAll('tr')
    entries = list()
    #Change the below to skip the first line
    #for row in patientlist_tr:
    #    cells = row.findChildren('td')
    #    # Bed, name, ID
    #    entries.append((cells[0].text, cells[1].text, cells[13].text))
    # Write to CSV file (no header): bed,name,id
    #with open('patientlist_' + args.username + '.csv','w') as f:
    #    writer = csv.writer(f)
    #    writer.writerows(entries)
    #return True
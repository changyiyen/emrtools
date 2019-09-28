#!/usr/bin/python3
#-*- encoding: utf-8 -*-

#import asyncio
import datetime
#import multiprocessing
import os
import pathlib
import shlex
import subprocess
import sys

import flask

PYTHONPATH = sys.executable

app = flask.Flask(__name__)
app.debug = True

@app.route('/')
def main():
    # Main page submits form to /dispatch
    filelist = dict()
    for f in os.listdir(path=str(pathlib.Path(os.path.realpath(__file__)).parent.parent/'cache')):
        filelist[f] = datetime.datetime.fromtimestamp(os.path.getmtime(str(pathlib.Path(os.path.realpath(__file__)).parent.parent/'cache')+os.sep+f))
    return flask.render_template('main.html', filelist=filelist)

@app.route('/dispatch', methods=['POST'])
def dispatch():
    # Run tools with form data
    tool = shlex.quote(flask.request.form.get('tool'))
    uid = shlex.quote(flask.request.form.get('uid'))
    passwd = shlex.quote(flask.request.form.get('passwd'))
    chartno = shlex.quote(flask.request.form.get('chartno'))
    startdate = shlex.quote(flask.request.form.get('startdate'))
    enddate = shlex.quote(flask.request.form.get('enddate'))
    # Change to asynchronous call once results interface completed
    ## Potential security issue if whitelist approach not used?
    #output = subprocess.Popen(['python3', tool, '--uid', uid, '--passwd', passwd, '--chartno', chartno, '--startdate', startdate, '--enddate', enddate], cwd='../tools')
    #output = subprocess.run(['python3', tool, '--uid', uid, '--passwd', passwd, '--chartno', chartno, '--startdate', startdate, '--enddate', enddate], cwd='../tools')
    process_args = [PYTHONPATH, str(pathlib.Path(os.path.realpath(__file__)).parent.parent/'tools' / tool)]
    # It's probably not our responsibility to do input checking for UID,
    # password and chart number here. The only sanity check in place in the
    # whole setup is in the web UI, though shell injection doesn't seem to work
    # (easily) with subprocess_check_output().
    process_args.extend(['--uid', uid, '--passwd', passwd, '--chartno', chartno])
    if len(startdate) > 2:
        process_args.extend(['--startdate', startdate])
    if len(enddate) > 2:
        process_args.extend(['--enddate', enddate])
    #output = subprocess.check_output(['python3', str(pathlib.Path.cwd().parent / 'tools'/ tool), '--uid', uid, '--passwd', passwd, '--chartno', chartno, '--startdate', startdate, '--enddate', enddate, '--dir', '../cache'], cwd='../tools')
    output = subprocess.check_output(process_args, cwd=pathlib.Path(os.path.realpath(__file__)).parent.parent/'tools')

    # Starting from Python 3.7 there is a simple function for starting a task
    # asynchronously: asyncio.run(). Unfortunately we're on Python 3.6, so we're
    # using the old method of using an explicit event loop.    
    #loop = asyncio.get_event_loop()
    #proc = asyncio.create_subprocess_shell('python3 ' + tool + ' --uid ' + uid + ' --passwd ' + passwd + ' --chartno ' + chartno + ' --startdate ' + startdate + ' --enddate ' + enddate + ' --dir ' + ' ../webui/cache', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    # The following returns a Process object immediately, but we still need a
    # way to have the results page query Flask to see if the task has been
    # completed (with a task ID?)
    #loop.run_until_complete(proc)

    # It's probably possible to check whether the running tool has exited by
    # using the process ID, but it's probably a potential security threat. On
    # the other hand, if we run the tool synchronously (i.e. the tool blocks),
    # then we would be limited by the browser timeout, the length of which can
    # vary (e.g. default 1 minute for IE, 5 minutes for Chromium). It is still
    # unclear how big an issue timeout would be.

    #output = subprocess.check_output(['python3', tool, '--help'], cwd='../tools')
    # Redirect to page showing console output, progress bar, and list of links to result pages
    return flask.render_template('results.html', chartno=chartno, output=output)

@app.route('/cache/<path:filename>')
def filelist(filename):
    return flask.send_from_directory(str(pathlib.Path(os.path.realpath(__file__)).parent.parent/'cache'), filename)

if __name__ == '__main__':
    app.run()

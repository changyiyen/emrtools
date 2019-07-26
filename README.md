# emrtools - toolkit for working with the NCKUH EMR system

## Overview

This toolkit was developed to assist in the processing of data from the NCKUH EMR system. It contains several command-line tools as well as a server providing a web interface to run these tools (for those who are command line-averse).

Currently the emrtools directory contents include (ignoring the RCS directories):

* cache - HTML reports generated by the tools

* tools - the command-line tools

* webui - Flask-powered web server providing a graphical interface

  * static - static files for the web pages

  * templates - templates provided to Flask for page generation

The command-line tools are:

* emr_diagnosis.py - lists all known problems for a patient for a given time period (*not* the ICD codes!)

* emr_diff.py - calculates diffs between notes for OPD visits for a patient for a given time period

  * Note: one side effect of using this tool is that the output makes doing a whole-text search for a particular word or phrase much easier (and, by extension, the time at which a particular diagnosis was made).

* emr_encounters.py - lists encounter codes for a patient for a given time period

* ivue_scraper.py - simple screen scraper for Philips iVue systems

## Dependencies

All files were written for Python 3.6+. Dependencies include [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) (bs4) (for page parsing), [lxml](https://lxml.de/parsing.html) (BeautifulSoup dependency) and [Flask](https://palletsprojects.com/p/flask/) (for the server). All dependencies can be installed with Pip3, e.g.:

```shell
pip3 install beautifulsoup4
pip3 install lxml
pip3 install Flask
```

## Examples

* To get a list of diagnoses:

```shell
python3 emr_diagnosis.py -u 123456 -p n@800101 -c 12345678 -s 2018-01-01 -e 2019-07-01
```

* To get a report of diffs:

```shell
python3 emr_diff.py -u 123456 -p n@800101 -c 12345678 -s 2018-01-01 -e 2019-07-01
```


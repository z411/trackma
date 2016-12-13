#!/usr/bin/python

import ntpath
import re
import urllib.parse
import urllib.request
import xml.dom.minidom as xdmd

import trackma.utils as utils


def get_config():
    # get configs from file
    configfile = utils.get_root_filename('config.json')
    try:
        config = utils.parse_config(configfile, utils.config_defaults)
    except IOError:
        raise utils.EngineFatal("Couldn't open config file.")

    plex_host_port = config['plex_host']+":"+config['plex_port']

    if config['tracker_type'] == "plex":
        enabled = True
    else:
        enabled = False

    return [enabled, plex_host_port]


def last_watched():
    # returns the last watched file in plex (deprecated, playing_file() is used now)
    hostnport = get_config()[1]
    sections = "http://"+hostnport+"/library/sections"
    sedoc = xdmd.parse(urllib.request.urlopen(sections))

    leng = int(sedoc.getElementsByTagName("MediaContainer")[0].getAttribute("size"))

    # compare timestamps in the sections to get the filename
    tstamps = []
    for item in range(leng):
        key = sedoc.getElementsByTagName("Directory")[item].getAttribute("key")
        xd = xdmd.parse(urllib.request.urlopen(sections+"/"+key+"/recentlyViewed"))
        tstamps.append(xd.getElementsByTagName("Video")[0].getAttribute("lastViewedAt"))

    key = sedoc.getElementsByTagName("Directory")[tstamps.index(max(tstamps))].getAttribute("key")
    url = sections+"/"+key+"/recentlyViewed"

    doc = xdmd.parse(urllib.request.urlopen(url))
    attr = doc.getElementsByTagName("Part")[0].getAttribute("file")
    fname = urllib.parse.unquote(ntpath.basename(attr)[:-4])

    return fname


def status():
    # returns the plex status of the first active session
    hostnport = get_config()[1]

    try:
        session_url = "http://"+hostnport+"/status/sessions"
        sdoc = xdmd.parse(urllib.request.urlopen(session_url))
    except urllib.request.URLError:
        return "NOT_RUNNING"

    active = int(sdoc.getElementsByTagName("MediaContainer")[0].getAttribute("size"))

    if active:
        return "ACTIVE"
    else:
        return "IDLE"


def timer_from_file():
    # returns 80% of video duration for the update timer
    hostnport = get_config()[1]
    session_url = "http://"+hostnport+"/status/sessions"
    sdoc = xdmd.parse(urllib.request.urlopen(session_url))

    if status() == "IDLE":
        return 20

    duration = int(sdoc.getElementsByTagName("Video")[0].getAttribute("duration"))
    # voffset = int(sdoc.getElementsByTagName("Video")[0].getAttribute("viewOffset"))

    return round((duration*0.80)/60000)*60


def playing_file():
    # returns the filename of the currently playing file
    hostnport = get_config()[1]

    if status() == "IDLE":
        return False

    session_url = "http://"+hostnport+"/status/sessions"
    sdoc = xdmd.parse(urllib.request.urlopen(session_url))

    attr = sdoc.getElementsByTagName("Part")[0].getAttribute("file")
    name = urllib.parse.unquote(ntpath.basename(attr)[:-4])

    return name

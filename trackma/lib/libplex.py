#!/usr/bin/python

import ntpath
import re
import urllib2
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
    sections = u"http://"+hostnport+u"/library/sections"
    sedoc = xdmd.parse(urllib2.urlopen(sections))

    leng = int(sedoc.getElementsByTagName(u"MediaContainer")[0].getAttribute(u"size"))

    # compare timestamps in the sections to get the filename
    tstamps = []
    for item in xrange(leng):
        key = sedoc.getElementsByTagName(u"Directory")[item].getAttribute(u"key")
        xd = xdmd.parse(urllib2.urlopen(sections+u"/"+key+u"/recentlyViewed"))
        tstamps.append(xd.getElementsByTagName(u"Video")[0].getAttribute(u"lastViewedAt"))

    key = sedoc.getElementsByTagName(u"Directory")[tstamps.index(max(tstamps))].getAttribute(u"key")
    url = sections+u"/"+key+u"/recentlyViewed"

    doc = xdmd.parse(urllib2.urlopen(url))
    attr = doc.getElementsByTagName(u"Part")[0].getAttribute(u"file")
    fname = urllib2.unquote(ntpath.basename(attr)[:-4])

    return fname


def status():
    # returns the plex status of the first active session
    hostnport = get_config()[1]

    try:
        session_url = u"http://"+hostnport+u"/status/sessions"
        sdoc = xdmd.parse(urllib2.urlopen(session_url))
    except urllib2.URLError:
        return u"NOT_RUNNING"

    active = int(sdoc.getElementsByTagName(u"MediaContainer")[0].getAttribute(u"size"))

    if active:
        return u"ACTIVE"
    else:
        return u"IDLE"


def playing_file():
    # returns the filename of the currently playing file
    hostnport = get_config()[1]

    if status() == "IDLE":
        return False

    session_url = u"http://"+hostnport+u"/status/sessions"
    sdoc = xdmd.parse(urllib2.urlopen(session_url))

    attr = sdoc.getElementsByTagName(u"Part")[0].getAttribute(u"file")
    name = urllib2.unquote(ntpath.basename(attr)[:-4])

    return name

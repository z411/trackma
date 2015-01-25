#!/usr/bin/python

import trackma.utils as utils
import re, ntpath
import xml.dom.minidom as xdmd
import urllib2

def get_config():
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
	hostnport = get_config()[1]
	sections = u"http://"+hostnport+u"/library/sections"
	sedoc = xdmd.parse(urllib2.urlopen(sections))

	leng = int(sedoc.getElementsByTagName(u"MediaContainer")[0].getAttribute(u"size"))

	tstamps = []
	for item in xrange(leng):
		key = sedoc.getElementsByTagName(u"Directory")[item].getAttribute(u"key")
		xd = xdmd.parse(urllib2.urlopen(sections+u"/"+key+u"/recentlyViewed"))
		tstamps.append(xd.getElementsByTagName(u"Video")[0].getAttribute(u"lastViewedAt"))

	key = sedoc.getElementsByTagName(u"Directory")[tstamps.index(max(tstamps))].getAttribute(u"key")
	url = sections+u"/"+key+u"/recentlyViewed"

	# Get last watched item from plex xml data
	doc = xdmd.parse(urllib2.urlopen(url))
	attr = doc.getElementsByTagName(u"Part")[0].getAttribute(u"file")
	fname = urllib2.unquote(ntpath.basename(attr)[:-4])

	return fname

def status():
	enabled, hostnport = get_config()

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
	hostnport = get_config()[1]

	session_url = u"http://"+hostnport+u"/status/sessions"
	sdoc = xdmd.parse(urllib2.urlopen(session_url))

	attr = sdoc.getElementsByTagName(u"Part")[0].getAttribute(u"file")
	name = urllib2.unquote(ntpath.basename(attr)[:-4])

	return name

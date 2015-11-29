# -*- coding: utf-8 -*-
#
# This hook sends episode updates to monthly.moe and marks them as watched.
#
# To use, copy this file to ~/.trackma/hook.py and fill in the access token.

##### Hook start #####
ACCESS_TOKEN = ""

if not ACCESS_TOKEN:
    raise Exception("You must provide the Monthly.moe HTTP API access token..")

import urllib, urllib2, json
import trackma.utils as utils

MONTHLY_URL = "http://www.monthly.moe/api"
HEADERS = {'User-Agent': 'Trackma/{}'.format(utils.VERSION)}

def monthly_send(engine, show):
    api_name = engine.api_info['name']
    if api_name != "MyAnimeList":
        engine.msg.warn('Monthly.moe', "This currently only works with MyAnimeList.")
        return

    engine.msg.info('Monthly.moe', "Updating episode.")

    data = urllib.urlencode({
        'token': ACCESS_TOKEN,
        'mal_id': show['id'],
        'type': 'episode',
        'number': show['my_progress'],
    })
    req = urllib2.Request(MONTHLY_URL, data, HEADERS)
    response = urllib2.urlopen(req)
    json_data = json.load(response)

    if not json_data['success']:
        engine.msg.warn('Monthly.moe', "Problem updating episode.")

##### HOOK END #####

def episode_changed(engine, show):
    monthly_send(engine, show)


# -*- coding: utf-8 -*-
#
# This hook sends episode updates to monthly.moe and marks them as watched.
#
# To use, copy this file to ~/.trackma/hooks/ and fill in the access token.

import json
import urllib.parse
import urllib.request

import trackma.utils as utils

ACCESS_TOKEN = ""

if not ACCESS_TOKEN:
    raise Exception("You must provide the Monthly.moe HTTP API access token..")

MONTHLY_URL = "https://www.monthly.moe/api/v1/user/library/taiga"
HEADERS = {'User-Agent': 'Trackma/{}'.format(utils.VERSION)}


def episode_changed(engine, show):
    api_name = engine.api_info['name'].lower()
    if api_name not in ["myanimelist", "anilist"]:
        engine.msg.warn('Monthly.moe', "This currently only works with MyAnimeList or AniList.")
        return

    engine.msg.info('Monthly.moe', "Updating episode.")

    data = urllib.parse.urlencode({
        'token': ACCESS_TOKEN,
        'id': show['id'],
        'service': api_name,
        'playstatus': 'updated',
        'watched': show['my_progress'],
        'total': show['total'],
    }).encode('utf-8')
    req = urllib.request.Request(MONTHLY_URL, data, HEADERS)
    response = urllib.request.urlopen(req)
    json_data = json.loads(response.read().decode('utf-8'))

    if not json_data['success']:
        engine.msg.warn('Monthly.moe', "Problem updating episode.")


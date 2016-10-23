# -*- coding: utf-8 -*-
#
# This hook posts to Twitter whenever you complete a show.
# You most provide consumer and access keys yourself.
#
# We should probably create an application and provide a access token
# generator script.
#
# To use, copy this file to ~/.trackma/hooks/ and fill in the consumer/access tokens.

import twitter
CONSUMER_KEY    = ""
CONSUMER_SECRET = ""
ACCESS_KEY      = ""
ACCESS_SECRET   = ""

if not ACCESS_KEY or not ACCESS_SECRET:
    raise Exception("You must provide the Twitter access token in the hook file.")

api = twitter.Api(consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token_key=ACCESS_KEY,
        access_token_secret=ACCESS_SECRET)

def status_changed(engine, show, old_status):
    api_name        = engine.api_info['name']
    finished_status = engine.mediainfo['status_finish']
    score_max       = engine.mediainfo['score_max']

    if show['my_status'] == finished_status:
        msg = "[%s] Finished %s" % (api_name, show['title'])
        if show['my_score']:
            msg += " - Score: %s/%s" % (show['my_score'], score_max)
        msg += " %s" % show['url']

        if len(msg) <= 140:
            engine.msg.info('Twitter', "Tweeting: %s (%d)" % (msg, len(msg)))
            api.PostUpdate(msg)
        else:
            engine.msg.warn('Twitter', "Tweet too long.")



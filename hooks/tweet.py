# -*- coding: utf-8 -*-
#
# This hook posts to Twitter whenever you complete a show.
#
<<<<<<< HEAD:hooks/tweet.py
# We should probably create an application and provide a access token
# generator script.
#
# To use, copy this file to ~/.trackma/hooks/ and fill in the consumer/access tokens.

import twitter
CONSUMER_KEY    = ""
CONSUMER_SECRET = ""
=======
# To use it, copy this file to ~/.trackma/hooks/ and fill in the consumer/access tokens.
# You may use the twitter_authorize.py utility to fetch them.

#########################

>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34:docs/hook_examples/twitter.py
ACCESS_KEY      = ""
ACCESS_SECRET   = ""

#########################

if not ACCESS_KEY or not ACCESS_SECRET:
    raise Exception("You must provide the Twitter access token in the hook file.")

CONSUMER_KEY    = "9Hb6ZdMmvuAWxi4GCkfhToRiH"
CONSUMER_SECRET = "86kx9Mv9wJ5UTkDEw2jRBFYstpkDK2iP7ZAo12fhf0WooMln5w"

try:
    import twitter
    from twitter.error import TwitterError
except NameError:
    print("tweet-hook: python3-twitter is not installed.")
api = twitter.Api(consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token_key=ACCESS_KEY,
        access_token_secret=ACCESS_SECRET)

def status_changed(engine, show, old_status):
    api_name        = engine.api_info['name']
    finished_status = engine.mediainfo['statuses_finish']
    score_max       = engine.mediainfo['score_max']

    if show['my_status'] in finished_status:
        msg = "[%s] Finished %s" % (api_name, show['title'])
        if show['my_score']:
            msg += " - Score: %s/%s" % (show['my_score'], score_max)
        msg += " %s" % show['url']

        if len(msg) <= 280:
            engine.msg.info('Twitter', "Tweeting: %s (%d)" % (msg, len(msg)))
            try:
                api.PostUpdate(msg)
            except TwitterError as e:
                engine.msg.warn('Twitter', "[%d] %s" % (e.message[0]['code'], e.message[0]['message']))
        else:
            engine.msg.warn('Twitter', "Tweet too long.")



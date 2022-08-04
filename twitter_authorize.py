#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Modified from bear/python-twitter/get_access_token.py

import webbrowser

from requests_oauthlib import OAuth1Session

REQUEST_TOKEN_URL = 'https://api.twitter.com/oauth/request_token'
ACCESS_TOKEN_URL = 'https://api.twitter.com/oauth/access_token'
AUTHORIZATION_URL = 'https://api.twitter.com/oauth/authorize'
SIGNIN_URL = 'https://api.twitter.com/oauth/authenticate'

CONSUMER_KEY = '9Hb6ZdMmvuAWxi4GCkfhToRiH'
CONSUMER_SECRET = '86kx9Mv9wJ5UTkDEw2jRBFYstpkDK2iP7ZAo12fhf0WooMln5w'


def get_access_token():
    oauth_client = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET, callback_uri='oob')

    print('Requesting temp token from Twitter...')
    resp = oauth_client.fetch_request_token(REQUEST_TOKEN_URL)
    url = oauth_client.authorization_url(AUTHORIZATION_URL)

    print('\nI will try to start a browser to visit the following Twitter page.'
          'If the browser will not start, copy the URL to your browser '
          'and retrieve the pincode to be used '
          'in the next step to obtaining an Authentication Token: \n'
          '\n\t{0}'.format(url))

    webbrowser.open(url)
    pincode = input('\nEnter your pincode: ')

    print('Generating and signing request for an access token...')

    oauth_client = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET,
                                 resource_owner_key=resp.get('oauth_token'),
                                 resource_owner_secret=resp.get('oauth_token_secret'),
                                 verifier=pincode)
    try:
        resp = oauth_client.fetch_access_token(ACCESS_TOKEN_URL)
    except ValueError as e:
        raise 'Invalid response from Twitter requesting temp token: {0}'.format(e)

    print('''======================\nYour tokens/keys are as follows:
        ACCESS_KEY    = "{atk}"
        ACCESS_SECRET = "{ats}"'''.format(
            ck=CONSUMER_KEY,
            cs=CONSUMER_SECRET,
            atk=resp.get('oauth_token'),
            ats=resp.get('oauth_token_secret')))

    print()
    print('Please fill these variables in the hooks/tweet.py file')
    print('and copy it into the ~/.config/trackma/hooks directory.')


def main():
    print("Trackma Twitter Authorization Utility")
    print()
    print("Trackma includes a hook to post updates to Twitter (hooks/tweet.py).")
    print("This utility will ask you to log into Twitter and will")
    print("return a token for you to include in the hooks/tweet.py file.")
    print()
    key = input("Continue? [Y/n] ")
    if not key or key.lower() == 'y':
        get_access_token()


if __name__ == "__main__":
    main()

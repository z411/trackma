# This file is part of Trackma.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import json
import urllib.parse
import urllib.request
import socket
import time
import datetime

from trackma.lib.lib import lib
from trackma import utils


class libmalv2(lib):
    """
    API class to communicate with MyAnimeList (new API)

    Website: https://anilist.co

    messenger: Messenger object to send useful messages to
    """
    name = 'libmalv2'
    msg = None
    logged_in = False

    api_info = {'name': 'MyAnimeList (new)', 'shortname': 'malv2',
                'version': 'v3', 'merge': False}
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': True,
        'can_date': True,
        'date_next_ep': True,
        'statuses_start': ['CURRENT', 'REPEATING'],
        'statuses_finish': ['COMPLETED'],
        'statuses_library': ['CURRENT', 'REPEATING', 'PAUSED', 'PLANNING'],
        'statuses':  ['CURRENT', 'COMPLETED', 'REPEATING', 'PAUSED', 'DROPPED', 'PLANNING'],
        'statuses_dict': {
            'CURRENT': 'Watching',
            'COMPLETED': 'Completed',
            'REPEATING': 'Rewatching',
            'PAUSED': 'Paused',
            'DROPPED': 'Dropped',
            'PLANNING': 'Plan to Watch'
        },
        'score_max': 10,
        'score_step': 1,
        'search_methods': [utils.SEARCH_METHOD_KW, utils.SEARCH_METHOD_SEASON],
    }
    mediatypes['manga'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': False,
        'can_date': True,
        'statuses_start': ['CURRENT', 'REPEATING'],
        'statuses_finish': ['COMPLETED'],
        'statuses':  ['CURRENT', 'COMPLETED', 'REPEATING', 'PAUSED', 'DROPPED', 'PLANNING'],
        'statuses_dict': {
            'CURRENT': 'Reading',
            'COMPLETED': 'Completed',
            'REPEATING': 'Rereading',
            'PAUSED': 'Paused',
            'DROPPED': 'Dropped',
            'PLANNING': 'Plan to Read'
        },
        'score_max': 10,
        'score_step': 1,
        'search_methods': [utils.SEARCH_METHOD_KW],
    }
    default_mediatype = 'anime'

    # Supported signals for the data handler
    signals = {'show_info_changed': None, }

    auth_url = "https://myanimelist.net/v1/oauth2/token"
    query_url = "https://graphql.anilist.co"
    client_id = "32c510ab2f47a1048a8dd24de266dc0c"
    user_agent = 'Trackma/{}'.format(utils.VERSION)

    def __init__(self, messenger, account, userconfig):
        super(libmalv2, self).__init__(messenger, account, userconfig)

        self.pin = account['password'].strip()
        self.code_verifier = account['extra']['code_verifier']
        self.userid = self._get_userconfig('userid')

        self.opener = urllib.request.build_opener()
        self.opener.addheaders = [('User-agent', self.user_agent)]

    def _request(self, method, url, get=None, post=None, auth=False):
        content_type = None

        if get:
            url += "?%s" % urllib.parse.urlencode(get)
        if post:
            post = urllib.parse.urlencode(post).encode('utf-8')
            content_type = 'application/x-www-form-urlencoded'

        request = urllib.request.Request(url, post)
        request.get_method = lambda: method

        if content_type:
            request.add_header('Content-Type', content_type)

        if auth:
            request.add_header('Authorization', '{0} {1}'.format(
                self._get_userconfig('token_type').capitalize(),
                self._get_userconfig('access_token'),
            ))

        try:
            response = self.opener.open(request)

            return response.read().decode('utf-8')
        except urllib.request.HTTPError as e:
            raise utils.APIError("Connection error: %s" % e)
        except urllib.request.URLError as e:
            raise utils.APIError("URL error: %s" % e)
        except socket.timeout:
            raise utils.APIError("Operation timed out.")
    
    def _request_access_token(self, refresh=False):
        """
        Requests or refreshes the access token through OAuth2
        """
        params = {
            'client_id':     self.client_id,
        }

        if refresh:
            self.msg.info(self.name, 'Refreshing access token...')

            params['grant_type'] = 'refresh_token'
            params['refresh_token'] = self._get_userconfig('refresh_token')
        else:
            self.msg.info(self.name, 'Requesting access token...')

            params['code'] = self.pin
            params['code_verifier'] = self.code_verifier
            params['grant_type'] = 'authorization_code'
            
        response = self._request('POST', self.auth_url, post=params)
        data = json.loads(response)

        timestamp = int(time.time())

        self._set_userconfig('access_token',  data['access_token'])
        self._set_userconfig('token_type',    data['token_type'])
        self._set_userconfig('expires',       timestamp + data['expires_in'])
        self._set_userconfig('refresh_token', data['refresh_token'])

        self.logged_in = True
        self._emit_signal('userconfig_changed')
    
    def check_credentials(self):
        timestamp = int(time.time())
        
        if not self._get_userconfig('access_token'):
            self._request_access_token(False)
        elif (timestamp+60) > self._get_userconfig('expires'):
            self._request_access_token(True)
        else:
            self.logged_in = True

        #if not self.userid:
        #    self._refresh_user_info()

        return True

    def fetch_list(self):
        self.check_credentials()
        self.msg.info(self.name, 'Downloading list...')

        return {}

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

class libanilist(lib):
    """
    API class to communicate with Anilist

    Website: https://anilist.co

    messenger: Messenger object to send useful messages to
    """
    name = 'libanilist'
    msg = None
    logged_in = False

    api_info = { 'name': 'Anilist', 'shortname': 'anilist', 'version': '1.1', 'merge': False }
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': True,
        'date_next_ep': True,
        'status_start': 'watching',
        'status_finish': 'completed',
        'statuses':  ['watching', 'completed', 'on-hold', 'dropped', 'plan to watch'],
        'statuses_dict': {
            'watching': 'Watching',
            'completed': 'Completed',
            'on-hold': 'On Hold',
            'dropped': 'Dropped',
            'plan to watch': 'Plan to Watch'
        },
        'score_max': 100,
        'score_step': 1,
    }
    mediatypes['manga'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': False,
        'status_start': 'reading',
        'status_finish': 'completed',
        'statuses':  ['reading', 'completed', 'on-hold', 'dropped', 'plan to read'],
        'statuses_dict': {
            'reading': 'Reading',
            'completed': 'Completed',
            'on-hold': 'On Hold',
            'dropped': 'Dropped',
            'plan to read': 'Plan to Read'
        },
        'score_max': 100,
        'score_step': 1,
    }
    default_mediatype = 'anime'

    # Supported signals for the data handler
    signals = { 'show_info_changed': None, }

    url = "https://anilist.co/api/"
    client_id = "z411-gdjc3"
    _client_secret = "MyzwuYoMqPPglXwCTcexG1i"

    def __init__(self, messenger, account, userconfig):
        """Initializes the API"""
        super(libanilist, self).__init__(messenger, account, userconfig)

        self.pin = account['password'].strip()
        self.userid = userconfig['userid']

        if len(self.pin) != 40:
            raise utils.APIFatal("Invalid PIN.")

        if self.mediatype == 'manga':
            self.total_str = "total_chapters"
            self.watched_str = "chapters_read"
            self.airing_str = "publishing_status"
            self.status_translate = {
                'publishing': utils.STATUS_AIRING,
                'finished publishing': utils.STATUS_FINISHED,
                'not yet published': utils.STATUS_NOTYET,
                'cancelled': utils.STATUS_CANCELLED,
            }
        else:
            self.total_str = "total_episodes"
            self.watched_str = "episodes_watched"
            self.airing_str = "airing_status"
            self.status_translate = {
                'currently airing': utils.STATUS_AIRING,
                'finished airing': utils.STATUS_FINISHED,
                'not yet aired': utils.STATUS_NOTYET,
                'cancelled': utils.STATUS_CANCELLED,
            }

        #handler=urllib.request.HTTPHandler(debuglevel=1)
        #self.opener = urllib.request.build_opener(handler)
        self.opener = urllib.request.build_opener()
        self.opener.addheaders = [('User-agent', 'Trackma/0.1')]

    def _request(self, method, url, get=None, post=None, auth=False):
        if get:
            url = "{}?{}".format(url, urllib.parse.urlencode(get))
        if post:
            post = urllib.parse.urlencode(post).encode('utf-8')

        request = urllib.request.Request(self.url + url, post)
        request.get_method = lambda: method

        if auth:
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            request.add_header('Authorization', '{0} {1}'.format(
                self._get_userconfig('token_type').capitalize(),
                self._get_userconfig('access_token'),
            ))

        try:
            response = self.opener.open(request, timeout = 10)
            return json.loads(response.read().decode('utf-8'))
        except urllib.request.HTTPError as e:
            if e.code == 400:
                raise utils.APIError("Invalid PIN. It is either probably expired or meant for another application.")
            else:
                raise utils.APIError("Connection error: %s" % e)
        except socket.timeout:
            raise utils.APIError("Connection timed out.")

    def _request_access_token(self):
        self.msg.info(self.name, 'Requesting access token...')
        param = {
            'grant_type': 'authorization_pin',
            'client_id':  self.client_id,
            'client_secret': self._client_secret,
            'code': self.pin,
        }
        data = self._request("POST", "auth/access_token", get=param)

        self._set_userconfig('access_token', data['access_token'])
        self._set_userconfig('token_type', data['token_type'])
        self._set_userconfig('expires', data['expires'])
        self._set_userconfig('refresh_token', data['refresh_token'])

        self.logged_in = True
        self._refresh_user_info()
        self._emit_signal('userconfig_changed')

    def _refresh_access_token(self):
        self.msg.info(self.name, 'Refreshing access token...')
        param = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self._client_secret,
            'refresh_token': self._get_userconfig('refresh_token'),
        }
        data = self._request("POST", "auth/access_token", get=param)

        self._set_userconfig('access_token', data['access_token'])
        self._set_userconfig('token_type', data['token_type'])
        self._set_userconfig('expires', data['expires'])

        self.logged_in = True
        self._refresh_user_info()
        self._emit_signal('userconfig_changed')

    def _refresh_user_info(self):
        self.msg.info(self.name, 'Refreshing user details...')
        param = {'access_token': self._get_userconfig('access_token')}

        data = self._request("GET", "user", get=param)

        self._set_userconfig('userid', data['id'])
        self._set_userconfig('username', data['display_name'])

        self.userid = data['id']

    def check_credentials(self):
        """
        Log into Anilist. Since it uses OAuth, we either request an access token
        or refresh the current one. If neither is necessary, just continue.
        """
        timestamp = int(time.time())

        if not self._get_userconfig('access_token'):
            self._request_access_token()
        elif (timestamp+60) > self._get_userconfig('expires'):
            self._refresh_access_token()
        else:
            self.logged_in = True
        return True

    def fetch_list(self):
        self.check_credentials()
        self.msg.info(self.name, 'Downloading list...')

        param = {'access_token': self._get_userconfig('access_token')}
        data = self._request("GET", "user/{0}/{1}list".format(self.userid, self.mediatype), get=param)

        showlist = {}
        airinglist = []

        #with open('list', 'w') as f:
        #    json.dump(data, f, indent=2)

        if not data["lists"]:
            # No lists returned so no need to continue
            return showlist

        for remotelist in data["lists"].values():
            for item in remotelist:
                if item['list_status'] not in self.media_info()['statuses']:
                    continue

                show = utils.show()
                showid = item[self.mediatype]['id']
                showdata = {
                    'id': showid,
                    'title': item[self.mediatype]['title_romaji'],
                    'aliases': [item[self.mediatype]['title_english']],
                    'type': item[self.mediatype]['type'],
                    'status': self.status_translate[item[self.mediatype][self.airing_str]],
                    'my_progress': self._c(item[self.watched_str]),
                    'my_status': item['list_status'],
                    'my_score': self._c(item['score']),
                    'total': self._c(item[self.mediatype][self.total_str]),
                    'image': item[self.mediatype]['image_url_lge'],
                    'image_thumb': item[self.mediatype]['image_url_med'],
                    'url': str("https://anilist.co/%s/%d" % (self.mediatype, showid)),
                }
                show.update({k:v for k,v in showdata.items() if v})

                if show['status'] == 1:
                    airinglist.append(showid)

                showlist[showid] = show

        if self.mediatype == 'anime': # Airing data unavailable for manga
            if len(airinglist) > 0:
                browseparam = {'access_token': self._get_userconfig('access_token'),
                         'status': 'Currently Airing',
                         'airing_data': 'true',
                         'full_page': 'true'}
                data = self._request("GET", "browse/anime", get=browseparam)
                for item in data:
                    id = item['id']
                    if id in showlist and 'airing' in item:
                        if item['airing']:
                            showlist[id].update({
                                'next_ep_number': item['airing']['next_episode'],
                                'next_ep_time': item['airing']['time'],
                            })
        return showlist

    def add_show(self, item):
        self.check_credentials()
        self.msg.info(self.name, "Adding item %s..." % item['title'])
        self._update_entry(item, "POST")

    def update_show(self, item):
        self.check_credentials()
        self.msg.info(self.name, "Updating item %s..." % item['title'])
        self._update_entry(item, "PUT")

    def delete_show(self, item):
        self.check_credentials()
        self.msg.info(self.name, "Deleting item %s..." % item['title'])

        try:
            data = self._request("DELETE", "{}list/{}".format(self.mediatype, item['id']), auth=True)
        except ValueError:
            # An empty document, without any JSON, is returned
            # when the delete worked.
            pass

    def search(self, criteria):
        self.check_credentials()

        self.msg.info(self.name, "Searching for {}...".format(criteria))
        param = {'access_token': self._get_userconfig('access_token')}
        data = self._request("GET", "{0}/search/{1}".format(self.mediatype, criteria), get=param)

        if type(data) == dict:
            # In case of error API returns a small JSON payload
            # which translates into a dict with the key 'error'
            # instead of a list.
            if data['error']['messages'][0] == 'No Results.':
                data = []
            else:
                raise utils.APIError("Error while searching for \
                        {0}: {1}".format(criteria, str(data)))

        showlist = []
        for item in data:
            show = utils.show()
            showid = item['id']
            showdata = {
                'id': showid,
                'title': item['title_romaji'],
                'aliases': [item['title_english']],
                'type': item['type'],
                'status': item[self.airing_str],
                'my_status': self.media_info()['status_start'],
                'total': item[self.total_str],
                'image': item['image_url_lge'],
                'image_thumb': item['image_url_med'],
                'url': str("https://anilist.co/%s/%d" % (self.mediatype, showid)),
            }
            show.update({k:v for k,v in showdata.items() if v})

            showlist.append( show )

        return showlist

    def request_info(self, itemlist):
        self.check_credentials()
        param = {'access_token': self._get_userconfig('access_token')}
        infolist = []

        for show in itemlist:
            data = self._request("GET", "{0}/{1}".format(self.mediatype, show['id']), get=param)
            infolist.append( self._parse_info(data) )

        self._emit_signal('show_info_changed', infolist)
        return infolist

    def media_info(self):
        """Return information about the currently selected mediatype."""
        return self.mediatypes[self.mediatype]

    def _update_entry(self, item, method):
        values = { 'id': item['id'] }
        if 'my_progress' in item:
            values[self.watched_str] = item['my_progress']
        if 'my_status' in item:
            values['list_status'] = item['my_status']
        if 'my_score' in item:
            values['score'] = item['my_score']

        data = self._request(method, "{}list".format(self.mediatype), post=values, auth=True)
        return True

    def _parse_info(self, item):
        info = utils.show()
        showid = item['id']
        info.update({
            'id': showid,
            'title': item['title_romaji'],
            'status': self.status_translate[item[self.airing_str]],
            'image': item['image_url_lge'],
            'url': str("https://anilist.co/%s/%d" % (self.mediatype, showid)),
            'start_date': self._str2date(item.get('start_date')),
            'end_date': self._str2date(item.get('end_date')),
            'extra': [
                ('English',         item.get('title_english')),
                ('Japanese',        item.get('title_japanese')),
                ('Classification',  item.get('classification')),
                ('Genres',          item.get('genres')),
                ('Synopsis',        item.get('description')),
                ('Type',            item.get('type')),
                ('Average score',   item.get('average_score')),
                ('Status',          item.get(self.airing_str)),
                ('Start Date',      item.get('start_date')),
                ('End Date',        item.get('end_date')),
            ]
        })
        return info

    def _str2date(self, string):
        if string is not None:
            try:
                return datetime.datetime.strptime(string[:10], "%Y-%m-%d")
            except ValueError:
                return None # Ignore date if it's invalid
        else:
            return None


    def _c(self, s):
        if s is None:
            return 0
        else:
            return s


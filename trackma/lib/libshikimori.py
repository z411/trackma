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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import json
import urllib.parse
import urllib.request
import socket
import time

from trackma.lib.lib import lib
from trackma import utils

class libshikimori(lib):
    """
    API class to communicate with Shikimori

    Website: http://shikimori.org

    messenger: Messenger object to send useful messages to
    """
    name = 'libshikimori'
    msg = None
    logged_in = False

    api_info = { 'name': 'Shikimori', 'shortname': 'shikimori', 'version': '1', 'merge': False }
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': True,
        'statuses_start': [1, 9],
        'statuses_finish': [2],
        'statuses_library': [1, 3, 0],
        'statuses':  [1, 2, 3, 9, 4, 0],
        'statuses_dict': {
            1: 'Watching',
            2: 'Completed',
            3: 'On-Hold',
            9: 'Rewatching',
            4: 'Dropped',
            0: 'Plan to Watch'
        },
        'score_max': 10,
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
        'statuses_start': [1, 9],
        'statuses_finish': [2],
        'statuses':  [1, 2, 3, 9, 4, 0],
        'statuses_dict': {
            1: 'Reading',
            2: 'Completed',
            3: 'On-Hold',
            9: 'Rereading',
            4: 'Dropped',
            0: 'Plan to Read'
        },
        'score_max': 10,
        'score_step': 1,
    }
    default_mediatype = 'anime'

    # Supported signals for the data handler
    signals = { 'show_info_changed': None, }

    url = "http://shikimori.org"

    def __init__(self, messenger, account, userconfig):
        """Initializes the API"""
        super(libshikimori, self).__init__(messenger, account, userconfig)

        self.username = account['username']
        self.password = account['password']
        self.userid = userconfig['userid']

        if not self.password:
            raise utils.APIFatal("No password.")

        if self.mediatype == 'manga':
            self.total_str = "chapters"
            self.watched_str = "chapters"
            self.airing_str = "publishing_status"
            self.status_translate = {
                'publishing': utils.STATUS_AIRING,
                'finished': utils.STATUS_FINISHED,
                'not yet published': utils.STATUS_NOTYET,
                'cancelled': utils.STATUS_CANCELLED,
            }
        else:
            self.total_str = "episodes"
            self.watched_str = "episodes"
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
        self.opener.addheaders = [('User-agent', 'Trackma/0.4')]

    def _request(self, method, url, get=None, post=None, jsondata=None, auth=False):
        if get:
            url = "{}?{}".format(url, urllib.parse.urlencode(get))
        if post:
            post = urllib.parse.urlencode(post)
        if jsondata:
            post = json.dumps(jsondata, separators=(',',':')).encode('utf-8')

        request = urllib.request.Request(self.url + url, post)
        request.get_method = lambda: method

        if auth:
            request.add_header('Content-Type', 'application/json')
            request.add_header('X-User-Nickname', self.username)
            request.add_header('X-User-Api-Access-Token', self._get_userconfig('access_token'))

        try:
            response = self.opener.open(request, timeout = 10)
            return json.loads(response.read().decode('utf-8'))
        except urllib.request.HTTPError as e:
            if e.code == 400:
                raise utils.APIError("400")
            else:
                raise utils.APIError("Connection error: %s" % e)
        except socket.timeout:
            raise utils.APIError("Connection timed out.")
        except ValueError:
            pass # No JSON data

    def _request_access_token(self):
        self.msg.info(self.name, 'Requesting access token...')
        param = {
            'nickname': self.username,
            'password':  self.password,
        }
        data = self._request("POST", "/api/access_token", get=param)

        self._set_userconfig('access_token', data['api_access_token'])

        self.logged_in = True
        self._refresh_user_info()
        self._emit_signal('userconfig_changed')

    def _refresh_user_info(self):
        self.msg.info(self.name, 'Refreshing user details...')

        data = self._request("GET", "/api/users/whoami", auth=True)

        self._set_userconfig('userid', data['id'])
        self._set_userconfig('username', data['nickname'])

        self.userid = data['id']

    def check_credentials(self):
        """
        Log into Shikimori. Ask for the request token if necessary.
        """
        timestamp = int(time.time())

        if not self._get_userconfig('access_token'):
            self._request_access_token()
        else:
            self.logged_in = True
        return True

    def fetch_list(self):
        self.check_credentials()
        self.msg.info(self.name, 'Downloading list...')

        data = self._request("GET", "/api/users/{}/{}_rates".format(self.userid, self.mediatype))

        showlist = {}

        #with open('list', 'w') as f:
        #    json.dump(data, f, indent=2)

        for item in data:
            show = utils.show()
            showid = item[self.mediatype]['id']
            show.update({
                'id': showid,
                'my_id': item['id'],
                'title': item[self.mediatype]['name'],
                'aliases': [item[self.mediatype]['russian']],
                #'type': item[self.mediatype]['type'],
                #'status': self.status_translate[item[self.mediatype][self.airing_str]],
                'my_id': item['id'],
                'my_progress': item[self.watched_str],
                'my_status': item['status'],
                'my_score': item['score'],
                'total': item[self.mediatype][self.total_str],
                'url': self.url + item[self.mediatype]['url'],
                'image': self.url + item[self.mediatype]['image']['original'],
                'image_thumb': self.url + item[self.mediatype]['image']['preview'],
            })

            showlist[showid] = show

        return showlist

    def add_show(self, item):
        self.check_credentials()
        self.msg.info(self.name, "Adding item %s..." % item['title'])
        return self._update_entry(item, "POST")

    def update_show(self, item):
        self.check_credentials()
        self.msg.info(self.name, "Updating item %s..." % item['title'])
        return self._update_entry(item, "PUT")

    def delete_show(self, item):
        self.check_credentials()
        self.msg.info(self.name, "Deleting item %s..." % item['title'])

        data = self._request("DELETE", "/api/user_rates/{}".format(item['my_id']), auth=True)

    def search(self, criteria, method):
        self.check_credentials()

        self.msg.info(self.name, "Searching for {}...".format(criteria))
        param = {'q': criteria}
        try:
            data = self._request("GET", "/api/{}s/search".format(self.mediatype), get=param)
        except ValueError:
            # An empty document, without any JSON, is returned
            # when there are no results.
            return []

        showlist = []

        for item in data:
            show = utils.show()
            showid = item['id']
            show.update({
                'id': showid,
                'title': item['name'],
                'aliases': [item['russian']],
                'type': item.get('kind', ''),
                #'status': item[self.airing_str],
                'status': 0,
                'my_status': self.media_info()['statuses_start'][0],
                'total': item[self.total_str],
                'image': self.url + item['image']['original'],
                'image_thumb': self.url + item['image']['preview'],
            })

            showlist.append( show )

        return showlist

    def request_info(self, itemlist):
        self.check_credentials()
        infolist = []

        for show in itemlist:
            data = self._request("GET", "/api/{}s/{}".format(self.mediatype, show['id']))
            infolist.append( self._parse_info(data) )

        self._emit_signal('show_info_changed', infolist)
        return infolist

    def media_info(self):
        """Return information about the currently selected mediatype."""
        return self.mediatypes[self.mediatype]

    def _update_entry(self, item, method):
        # Note: This method returns the newly added or modified item ID (my_id)
        if method == 'POST':
            user_rate = {
                'user_id': self.userid,
                'target_id': item['id'],
                'target_type': self.mediatype.capitalize(),
            }
            dest_url = "/api/user_rates"
        else:
            #user_rate = {'score': 0, 'status': 0, 'episodes': 0, 'volumes': 0, 'chapters': 0, 'text': '', 'rewatches': 0}
            user_rate = {}
            dest_url = "/api/user_rates/{}".format(item['my_id'])

        if 'my_progress' in item:
            user_rate[self.watched_str] = item['my_progress']
        if 'my_status' in item:
            user_rate['status'] = item['my_status']
        if 'my_score' in item:
            user_rate['score'] = item['my_score']

        values = {'user_rate': user_rate}
        data = self._request(method, dest_url, jsondata=values, auth=True)
        return data['id']

    def _parse_info(self, item):
        info = utils.show()
        info.update({
            'id': item['id'],
            'title': item['name'],
            'status': 0,
            'image': self.url + item['image']['original'],
            'url': self.url + item['url'],
            'extra': [
                ('Description',     item.get('description')),
                #('Genres',          item.get('genres')),
                ('Type',            item.get('kind').capitalize()),
                ('Average score',   item.get('score')),
                ('Russian title',   item.get('russian')),
                ('Japanese title',  item.get('japanese')[0]),
                ('English title',   item.get('english')),
            ]
        })
        return info

    def _c(self, s):
        return 0 if s is None else s


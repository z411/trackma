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
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from trackma import utils
from trackma.lib.lib import lib


class libshikimori(lib):
    """
    API class to communicate with Shikimori

    Website: https://shikimori.org

    messenger: Messenger object to send useful messages to
    """
    name = 'libshikimori'
    msg = None
    logged_in = False

    api_info = {'name': 'Shikimori', 'shortname': 'shikimori',
                'version': 2, 'merge': False}
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': True,
        'statuses_start': ['watching', 'rewatching'],
        'statuses_finish': ['completed'],
        'statuses_library': ['watching', 'rewatching', 'planned'],
        'statuses':  ['watching', 'completed', 'on_hold', 'rewatching', 'dropped', 'planned'],
        'statuses_dict': {
            'watching': 'Watching',
            'completed': 'Completed',
            'on_hold': 'On-Hold',
            'rewatching': 'Rewatching',
            'dropped': 'Dropped',
            'planned': 'Plan to Watch'
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
        'statuses_start': ['watching', 'rewatching'],
        'statuses_finish': ['completed'],
        'statuses':  ['watching', 'completed', 'on_hold', 'rewatching', 'dropped', 'planned'],
        'statuses_dict': {
            'watching': 'Reading',
            'completed': 'Completed',
            'on_hold': 'On-Hold',
            'rewatching': 'Re-reading',
            'dropped': 'Dropped',
            'planned': 'Plan to Read'
        },
        'score_max': 10,
        'score_step': 1,
    }
    default_mediatype = 'anime'

    # Supported signals for the data handler
    signals = {'show_info_changed': None, }

    url = "https://shikimori.org"
    auth_url = "https://shikimori.org/oauth/token"
    api_url = "https://shikimori.org/api"

    client_id = "Jfu9MKkUKPG4fOC95A6uwUVLHy3pwMo3jJB7YLSp7Ro"
    client_secret = "y7YmQx8n1l7eBRugUSiB7NfNJxaNBMvwppfxJLormXU"

    status_translate = {
        'ongoing': utils.Status.AIRING,
        'released': utils.Status.FINISHED,
        'anons': utils.Status.NOTYET,
        'cancelled': utils.Status.CANCELLED,
    }

    type_translate = {
        None: utils.Type.UNKNOWN,
        'tv': utils.Type.TV,
        'movie': utils.Type.MOVIE,
        'ova': utils.Type.OVA,
        'ona': utils.Type.OVA,
        'special': utils.Type.SP,
        'music': utils.Type.OTHER,
        'tv_13': utils.Type.TV,
        'tv_24': utils.Type.TV,
        'tv_48': utils.Type.TV,
    }

    def __init__(self, messenger, account, userconfig):
        """Initializes the API"""
        super(libshikimori, self).__init__(messenger, account, userconfig)

        self.pin = account['password']
        self.userid = self._get_userconfig('userid')

        if not self.pin:
            raise utils.APIFatal("No PIN.")

        if self.mediatype == 'manga':
            self.total_str = "chapters"
            self.watched_str = "chapters"

        else:
            self.total_str = "episodes"
            self.watched_str = "episodes"

        # handler=urllib.request.HTTPHandler(debuglevel=1)
        # self.opener = urllib.request.build_opener(handler)
        self.opener = urllib.request.build_opener()
        self.opener.addheaders = [('User-agent', 'Trackma')]

    def _request(self, method, url, get=None, post=None, jsondata=None, auth=False):
        content_type = None

        if get:
            url += "?%s" % urllib.parse.urlencode(get)
        if post:
            post = urllib.parse.urlencode(post).encode('utf-8')
            content_type = 'application/x-www-form-urlencoded'
        if jsondata:
            post = json.dumps(jsondata).encode('utf-8')
            content_type = 'application/json'

        request = urllib.request.Request(url, post)
        self.msg.debug("URL: %s" % url)
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

            return json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as e:
            raise utils.APIError("URL error: %s" % e)
        except socket.timeout:
            raise utils.APIError("Operation timed out.")

    def _request_access_token(self, refresh=False):
        """
        Requests or refreshes the access token through OAuth2
        """
        params = {
            'client_id':     self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri':  'urn:ietf:wg:oauth:2.0:oob',
        }

        if refresh:
            self.msg.info('Refreshing access token...')

            params['grant_type'] = 'refresh_token'
            params['refresh_token'] = self._get_userconfig('refresh_token')
        else:
            self.msg.info('Requesting access token...')

            params['code'] = self.pin
            params['grant_type'] = 'authorization_code'

        data = self._request('POST', self.auth_url, post=params)

        timestamp = int(time.time())

        self._set_userconfig('access_token',  data['access_token'])
        self._set_userconfig('token_type',    data['token_type'])
        self._set_userconfig('expires',       timestamp + data['expires_in'])
        self._set_userconfig('refresh_token', data['refresh_token'])

        self.logged_in = True
        self._emit_signal('userconfig_changed')

    def _refresh_user_info(self):
        self.msg.info('Refreshing user details...')

        data = self._request("GET", self.api_url + "/users/whoami", auth=True)

        self._set_userconfig('userid', data['id'])
        self._set_userconfig('username', data['nickname'])

        self.userid = data['id']
        self._emit_signal('userconfig_changed')

    def check_credentials(self):
        timestamp = int(time.time())

        if not self._get_userconfig('access_token'):
            self._request_access_token(False)
        elif (timestamp+60) > self._get_userconfig('expires'):
            self._request_access_token(True)
        else:
            self.logged_in = True

        if not self.userid:
            self._refresh_user_info()

        return True

    def fetch_list(self):
        self.check_credentials()
        self.msg.info('Downloading list...')

        params = {'limit': 5000}
        data = self._request(
            "GET", self.api_url + "/users/{}/{}_rates".format(self.userid, self.mediatype), get=params)

        showlist = {}
        for item in data:
            show = utils.show()
            showid = item[self.mediatype]['id']
            show.update({
                'id': showid,
                'my_id': item['id'],
                'title': item[self.mediatype]['name'],
                'aliases': [item[self.mediatype]['russian']],
                'type': self.type_translate[item[self.mediatype]['kind']],
                'status': self.status_translate[item[self.mediatype]['status']],
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
        self.msg.info("Adding item %s..." % item['title'])
        return self._update_entry(item, "POST")

    def update_show(self, item):
        self.check_credentials()
        self.msg.info("Updating item %s..." % item['title'])
        return self._update_entry(item, "PUT")

    def delete_show(self, item):
        self.check_credentials()
        self.msg.info("Deleting item %s..." % item['title'])

        data = self._request(
            "DELETE", self.api_url + "/user_rates/{}".format(item['my_id']), auth=True)

    def search(self, criteria, method):
        self.check_credentials()

        self.msg.info("Searching for {}...".format(criteria))
        param = {'q': criteria}
        try:
            data = self._request(
                "GET", self.api_url + "/{}s/search".format(self.mediatype), get=param)
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
                'type': self.type_translate[item['kind']],
                'status': self.status_translate[item['status']],
                'my_status': self.media_info()['statuses_start'][0],
                'total': item[self.total_str],
                'image': self.url + item['image']['original'],
                'image_thumb': self.url + item['image']['preview'],
            })

            showlist.append(show)

        return showlist

    def request_info(self, itemlist):
        self.check_credentials()
        infolist = []

        for show in itemlist:
            data = self._request(
                "GET", self.api_url + "/{}s/{}".format(self.mediatype, show['id']))
            infolist.append(self._parse_info(data))

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
            dest_url = self.api_url + "/user_rates"
        else:
            # user_rate = {'score': 0, 'status': 0, 'episodes': 0, 'volumes': 0, 'chapters': 0, 'text': '', 'rewatches': 0}
            user_rate = {}
            dest_url = self.api_url + "/user_rates/{}".format(item['my_id'])

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
            'type': self.type_translate[item['kind']],
            'status': self.status_translate[item['status']],
            'image': self.url + item['image']['original'],
            'url': self.url + item['url'],
            'extra': [
                ('Description',     self._lc(item.get('description'))),
                # ('Genres',          item.get('genres')),
                ('Type',            self._lc(item.get('kind').capitalize())),
                ('Average score',   self._lc(item.get('score'))),
                ('Russian title',   self._lc(item.get('russian'))),
                ('Japanese title',  self._lc(item.get('japanese')[0])),
                ('English title',   self._lc(item.get('english'))),
            ]
        })
        return info

    def _lc(self, v):
        if v == [None]:
            return None
        return v

# -*- coding: utf-8 -*-
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

import datetime
import time
import urllib.parse
import urllib.request
import json
import gzip
import socket

#import http.client
#http.client.HTTPConnection.debuglevel = 1

from trackma.lib.lib import lib
from trackma import utils


class libkitsu(lib):
    """
    API class to communicate with Hummingbird
    Should inherit a base library interface.

    Website: https://kitsu.io/
    API documentation:
    Designed by:

    """
    name = 'libkitsu'
    user_agent = 'Trackma/{}'.format(utils.VERSION)

    auth = ''
    logged_in = False

    api_info =  {
        'name': 'Kitsu',
        'shortname': 'kitsu',
        'version': 'v0.3',
        'merge': True
    }

    default_mediatype = 'anime'
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': True,
        'status_start': 'current',
        'status_finish': 'completed',
        'statuses':  ['current', 'completed', 'on_hold', 'dropped', 'planned'],
        'statuses_dict': {
            'current': 'Watching',
            'completed': 'Completed',
            'on_hold': 'On Hold',
            'dropped': 'Dropped',
            'planned': 'Plan to Watch'
            },
        'score_max': 5,
        'score_step': 0.5,
    }

    url    = 'https://kitsu.io/api'
    prefix = 'https://kitsu.io/api/edge'

    # TODO : These values are previsional.
    _client_id     = 'dd031b32d2f56c990b1425efe6c42ad847e7fe3ab46bf1299f05ecd856bdb7dd'
    _client_secret = '54d7307928f63414defd96399fc31ba847961ceaecef3a5fd93144e960c0e151'

    status_translate = {'Currently Airing': utils.STATUS_AIRING,
            'Finished Airing': utils.STATUS_FINISHED,
            'Not Yet Aired': utils.STATUS_NOTYET}

    def __init__(self, messenger, account, userconfig):
        """Initializes the useragent through credentials."""
        super(libkitsu, self).__init__(messenger, account, userconfig)

        self.username = account['username']
        self.password = account['password']

        # Build opener with the mashape API key
        self.opener = urllib.request.build_opener()
        self.opener.addheaders = [
            ('User-Agent',      self.user_agent),
            ('Content-Type',    'application/vnd.api+json'),
            ('Accept',          'application/vnd.api+json'),
            ('Accept-Encoding', 'gzip'),
            ('Accept-Charset',  'utf-8'),
        ]

    def _request(self, url, get=None, post=None, auth=False):
        if get:
            url += "?%s" % urllib.parse.urlencode(get)
        if post:
            post = urllib.parse.urlencode(post).encode('utf-8')

        request = urllib.request.Request(url, post)
        #request.add_header('User-Agent',      self.user_agent)
        #request.add_header('Content-Type',    'application/vnd.api+json')
        #request.add_header('Accept',          'application/vnd.api+json')
        #request.add_header('Accept-Encoding', 'gzip')
        #request.add_header('Accept-Charset',  'utf-8')

        if auth:
            request.add_header('Authorization', '{0} {1}'.format(
                self._get_userconfig('token_type').capitalize(),
                self._get_userconfig('access_token'),
            ))

        try:
            response = self.opener.open(request)
            
            # The response most probably will be gzipped so we
            # have to take care of that first
            if response.info().get('content-encoding') == 'gzip':
                return gzip.GzipFile(fileobj=response).read().decode('utf-8')
            else:
                return response.read().decode('utf-8')
        except urllib.request.HTTPError as e:
            if e.code == 401:
                raise utils.APIError("Incorrect credentials.")
            else:
                raise utils.APIError("Connection error: %s" % e)
        except urllib.request.URLError as e:
            raise utils.APIError("URL error: %s" % e)
        except socket.timeout:
            raise utils.APIError("Operation timed out.")

    def _request_access_token(self):
        self.msg.info(self.name, 'Requesting access token...')
        params = {
            'grant_type':    'password',
            'username':      self.username,
            'password':      self.password,
            'client_id':     self._client_id,
            'client_secret': self._client_secret,
        }

        response = self._request(self.url + '/oauth/token', post=params)
        data = json.loads(response)
        
        timestamp = int(time.time())

        self._set_userconfig('access_token',  data['access_token'])
        self._set_userconfig('token_type',    data['token_type'])
        self._set_userconfig('expires',       timestamp + data['expires_in'])
        self._set_userconfig('refresh_token', data['refresh_token'])

        self.logged_in = True
        self._refresh_user_info()
        self._emit_signal('userconfig_changed')

    def _refresh_access_token(self):
        self.msg.info(self.name, 'Refreshing access token...')
        param = {
            'grant_type': 'refresh_token',
            'client_id': self._client_id,
            'client_secret': self._client_secret,
            'refresh_token': self._get_userconfig('refresh_token'),
        }
        
        # TODO : Where's the refresh endpoint?
        raise NotImplementedError

    def _refresh_user_info(self):
        self.msg.info(self.name, 'Refreshing user details...')
        params = {
                "filter[name]": self.username,
        }
        data = self._request(self.prefix + "/users", get=params)
        json_data = json.loads(data)
        user = json_data['data'][0]

        # Parse user information
        self._set_userconfig('userid', user['id'])
        self._set_userconfig('username', user['attributes']['name'])

    def check_credentials(self):
        """
        Log into Kitsu. If there isn't an acess token, request it, or
        refresh it if necessary.
        """
        timestamp = int(time.time())

        if not self._get_userconfig('access_token'):
            self._request_access_token()
        elif (timestamp+60) > self._get_userconfig('expires'):
            self._refresh_access_token()
        else:
            self.logged_in = True

        #self.auth = response.strip('"')
        #self._set_userconfig('username', self.username)
        #self.logged_in = True
        return True

    def fetch_list(self):
        """Queries the full list from the remote server.
        Returns the list if successful, False otherwise."""
        self.check_credentials()
        self.msg.info(self.name, 'Downloading list...')

        try:
            showlist = dict()
            infolist = list()

            # Get first page and continue from there
            params = {
                "filter[userId]": self._get_userconfig('userid'),
                "include": "media",
                "page[limit]": "500",
            }

            url = "{}/library-entries?{}".format(self.prefix, urllib.parse.urlencode(params))
            i = 1

            while url:
                self.msg.info(self.name, 'Getting page {}...'.format(i))

                data = self._request(url)
                data_json = json.loads(data)

                entries = data_json['data']
                links = data_json['links']

                for entry in entries:
                    showid = int(entry['relationships']['media']['data']['id'])
                    status = entry['attributes']['status']
                    rating = entry['attributes']['rating']
                    
                    showlist[showid] = utils.show()
                    showlist[showid].update({
                        'id': showid,
                        'my_progress': entry['attributes']['progress'],
                        'my_score': float(rating) if rating is not None else 0.0,
                        'my_status': entry['attributes']['status'],
                    })

                medias = data_json['included']
                for media in medias:
                    info = utils.show()
                    info.update({
                        'id': int(media['id']),
                        'title': media['attributes']['canonicalTitle']
                    })

                    infolist.append(info)

                url = links.get('next')
                i += 1

            self._emit_signal('show_info_changed', infolist)

            return showlist
        except urllib.request.HTTPError as e:
            raise utils.APIError("Error getting list.")

    def merge(self, show, info):
        show['title'] = info['title']
        # TODO implement all

    def request_info(self, item_list):
        print("These are missing: " + repr(item_list))
        raise NotImplementedError

    def add_show(self, item):
        """Adds a new show in the server"""
        self.update_show(item)

    def update_show(self, item):
        """Sends a show update to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Updating show %s..." % item['title'])

        # Send the POST data to the Hummingbird API
        values = {'auth_token': self.auth}

        # Update necessary keys
        if 'my_progress' in item.keys():
            values['episodes_watched'] = item['my_progress']
        if 'my_status' in item.keys():
            values['status'] = item['my_status']
        if 'my_score' in item.keys():
            values['sane_rating_update'] = item['my_score']

        try:
            self._request("/libraries/%s" % item['id'], post=values)
        except urllib.request.HTTPError as e:
            raise utils.APIError('Error updating: ' + str(e.code))

    def delete_show(self, item):
        """Sends a show delete to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Deleting show %s..." % item['title'])

        values = {'auth_token': self.auth}
        try:
            self._request("/libraries/%s/remove" % item['id'], post=values)
        except urllib.request.HTTPError as e:
            raise utils.APIError('Error deleting: ' + str(e.code))

    def search(self, query):
        self.msg.info(self.name, "Searching for %s..." % query)

        values = {'query': query}
        try:
            data = self._request("/search/anime", get=values)
            shows = json.loads(data.read().decode('utf-8'))

            infolist = []
            for show in shows:
                info = self._parse_info(show)
                info['my_status'] = 'currently-watching' # TODO : Default to watching; this should be changeable
                infolist.append(info)

            self._emit_signal('show_info_changed', infolist)

            if not infolist:
                raise utils.APIError('No results.')

            return infolist
        except urllib.request.HTTPError as e:
            raise utils.APIError('Error searching: ' + str(e.code))

    def _str2date(self, string):
        if string != '0000-00-00':
            try:
                return datetime.datetime.strptime(string, "%Y-%m-%d")
            except:
                return None # Ignore date if it's invalid
        else:
            return None

    def _parse_info(self, show):
        info = utils.show()
        alt_titles = []
        if show['alternate_title'] is not None:
            alt_titles.append(show['alternate_title'])
        info.update({
            'id': show['id'],
            'title': show['title'] or show['alternate_title'] or "",
            'status': self.status_translate[show['status']],
            'image': show['cover_image'],
            'url': show['url'],
            'aliases': alt_titles,
            'extra': [
                ('Alternate title', show['alternate_title']),
                ('Show type',       show['show_type']),
                ('Synopsis',        show['synopsis']),
                ('Status',          show['status']),
            ]
        })
        return info

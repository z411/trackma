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
    API class to communicate with Kitsu
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
    default_statuses = ['current', 'completed', 'on_hold', 'dropped', 'planned']
    default_statuses_dict = {
            'current': 'Watching',
            'completed': 'Completed',
            'on_hold': 'On Hold',
            'dropped': 'Dropped',
            'planned': 'Plan to Watch'
            }

    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': True,
        'statuses_start': ['current'],
        'statuses_finish': ['completed'],
        'statuses_library': ['current', 'on_hold', 'planned'],
        'statuses': default_statuses,
        'statuses_dict': default_statuses_dict,
        'score_max': 5,
        'score_step': 0.5,
    }
    mediatypes['manga'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': False,
        'statuses_start': ['current'],
        'statuses_finish': ['completed'],
        'statuses': default_statuses,
        'statuses_dict': default_statuses_dict,
        'score_max': 5,
        'score_step': 0.5,
    }
    mediatypes['drama'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': True,
        'statuses_start': ['current'],
        'statuses_finish': ['completed'],
        'statuses': default_statuses,
        'statuses_dict': default_statuses_dict,
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
            ('Accept',          'application/vnd.api+json'),
            ('Accept-Encoding', 'gzip'),
            ('Accept-Charset',  'utf-8'),
        ]

    def _request(self, method, url, get=None, post=None, body=None, auth=False):
        content_type = None

        if get:
            url += "?%s" % urllib.parse.urlencode(get)
        if post:
            post = urllib.parse.urlencode(post).encode('utf-8')
            content_type = 'application/x-www-form-urlencoded'
        if body:
            post = body.encode('utf-8')
            content_type = 'application/vnd.api+json'

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
                api_error = self._parse_errors(e)
                if api_error:
                    raise utils.APIError("API error: %s" % api_error)
                else:
                    raise utils.APIError("Connection error: %s" % e)
        except urllib.request.URLError as e:
            raise utils.APIError("URL error: %s" % e)
        except socket.timeout:
            raise utils.APIError("Operation timed out.")

    def _parse_errors(self, e):
        try:
            data = json.loads(e.read().decode('utf-8'))
            errors = ""
            for error in data['errors']:
                errors += "{}: {}".format(error['code'], error['detail'])

            return errors
        except:
            return None

    def _request_access_token(self, refresh=False):
        params = {
            'client_id':     self._client_id,
            'client_secret': self._client_secret,
        }

        if refresh:
            self.msg.info(self.name, 'Refreshing access token...')

            params['grant_type']    = 'refresh_token'
            params['refresh_token'] = self._get_userconfig('refresh_token')
        else:
            self.msg.info(self.name, 'Requesting access token...')

            params['grant_type'] = 'password'
            params['username']   = self.username
            params['password']   = self.password

        response = self._request('POST', self.url + '/oauth/token', post=params)
        data = json.loads(response)

        timestamp = int(time.time())

        self._set_userconfig('access_token',  data['access_token'])
        self._set_userconfig('token_type',    data['token_type'])
        self._set_userconfig('expires',       timestamp + data['expires_in'])
        self._set_userconfig('refresh_token', data['refresh_token'])

        self.logged_in = True
        self._refresh_user_info()
        self._emit_signal('userconfig_changed')

    def _refresh_user_info(self):
        self.msg.info(self.name, 'Refreshing user details...')
        params = {
                "filter[self]": 'true',
        }
        data = self._request('GET', self.prefix + "/users", get=params, auth=True)
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
            self._request_access_token(False)
        elif (timestamp+60) > self._get_userconfig('expires'):
            self._request_access_token(True)
        else:
            self.logged_in = True

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
                "filter[user_id]": self._get_userconfig('userid'),
                "filter[kind]": self.mediatype,
                #"include": self.mediatype, # TODO : This returns a 500 for some reason.
                "include": "media",
                # TODO : List for manga should be different
                "fields[anime]": "id,slug,canonicalTitle,titles,episodeCount,synopsis,subtype,posterImage,startDate,endDate",
                "page[limit]": "250",
            }

            url = "{}/library-entries?{}".format(self.prefix, urllib.parse.urlencode(params))
            i = 1

            while url:
                self.msg.info(self.name, 'Getting page {}...'.format(i))

                data = self._request('GET', url)
                data_json = json.loads(data)

                #print(json.dumps(data_json, sort_keys=True, indent=2))
                #return []

                entries = data_json['data']
                links = data_json['links']

                for entry in entries:
                    # TODO : Including the mediatype returns a 500 for some reason.
                    #showid = int(entry['relationships'][self.mediatype]['data']['id'])
                    showid = int(entry['relationships']['media']['data']['id'])
                    status = entry['attributes']['status']
                    rating = entry['attributes']['rating']

                    showlist[showid] = utils.show()
                    showlist[showid].update({
                        'id': showid,
                        'my_id': entry['id'],
                        'my_progress': entry['attributes']['progress'],
                        'my_score': float(rating) if rating is not None else 0.0,
                        'my_status': entry['attributes']['status'],
                        'my_start_date': self._iso2date(entry['attributes']['startedAt']),
                        'my_finish_date': self._iso2date(entry['attributes']['finishedAt']),
                    })

                if 'included' in data_json:
                    medias = data_json['included']
                    for media in medias:
                        info = self._parse_info(media)
                        infolist.append(info)

                    self._emit_signal('show_info_changed', infolist)

                url = links.get('next')
                i += 1

            return showlist
        except urllib.request.HTTPError as e:
            raise utils.APIError("Error getting list.")

    def merge(self, show, info):
        show['title']   = info['title']
        show['aliases'] = info['aliases']
        show['url']     = info['url']
        show['total']   = info['total']
        show['image']   = info['image']

        show['image_thumb'] = info['image_thumb']

        show['start_date'] = info['start_date']
        show['end_date']   = info['end_date']
        show['status']     = info['status']

    def request_info(self, item_list):
        print("These are missing: " + repr(item_list))
        # TODO implement
        raise NotImplementedError

    def add_show(self, item):
        """Adds a new show in the server"""
        self.check_credentials()
        self.msg.info(self.name, "Adding show %s..." % item['title'])

        data = self._build_data(item)

        try:
            data = self._request('POST', self.prefix + "/library-entries", body=data, auth=True)

            data_json = json.loads(data)
            return int(data_json['data']['id'])
        except urllib.request.HTTPError as e:
            raise utils.APIError('Error adding: ' + str(e.code))

    def update_show(self, item):
        """Sends a show update to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Updating show %s..." % item['title'])

        data = self._build_data(item)

        try:
            self._request('PATCH', self.prefix + "/library-entries/%s" % item['my_id'], body=data, auth=True)
        except urllib.request.HTTPError as e:
            raise utils.APIError('Error updating: ' + str(e.code))

    def delete_show(self, item):
        """Sends a show delete to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Deleting show %s..." % item['title'])

        try:
            self._request('DELETE', self.prefix + "/library-entries/%s" % item['my_id'], auth=True)
        except urllib.request.HTTPError as e:
            raise utils.APIError('Error deleting: ' + str(e.code))

    def search(self, query, method):
        self.msg.info(self.name, "Searching for %s..." % query)

        values = {
                  "filter[text]": query,
                  "page[limit]": 20,
                 }

        try:
            data = self._request('GET', self.prefix + "/" + self.mediatype, get=values)
            shows = json.loads(data)

            infolist = []
            for media in shows['data']:
                info = self._parse_info(media)
                infolist.append(info)

            self._emit_signal('show_info_changed', infolist)

            if not infolist:
                raise utils.APIError('No results.')

            return infolist
        except urllib.request.HTTPError as e:
            raise utils.APIError('Error searching: ' + str(e.code))

    def _build_data(self, item):
        values = {'data': {
            'type': 'libraryEntries',
            'attributes': {},
            'relationships': {
                'media': {
                    'data': {
                        'type': self.mediatype,
                        'id': item['id'],
                        }
                    },
                'user': {
                    'data': {
                        'type': 'users',
                        'id': self._get_userconfig('userid'),
                        }
                    },
                }
            }
        }

        # Update necessary keys
        if item['my_id']:
            values['data']['id'] = str(item['my_id'])
        if 'my_progress' in item:
            values['data']['attributes']['progress'] = item['my_progress']
        if 'my_status' in item:
            values['data']['attributes']['status'] = item['my_status']
        if 'my_score' in item:
            values['data']['attributes']['rating'] = item['my_score'] or None

        return json.dumps(values)

    def _str2date(self, string):
        if string is None:
            return None

        try:
            return datetime.datetime.strptime(string, "%Y-%m-%d")
        except:
            self.msg.debug(self.name, 'Invalid date {}'.format(string))
            return None # Ignore date if it's invalid

    def _iso2date(self, string):
        if string is None:
            return None

        try:
            return datetime.datetime.strptime(string, "%Y-%m-%dT%H:%M:%S.%fZ").date()
        except:
            self.msg.debug(self.name, 'Invalid date {}'.format(string))
            return None # Ignore date if it's invalid            

    def _guess_status(self, start_date, end_date):
        # Try to guess show status by checking start and end dates
        now = datetime.datetime.now()

        if end_date and end_date < now:
            return utils.STATUS_FINISHED

        if start_date:
            if start_date > now:
                return utils.STATUS_NOTYET
            else:
                return utils.STATUS_AIRING

        # Safe to assume dates haven't even been announced yet
        return utils.STATUS_NOTYET

    def _parse_info(self, media):
        info = utils.show()
        attr = media['attributes']

        #print(json.dumps(media, indent=2))
        #raise NotImplementedError

        if media['type'] == 'anime':
            total = attr['episodeCount']
        elif media['type'] == 'manga':
            total = attr['chapterCount']
        elif media['type'] == 'drama':
            total = attr['episodeCount'] # TODO Unconfirmed

        info.update({
            'id': int(media['id']),
            # TODO : Some shows actually don't have a canonicalTitle; this should be fixed in the future.
            # For now I'm just picking the romaji title in these cases.
            'title':       attr['titles'].get('en_jp') or attr.get('canonicalTitle') or attr['titles'].get('en'),
            'total':       total or 0,
            'image':       attr['posterImage'] and attr['posterImage']['small'],
            'image_thumb': attr['posterImage'] and attr['posterImage']['tiny'],
            'start_date':  self._str2date(attr['startDate']),
            'end_date':    self._str2date(attr['endDate']),
            'url': "https://kitsu.io/{}/{}".format(self.mediatype, attr['slug']),
            'aliases':     list(filter(None, attr['titles'].values())),
            'extra': [
                ('Synopsis', attr['synopsis']),
                ('Type',     attr['subtype']),
            ]
        })

        # WORKAROUND: Shows with 1 episode (TVs, SPs, OVAs) end the same day they start
        if total == 1:
            info['end_date'] = info['start_date']

        # WORKAROUND: Since there's no way to get the formal status,
        # use the helper function to guess it.
        info['status'] = self._guess_status(info['start_date'], info['end_date'])

        return info

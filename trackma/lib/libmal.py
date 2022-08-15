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
import gzip
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from trackma import utils
from trackma.lib.lib import lib


class libmal(lib):
    """
    API class to communicate with MyAnimeList (new API)

    Website: https://myanimelist.net
    """
    name = 'libmal'
    msg = None
    logged_in = False

    api_info = {'name': 'MyAnimeList', 'shortname': 'mal',
                'version': 3, 'merge': False}
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
        'statuses_start': ['watching'],
        'statuses_finish': ['completed'],
        'statuses_library': ['watching', 'on_hold', 'plan_to_watch'],
        'statuses':  ['watching', 'completed', 'on_hold', 'dropped', 'plan_to_watch'],
        'statuses_dict': {
            'watching': 'Watching',
            'completed': 'Completed',
            'on_hold': 'On hold',
            'dropped': 'Dropped',
            'plan_to_watch': 'Plan to Watch'
        },
        'score_max': 10,
        'score_step': 1,
        'search_methods': [utils.SearchMethod.KW, utils.SearchMethod.SEASON],
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
        'statuses_start': ['reading'],
        'statuses_finish': ['completed'],
        'statuses':  ['reading', 'completed', 'on_hold', 'dropped', 'plan_to_read'],
        'statuses_dict': {
            'reading': 'Reading',
            'completed': 'Completed',
            'on_hold': 'On hold',
            'dropped': 'Dropped',
            'plan_to_read': 'Plan to Read'
        },
        'score_max': 10,
        'score_step': 1,
        'search_methods': [utils.SearchMethod.KW],
    }
    default_mediatype = 'anime'

    type_translate = {
        'tv': utils.Type.TV,
        'movie': utils.Type.MOVIE,
        'special': utils.Type.SP,
        'ova': utils.Type.OVA,
        'ona': utils.Type.OVA,
        'music': utils.Type.OTHER,
        'unknown': utils.Type.UNKNOWN,
        'manga': utils.Type.MANGA,
        'novel': utils.Type.NOVEL,
        'light_novel': utils.Type.NOVEL,
        'manhwa': utils.Type.MANGA,
        'manhua': utils.Type.MANGA,
        'one_shot': utils.Type.ONE_SHOT,
        'doujinshi': utils.Type.MANGA,
    }
    
    status_translate = {
        'currently_airing': utils.Status.AIRING,
        'finished_airing': utils.Status.FINISHED,
        'not_yet_aired': utils.Status.NOTYET,
    }
    
    season_translate = {
        utils.Season.WINTER: 'winter',
        utils.Season.SPRING: 'spring',
        utils.Season.SUMMER: 'summer',
        utils.Season.FALL: 'fall',
    }

    # Supported signals for the data handler
    signals = {'show_info_changed': None, }

    auth_url = "https://myanimelist.net/v1/oauth2/token"
    query_url = "https://api.myanimelist.net/v2"
    client_id = "32c510ab2f47a1048a8dd24de266dc0c"
    user_agent = 'Trackma/{}'.format(utils.VERSION)
    
    library_page_limit = 1000
    search_page_limit = 100
    season_page_limit = 500

    def __init__(self, messenger, account, userconfig):
        super(libmal, self).__init__(messenger, account, userconfig)

        self.pin = account['password'].strip()
        
        if 'extra' not in account or 'code_verifier' not in account['extra']:
            raise utils.APIFatal(
                "This account seems to be using the old MyAnimeList API."
                "Please re-create and authorize the account.")
        
        self.code_verifier = account['extra']['code_verifier']
        self.userid = self._get_userconfig('userid')
        
        if self.mediatype == 'manga':
            self.total_str = "num_chapters"
            self.watched_str = self.watched_send_str = "num_chapters_read"
        else:
            self.total_str = "num_episodes"
            self.watched_str = "num_episodes_watched"
            self.watched_send_str = "num_watched_episodes"  # Please fix this upstream...

        self.opener = urllib.request.build_opener()
        self.opener.addheaders = [
            ('User-Agent',      self.user_agent),
            ('Accept',          'application/json'),
            ('Accept-Encoding', 'gzip'),
            ('Accept-Charset',  'utf-8'),
        ]

    def _request(self, method, url, get=None, post=None, auth=False):
        content_type = None

        if get:
            url += "?%s" % urllib.parse.urlencode(get)
        if post:
            post = urllib.parse.urlencode(post).encode('utf-8')
            content_type = 'application/x-www-form-urlencoded'
            self.msg.debug("POST data: " + str(post))

        self.msg.debug(method + " URL: " + url)
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

            if response.info().get('content-encoding') == 'gzip':
                response = gzip.GzipFile(fileobj=response).read().decode('utf-8')
            else:
                response = response.read().decode('utf-8')
            
            return json.loads(response)
        except urllib.error.HTTPError as e:
            raise utils.APIError("Connection error: %s" % e)
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
        }

        if refresh:
            self.msg.info('Refreshing access token...')

            params['grant_type'] = 'refresh_token'
            params['refresh_token'] = self._get_userconfig('refresh_token')
        else:
            self.msg.info('Requesting access token...')

            params['code'] = self.pin
            params['code_verifier'] = self.code_verifier
            params['grant_type'] = 'authorization_code'
            
        data = self._request('POST', self.auth_url, post=params)

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
            try:
                self._request_access_token(True)
            except utils.APIError:
                self._request_access_token(False)
        else:
            self.logged_in = True

        # if not self.userid:
        #     self._refresh_user_info()

        return True

    def fetch_list(self):
        self.check_credentials()
        shows = {}
        
        fields = 'id,alternative_titles,title,start_date,main_picture,status,' + self.total_str
        listfields = 'score,status,start_date,finish_date,' + self.watched_str
        params = {
            'fields': '%s,list_status{%s}' % (fields, listfields),
            'limit': self.library_page_limit,
            'nsfw': 'true'
        }
        
        url = "{}/users/@me/{}list?{}".format(self.query_url, self.mediatype, urllib.parse.urlencode(params))
        i = 1
        
        while url:
            self.msg.info('Downloading list (page %d)...' % i)
            data = self._request('GET', url, auth=True)
            for item in data['data']:
                showid = item['node']['id']
                shows[showid] = utils.show()
                shows[showid].update({
                    'id': showid,
                    'title': item['node']['title'],
                    'url': "https://myanimelist.net/%s/%d" % (self.mediatype, showid),
                    'aliases': self._get_aliases(item['node']),
                    'image': item['node'].get('main_picture', {}).get('large'),
                    'image_thumb': item['node'].get('main_picture', {}).get('medium'),
                    'total': item['node'][self.total_str],
                    'status': self._translate_status(item['node']['status']),
                    'start_date': self._str2date(item['node'].get('start_date')),
                    'my_progress': item['list_status'][self.watched_str],
                    'my_score': item['list_status']['score'],
                    'my_status': item['list_status']['status'],
                    'my_start_date': self._str2date(item['list_status'].get('start_date')),
                    'my_finish_date': self._str2date(item['list_status'].get('finish_date')),
                })
            
            url = data['paging'].get('next')
            i += 1

        return shows

    def add_show(self, item):
        self.check_credentials()
        self.msg.info("Adding item %s..." % item['title'])
        self._update_entry(item)

    def update_show(self, item):
        self.check_credentials()
        self.msg.info("Updating item %s..." % item['title'])
        self._update_entry(item)
    
    def delete_show(self, item):
        self.check_credentials()
        self.msg.info("Deleting item %s..." % item['title'])
        data = self._request('DELETE', self.query_url + '/%s/%d/my_list_status' % (self.mediatype, item['id']), auth=True)
    
    def search(self, criteria, method):
        self.check_credentials()
        self.msg.info("Searching for {}...".format(criteria))
        
        fields = 'alternative_titles,end_date,genres,id,main_picture,mean,media_type,' + self.total_str + ',popularity,rating,start_date,status,studios,synopsis,title'
        params = {'fields': fields, 'nsfw': 'true'}
        
        if method == utils.SearchMethod.KW:
            url = '/%s' % self.mediatype
            params['q'] = criteria
            params['limit'] = self.search_page_limit
        elif method == utils.SearchMethod.SEASON:
            season, season_year = criteria            

            url = '/%s/season/%d/%s' % (self.mediatype, season_year, self.season_translate[season])
            params['limit'] = self.season_page_limit
        else:
            raise utils.APIError("Invalid search method.")
        
        results = []
        data = self._request('GET', self.query_url + url, get=params, auth=True)
        for item in data['data']:
            results.append(self._parse_info(item['node']))
        
        self._emit_signal('show_info_changed', results)
        return results
        
    def request_info(self, itemlist):
        self.check_credentials()
        infolist = []
        
        fields = 'alternative_titles,end_date,genres,id,main_picture,mean,media_type,' + self.total_str + ',popularity,rating,start_date,status,studios,synopsis,title'
        params = {'fields': fields, 'nsfw': 'true'}
        for item in itemlist:
            data = self._request('GET', self.query_url + '/%s/%d' % (self.mediatype, item['id']), get=params, auth=True)
            infolist.append(self._parse_info(data))
        
        self._emit_signal('show_info_changed', infolist)
        return infolist

    def _update_entry(self, item):
        values = {}
        if 'my_progress' in item:
            values[self.watched_send_str] = item['my_progress']
        if 'my_status' in item:
            values['status'] = item['my_status']
        if 'my_score' in item:
            values['score'] = item['my_score']
        if 'my_start_date' in item:
            values['start_date'] = item['my_start_date'] or ""
        if 'my_finish_date' in item:
            values['finish_date'] = item['my_finish_date'] or ""

        data = self._request('PATCH', self.query_url + '/%s/%d/my_list_status' % (self.mediatype, item['id']), post=values, auth=True)

    def _get_aliases(self, item):
        aliases = [item['alternative_titles']['en'], item['alternative_titles']['ja']] + item['alternative_titles']['synonyms']
        
        return aliases
    
    def _parse_info(self, item):
        info = utils.show()
        showid = item['id']
        
        info.update({
            'id': showid,
            'title': item['title'],
            'url': "https://myanimelist.net/%s/%d" % (self.mediatype, showid),
            'aliases': self._get_aliases(item),
            'type': self.type_translate[item['media_type']],
            'total': item[self.total_str],
            'status': self._translate_status(item['status']),
            'image': item.get('main_picture', {}).get('large'),
            'start_date': self._str2date(item.get('start_date')),
            'end_date': self._str2date(item.get('end_date')),
            'extra': [
                ('English',         item['alternative_titles'].get('en')),
                ('Japanese',        item['alternative_titles'].get('ja')),
                ('Synonyms',        item['alternative_titles'].get('synonyms')),
                ('Synopsis',        item.get('synopsis')),
                ('Type',            item.get('media_type')),
                ('Mean score',   item.get('mean')),
                ('Status',          self._translate_status(item['status'])),
            ]
        })
        
        return info
        
    def _translate_status(self, orig_status):
        return self.status_translate.get(orig_status, utils.Status.UNKNOWN)

    def _str2date(self, string):
        if string is None:
            return None

        try:
            return datetime.datetime.strptime(string, "%Y-%m-%d")
        except Exception:
            self.msg.debug('Invalid date {}'.format(string))
            return None  # Ignore date if it's invalid

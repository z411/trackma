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

    api_info = { 'name': 'Anilist', 'shortname': 'anilist', 'version': '2.0', 'merge': False }
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
        'statuses':  ['Watching', 'Completed', 'Paused', 'Dropped', 'Planning'],
        'statuses_dict': {
            'Watching': 'Watching',
            'Completed': 'Completed',
            'Paused': 'On Hold',
            'Dropped': 'Dropped',
            'Planning': 'Plan to Watch'
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
        'statuses':  ['reading', 'completed', 'on-hold', 'dropped', 'plan to read'],  # TODO
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

    release_formats = ['TV', 'TV_SHORT', 'MOVIE', 'SPECIAL', 'OVA', 'ONA', 'MUSIC', 'MANGA', 'NOVEL', 'ONE_SHOT']

    # Supported signals for the data handler
    signals = { 'show_info_changed': None, }

    auth_url = 'https://anilist.co/api/v2/'
    query_url = 'https://graphql.anilist.co'
    client_id = '524'  # Trackma v2 testing
    _client_secret = 'mBxS3BNBtVHdluPC00KenhVKAgwm5NSem6sIfxua'
    #url = 'https://anilist.co/api/'
    #client_id = "z411-gdjc3"
    #_client_secret = "MyzwuYoMqPPglXwCTcexG1i"

    def __init__(self, messenger, account, userconfig):
        """Initializes the API"""
        super(libanilist, self).__init__(messenger, account, userconfig)

        self.pin = account['password'].strip()
        self.userid = userconfig['userid']

        if len(self.pin) == 40:  # Old pins were 40 digits, new ones seem to be 654 digits
            raise utils.APIFatal("This appears to be a V1 API PIN. You need a V2 API PIN to continue using Anilist.")
        elif len(self.pin) != 654:
            raise utils.APIFatal("Invalid PIN.")

        if self.mediatype == 'manga':
            self.total_str = "chapters"
            self.watched_str = "chapters_read"
        else:
            self.total_str = "episodes"
            self.watched_str = "episodes_watched"
        self.status_translate = {
            'RELEASING': utils.STATUS_AIRING,
            'FINISHED': utils.STATUS_FINISHED,
            'NOT_YET_RELEASED': utils.STATUS_NOTYET,
            'CANCELLED': utils.STATUS_CANCELLED,
        }

        #handler=urllib.request.HTTPHandler(debuglevel=1)
        #self.opener = urllib.request.build_opener(handler)
        self.opener = urllib.request.build_opener()
        self.opener.addheaders = [('User-agent', 'Trackma/0.1')]

    def _do_request(self, request):
        try:
            response = self.opener.open(request, timeout=10)
            return json.loads(response.read().decode('utf-8'))
        except urllib.request.HTTPError as e:
            if e.code == 400:
                raise utils.APIError("Invalid PIN. It is either probably expired or meant for another application. %s" % e)
            else:
                raise utils.APIError("Connection error: %s, %s" % (e, request.full_url))
        except urllib.request.URLError as e:
            raise utils.APIError("Connection error: %s, %s" % (e, request.full_url))
        except socket.timeout:
            raise utils.APIError("Connection timed out.")

    def _auth_request(self, method, url, get=None, post=None, auth=False):
        if get:
            url = "{}?{}".format(url, urllib.parse.urlencode(get))
        if post:
            post = urllib.parse.urlencode(post).encode('utf-8')

        request = urllib.request.Request(self.auth_url + url, post)
        request.get_method = lambda: method

        if auth:
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            request.add_header('Authorization', '{0} {1}'.format(
                self._get_userconfig('token_type').capitalize(),
                self._get_userconfig('access_token'),
            ))

        return self._do_request(request)

    def _request(self, query, variables=None, auth=True):
        """Submits a GraphQL API request"""
        if variables is not None:
          post = json.dumps({'query': query, 'variables': variables}, ensure_ascii=False).encode('utf-8')
        else:
          post = json.dumps({'query': query}, ensure_ascii=False).encode('utf-8')
        request = urllib.request.Request(self.query_url, post)
        request.add_header('Content-Type', 'application/json')
        request.add_header('Accept', 'application/json')

        if auth:
            request.add_header('Authorization', '{0} {1}'.format(
                self._get_userconfig('token_type').capitalize(),
                self._get_userconfig('access_token'),
            ))

        return self._do_request(request)

    def _request_access_token(self):
        self.msg.info(self.name, 'Requesting access token...')
        param = {
            'grant_type': 'authorization_code',
            'client_id':  self.client_id,
            'client_secret': self._client_secret,
            'code': self.pin,
        }
        data = self._auth_request('POST', 'oauth/token', post=param)

        self._set_userconfig('access_token', data['access_token'])
        self._set_userconfig('token_type', data['token_type'])
        self._set_userconfig('expires', data['expires_in']+int(time.time()))
        self._set_userconfig('refresh_token', data['refresh_token'])

        self.logged_in = True
        self._refresh_user_info()
        self._emit_signal('userconfig_changed')

    def _refresh_user_info(self):
        self.msg.info(self.name, 'Refreshing user details...')
        query = '{Viewer{ id name avatar{large} options{titleLanguage displayAdultContent} mediaListOptions{scoreFormat} }}'
        data = self._request(query, auth=True)['data']['Viewer']

        self._set_userconfig('userid', data['id'])
        self._set_userconfig('username', data['name'])

        self.userid = data['id']

    def check_credentials(self):
        """
        Log into Anilist. Since it uses OAuth, we either request an access token
        or refresh the current one. If neither is necessary, just continue.
        """
        timestamp = int(time.time())
        if not self._get_userconfig('access_token'):
            self._request_access_token()
        elif timestamp > self._get_userconfig('expires'):
            self._request_access_token()
        else:
            self.logged_in = True
        return True

    def fetch_list(self):
        self.check_credentials()
        self.msg.info(self.name, 'Downloading list...')

        query = '''query ($id: Int!, $listType: MediaType) {
  MediaListCollection (userId: $id, type: $listType) {
    lists {
      name
      isCustomList
      isSplitCompletedList
      entries {
        ... mediaListEntry
      }
    }
    user {
      id
      name
      avatar {
        large
      }
      mediaListOptions {
        scoreFormat
        rowOrder
      }
    }
  }
}

fragment mediaListEntry on MediaList {
  id
  score
  scoreRaw: score (format: POINT_100)
  progress
  progressVolumes
  repeat
  private
  notes
  hiddenFromStatusLists
  startedAt { year month day }
  completedAt { year month day }
  updatedAt
  createdAt
  media {
    id
    title { userPreferred romaji english native }
    coverImage { large medium }
    format
    status
    chapters episodes
    nextAiringEpisode { airingAt episode }
    startDate { year month day }
    endDate { year month day }
    siteUrl
  }
}'''
        variables = {'id': self.userid, 'listType': self.mediatype.upper()}
        data = self._request(query, variables)['data']['MediaListCollection']

        showlist = {}

        if not data['lists']:
            # No lists returned so no need to continue
            return showlist

        for remotelist in data['lists']:
            my_status = remotelist['name']
            if my_status not in self.media_info()['statuses']:
                continue
            if remotelist['isCustomList']:
                continue  # Maybe do something with this later
            if remotelist['isSplitCompletedList']:
                continue  # Maybe do something with this later
            for item in remotelist['entries']:
                show = utils.show()
                media = item['media']
                showid = media['id']
                showdata = {
                    'id': showid,
                    'title': media['title']['userPreferred'],
                    'aliases': [media['title']['romaji'], media['title']['english'], media['title']['native']],
                    'type': media['format'],  # Need to reformat output
                    'status': self.status_translate[media['status']],
                    'my_progress': self._c(item['progress']),
                    'my_status': my_status,
                    'my_score': self._c(item['score']),
                    'total': self._c(media[self.total_str]),
                    'image': media['coverImage']['large'],
                    'image_thumb': media['coverImage']['medium'],
                    'url': media['siteUrl'],
                    'start_date': self._dict2date(media['startDate']),
                    'end_date': self._dict2date(media['endDate']),
                    'my_start_date': self._dict2date(item['startedAt']),
                    'my_finish_date': self._dict2date(item['completedAt']),
                }
                if media['nextAiringEpisode']:
                  showdata['next_ep_number'] = media['nextAiringEpisode']['episode']
                  showdata['next_ep_time'] = media['nextAiringEpisode']['airingAt']
                show.update({k:v for k,v in showdata.items() if v})
                showlist[showid] = show
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

        query = '''query ($query: String, $type: MediaType) {
  Page {
    media(search: $query, type: $type) {
      id
      title { userPreferred romaji english native }
      coverImage { medium large }
      format
      averageScore
      popularity
      chapters episodes
      season
      status
      isAdult
      startDate { year month day }
      endDate { year month day }
      siteUrl
      mediaListEntry { status progress score }
    }
  }
}'''
        variables = {'query': urllib.parse.quote_plus(criteria), 'listType': self.mediatype.upper()}
        data = self._request(query, variables)['data']['Page']['media']

        showlist = []
        for media in data:
            show = utils.show()
            showid = media['id']
            showdata = {
                'id': showid,
                'title': media['title']['userPreferred'],
                'aliases': [media['title']['romaji'], media['title']['english'], media['title']['native']],
                'type': media['format'],  # Need to reformat output
                'status': self.status_translate[media['status']],
                'total': self._c(media[self.total_str]),
                'image': media['coverImage']['large'],
                'image_thumb': media['coverImage']['medium'],
                'url': media['siteUrl'],
            }
            if media['mediaListEntry']:
                showdata['my_progress'] = self._c(media['mediaListEntry']['progress'])
                showdata['my_status'] = media['mediaListEntry']['status']
                showdata['my_score'] = self._c(media['mediaListEntry']['score'])
            show.update({k:v for k,v in showdata.items() if v})
            showlist.append(show)

        return showlist

    def request_info(self, itemlist):
        self.check_credentials()
        infolist = []

        query = '''query ($id: Int!, $type: MediaType) {
  Media(id: $id, type: $type) {
      id
      title { userPreferred romaji english native }
      coverImage { medium large }
      format
      averageScore
      popularity
      chapters episodes
      season
      status
      isAdult
      startDate { year month day }
      endDate { year month day }
      siteUrl
      mediaListEntry { status progress score }
      description
      genres
      synonyms
      averageScore
  }
}'''

        for show in itemlist:
            variables = {'id': show['id'], 'listType': self.mediatype.upper()}
            data = self._request(query, variables)['data']['Media']
            infolist.append(self._parse_info(data))

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

        query = '''
mutation ($mediaId: Int, $status: MediaListStatus, $score: Float, $progress: Int, $private: Boolean, $notes: String, $hiddenFromStatusLists: Boolean, $startedAt: FuzzyDateInput, $completedAt: FuzzyDateInput) {
  SaveMediaListEntry(mediaId: $mediaId, status: $status, score: $score, progress: $progress, private: $private, notes: $notes, hiddenFromStatusLists: $hiddenFromStatusLists, startedAt: $startedAt, completedAt: $completedAt) {
    id
    status
    score
    progress
    private
    notes
    hiddenFromStatusLists
    startedAt
    completedAt
  }
}'''

        data = self._request(method, "{}list".format(self.mediatype), post=values, auth=True)
        return True

    def _parse_info(self, item):
        info = utils.show()
        showid = item['id']
        info.update({
            'id': showid,
            'title': item['title']['userPreferred'],
            'status': self.status_translate[item['status']],
            'image': item['coverImage']['large'],
            'url': item['siteUrl'],
            'start_date': self._dict2date(item.get('startDate')),
            'end_date': self._dict2date(item.get('endDate')),
            'extra': [
                ('English',         item['title'].get('english')),
                ('Romaji',          item['title'].get('romaji')),
                ('Japanese',        item['title'].get('native')),
                ('Synonyms',        item['title'].get('synonyms')),
                #('Classification',  item.get('classification')),
                ('Genres',          item.get('genres')),
                ('Synopsis',        item.get('description')),
                ('Type',            item.get('format')),
                ('Average score',   item.get('averageScore')),
                ('Status',          self.status_translate[item['status']]),
                #('Start Date',      item.get('start_date')),
                #('End Date',        item.get('end_date')),
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

    def _dict2date(self, item):
        if not item:
            return None
        try:
            return datetime.date(item['year'], item['month'], item['day'])
        except (TypeError, ValueError):
            return None


    def _c(self, s):
        if s is None:
            return 0
        else:
            return s


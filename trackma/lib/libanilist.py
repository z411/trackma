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

    api_info = { 'name': 'Anilist', 'shortname': 'anilist', 'version': '2.1', 'merge': False }
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
        'score_max': 100,
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
            'CURRENT': 'Watching',
            'COMPLETED': 'Completed',
            'REPEATING': 'Rewatching',
            'PAUSED': 'Paused',
            'DROPPED': 'Dropped',
            'PLANNING': 'Plan to Read'
        },
        'score_max': 100,
        'score_step': 1,
        'search_methods': [utils.SEARCH_METHOD_KW],
    }
    default_mediatype = 'anime'

    score_types = {
        'POINT_100': (100, 1),
        'POINT_10_DECIMAL': (10, 0.1),
        'POINT_10': (10, 1),
        'POINT_5': (5, 1),
        'POINT_3': (3, 1),
    }

    type_translate = {
        'TV': utils.TYPE_TV,
        'TV_SHORT': utils.TYPE_TV,
        'MOVIE': utils.TYPE_MOVIE,
        'SPECIAL': utils.TYPE_SP,
        'OVA': utils.TYPE_OVA,
        'ONA': utils.TYPE_OVA,
        'MUSIC': utils.TYPE_OTHER,
        'MANGA': utils.TYPE_OTHER,
        'NOVEL': utils.TYPE_OTHER,
        'ONE_SHOT': utils.TYPE_OTHER,
    }
    status_translate = {
            'RELEASING': utils.STATUS_AIRING,
            'FINISHED': utils.STATUS_FINISHED,
            'NOT_YET_RELEASED': utils.STATUS_NOTYET,
            'CANCELLED': utils.STATUS_CANCELLED,
    }

    season_translate = {
        utils.SEASON_WINTER: 'WINTER',
        utils.SEASON_SPRING: 'SPRING',
        utils.SEASON_SUMMER: 'SUMMER',
        utils.SEASON_FALL: 'FALL',
    }
 
    # Supported signals for the data handler
    signals = { 'show_info_changed': None, }

    auth_url = "https://anilist.co/api/v2/"
    query_url = "https://graphql.anilist.co"
    client_id = "537"
    _client_secret = "9Hl31gyz2q9xMhhJwLKRA8DAn0pXl9sOHFf6I1YO"
    user_agent = 'Trackma/{}'.format(utils.VERSION)

    def __init__(self, messenger, account, userconfig):
        """Initializes the API"""
        super(libanilist, self).__init__(messenger, account, userconfig)

        self.pin = account['password'].strip()
        self.userid = self._get_userconfig('userid')

        if self.mediatype == 'manga':
            self.total_str = "chapters"
            self.watched_str = "chapters_read"
        else:
            self.total_str = "episodes"
            self.watched_str = "episodes_watched"
       
        # If we already know the scoreFormat of the cached list, apply it now
        self.scoreformat = self._get_userconfig('scoreformat_' + self.mediatype)
        if self.scoreformat:
            self._apply_scoreformat(self.scoreformat)

        self.opener = urllib.request.build_opener()
        self.opener.addheaders = [('User-agent', self.user_agent)]

    def _raw_request(self, method, url, get=None, post=None, jsonpost=None, auth=False):
        if get:
            url = "{}?{}".format(url, urllib.parse.urlencode(get))
        if post:
            post = urllib.parse.urlencode(post).encode('utf-8')
        if jsonpost:
            post = json.dumps(jsonpost, ensure_ascii=False).encode('utf-8')

        request = urllib.request.Request(url, post)
        request.get_method = lambda: method

        request.add_header('Content-Type', 'application/json')
        request.add_header('Accept', 'application/json')

        if auth:
            request.add_header('Authorization', 'Bearer {}'.format(
                self.pin,
            ))

        try:
            response = self.opener.open(request, timeout = 10)
            return json.loads(response.read().decode('utf-8'))
        except urllib.request.HTTPError as e:
            if e.code == 400:
                raise utils.APIError("Invalid request: %s" % e.read())
            else:
                raise utils.APIError("Connection error: %s" % e.read())
        except socket.timeout:
            raise utils.APIError("Connection timed out.")

    def _request(self, query, variables=None):
        if variables:
            data = {'query': query, 'variables': variables}
        else:
            data = {'query': query}

        return self._raw_request('POST', self.query_url, jsonpost=data, auth=True)

    def check_credentials(self):
        if len(self.pin) == 40:  # Old pins were 40 digits, new ones seem to be 654 digits
            raise utils.APIFatal("This appears to be a V1 API PIN. You need a V2 API PIN to continue using AniList."
                                 " Please re-authorize or re-create your AniList account.")

        if not self.userid:
            self._refresh_user_info()

        return True

    def _refresh_user_info(self):
        self.msg.info(self.name, 'Refreshing user details...')
        query = '{Viewer{ id name avatar{large} options{titleLanguage displayAdultContent} mediaListOptions{scoreFormat} }}'
        data = self._request(query)['data']['Viewer']

        self._set_userconfig('userid', data['id'])
        self._set_userconfig('username', data['name'])
        self._emit_signal('userconfig_changed')

        self.userid = data['id']

    def fetch_list(self):
        self.check_credentials()
        self.msg.info(self.name, 'Downloading list...')

        query = '''query ($id: Int!, $listType: MediaType) {
  MediaListCollection (userId: $id, type: $listType) {
    lists {
      name
      isCustomList
      status
      entries {
        ... mediaListEntry
      }
    }
    user {
      mediaListOptions {
        scoreFormat
      }
    }
  }
}

fragment mediaListEntry on MediaList {
  id
  score
  progress
  startedAt { year month day }
  completedAt { year month day }
  media {
    id
    title { userPreferred romaji english native }
    synonyms
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

        # Handle different score formats provided by Anilist
        self.scoreformat = data['user']['mediaListOptions']['scoreFormat']
        self._apply_scoreformat(self.scoreformat)
        
        self._set_userconfig('scoreformat_' + self.mediatype, self.scoreformat)
        self._emit_signal('userconfig_changed')

        for remotelist in data['lists']:
            my_status = remotelist['status']

            if my_status not in self.media_info()['statuses']:
                continue
            if remotelist['isCustomList']:
                continue  # Maybe do something with this later
            for item in remotelist['entries']:
                show = utils.show()
                media = item['media']
                showid = media['id']
                showdata = {
                    'my_id': item['id'],
                    'id': showid,
                    'title': media['title']['userPreferred'],
                    'aliases': self._get_aliases(media),
                    'type': self.type_translate[media['format']],
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
                  showdata['next_ep_time'] = self._int2date(media['nextAiringEpisode']['airingAt'])
                show.update({k:v for k,v in showdata.items() if v})
                showlist[showid] = show
        return showlist

    args_SaveMediaListEntry = {
        'id': 'Int',                         # The list entry id, required for updating
        'mediaId': 'Int',                    # The id of the media the entry is of
        'status': 'MediaListStatus',         # The watching/reading status
        'scoreRaw': 'Int',                   # The score of the media in 100 point
        'progress': 'Int',                   # The amount of episodes/chapters consumed by the user
        'startedAt': 'FuzzyDateInput',       # When the entry was started by the user
        'completedAt': 'FuzzyDateInput',     # When the entry was completed by the user
    }
    def _update_entry(self, item):
        """
        New entries will lack a list entry id, while updates will include one.
        In the case of a new entry, we want to record the new id.
        """
        values = { 'mediaId': item['id'] }
        if 'my_id' in item and item['my_id']:
            values['id'] = item['my_id']
        if 'my_progress' in item:
            values['progress'] = item['my_progress']
        if 'my_status' in item:
            values['status'] = item['my_status']
        if 'my_score' in item:
            values['scoreRaw'] = self._score2raw(item['my_score'])
        if 'my_start_date' in item:
            values['startedAt'] = self._date2dict(item['my_start_date'])
        if 'my_finish_date' in item:
            values['completedAt'] = self._date2dict(item['my_finish_date'])

        vars_defn = ', '.join(['${}: {}'.format(k, self.args_SaveMediaListEntry[k]) for k in values.keys()])
        subs_defn = ', '.join(['{0}: ${0}'.format(k) for k in values.keys()])
        query = 'mutation ({0}) {{ SaveMediaListEntry({1}) {{id}} }}'.format(vars_defn, subs_defn)

        data = self._request(query, values)['data']
        return data['SaveMediaListEntry']['id']

    def add_show(self, item):
        self.check_credentials()
        self.msg.info(self.name, "Adding item %s..." % item['title'])
        return self._update_entry(item)

    def update_show(self, item):
        self.check_credentials()
        self.msg.info(self.name, "Updating item %s..." % item['title'])
        self._update_entry(item)

    def delete_show(self, item):
        self.check_credentials()
        self.msg.info(self.name, "Deleting item %s..." % item['title'])
        query = 'mutation ($id: Int) {DeleteMediaListEntry(id: $id){deleted} }'
        variables = {'id': item['my_id']}
        self._request(query, variables)

    def search(self, criteria, method):
        self.check_credentials()
        self.msg.info(self.name, "Searching for {}...".format(criteria))

        if method == utils.SEARCH_METHOD_KW:
            query = "query ($query: String, $type: MediaType) { Page { media(search: $query, type: $type) {"
            variables = {'query': urllib.parse.quote_plus(criteria)}
        elif method == utils.SEARCH_METHOD_SEASON:
            season, seasonYear = criteria
            
            query = "query ($season: MediaSeason, $seasonYear: Int, $type: MediaType) { Page { media(season: $season, seasonYear: $seasonYear, type: $type) {"
            variables = {'season': self.season_translate[season], 'seasonYear': seasonYear}

        query += '''
      id
      title { userPreferred romaji english native }
      coverImage { medium large }
      format
      averageScore
      chapters episodes
      status
      startDate { year month day }
      endDate { year month day }
      siteUrl
      description
      genres
      synonyms
      averageScore
      studios(sort: NAME, isMain: true) { nodes { name } }
    }
  }
}'''
        variables['type'] = self.mediatype.upper()
        data = self._request(query, variables)['data']['Page']['media']

        infolist = []
        for media in data:
            infolist.append(self._parse_info(media))

        self._emit_signal('show_info_changed', infolist)
        return infolist

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
      chapters episodes
      status
      startDate { year month day }
      endDate { year month day }
      siteUrl
      description
      genres
      synonyms
      averageScore
      studios(sort: NAME, isMain: true) { nodes { name } }
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

    def _parse_info(self, item):
        info = utils.show()
        showid = item['id']
        
        info.update({
            'id': showid,
            'title': item['title']['userPreferred'],
            'total': self._c(item[self.total_str]),
            'aliases': self._get_aliases(item),
            'type': self.type_translate[item['format']],
            'status': self.status_translate[item['status']],
            'image': item['coverImage']['large'],
            'image_thumb': item['coverImage']['medium'],
            'url': item['siteUrl'],
            'start_date': self._dict2date(item.get('startDate')),
            'end_date': self._dict2date(item.get('endDate')),
            'extra': [
                ('English',         item['title'].get('english')),
                ('Romaji',          item['title'].get('romaji')),
                ('Japanese',        item['title'].get('native')),
                ('Synonyms',        item.get('synonyms')),
                ('Genres',          item.get('genres')),
                ('Studios',         [s['name'] for s in item['studios']['nodes']]),
                ('Synopsis',        item.get('description')),
                ('Type',            item.get('format')),
                ('Average score',   item.get('averageScore')),
                ('Status',          self.status_translate[item['status']]),
            ]
        })
        return info

    def _apply_scoreformat(self, fmt):
        media = self.media_info()
        (media['score_max'], media['score_step']) = self.score_types[fmt]
    
    def _get_aliases(self, item):
        aliases = [a for a in (item['title']['romaji'], item['title']['english'], item['title']['native']) if a] + item['synonyms']

        return aliases

    def _dict2date(self, item):
        if not item:
            return None
        try:
            return datetime.datetime(item['year'], item['month'], item['day'])
        except (TypeError, ValueError):
            return None

    def _date2dict(self, date):
        if not date:
            return {}
        try:
            return {'year': date.year, 'month': date.month, 'day': date.day}
        except (TypeError, ValueError):
            return {}

    def _score2raw(self, score):
        if score == 0:
            return 0

        if self.scoreformat in ['POINT_10', 'POINT_10_DECIMAL']:
            return int(score*10)
        elif self.scoreformat == 'POINT_5':
            return int(score*20)
        elif self.scoreformat == 'POINT_3':
            return int(score*25)
        else:
            return score

    def _int2date(self, item):
        if not item:
            return None
        try:
            return datetime.datetime.utcfromtimestamp(item)
        except ValueError:
            return None

    def _c(self, s):
        if s is None:
            return 0
        else:
            return s


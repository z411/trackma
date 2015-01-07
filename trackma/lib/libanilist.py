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

from trackma.lib.lib import lib
import trackma.utils as utils

import json
import urllib, urllib2
import time

class libanilist(lib):
    """
    API class to communicate with Anilist

    Website: http://anilist.co

    messenger: Messenger object to send useful messages to
    mediatype: String containing the media type to be used
    """
    name = 'libanilist'
    msg = None
    logged_in = False
    
    api_info = { 'name': 'Anilist', 'version': '1', 'merge': False }
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_add': False,
        'can_delete': False,
        'can_score': False,
        'can_status': False,
        'can_update': False,
        'can_play': False,
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
    default_mediatype = 'anime'

    # Supported signals for the data handler
    signals = { 'show_info_changed': None, }
    
    url = "http://anilist.co/api/"
    client_id = "z411-gdjc3"
    _client_secret = "MyzwuYoMqPPglXwCTcexG1i"
    
    def __init__(self, messenger, account, userconfig):
        """Initializes the API"""
        super(libanilist, self).__init__(messenger, account, userconfig)

        self.pin = account['password'].strip()
        self.userid = userconfig['userid']
        
        if len(self.pin) != 40:
            raise utils.APIFatal("Invalid PIN.")
        
        #handler=urllib2.HTTPHandler(debuglevel=1)
        #self.opener = urllib2.build_opener(handler)
        self.opener = urllib2.build_opener()
        self.opener.addheaders = [('User-agent', 'TestClient/0.1')]
        
    def _request(self, method, url, get=None, post=None, auth=False):
        if get:
            url = "{}?{}".format(url, urllib.urlencode(get))
        if post:
            post = urllib.urlencode(post)

        request = urllib2.Request(self.url + url, post)
        request.get_method = lambda: method
        
        if auth:
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            request.add_header('Authorization', '{0} {1}'.format(
                self._get_userconfig('token_type'),
                self._get_userconfig('access_token'),
            ))
        
        try:
            response = self.opener.open(request, timeout = 10)
            return json.load(response)
        except urllib2.HTTPError, e:
            raise utils.APIError("Connection error: %s" % e)
    
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
        data = self._request("GET", "user/{0}/animelist".format(self.userid), get=param)

        showlist = {}
        for remotelist in data["lists"].itervalues():
            for item in remotelist:
                show = utils.show()
                showid = item['anime']['id']
                show.update({
                    'id': showid,
                    'title': item['anime']['title_romaji'],
                    #'aliases': item['anime']['synonyms'],
                    'my_progress': item['episodes_watched'],
                    'my_status': item['list_status'],
                    'my_score': self._score(item['score']),
                    'total': item['anime']['total_episodes'],
                    'image': item['anime']['image_url_med'],
                })

                showlist[showid] = show

        return showlist
    
    def add_show(self, item):
        """
        Adds the **item** in the remote server list. The **item** is a show dictionary passed by the Data Handler.
        """
        raise NotImplementedError
    
    def update_show(self, item):
        """
        Sends the updates of a show to the remote site.

        This function gets called every time a show should be updated remotely,
        and in a queue it may be called many times consecutively, so you should
        use a boolean (or other method) to login only once.

        """
        raise NotImplementedError
    
    def delete_show(self, item):
        """
        Deletes the **item** in the remote server list. The **item** is a show dictionary passed by the Data Handler.
        """
        raise NotImplementedError
        
    def search(self, criteria):
        """
        Called when the data handler needs a detailed list of shows from the remote server.
        It should return a list of show dictionaries with the additional 'extra' key (which is a list of tuples)
        containing any additional detailed information about the show.
        """
        raise NotImplementedError
    
    def request_info(self, ids):
        # Request detailed information for requested shows
        raise NotImplementedError
    
    def media_info(self):
        """Return information about the currently selected mediatype."""
        return self.mediatypes[self.mediatype]

    def _score(self, s):
        return 0 if s is None else s
        

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
        'status_start': 1,
        'status_finish': 2,
        'statuses':  [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Watching', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Watch' },
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
        
        if len(self.pin) != 40:
            raise utils.APIFatal("Invalid PIN.")
        
        handler=urllib2.HTTPHandler(debuglevel=1)
        self.opener = urllib2.build_opener(handler)
        #self.opener = urllib2.build_opener()
        
    def _request(self, method, url, post=None):
        if post:
            post = urllib.urlencode(post)

        request = urllib2.Request(self.url + url, post)
        request.get_method = lambda: method
        
        if self.logged_in:
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            request.add_header('Authorization', '{0} {1}'.format(
                self._get_userconfig('token_type'),
                self._get_userconfig('access_token'),
            ))
        
        try:
            print request
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
        urlparam = urllib.urlencode(param)
        data = self._request("POST", "auth/access_token?{}".format(urlparam))
        
        #url = ('auth/access_token?grant_type=authorization_code'
        #    '&client_id={0}&client_secret={1}&redirect_uri={2}'
        #    '&code={3}').format(self.client_id,param['client_secret'],param['redirect_uri'],param['code'])
        #data = self._request("POST", url)
        
        self._set_userconfig('access_token', data['access_token'])
        self._set_userconfig('token_type', data['token_type'])
        self._set_userconfig('expires', data['expires'])
        self._set_userconfig('refresh_token', data['refresh_token'])
        
        self.logged_in = True
        self._refresh_user_info()
    
    def _refresh_access_token(self):
        self.msg.info(self.name, 'Refreshing access token...')
        post = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self._client_secret,
            'refresh_token': self._get_userconfig('refresh_token'),
        }
        data = self._request("POST", "auth/access_token", post)
        
        self._set_userconfig('access_token', data['access_token'])
        self._set_userconfig('token_type', data['token_type'])
        self._set_userconfig('expires', data['expires'])
        
        self.logged_in = True
        self._refresh_user_info()
    
    def _refresh_user_info(self):
        self.msg.info(self.name, 'Refreshing user details...')
        data = self._request("GET", "user")
        
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
        
        data = self._request("GET", "user/{0}/animelist/raw".format(self.userid))
        
        print data
    
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
        

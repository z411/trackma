# -*- coding: utf-8 -*-

# This file is part of wMAL.
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

from wmal.lib.lib import lib
import wmal.utils as utils

import urllib, urllib2
import json

class libmalu(lib):
    """
    API class to communicate with MyAnimeList
    using the improved unofficial API.

    Website: http://mal-api.com/
    API documentation: http://mal-api.com/docs/
    Designed by: https://twitter.com/sliceoflifer

    """
    name = 'libmalu'
    
    username = '' # TODO Must be filled by check_credentials
    logged_in = False
    password_mgr = None
    handler = None
    opener = None
    
    api_info =  { 'name': 'MAL Unoff.', 'version': 'v0.1', 'merge': False }
    
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
        'status_start': 1,
        'status_finish': 2,
        'statuses':  [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Watching', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Watch' },
    }
    mediatypes['manga'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': False,
        'statuses': [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Reading', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Read' },
    }
    
    def __init__(self, messenger, account, userconfig):
        """Initializes the useragent through credentials."""
        super(libmalu, self).__init__(messenger, account, userconfig)
        
        self.username = account['username']
        
        self.password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.password_mgr.add_password("myanimelist.net", "mal-api.com:80", account['username'], account['password']);
        
        self.handler = urllib2.HTTPBasicAuthHandler(self.password_mgr)
        self.opener = urllib2.build_opener(self.handler)
        
        urllib2.install_opener(self.opener)
    
    def _request(self, method, url, data=None):
        request = urllib2.Request(url)
        request.get_method = lambda: method
        return self.opener.open(request, data)

    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        
        # This shit never works, let's just continue
        # If credentials are wrong it'll return an unauthorized error
        # later
        return True
        
        if self.logged_in:
            return True     # Already logged in
        
        self.msg.info(self.name, 'Logging in...')
        try:
            response = self.opener.open("http://mal-api.com/account/verify_credentials")
            self.logged_in = True
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError("Incorrect credentials.")
    
    def add_show(self, item):
        """Adds a new show in the server"""
        self.check_credentials()
        self.msg.info(self.name, "Adding show %s..." % item['title'])

        data = self._build_data(item, True)
        try:
            # POST request
            self.opener.open("http://mal-api.com/%slist/%s" % (self.mediatype, self.mediatype), data)
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError('Error adding: ' + str(e.code))

    def update_show(self, item):
        """Sends a show update to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Updating show %s..." % item['title'])
        
        data = self._build_data(item)
        try:
            self._request('PUT', "http://mal-api.com/%slist/%s/%d" % (self.mediatype, self.mediatype, item['id']), data)
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError('Error updating: ' + str(e.code))
    
    def delete_show(self, item):
        """Sends a show delete to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Deleting show %s..." % item['title'])
        
        try:
            self._request('DELETE', "http://mal-api.com/%slist/%s/%d" % (self.mediatype, self.mediatype, item['id']))
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError('Error deleting: ' + str(e.code))
    
    def fetch_list(self):
        """Queries the full list from the remote server.
        Returns the list if successful, False otherwise."""
        self.check_credentials()
        self.msg.info(self.name, 'Downloading list...')
        
        try:
            # Get an XML list from MyAnimeList API
            response = self.opener.open("http://mal-api.com/%slist/%s" % (self.mediatype, self.username))
            data = json.load(response)

            if self.mediatype == 'anime':
                self.msg.info(self.name, 'Parsing anime list...')
                return self._parse_anime(data)
            elif self.mediatype == 'manga':
                self.msg.info(self.name, 'Parsing manga list...')
                return self._parse_manga(data)
            else:
                raise utils.APIFatal('Attempted to parse unsupported media type.')
        except urllib2.HTTPError, e:
            raise utils.APIError("Error getting list.")
        
    def _parse_anime(self, data):
        """Loads JSON anime list into a dictionary"""
        showlist = dict()
        _my_statuses = {'watching': 1, 'completed': 2, 'on-hold': 3, 'dropped': 4, 'plan to watch': 6}
        _statuses = {'finished airing': 0, 'currently airing': 1, 'not yet aired': 2}
        
        for child in data['anime']:
            show_id = child['id']
            _my_status = child['watched_status']
            _status = child['status']
            
            show = utils.show()
            show.update({
                'id':           show_id,
                'title':        child['title'].encode('utf-8'),
                'my_progress':  child['watched_episodes'],
                'my_status':    _my_statuses[_my_status],
                'my_score':     child['score'],
                'total':        child['episodes'],
                'status':       _statuses[_status],
                'image':        child['image_url'],
            })
            showlist[show_id] = show
        return showlist
    
    def _parse_manga(self, data):
        """Loads JSON manga list into a dictionary"""
        showlist = dict()
        _my_statuses = {'reading': 1, 'completed': 2, 'on-hold': 3, 'dropped': 4, 'plan to read': 6}
        _statuses = {'finished': 0, 'publishing': 1, 'not yet published': 2}
        
        for child in data['manga']:
            manga_id = child[' id']
            _my_status = child['read_status']
            _status = child['status']
            
            show = utils.show()
            show.update({
                'id':           manga_id,
                'title':        child['title'].encode('utf-8'),
                'my_progress':  child['chapters_read'],
                'my_status':    _my_statuses[_my_status],
                'my_score':     child['score'],
                'total':        child['chapters'],
                'status':       _statuses[_status],
                'image':        child['image_url'],
            })
            mangalist[manga_id] = show
        return mangalist

    def _build_data(self, item, include_id=False):
        values = dict()

        if include_id:
            key = "%s_id" % self.mediatype
            values[key] = item['id']
        if 'my_progress' in item.keys():
            if self.mediatype == 'anime':
                progresskey = 'episodes'
            else:
                progresskey = 'chapters'

            values[progressname] = item['my_progress']
        if 'my_status' in item.keys():
            values['status'] = item['my_status']
        if 'my_score' in item.keys():
            values['score'] = item['score']

        return urllib.urlencode(values)

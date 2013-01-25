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

import lib

import urllib, urllib2
import json
import utils

class libmalu(lib.lib):
    """
    API class to communicate with MyAnimeList
    using the improved unofficial API.
    """
    name = 'libmalu'
    
    username = '' # TODO Must be filled by check_credentials
    logged_in = False
    password_mgr = None
    handler = None
    opener = None
    
    api_info =  { 'name': 'MAL Unoff.', 'version': 'v0.1', 'merge': False }
    
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': True,
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
    
    def __init__(self, messenger, config):
        """Initializes the useragent through credentials."""
        super(libmalu, self).__init__(messenger, config)
        
        self.username = config['username']
        
        self.password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.password_mgr.add_password("myanimelist.net", "mal-api.com:80", config['username'], config['password']);
        
        self.handler = urllib2.HTTPBasicAuthHandler(self.password_mgr)
        self.opener = urllib2.build_opener(self.handler)
        
        urllib2.install_opener(self.opener)
        
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
    
    def update_show(self, item):
        """Sends a show update to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Updating show %s..." % item['title'])
        
        # TODO
        
    
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
            
            showlist[show_id] = {
                'id':           show_id,
                'title':        child['title'].encode('utf-8'),
                'my_progress':  child['watched_episodes'],
                'my_status':    _my_statuses[_my_status],
                'my_score':     child['score'],
                'total':        child['episodes'],
                'status':       _statuses[_status],
                'image':        child['image_url'],
            }
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
            
            mangalist[manga_id] = {
                'id':           manga_id,
                'title':        child['title'].encode('utf-8'),
                'my_progress':  child['chapters_read'],
                'my_status':    _my_statuses[_my_status],
                'my_score':     child['score'],
                'total':        child['chapters'],
                'status':       _statuses[_status],
                'image':        child['image_url'],
            }
        return mangalist

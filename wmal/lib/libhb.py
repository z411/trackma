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

class libhb(lib):
    """
    API class to communicate with Hummingbird
    Should inherit a base library interface.

    Website: http://hummingbird.me/
    API documentation: 
    Designed by: 

    """
    name = 'libhb'
    
    username = '' # TODO Must be filled by check_credentials
    auth = ''
    logged_in = False
    
    api_info =  { 'name': 'Hummingbird', 'version': 'v0.2', 'merge': False }
    
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
        'statuses':  ['currently-watching', 'completed', 'on-hold', 'dropped', 'plan-to-watch'],
        'statuses_dict': { 'currently-watching': 'Watching', 'completed': 'Completed', 'on-hold': 'On Hold', 'dropped': 'Dropped', 'plan-to-watch': 'Plan to Watch' },
        'score_max': 10,
        'score_decimals': 1,
    }
    
    def __init__(self, messenger, account, userconfig):
        """Initializes the useragent through credentials."""
        # Since MyAnimeList uses a cookie we just create a HTTP Auth handler
        # together with the urllib2 opener.
        super(libhb, self).__init__(messenger, account, userconfig)
        
        self.username = account['username']
        self.password = account['password']

        # Build opener with the mashape API key
        self.opener = urllib2.build_opener()
        self.opener.addheaders = [('X-Mashape-Authorization', 'DJO7uQdZPu1gNfQWWwVHtS7xt8JhJSDf')]
        
    def _request(self, url, post=None):
        if post:
            post = urllib.urlencode(post)

        try:
            return self.opener.open(url, post, 10)
        except urllib2.URLError, e:
            raise utils.APIError("Connection error: %s" % e) 
   
    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        if self.logged_in:
            return True     # Already logged in
        
        self.msg.info(self.name, 'Logging in...')
        try:
            response = self._request( "https://hummingbirdv1.p.mashape.com/users/authenticate", {'username': self.username, 'password': self.password} ).read()
            self.auth = response.strip('"')
            self.logged_in = True
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError("Incorrect credentials.")
   
    def fetch_list(self):
        """Queries the full list from the remote server.
        Returns the list if successful, False otherwise."""
        self.check_credentials()
        self.msg.info(self.name, 'Downloading list...')
        
        try:
            # Get an XML list from MyAnimeList API
            data = self._request( "https://hummingbirdv1.p.mashape.com/users/%s/library?%s" % (self.username, urllib.urlencode({'auth_token': self.auth})) )
            shows = json.load(data)
            
            showlist = dict()
            infolist = list()
            for show in shows:
                slug = show['anime']['slug']

                showlist[slug] = utils.show()
                showlist[slug].update({
                    'id': slug,
                    'title': show['anime']['title'],
                    'my_progress': show['episodes_watched'],
                    'my_status': show['status'],
                    'total': show['anime']['episode_count'],
                    'image': show['anime']['cover_image'],
                })
                
                info = utils.show()
                info.update({
                    'id': slug,
                    'title': show['anime']['title'],
                    'image': show['anime']['cover_image'],
                    'url': show['anime']['url'],
                    'extra': [
                        ('Alternate title', show['anime']['alternate_title']),
                        ('Show type',       show['anime']['show_type']),
                        ('Synopsis',        show['anime']['synopsis']),
                        ('Status',          show['anime']['status']),
                    ]
                })
                infolist.append(info)
                
            self._emit_signal('show_info_changed', infolist)
            return showlist
        except urllib2.HTTPError, e:
            raise utils.APIError("Error getting list.")
    
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
            values['rating'] = item['my_score']

        try:
            response = self._request("https://hummingbirdv1.p.mashape.com/libraries/%s" % item['id'], values)
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError('Error updating: ' + str(e.code))
    
    def delete_show(self, item):
        """Sends a show delete to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Deleting show %s..." % item['title'])
        
        values = {'auth_token': self.auth}
        try:
            response = self._request("https://hummingbirdv1.p.mashape.com/libraries/%s/remove" % item['id'], values)
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError('Error deleting: ' + str(e.code))
   
    def _urlencode(self, in_dict):
        """Helper function to urlencode dicts in unicode. urllib doesn't like them."""
        out_dict = {}
        for k, v in in_dict.iteritems():
            out_dict[k] = v
            if isinstance(v, unicode):
                out_dict[k] = v.encode('utf8')
            elif isinstance(v, str):
                out_dict[k] = v.decode('utf8')
        return urllib.urlencode(out_dict)

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

class libmelative(lib.lib):
    name = 'libmelative'
    
    api_info =  { 'name': 'Melative', 'version': 'v0.1', 'merge': False }
    
    mediatypes = dict()
    
    # All mediatypes share the same statuses so we'll reuse them
    statuses = [1, 2, 3, 4, 6]
    statuses_dict = { 1: 'Current', 2: 'Complete', 3: 'Hold', 4: 'Dropped', 6: 'Wishlisted' }
    #mediadict = 
    
    mediatypes['anime'] = {
        'has_progress': True,
        'can_score': False,
        'can_status': False,
        'can_update': False,
        'can_play': False,
        'statuses':  statuses,
        'statuses_dict': statuses_dict,
    }
    mediatypes['manga'] = {
        'has_progress': True,
        'can_score': False,
        'can_status': False,
        'can_update': False,
        'can_play': False,
        'statuses':  statuses,
        'statuses_dict': statuses_dict,
    }
    mediatypes['vn'] = {
        'has_progress': False,
        'can_score': False,
        'can_status': False,
        'can_update': False,
        'can_play': False,
        'statuses':  statuses,
        'statuses_dict': statuses_dict,
    }
    mediatypes['lightnovel'] = {
        'has_progress': True,
        'can_score': False,
        'can_status': False,
        'can_update': False,
        'can_play': False,
        'statuses':  statuses,
        'statuses_dict': statuses_dict,
    }
    
    def __init__(self, messenger, config):
        """Initializes the useragent through credentials."""
        super(libmelative, self).__init__(messenger, config)
        
        self.username = config['username']
        
        self.password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.password_mgr.add_password("Melative", "melative.com:80", config['username'], config['password']);
        
        self.handler = urllib2.HTTPBasicAuthHandler(self.password_mgr)
        self.opener = urllib2.build_opener(self.handler)
        
        urllib2.install_opener(self.opener)
        
    def check_credentials(self):
        self.msg.info(self.name, 'Logging in...')
        
        try:
            response = self.opener.open("http://melative.com/api/account/verify_credentials.json")
            self.logged_in = True
            
            # Parse user information
            data = json.load(response)
            
            self.username = data['name']
            self.userid = data['id']

            return True
        except urllib2.HTTPError, e:
            raise utils.APIError("Incorrect credentials.")
    
    def fetch_list(self):
        self.check_credentials()
        self.msg.info(self.name, 'Downloading list...')
        
        # Get a JSON list from API
        response = self.opener.open("http://melative.com/api/library.json?user={0}&context_type={1}".format(self.username, self.mediatype))
        data = json.load(response)
        
        # Load data from the JSON stream into a parsed dictionary
        statuses = self.media_info()['statuses_dict']
        itemlist = dict()
        for record in data['library']:
            entity = record['entity']
            segment = record['segment']
            itemid = int(entity['id'])
            
            # use appropiate number for the show state
            _status = 0
            for k, v in statuses.items():
                if v.lower() == record['state']:
                    _status = k
            
            # use show length if available
            try:
                _total = int(entity['length'])
            except TypeError:
                _total = 0
                    
            if self.mediatypes[self.mediatype]['has_progress']:
                _progress = int(segment['name'])
            else:
                _progress = 0
                
            itemlist[itemid] = {
                'id':           itemid,
                'title':        entity['aliases'][0].encode('utf-8'),
                'my_status':    _status,
                'my_score':     int(record['rating'] or 0),
                'my_progress':  _progress,
                'total':        _total,
                'image':        entity['image_url'],
                'status': 0, #placeholder
            }
        
        return itemlist
            
        #except urllib2.HTTPError, e:
        #    raise utils.APIError("Error getting list. %s" % e.message)
    

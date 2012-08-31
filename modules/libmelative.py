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
import xml.etree.ElementTree as ET
import utils

class libmelative(lib.lib):
    name = 'libmelative'
    
    api_info =  { 'name': 'Melative', 'version': 'v0.1' }
    
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_update': False,
        'can_play': False,
        'statuses':  [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Current', 2: 'Complete', 3: 'Hold', 4: 'Dropped', 6: 'Wishlisted' },
    }
    
    def __init__(self, messenger, config):
        """Initializes the useragent through credentials."""
        super(libmelative, self).__init__(messenger, config)
        
        self.password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.password_mgr.add_password("Melative", "melative.com:80", config['username'], config['password']);
        
        self.handler = urllib2.HTTPBasicAuthHandler(self.password_mgr)
        self.opener = urllib2.build_opener(self.handler)
        
        urllib2.install_opener(self.opener)
        
    def check_credentials(self):
        self.msg.info(self.name, 'Logging in...')
        
        try:
            data = self.opener.open("http://melative.com/api/account/verify_credentials.xml").read()
            self.logged_in = True
            
            # Parse user information
            userinfo = ET.fromstring(data)
            self.username = userinfo.find('name').text
            self.userid = int(userinfo.find('id').text)
            
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError("Incorrect credentials.")
    
    def fetch_list(self):
        self.msg.info(self.name, 'Downloading list...')
        
        #try:
        
        # Get an XML list from API
        response = self.opener.open("http://melative.com/api/library?user={0}&context_type={1}".format(self.username, self.mediatype))
        data = response.read()
        
        # Load data from the XML into a parsed dictionary
        statuses = self.media_info()['statuses_dict']
        library = ET.fromstring(data).find('library')
        itemlist = dict()
        for record in library:
            if record.tag == 'record':
                entity = record.find('entity')
                segment = record.find('segment')
                itemid = int(entity.find('id').text)
                
                _status = 0
                for k, v in statuses.items():
                    if v.lower() == record.find('state').text:
                        _status = k
                
                try:
                    _total = int(entity.find('length').text)
                except TypeError:
                    _total = 0
                
                itemlist[itemid] = {
                    'id':           itemid,
                    'title':        entity.find('aliase').text.encode('utf-8'),
                    'my_status':    _status,
                    'my_score':     int(record.find('rating').text),
                    'my_progress':  int(segment.find('name').text),
                    'total':        _total,
                    'image':        entity.find('image_url').text,
                    'status': 0, #placeholder
                }
        
        return itemlist
            
        #except urllib2.HTTPError, e:
        #    raise utils.APIError("Error getting list. %s" % e.message)
    

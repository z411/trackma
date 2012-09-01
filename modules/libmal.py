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

class libmal(lib.lib):
    """
    API class to communicate with MyAnimeList
    Should inherit a base library interface.
    """
    name = 'libmal'
    
    username = '' # TODO Must be filled by check_credentials
    logged_in = False
    password_mgr = None
    handler = None
    opener = None
    
    api_info =  { 'name': 'MyAnimeList', 'version': 'v0.1' }
    
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': True,
        'statuses':  [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Watching', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Watch' },
    }
    mediatypes['manga'] = {
        'has_progress': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': False,
        'statuses': [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Reading', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Read' },
    }
    
    def __init__(self, messenger, config):
        """Initializes the useragent through credentials."""
        super(libmal, self).__init__(messenger, config)
        
        self.username = config['username']
        
        self.password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.password_mgr.add_password("MyAnimeList API", "myanimelist.net:80", config['username'], config['password']);
        
        self.handler = urllib2.HTTPBasicAuthHandler(self.password_mgr)
        self.opener = urllib2.build_opener(self.handler)
        
        urllib2.install_opener(self.opener)
    
    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        if self.logged_in:
            return True     # Already logged in
        
        self.msg.info(self.name, 'Logging in...')
        try:
            response = self.opener.open("http://myanimelist.net/api/account/verify_credentials.xml")
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
            response = self.opener.open("http://myanimelist.net/malappinfo.php?u="+self.username+"&status=all&type="+self.mediatype)
            data = response.read()
            
            # Load data from the XML into a parsed dictionary
            root = ET.fromstring(data)
            if self.mediatype == 'anime':
                self.msg.info(self.name, 'Parsing anime list...')
                return self._parse_anime(root)
            elif self.mediatype == 'manga':
                self.msg.info(self.name, 'Parsing manga list...')
                return self._parse_manga(root)
            else:
                raise utils.APIFatal('Attempted to parse unsupported media type.')
        except urllib2.HTTPError, e:
            raise utils.APIError("Error getting list.")
    
    def update_show(self, item):
        """Sends a show update to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Updating show %s..." % item['title'])
        
        # Start building XML
        root = ET.Element("entry")
        
        # Use the correct name depending on mediatype
        if self.mediatype == 'anime':
            progressname = 'episode'
        else:
            progressname = 'chapter'
        
        # Update necessary keys
        if 'my_progress' in item.keys():
            episode = ET.SubElement(root, progressname)
            episode.text = str(item['my_progress'])
        if 'my_status' in item.keys():
            status = ET.SubElement(root, "status")
            status.text = str(item['my_status'])
        if 'my_score' in item.keys():
            status = ET.SubElement(root, "score")
            status.text = str(item['my_score'])
        
        # Send the XML as POST data to the MyAnimeList API
        values = {'data': ET.tostring(root)}
        data = urllib.urlencode(values)
        try:
            response = self.opener.open("http://myanimelist.net/api/"+self.mediatype+"list/update/"+str(item['id'])+".xml", data)
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError('Error updating: ' + str(e.code))
    
    def _parse_anime(self, root):
        showlist = dict()
        for child in root:
            if child.tag == 'anime':
                show_id = int(child.find('series_animedb_id').text)
                
                showlist[show_id] = {
                    'id':           show_id,
                    'title':        child.find('series_title').text.encode('utf-8'),
                    'my_progress':  int(child.find('my_watched_episodes').text),
                    'my_status':    int(child.find('my_status').text),
                    'my_score':     int(child.find('my_score').text),
                    'total':     int(child.find('series_episodes').text),
                    'status':       int(child.find('series_status').text),
                    'image':        child.find('series_image').text,
                }
        return showlist
    
    def _parse_manga(self, root):
        mangalist = dict()
        for child in root:
            if child.tag == 'manga':
                manga_id = int(child.find('series_mangadb_id').text)
                
                mangalist[manga_id] = {
                    'id':           manga_id,
                    'title':        child.find('series_title').text.encode('utf-8'),
                    'my_progress':  int(child.find('my_read_chapters').text),
                    'my_status':    int(child.find('my_status').text),
                    'my_score':     int(child.find('my_score').text),
                    'total':     int(child.find('series_chapters').text),
                    'status':       int(child.find('series_status').text),
                    'image':        child.find('series_image').text,
                }
        return mangalist

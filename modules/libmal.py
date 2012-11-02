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
import xml.etree.ElementTree as ET
from cStringIO  import StringIO

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
        # Since MyAnimeList uses a cookie we just create a HTTP Auth handler
        # together with the urllib2 opener.
        super(libmal, self).__init__(messenger, config)
        
        self.username = config['username']
        
        self.password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.password_mgr.add_password("MyAnimeList API", "myanimelist.net:80", config['username'], config['password']);
        
        self.handler = urllib2.HTTPBasicAuthHandler(self.password_mgr)
        self.opener = urllib2.build_opener(self.handler)
        
        urllib2.install_opener(self.opener)
        
    def _make_parser(self):
        # For some reason MAL returns an XML file with HTML exclusive
        # entities like &aacute;, so we have to create a custom XMLParser
        # to convert these entities correctly.
        parser = ET.XMLParser()
        parser.parser.UseForeignDTD(True)
        parser.entity['aacute'] = 'á'
        parser.entity['eacute'] = 'é'
        parser.entity['iacute'] = 'í'
        parser.entity['oacute'] = 'ó'
        parser.entity['uacute'] = 'ú'
        parser.entity['lsquo'] = '‘'
        parser.entity['rsquo'] = '’'
        parser.entity['ldquo'] = '“'
        parser.entity['rdquo'] = '“'
        parser.entity['ndash'] = '-'
        parser.entity['mdash'] = '—'
        parser.entity['hellip'] = '…'
        
        return parser
    
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
            data = StringIO(response.read())
            
            # Parse the XML data and load it into a dictionary
            # using the proper function (anime or manga)
            root = ET.ElementTree().parse(data, parser=self._make_parser())
            
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
    
    def add_show(self, item):
        """Adds a new show in the server"""
        self.check_credentials()
        self.msg.info(self.name, "Adding show %s..." % item['title'])
        
        xml = self._build_xml(item)
        
        # Send the XML as POST data to the MyAnimeList API
        values = {'data': xml}
        data = urllib.urlencode(values)
        try:
            response = self.opener.open("http://myanimelist.net/api/"+self.mediatype+"list/add/"+str(item['id'])+".xml", data)
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError('Error adding: ' + str(e.code))
        
    def update_show(self, item):
        """Sends a show update to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Updating show %s..." % item['title'])
        
        xml = self._build_xml(item)
        
        # Send the XML as POST data to the MyAnimeList API
        values = {'data': xml}
        data = urllib.urlencode(values)
        try:
            response = self.opener.open("http://myanimelist.net/api/"+self.mediatype+"list/update/"+str(item['id'])+".xml", data)
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError('Error updating: ' + str(e.code))
    
    def delete_show(self, item):
        """Sends a show delete to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Deleting show %s..." % item['title'])
        
        try:
            response = self.opener.open("http://myanimelist.net/api/"+self.mediatype+"list/delete/"+str(item['id'])+".xml")
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError('Error deleting: ' + str(e.code))
        
    def search(self, criteria):
        """Searches MyAnimeList database for the queried show"""
        self.msg.info(self.name, "Searching for %s..." % criteria)
        
        # Send the urlencoded query to the search API
        query = urllib.urlencode({'q': criteria})
        response = self.opener.open("http://myanimelist.net/api/"+self.mediatype+"/search.xml?" + query)
        data = StringIO(response.read())
        
        # Load the results into XML
        root = ET.ElementTree().parse(data, parser=self._make_parser())
        
        # Use the correct tag name for episodes
        if self.mediatype == 'manga':
            episodes_str = 'chapters'
        else:
            episodes_str = 'episodes'
        
        # Since the MAL API returns the status as a string, and
        # we handle statuses as integers, we need to convert them
        status_translate = {'Currently Airing': 1, 'Finished Airing': 2, 'Not yet aired': 3}
        
        entries = list()
        for child in root.iter('entry'):
            show = {
                'id':           int(child.find('id').text),
                'title':        child.find('title').text.encode('utf-8'),
                'my_progress':  0,
                'my_status':    1,
                'my_score':     0,
                'type':         child.find('type').text,
                'status':       status_translate[child.find('status').text], # TODO : This should return an int!
                'total':        int(child.find(episodes_str).text),
                'image':        child.find('image').text,
            }
            entries.append(show)
        
        return entries
        
    def _parse_anime(self, root):
        """Converts an XML anime list to a dictionary"""
        showlist = dict()
        for child in root.iter('anime'):
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
        """Converts an XML manga list to a dictionary"""
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
    
    def _build_xml(self, item):
        """
        Creates an "anime|manga data" XML to be used in the
        add, update and delete methods.
        
        More information: 
          http://myanimelist.net/modules.php?go=api#animevalues
          http://myanimelist.net/modules.php?go=api#mangavalues
        
        """
        
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
            
        return ET.tostring(root)

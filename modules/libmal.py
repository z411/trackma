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

import urllib, urllib2
import xml.etree.ElementTree as ET

import utils

class libmal(object):
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
    msg = None
    
    def __init__(self, messenger, username, password):
        """Initializes the useragent through credentials."""
        self.msg = messenger
        self.username = username
        
        self.msg.info(self.name, 'Version v0.1')
        
        self.password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.password_mgr.add_password("MyAnimeList API", "myanimelist.net:80", username, password);
        
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
            self.loged_in = True
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError("Incorrect credentials.")
    
    def fetch_list(self):
        """Queries the full list from the remote server.
        Returns the list if successful, False otherwise."""
        self.msg.info(self.name, 'Downloading anime list...')
        
        showlist = dict()
        try:
            # Get an XML list from MyAnimeList API
            response = self.opener.open("http://myanimelist.net/malappinfo.php?u="+self.username+"&status=all&type=anime")
            data = response.read()
            
            # Load data from the XML into a parsed dictionary
            root = ET.fromstring(data)
            self.msg.info(self.name, 'Parsing list...')
            
            for child in root:
                if child.tag == 'anime':
                    show_id = int(child.find('series_animedb_id').text)
                    
                    showlist[show_id] = {
                        'id':           show_id,
                        'title':        child.find('series_title').text.encode('utf-8'),
                        'my_episodes':  int(child.find('my_watched_episodes').text),
                        'my_status':    int(child.find('my_status').text),
                        'my_score':     int(child.find('my_score').text),
                        'episodes':     int(child.find('series_episodes').text),
                        'status':       int(child.find('series_status').text),
                        'image':        child.find('series_image').text,
                    }
            
            return showlist
        except urllib2.HTTPError, e:
            raise utils.APIError("Error getting list.")
    
    def update_show(self, item):
        """Sends a show update to the server"""
        self.msg.info(self.name, "Updating show %s..." % item['title'])
        
        # Start building XML
        root = ET.Element("entry")
        
        # Update necessary keys
        if 'my_episodes' in item.keys():
            episode = ET.SubElement(root, "episode")
            episode.text = str(item['my_episodes'])
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
            response = self.opener.open("http://myanimelist.net/api/animelist/update/"+str(item['id'])+".xml", data)
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError('Error updating: ' + str(e.code))

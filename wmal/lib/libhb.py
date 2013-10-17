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
        'statuses':  ['currently-watching', 3, 4, 6],
        'statuses_dict': { 'currently-watching': 'Watching', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Watch' },
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
            data = self._request( "https://hummingbirdv1.p.mashape.com/users/z411/library?%s" % urllib.urlencode({'status': 'currently-watching', 'auth_token': self.auth}) )
            shows = json.load(data)
            
            showlist = dict()
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

            return showlist
        except urllib2.HTTPError, e:
            raise utils.APIError("Error getting list.")
    
    def add_show(self, item):
        """Adds a new show in the server"""
        self.check_credentials()
        self.msg.info(self.name, "Adding show %s..." % item['title'])
        
        xml = self._build_xml(item)
        
        # Send the XML as POST data to the MyAnimeList API
        values = {'data': xml}
        data = self._urlencode(values)
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
        data = self._urlencode(values)
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
        query = self._urlencode({'q': criteria})
        data = self._request_gzip("http://myanimelist.net/api/"+self.mediatype+"/search.xml?" + query)
        
        # Load the results into XML
        try:
            root = ET.ElementTree().parse(data, parser=self._make_parser())
        except ET.ParseError:
            return []
        
        # Use the correct tag name for episodes
        if self.mediatype == 'manga':
            episodes_str = 'chapters'
        else:
            episodes_str = 'episodes'
                
        # Since the MAL API returns the status as a string, and
        # we handle statuses as integers, we need to convert them
        if self.mediatype == 'anime':
            status_translate = {'Currently Airing': 1, 'Finished Airing': 2, 'Not yet aired': 3}
        elif self.mediatype == 'manga':
            status_translate = {'Publishing': 1, 'Finished': 2}
        
        entries = list()
        for child in root.iter('entry'):
            show = utils.show()
            showid = int(child.find('id').text)
            show.update({
                'id':           showid,
                'title':        child.find('title').text,
                'type':         child.find('type').text,
                'status':       status_translate[child.find('status').text], # TODO : This should return an int!
                'total':        int(child.find(episodes_str).text),
                'image':        child.find('image').text,
                'url':          "http://myanimelist.net/anime/%d" % showid,
                'extra': [
                    ('English',  child.find('english').text),
                    ('Synonyms', child.find('synonyms').text),
                    ('Synopsis', self._translate_synopsis(child.find('synopsis').text)),
                    (episodes_str.title(), child.find(episodes_str).text),
                    ('Type',     child.find('type').text),
                    ('Score',    child.find('score').text),
                    ('Status',   child.find('status').text),
                    ('Start date', child.find('start_date').text),
                    ('End date', child.find('end_date').text),
                    ]
            })
            entries.append(show)
        
        self._emit_signal('show_info_changed', entries)
        return entries
    
    def _translate_synopsis(self, string):
        if string is None:
            return None
        else:
            return string.replace('<br />', '')

    def request_info(self, itemlist):
        resultdict = dict()
        for item in itemlist:
            # Search for it only if it hasn't been found earlier
            if item['id'] not in resultdict:
                infos = self.search(item['title'])
                for info in infos:
                    showid = info['id']
                    resultdict[showid] = info

        itemids = [ show['id'] for show in itemlist ]

        reslist = [ resultdict[itemid] for itemid in itemids ]
        return reslist

    def _parse_anime(self, root):
        """Converts an XML anime list to a dictionary"""
        showlist = dict()
        for child in root.iter('anime'):
            show_id = int(child.find('series_animedb_id').text)
            if child.find('series_synonyms').text:
                aliases = child.find('series_synonyms').text.lstrip('; ').split('; ')
            else:
                aliases = []
            
            show = utils.show()
            show.update({
                'id':           show_id,
                'title':        child.find('series_title').text,
                'aliases':      aliases,
                'my_progress':  int(child.find('my_watched_episodes').text),
                'my_status':    int(child.find('my_status').text),
                'my_score':     int(child.find('my_score').text),
                'total':     int(child.find('series_episodes').text),
                'status':       int(child.find('series_status').text),
                'image':        child.find('series_image').text,
                'url':          "http://myanimelist.net/anime/%d" % show_id,
            })
            showlist[show_id] = show
        return showlist
    
    def _parse_manga(self, root):
        """Converts an XML manga list to a dictionary"""
        mangalist = dict()
        for child in root.iter('manga'):
            manga_id = int(child.find('series_mangadb_id').text)
            if child.find('series_synonyms').text:
                aliases = child.find('series_synonyms').text.lstrip('; ').split('; ')
            else:
                aliases = []
            
            show = utils.show()
            show.update({
                'id':           manga_id,
                'title':        child.find('series_title').text,
                'aliases':      aliases,
                'my_progress':  int(child.find('my_read_chapters').text),
                'my_status':    int(child.find('my_status').text),
                'my_score':     int(child.find('my_score').text),
                'total':     int(child.find('series_chapters').text),
                'status':       int(child.find('series_status').text),
                'image':        child.find('series_image').text,
                'url':          "http://myanimelist.net/manga/%d" % manga_id,
            })
            mangalist[manga_id] = show
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

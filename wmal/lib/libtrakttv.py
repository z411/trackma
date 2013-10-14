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
import gzip
import json
import xml.etree.ElementTree as ET
import hashlib
from cStringIO import StringIO
import operator as op

class libtrakttv(lib):
    """
    API class to communicate with Trakt.tv
    Should inherit a base library interface.

    Website: http://www.trakt.tv
    API documentation: http://trakt.tv/api-docs
    """
    name = 'libtrakttv'
        
    username = '' # TODO Must be filled by check_credentials
    logged_in = False
    password_mgr = None
    handler = None
    opener = None
    
    api_info =  { 'name': 'trakt.tv', 'version': 'v0.1', 'merge': True } # merge needs request_info
    
    default_mediatype = 'show'
    mediatypes = dict()
    mediatypes['show'] = {
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
        'id_type': 'tvdb_id',
        'can_separate_episodes': True,
        'has_seasons': True
    }
    mediatypes['movie'] = {
        'has_progress': False,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': False,
        'can_play': True,
        'statuses': [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Watching', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Watch' },
        'id_type': 'tvdb_id'
    }
    
   
    def __init__(self, messenger, account, userconfig):
        """Initializes the useragent through credentials."""
        # Since trakt.tv uses a cookie we just create a HTTP Auth handler
        # together with the urllib2 opener.
        super(libtrakttv, self).__init__(messenger, account, userconfig)
        
        self.username = account['username']
        self.password =  hashlib.sha1(account['password']).hexdigest()
        self.apikey = account['apikey']
        
        self.password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.password_mgr.add_password("trakt.tv API", "trakt.tv:80", self.username, self.password);
        
        self.handler = urllib2.HTTPBasicAuthHandler(self.password_mgr)
        self.opener = urllib2.build_opener(self.handler)

        urllib2.install_opener(self.opener)
    
    def _request(self, url):
        try:
            return self.opener.open(url, timeout = 10)
        except urllib2.URLError, e:
            raise utils.APIError("Connection error: %s" % e) 

    def _request_gzip(self, url):
        """
        Requests the page as gzip and uncompresses it

        Returns a stream object

        """
        try:
            request = urllib2.Request(url)
            request.add_header('Accept-encoding', 'gzip')
            compressed_data = self.opener.open(request).read()
        except urllib2.URLError, e:
            raise utils.APIError("Connection error: %s" % e)

        compressed_stream = StringIO(compressed_data)
        return gzip.GzipFile(fileobj=compressed_stream)

    def _make_parser(self):
        return parser
        
    def _make_json(self, data=None):
        logins={'username': self.username, "password": self.password}
        if data:
            logins.update(data)
        return json.dumps(logins)
    
    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        if self.logged_in:
            return True     # Already logged in
        
        self.msg.info(self.name, 'Logging in...')
        try:
            response = self.opener.open("http://api.trakt.tv/account/test/"+self.apikey,self._make_json())
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
            # Get an JSON list from trakt.tv API
            # Get minimum info to go quicker
            # all other info need to first be read from cache later,
            # and requested only if not already there
            data = self.opener.open("http://api.trakt.tv/user/library/"+self.mediatype+"s/watched.json/"+self.apikey+"/"+self.username+"/min", self._make_json())

            # Parse the JSON data and load it into a dictionary
            # using the proper function (show or movie)
            if self.mediatype == 'show':
                self.msg.info(self.name, 'Parsing tv show list...')
                return self._parse_show(data)
            elif self.mediatype == 'movie':
                self.msg.info(self.name, 'Parsing movie list...')
                return self._parse_movie(data)
            else:
                raise utils.APIFatal('Attempted to parse unsupported media type.')
        except urllib2.HTTPError, e:
            raise utils.APIError("Error getting list.")
    

    def _parse_show(self, root):
        """Converts an JSON tv show list to a dictionary"""
        showlist = dict()
        j = json.loads(root.read())
        
        for showinfo in j:
            show = utils.show()
            show.update({
                'id':           int(showinfo['tvdb_id']),
                'title':        str(showinfo['title']),
                'aliases':      [],
                'my_progress':  self.get_last_seen(showinfo), #(int season, int episode)
                'my_status':    1,
                'my_score':     -1,
                'total':        1000000,
                'status':       -1,
                'image':        "",
                'url':          "",
            })
            showlist[int(showinfo['tvdb_id'])] = show
        return showlist

    def _parse_movie(self, root):
        """Converts an JSON movie list to a dictionary"""
        movielist = dict()
        j = json.loads(root.read())
        
        for movieinfo in j:
            movie = utils.show()
            movie.update({
                'id':           str(movieinfo['imdb_id']),
                'title':        str(movieinfo['title']),
                'aliases':      [],
                'my_progress':  1,
                'my_status':    2,
                'my_score':     -1,
                'total':        1, #no progress, so completed as soon as seen
                'status':       2, #no progress, so completed when out
                'image':        "",
                'url':          "",
            })
            movielist[str(movieinfo['imdb_id'])] = movie
        return movielist

    #Get last seen episode, even if some gaps
    def get_last_seen(self, show):
        max_season = (1, [0])
        for seasons in show['seasons']:
            if seasons['season'] >= max_season[0]:
                max_season = (seasons['season'], seasons['episodes'])
        
        return (max_season[0], max_season[1][len(max_season[1])-1])   

    def add_show(self, item):
        """Adds a new show in the server. Adds it to the watchlist. TODO"""
        pass
        
    def update_show(self, item):
        """Sends a show update to the server"""
        
        if ('my_progress' in item.keys()):
            # Loop to take first non-zero, break as soon as finds one
            for i, it in enumerate(item['my_progress']):
                if item['my_progress'][i][1] > 0:  # Add episodes. Considering that if negative, has to delete some
                    self.add_seen_episodes(item, item['my_progress'])
                    break
                elif item['my_progress'][i][1] < 0:
                    self.delete_seen_episodes(item, item['my_progress'])
                    break
        if 'my_status' in item.keys():
            #This is only for local database, nothing to push to server
            pass
        if 'my_score' in item.keys():
            self.change_show_score(item, item['my_score'])
    
    #Add episodes or movies
    def add_seen_episodes(self, item, episodes_seen):
        self.msg.info(self.name, "Adding seen episodes to show %s..." % item['title'])
        self.change_seen_status(item, episodes_seen, '')
    
    #Delete episodes or movies
    def delete_seen_episodes(self, item, episodes_seen):
        self.msg.info(self.name, "Deleting seen episodes to show %s..." % item['title'])
        self.change_seen_status(item, episodes_seen, 'un')
    
    #Add/Delete episodes or movies, based on prefix
    def change_seen_status(self, item, episodes_seen, prefix=''):
        self.check_credentials()
                
        #Making the JSON
        data = self._make_json({})
        if self.mediatype == 'show':
            url="http://api.trakt.tv/show/episode/"+prefix+"seen/"+self.apikey
            episode_list=[]
            for ep in episodes_seen:
                episode_list.append({"season": ep[0], "episode": abs(ep[1])})
            data = self._make_json({"tvdb_id": item['id'],"episodes": episode_list})
        elif self.mediatype == 'movie':
            url="http://api.trakt.tv/movie/"+prefix+"seen/"+self.apikey
            data = self._make_json({"movies": [ {"imdb_id": item['id']} ] })

        try:
            print data
            self.opener.open(url, data)
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError('Error updating: ' + str(e.code))

    def delete_show(self, item):
        """Sends a show delete to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Deleting show %s..." % item['title'])

        id_type = self.mediatypes[self.mediatype]['id_type']
        data = self._make_json({id_type: item['id']})

        try:
            self.opener.open("http://api.trakt.tv/"+self.mediatype+"/unlibrary/"+self.apikey, data)
            return True
        except urllib2.HTTPError, e:
            raise utils.APIError('Error deleting: ' + str(e.code))



    def change_score_show(self, item, my_score):
        #TODO later
        pass

    def search(self, criteria):
        if self.mediatype == 'show':
            return self.search_show(criteria)
        elif self.mediatype == 'movie':
            return self.search_movie(criteria)
        
    def search_show(self, criteria):
        """Searches thetvdb database for the queried show,
           much better than the trakttv search wich returns search on every word.
           Fills only title and id, will need full info"""
        self.msg.info(self.name, "Searching for tv show %s..." % criteria)
        
        # Send the urlencoded query to the search API
        query = self._urlencode({'seriesname': criteria})
        data = self._request_gzip("http://thetvdb.com/api/GetSeries.php?" + query)
        
        # Load the results into XML
        try:
            root = ET.ElementTree().parse(data, parser=self._make_parser())
        except ET.ParseError:
            self.msg.warn(self.name, "Problem parsing the search ...")
            return []
        except IOError:
            self.msg.warn(self.name, "Problem during the search, response was not as expected. Try less words ...")
            return []
        
        entries = list()
        for child in root.iter('Series'):
            show = utils.show()
            showid = int(child.find('seriesid').text)
            show.update({
                'id':           showid,
                'title':        child.find('SeriesName').text,
                'my_progress':  (1, 0)
            })
            entries.append(show)
        
        return entries
    
    
    def search_movie(self, criteria):
        """Searches trakt.tv database for the queried movie.
           Fills only title and id, will need full info"""
        self.msg.info(self.name, "Searching for tv show %s..." % criteria)
        
        # Send the urlencoded query to the search API
        query = self._urlencode({criteria})
        data = self.opener.open("http://api.trakt.tv/search/movies.json/"+self.apikey+"/"+query)
        
        j = json.loads(data.read())
        
        entries = list()
        for movie in j:
            show = utils.show()
            showid = movie['imdb_id']
            show.update({
                'id':           showid,
                'title':        movie['title'],
                'my_progress':  (1, 0)
            })
            entries.append(show)

        return entries
        
    def request_info(self, shows):
        if self.mediatype == 'show':
            return [self.request_full_info_show(show['id']) for show in shows]
        elif self.mediatype == 'movie':
            return [self.request_full_info_movie(show['id']) for show in shows]

    def request_full_info_show(self, showid):
        """Requests the full info"""
        self.msg.info(self.name, "Requesting full info for tv show %s..." % showid)
        
        data = self.opener.open("http://api.trakt.tv/show/summary.json/"+self.apikey+"/"+str(showid)+"/extended", self._make_json())
        
        j = dict()
        j.update(json.loads(data.read()))
        items_to_delete = ["top_watchers", "top_episodes", "stats", "people"]
        for item in items_to_delete:
            del j[item]
        
        j.update({'id': j['tvdb_id']})
        
        j['seasons'].sort(key=op.itemgetter('season'))
        n_seasons = j['seasons'][-1]['season']
        #print "Number of seasons: ",n_seasons
        for s in j['seasons']:
            #print "Season %d has %d episodes" % (s['season'], s['episodes'][-1]['episode'])
            for it in "url", "images", "poster":
                del s[it]
            l_ep = []   
            for ep in s['episodes']:
                l_ep.append({'episode': ep['episode'],
                            'title': ep['title'],
                            'synopsys': ep['overview'],
                            'air_time': ep['first_aired_utc']
                            })
            s['episodes'] = l_ep
        
        # Tell data.py to update and save infocache
        l = list()
        l.append(j)
        self._emit_signal('show_info_changed', l)
                            
        return j
        
    def request_full_info_movie(self, showid):
        """Requests the full info"""
        self.msg.info(self.name, "Requesting full info for movie %s..." % showid)
        
        data = self.opener.open("http://api.trakt.tv/movie/summary.json/"+self.apikey+"/"+str(showid)+"/extended", self._make_json())
        
        j = json.loads(data.read())
        items_to_delete = ["top_watchers", "stats", "people"]
        for item in items_to_delete:
            del j[item]
        
        
        # Tell data.py to update and save infocache
        self._emit_signal('show_info_changed', list(j))
        
        return j
    
    def merge_info(self, show, info):
        if self.mediatype == 'show':
            return self.merge_info_show(show, info)
        elif self.mediatype == 'movie':
            return self.merge_info_movie(show, info)   
    
    
    def merge_info_show(self, show, info):
        status_translate = {'Continuing': 1, 'Ended': 2}
        
        show.update({
                'my_score':     info['rating_advanced'],
                'total':        self.n_ep_in_season(info, show['my_progress'][0]),
                'status':       status_translate[info['status']],
                'image':        info['poster'].replace('.jpg','-300.jpg'),
                'url':          info['url']
            })
            
        if show.get('my_status') == 1 and self.is_last_ep(info, show['my_progress']):
            show.update({'my_status': 2})
            
    def merge_info_movie(self, show, info):
        show.update({
                'aliases':      [],
                'my_progress':  1,
                'my_status':    2,
                'my_score':     info['rating_advanced'],
                'total':        1, #no progress, so completed as soon as seen
                'status':       2, #no progress, so completed when out
                'image':        info['poster'],
                'url':          info['url']
                })
        
    
    def is_last_ep(self, info, ep):
        return ep == (info['seasons'][-1]['season'], info['seasons'][-1]['episodes'][-1]['episode'])
        
    def n_ep_in_season(self, info, season):
        return info['seasons'][-1]['episodes'][-1]['episode']
                
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
        










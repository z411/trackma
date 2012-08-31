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
from BeautifulSoup import BeautifulSoup

import utils

class libvndb(lib.lib):
    """
    API class to communicate with MyAnimeList
    Should inherit a base library interface.
    """
    name = 'libvndb'
    
    api_info =  { 'name': 'vndb', 'version': 'v0.1' }
    
    mediatypes = dict()
    mediatypes['vn'] = {
        'has_progress': False,
        'can_update': False,
        'can_play': False,
        'statuses':  [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Playing', 2: 'Finished', 3: 'Stalled', 4: 'Dropped', 6: 'Wishlist' },
    }
    
    def __init__(self, messenger, config):
        """Initializes the useragent through credentials."""
        super(libvndb, self).__init__(messenger, config)
        
        self.username = config['username']
    
    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        return True
    
    def fetch_list(self):
        """Queries the full list from the remote server.
        Returns the list if successful, False otherwise."""
        self.msg.info(self.name, 'Downloading list...')
        
        data = urllib.urlopen('http://vndb.org/u'+self.username+'/list').read()
        soup = BeautifulSoup(data)
        
        if soup.head.title.string == 'Page Not Found':
            raise utils.APIFatal("Invalid user. Remember to use the user ID in the config file.")
        
        rows = soup.findAll('tr')
        
        vnlist = dict()
        statuses = self.media_info()['statuses_dict']
        
        for row in rows:
            vn = dict()
            vnid = 0
            for td in row.contents:
                if td['class'] == "tc3_5": # title
                    vnid = int(td.a['href'][2:])
                    vn['id'] = vnid
                    vn['title'] = td.a.string.encode('utf-8')
                elif td['class'] == "tc6": # status
                    if not vnid:
                        continue
                    
                    _status = 0
                    for k, v in statuses.items():
                        if v == td.string:
                            _status = k
                    
                    vn['my_status'] = _status
                elif td['class'] == "tc8": # score
                    if not vnid:
                        continue
                    
                    if td.string == '-':
                        vn['my_score'] = 0
                    else:
                        vn['my_score'] = int(td.string)
            
            # Dummy TODO
            vn['status'] = 0
            vn['my_progress'] = 0
            vn['total'] = 0
            
            if vnid > 0:
                vnlist[vnid] = vn
        
        # Wishlist
        data = urllib.urlopen('http://vndb.org/u'+self.username+'/wish').read()
        soup = BeautifulSoup(data)
        rows = soup.findAll('tr')
        for row in rows:
            vn = dict()
            vnid = 0
            for td in row.contents:
                if td['class'] == "tc1": # title
                    a = td.contents[0]
                    try:
                        vnid = int(a['href'][2:])
                    except TypeError:
                        continue
                    
                    vn['id'] = vnid
                    vn['title'] = a.string.encode('utf-8')
            
            # Dummy TODO
            vn['my_score'] = 0
            vn['my_status'] = 6
            vn['status'] = 0
            vn['my_progress'] = 0
            vn['total'] = 0
            
            if vnid > 0:
                vnlist[vnid] = vn
        
        return vnlist
    

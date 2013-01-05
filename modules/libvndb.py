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
import socket
import json

import utils

class libvndb(lib.lib):
    """
    API class to communicate with MyAnimeList
    Should inherit a base library interface.
    """
    name = 'libvndb'
    
    api_info =  {
                  'name': 'VNDB',
                  'version': 'v0.1',
                  'merge': True,
                }
    
    mediatypes = dict()
    mediatypes['vn'] = {
        'has_progress': False,
        'can_score': False,
        'can_status': False,
        'can_update': False,
        'can_play': False,
        'statuses':  [1, 2, 3, 4, 6, 0],
        'statuses_dict': { 1: 'Playing', 2: 'Finished', 3: 'Stalled', 4: 'Dropped', 6: 'Wishlist', 0: 'Unknown' },
    }
    
    def __init__(self, messenger, config):
        """Initializes the useragent through credentials."""
        super(libvndb, self).__init__(messenger, config)
        
        self.username = config['username']
        self.password = config['password']
        self.logged_in = False
        
    def _connect(self):
        """Create TCP socket and connect"""
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect(("beta.vndb.org", 19534))
    
    def _disconnect(self):
        """Shutdown and close the socket"""
        self.s.shutdown(socket.SHUT_RDWR)
        self.s.close()
    
    def _sendcmd(self, cmd, options=None):
        """Send a VNDB compatible command and return the response data"""
        msg = cmd
        if options:
            msg += " " + json.dumps(options, separators=(',',':'))
        msg += "\x04" # EOT
        
        # Send message
        self.s.sendall(msg)
        
        # Construct response
        response = ""
        while True:
            response += self.s.recv(65536)
            if response.endswith("\x04"):
                response = response.strip("\x04")
                break
        
        # Separate into response name and JSON data
        _resp = response.split(' ', 1)
        name = _resp[0]
        try:
            data = json.loads(_resp[1])
        except IndexError:
            data = None
        
        # Treat error as an exception
        if name == 'error':
            raise utils.APIError(data['msg'])
        
        return (name, data)
        
    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        self.msg.info(self.name, 'Connecting...')
        self._connect()
        
        self.msg.info(self.name, 'Logging in...')
        (name, data) = self._sendcmd('login',
            {'protocol': 1,
             'client': 'wSync',
             'clientver': 0.2,
             'username': self.username,
             'password': self.password,
             })
        
        if name == 'ok':
            self.logged_in = True
            return True
        else:
            return False
    
    def fetch_list(self):
        """Queries the full list from the remote server.
        Returns the list if successful, False otherwise."""
        if not self.logged_in:
            self.check_credentials()
        
        # Retrieve VNs per pages
        page = 1
        vns = dict()
        while True:
            self.msg.info(self.name, 'Downloading list... (%d)' % page)
            
            (name, data) = self._sendcmd('get vnlist basic (uid = 0)',
                {'page': page,
                'results': 25
                })
        
            # Something is wrong if we don't get a results response.
            if name != 'results':
                raise utils.APIFatal("Invalid response (%s)" % name)
            
            # Process list
            for item in data['items']:
                vnid = item['vn']
                vns[vnid] = utils.show()
                vns[vnid]['id']         = vnid
                vns[vnid]['my_status']  = item['status']
            
            if not data['more']:
                # No more VNs, finish
                break
            page += 1
        
        # Retrieve scores per pages
        page = 1
        while True:
            self.msg.info(self.name, 'Downloading votes... (%d)' % page)
            
            (name, data) = self._sendcmd('get votelist basic (uid = 0)',
                {'page': page,
                'results': 25
                })
            
            # Something is wrong if we don't get a results response.
            if name != 'results':
                raise utils.APIFatal("Invalid response (%s)" % name)
            
            for item in data['items']:
                vnid = item['vn']
                try:
                    vns[vnid]['my_score'] = item['vote']
                except KeyError:
                    # Ghost vote; ignore it
                    pass
                
            if not data['more']:
                # No more VNs, finish
                break
            page += 1
        
        return vns
    
    def request_info(self, itemlist):
        if not self.logged_in:
            self.check_credentials()
            
        start = 0
        infos = list()
        remaining = itemlist
        while True:
            self.msg.info(self.name, 'Requesting details...(%d)' % start)
            end = start + 25
            
            (name, data) = self._sendcmd('get vn basic,details (id = %s)' % repr(itemlist[start:end]),
                {'page': 1,
                 'results': 25,
                })
            
            # Something is wrong if we don't get a results response.
            if name != 'results':
                raise utils.APIFatal("Invalid response (%s)" % name)
            
            # Process list
            for item in data['items']:
                info = {'id': item['id'],
                        'title': item['title'],
                        'image': item['image'],
                       }
                infos.append(info)
            
            start += 25
            if start > len(itemlist):
                # We're going beyond the list, finish
                break
        
        self._emit_signal('show_info_changed', infos)
        return infos
    
    def logout(self):
        self.msg.info(self.name, 'Disconnecting...')
        self._disconnect()
        self.logged_in = False

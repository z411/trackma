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

import socket

import lib
import utils

class libanidb(lib.lib):
    name = 'libanidb'
    
    api_info =  { 'name': 'AniDB', 'version': 'v0.1' }
    
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_update': False,
        'can_play': True,
        'statuses':  [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Watching', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Watch' },
    }
    
    def __init__(self, messenger, config):
        """Initializes the useragent through credentials."""
        super(libanidb, self).__init__(messenger, config)
        
        self.username = config['username']
        self.password = config['password']
        
        # Initialize socket for UDP communication with AniDB
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', int(config['local_port'])))
        self.sock.connect((config['address'], int(config['remote_port'])))
    
    def check_credentials(self):
        self.msg.info(self.name, 'Logging in...')
        
        (code, msg) = self._send("AUTH user={0}&pass={1}&protover=3&client=wmal&clientver=1".format(self.username, self.password))
        if code == 200:
            self.sessid = msg.split(' ', 1)[0]
            print "Reponse OK, session ID: %s" % self.sessid
        else:
            raise utils.APIFatal('Error %d: %s' % (code, msg))
        
        self._send("LOGOUT")

    def fetch_list(self):
        self.check_credentials()
        
        (code,msg) = self._send("MYLIST s={0}&lid=0".format(self.sessid))
        print msg
        
    def _send(self, msg):
        # Handle correctness of message length vs. sent data length
        self.sock.sendall(msg)
        response = self.sock.recv(1024).split(' ', 1)
        return int(response[0]), response[1]
    

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

import utils

class lib(object):
    """
    Base interface for creating API implementations for wMAL
    """
    name = 'libvndb'
    msg = None
    
    api_info = { 'name': 'vndb' }
    
    def __init__(self, messenger, username, password):
        """Initializes the class"""
        self.msg = messenger
        
        self.msg.info(self.name, 'Version v0.1')
    
    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        raise NotImplementedError
    
    def fetch_list(self):
        """Queries the full list from the remote server.
        Returns the list if successful, False otherwise."""
        raise NotImplementedError
    
    def update_show(self, item):
        """Sends a show update to the server"""
        raise NotImplementedError

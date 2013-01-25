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

import wmal.utils as utils

class lib(object):
    """
    Base interface for creating API implementations for wMAL.

    messenger: Messenger object to send useful messages to
    mediatype: String containing the media type to be used
    """
    name = 'lib'
    version = 'dummy'
    msg = None
    
    # api_info is a dictionary containing useful information about the API itself
    # name: API name
    # version: API version
    api_info = { 'name': 'BaseAPI', 'version': 'undefined', 'merge': False }
    
    # mediatypes is a dictionary containing the possible mediatypes for the current API.
    # An example mediatype should look like this:
    #
    # 
    default_mediatype = None
    mediatypes = dict()

    # Supported signals for the data handler
    signals = { 'show_info_changed':    None, }
    
    def __init__(self, messenger, account, userconfig):
        """Initializes the base for the API"""
        self.msg = messenger
        self.msg.info(self.name, 'Version %s' % self.api_info['version'])
        
        if not userconfig.get('mediatype'):
            userconfig['mediatype'] = self.default_mediatype
        
        if userconfig['mediatype'] in self.mediatypes:
            self.mediatype = userconfig['mediatype']
        else:
            raise utils.APIFatal('Unsupported mediatype.')
        
        self.api_info['mediatype'] = self.mediatype
        self.api_info['supported_mediatypes'] = self.mediatypes.keys()

    def _emit_signal(self, signal, args=None):
        try:
            if self.signals[signal]:
                self.signals[signal](args)
        except KeyError:
            raise Exception("Call to undefined signal.")

    def connect_signal(self, signal, callback):
        try:
            self.signals[signal] = callback
        except KeyError:
            raise utils.EngineFatal("Invalid signal.")
        
    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        raise NotImplementedError
    
    def fetch_list(self):
        """
        Fetches the remote list and returns a dictionary of show dictionaries

        A show dictionary has the following keys:
        
        id: (int) Internal ID of the show
        title: (string) UTF-8 encoded title of the show
        my_progress: (int) Current progress for the show
        my_status: (int) Current status number as defined in the mediatype
        my_score: (int) Current score or rating
        total: (int) Maximum possible progress for this show (total episodes, etc.)
        status: (int) Show status number as in airing, completed, not aired, etc.
        image: (string) Optional. URL for the show image/cover/etc.

        This function should return a dictionary with the show id as the key,
        and the show dictionary as the value.
        """
        raise NotImplementedError
    
    def add_show(self, item):
        raise NotImplementedError
    
    def update_show(self, item):
        """
        Send the updates of a show to the remote site

        This function gets called everytime a show should be updated remotely,
        and in a queue it may be called many times consecutively, so you should
        use a boolean (or other method) to login only once.

        """
        raise NotImplementedError
    
    def delete_show(self, item):
        raise NotImplementedError
        
    def search(self, criteria):
        # Search for shows
        raise NotImplementedError
    
    def request_info(self, ids):
        # Request detailed information for requested shows
        raise NotImplementedError
    
    def logout(self):
        # This is called whenever the API won't be required
        # for a good while
        pass
        
    def media_info(self):
        """Return information about the currently selected mediatype."""
        return self.mediatypes[self.mediatype]
        
    def set_message_handler(self, message_handler):
        self.msg = message_handler
    

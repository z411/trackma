# This file is part of Trackma.
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

from trackma import utils

class lib():
    """
    Base interface for creating API implementations for Trackma.

    messenger: Messenger object to send useful messages to
    mediatype: String containing the media type to be used
    """
    name = 'lib'
    version = 'dummy'
    msg = None

    api_info = { 'name': 'BaseAPI', 'version': 'undefined', 'merge': False }
    """
    api_info is a dictionary containing useful information about the API itself
    name: API name
    version: API version
    """

    mediatypes = dict()
    """
    mediatypes is a dictionary containing the possible mediatypes for the current API.
    An example mediatype should look like this:
    ::

        mediatypes['anime'] = {
            'has_progress': True,
            'can_add': True,
            'can_delete': True,
            'can_score': True,
            'can_status': True,
            'can_update': True,
            'can_play': True,
            'statuses_start': [1],
            'statuses_finish': [2],
            'statuses':  [1, 2, 3, 4, 6],
            'statuses_dict': { 1: 'Watching', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Watch' },
        }

    """

    default_mediatype = None

    # Supported signals for the data handler
    signals = {
            'show_info_changed': None,
            'userconfig_changed': None,
    }

    def __init__(self, messenger, account, userconfig):
        """Initializes the API"""
        self.userconfig = userconfig
        self.msg = messenger
        self.msg.info(self.name, 'Initializing...')

        if not userconfig.get('mediatype'):
            userconfig['mediatype'] = self.default_mediatype

        if userconfig['mediatype'] in self.mediatypes:
            self.mediatype = userconfig['mediatype']
        else:
            raise utils.APIFatal('Unsupported mediatype %s.' % userconfig['mediatype'])

        self.api_info['mediatype'] = self.mediatype
        self.api_info['supported_mediatypes'] = list(self.mediatypes.keys())

    def _emit_signal(self, signal, *args):
        try:
            if self.signals[signal]:
                self.signals[signal](*args)
        except KeyError:
            raise Exception("Call to undefined signal.")

    def _get_userconfig(self, key):
        return self.userconfig.get(key)

    def _set_userconfig(self, key, value):
        self.userconfig[key] = value

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
        Fetches the remote list and returns a dictionary of show dictionaries.

        It should return a dictionary with the show ID as the key and a show dictionary as its value.
        You can create an empty show dictionary with the :func:`utils.show` function.
        """
        raise NotImplementedError

    def add_show(self, item):
        """
        Adds the **item** in the remote server list. The **item** is a show dictionary passed by the Data Handler.
        """
        raise NotImplementedError

    def update_show(self, item):
        """
        Sends the updates of a show to the remote site.

        This function gets called every time a show should be updated remotely,
        and in a queue it may be called many times consecutively, so you should
        use a boolean (or other method) to login only once.

        """
        raise NotImplementedError

    def delete_show(self, item):
        """
        Deletes the **item** in the remote server list. The **item** is a show dictionary passed by the Data Handler.
        """
        raise NotImplementedError

    def search(self, criteria, method):
        """
        Called when the data handler needs a detailed list of shows from the remote server.
        It should return a list of show dictionaries with the additional 'extra' key (which is a list of tuples)
        containing any additional detailed information about the show.
        """
        raise NotImplementedError

    def request_info(self, items):
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


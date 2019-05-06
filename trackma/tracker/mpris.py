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

import os
import re
import urllib.parse

import dbus
import dbus.mainloop.glib
from gi.repository import GLib

from trackma.tracker import tracker
from trackma import utils

class MPRISTracker(tracker.TrackerBase):
    name = 'Tracker (MPRIS)'
    mpris_base = 'org.mpris.MediaPlayer2'

    def _connect(self, name):
        # Add and connect new player
        if self.re_players.search(name):
            self.msg.info(self.name, "Connecting to MPRIS player: {}".format(name))

            proxy = self.bus.get_object(name, '/org/mpris/MediaPlayer2')
            properties = dbus.Interface(proxy, dbus_interface='org.freedesktop.DBus.Properties')
            properties.connect_to_signal('PropertiesChanged', self._on_update, sender_keyword='sender')

            metadata = properties.Get(MPRISTracker.mpris_base + '.Player', 'Metadata')
            status   = properties.Get(MPRISTracker.mpris_base + '.Player', 'PlaybackStatus')

            sender = self.bus.get_name_owner(name)
            self.filenames[sender] = self._get_filename(metadata)
        
            if not self.active_player:
                self._handle_status(status, sender)
        else:
            self.msg.info(self.name, "Unknown player: {}".format(name))

    def _get_filename(self, metadata):
        if 'xesam:title' in metadata:
            return metadata['xesam:title']
        elif 'xesam:url' in metadata:
            # TODO : Support for full path
            return os.path.basename(urllib.parse.unquote_plus(metadata['xesam:url']))
        else:
            return None

    def _handle_status(self, status, sender):
        self.msg.debug(self.name, "New playback status: {}".format(status))

        if status == "Playing":
            self._playing(self.filenames[sender], sender)
            self.resume_timer()
        elif status == "Paused":
            self._playing(self.filenames[sender], sender)
            self.pause_timer()
        elif status == "Stopped":
            self._stopped(sender)

    def _playing(self, filename, sender):
        if filename != self.last_filename:
            self.msg.debug(self.name, "New video: {}".format(filename))

            (state, show_tuple) = self._get_playing_show(filename)
            self.update_show_if_needed(state, show_tuple)
            
            if self.last_state == utils.TRACKER_PLAYING:
                self.msg.debug(self.name, "({}) Setting active player: {}".format(self.last_state, sender))
                self.active_player = sender

                if not self.timing:
                    self._pass_timer()
                    GLib.timeout_add_seconds(1, self._pass_timer)
       
    def _stopped(self, sender):
        self.filenames[sender] = None

        if sender == self.active_player:
            # Active player got closed!
            self.msg.debug(self.name, "Clearing active player: {}".format(sender))
            self.active_player = None
            
            (state, show_tuple) = self._get_playing_show(None)
            self.update_show_if_needed(state, show_tuple)

    def _on_update(self, name, properties, v, sender=None):
        if not self.active_player or self.active_player == sender:
            if 'Metadata' in properties:
                # Player is playing a new video. We pass the title
                # to the tracker and start our playing timer.
                self.filenames[sender] = self._get_filename(properties['Metadata'])

            if 'PlaybackStatus' in properties:
                status = properties['PlaybackStatus']
                self._handle_status(status, sender)
        else:
            self.msg.debug(self.name, "Got signal from an inactive player, ignoring.")
 
    def _new_name(self, name, old, new):
        if name.startswith(MPRISTracker.mpris_base):
            if new:
                # New MPRIS player found; connect signals.
                self._connect(name)
            else:
                self._stopped(old)

    def _pass_timer(self):
        if self.last_state == utils.TRACKER_PLAYING:
            self.update_show_if_needed(self.last_state, self.last_show_tuple)
            self.timing = True
        else:
            self.timing = False

        return self.timing

    def observe(self, config, watch_dirs):
        self.msg.info(self.name, "Using MPRIS.")

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        self.re_players = re.compile(config['tracker_process'])
        self.filenames = {}
        self.timing = False
        self.active_player = None
        self.bus = dbus.SessionBus()

        # Look for already running players and conect them
        for name in self.bus.list_names():
            if name.startswith(MPRISTracker.mpris_base):
                self._connect(name)

        # Connect signal for any new players that could appear
        names = self.bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
        names.connect_to_signal('NameOwnerChanged', self._new_name, dbus_interface='org.freedesktop.DBus')

        # Run GLib loop
        loop = GLib.MainLoop()
        loop.run()

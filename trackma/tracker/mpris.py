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
        self.players.append(name)
        self.msg.info(self.name, "Connecting to MPRIS player: {}".format(name))

        proxy = self.bus.get_object(name, '/org/mpris/MediaPlayer2')
        properties = dbus.Interface(proxy, dbus_interface='org.freedesktop.DBus.Properties')
        properties.connect_to_signal('PropertiesChanged', self._on_update, sender_keyword='sender')

        metadata = properties.Get(MPRISTracker.mpris_base + '.Player', 'Metadata')
        status   = properties.Get(MPRISTracker.mpris_base + '.Player', 'PlaybackStatus')

        if 'xesam:title' in metadata:
            sender = self.bus.get_name_owner(name)
            self._playing(metadata['xesam:title'], sender)
        if status == "Paused":
            self.pause_timer()

    def _playing(self, title, sender):
        self.msg.debug(self.name, "New video: {}".format(title))

        (state, show_tuple) = self._get_playing_show(title)
        self.update_show_if_needed(state, show_tuple)

        self.active_player = sender

        if not self.timing and state == utils.TRACKER_PLAYING:
            self._pass_timer()
            GLib.timeout_add_seconds(1, self._pass_timer)

    def _on_update(self, name, properties, v, sender=None):
        if 'Metadata' in properties and 'xesam:title' in properties['Metadata']:
            # Player is playing a new video. We pass the title
            # to the tracker and start our playing timer.
            title = properties['Metadata']['xesam:title']

            self._playing(title, sender)
        if 'PlaybackStatus' in properties:
            status = properties['PlaybackStatus']
            self.msg.debug(self.name, "New playback status: {}".format(status))

            if status == "Paused":
                self.pause_timer()
            elif status == "Playing":
                self.resume_timer()

    def _new_name(self, name, old, new):
        if name.startswith(MPRISTracker.mpris_base):
            if new:
                # New MPRIS player found; connect signals.
                self._connect(name)
            else:
                if old == self.active_player:
                    # Active player got closed!
                    (state, show_tuple) = self._get_playing_show(None)
                    self.update_show_if_needed(state, show_tuple)

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

        self.players = []
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

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

from gi.repository import GLib
from pydbus import SessionBus

from trackma import utils
from trackma.tracker import tracker


class MPRISTracker(tracker.TrackerBase):
    name = 'Tracker (MPRIS)'
    mpris_base = 'org.mpris.MediaPlayer2'

    def is_active_player(self, sender):
        return not self.active_player or self.active_player == sender or self.last_state != utils.Tracker.PLAYING

    def _connect(self, name):
        # Add and connect new player
        if self.re_players.search(name):
            try:
                sender = self.bus.GetNameOwner(name)
            except GLib.Error:
                self.msg.warn("Bus was closed before access: {}".format(name))
                return

            self.msg.info("Connecting to MPRIS player: {}".format(name))
            try:
                proxy = self.session.get(name, '/org/mpris/MediaPlayer2')
                properties = proxy['org.freedesktop.DBus.Properties']

                # properties.connect(
                # 'PropertiesChanged', self._on_update, sender_keyword='sender')
                proxy.PropertiesChanged.connect(
                    lambda x, props, y: self._on_update(sender, props))
                metadata = properties.Get(
                    MPRISTracker.mpris_base + '.Player', 'Metadata')

                status = properties.Get(
                    MPRISTracker.mpris_base + '.Player', 'PlaybackStatus')

                self.filenames[sender] = self._get_filename(metadata)
                if not self.active_player:
                    self._handle_status(status, sender)

                if sender not in self.view_offsets:
                    GLib.timeout_add(
                        100, self._update_view_offset, sender, properties)

                self._update_view_offset(sender, properties)

            except GLib.Error:
                self._stopped(sender)
        else:
            self.msg.info("Unknown player: {}".format(name))

    def _get_filename(self, metadata):
        if 'xesam:title' in metadata and len(metadata['xesam:title']) > 5:
            return metadata['xesam:title']
        elif 'xesam:url' in metadata:
            # TODO : Support for full path
            return os.path.basename(urllib.parse.unquote_plus(metadata['xesam:url']))
        else:
            return None

    def _handle_status(self, status, sender):
        self.msg.debug("New playback status: {}".format(status))

        if status == "Playing":
            self._playing(self.filenames[sender], sender)
            self.resume_timer()
        elif status == "Paused":
            self._playing(self.filenames[sender], sender)
            self.pause_timer()
        elif status == "Stopped":
            self._stopped(sender)

        self.statuses[sender] = status

    def _playing(self, filename, sender):
        if filename != self.last_filename:
            self.msg.debug("New video: {}".format(filename))

            (state, show_tuple) = self._get_playing_show(filename)
            self.update_show_if_needed(state, show_tuple)

            self.msg.debug("New tracker status: {} (previously: {})".format(
                state, self.last_state))

            # We can override the active player if this player is playing a valid show.
            if not self.active_player or self.last_state == utils.Tracker.PLAYING:
                self.msg.debug("({}) Setting active player: {}".format(
                    self.last_state, sender))
                self.active_player = sender

                if not self.timing:
                    self.msg.debug("Starting MPRIS timer.")
                    self.timing = True

                    self._pass_timer()
                    GLib.timeout_add_seconds(1, self._pass_timer)

    def _stopped(self, sender):
        self.filenames[sender] = None

        if sender == self.active_player:
            # Active player got closed!
            self.msg.debug("Clearing active player: {}".format(sender))
            self.active_player = None
            self.view_offset = None

            (state, show_tuple) = self._get_playing_show(None)
            self.update_show_if_needed(state, show_tuple)

            # Remove timer if any
            self.timing = False

        if sender in self.view_offsets:
            del self.view_offsets[sender]

    def _update_view_offset(self, sender, properties):
        try:
            self.view_offsets[sender] = int(properties.Get(
                MPRISTracker.mpris_base + '.Player', 'Position'))/1000
            if self.view_offsets[sender]:
                if self.is_active_player(sender):
                    self.view_offset = self.view_offsets[sender]
            return True
        except GLib.Error:
            return False

    def _on_update(self, sender, properties):
        # We can override the active player if it's not playing a valid show.
        if self.is_active_player(sender):
            if 'Metadata' in properties:
                # Player is playing a new video. We pass the title
                # to the tracker and start our playing timer.
                self.filenames[sender] = self._get_filename(
                    properties['Metadata'])

                if 'PlaybackStatus' not in properties:
                    # Query the player status if we don't have it
                    self._handle_status(self.statuses[sender], sender)

            if 'PlaybackStatus' in properties:
                status = properties['PlaybackStatus']
                self._handle_status(status, sender)

        else:
            self.msg.debug("Got signal from an inactive player, ignoring.")

    def _new_name(self, name, old, new):
        if name.startswith(MPRISTracker.mpris_base):
            if new:
                # New MPRIS player found; connect signals.
                self._connect(name)
            else:
                self._stopped(old)

    def _pass_timer(self):
        self.update_show_if_needed(self.last_state, self.last_show_tuple)

        return self.timing

    def observe(self, config, watch_dirs):
        self.msg.info("Using MPRIS.")

        self.re_players = re.compile(config['tracker_process'])
        self.filenames = {}
        self.statuses = {}
        self.view_offsets = {}
        self.timing = False
        self.active_player = None
        self.session = SessionBus()
        self.bus = self.session.get('.DBus')

        # Look for already running players and connect them
        for name in self.bus.ListNames():
            if name.startswith(MPRISTracker.mpris_base):
                self._connect(name)

        # Connect signal for any new players that could appear
        self.bus.NameOwnerChanged.connect(self._new_name)

        # Run GLib loop
        loop = GLib.MainLoop()
        loop.run()

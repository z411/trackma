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

BUS_NAME_PREFIX = 'org.mpris.MediaPlayer2'
PATH_MPRIS = '/org/mpris/MediaPlayer2'
IFACE_PROPERTIES = 'org.freedesktop.DBus.Properties'
IFACE_MPRIS = 'org.mpris.MediaPlayer2'
IFACE_MPRIS_PLAYER = IFACE_MPRIS + '.Player'


def _get_filename(metadata):
    if 'xesam:title' in metadata and len(metadata['xesam:title']) > 5:
        return metadata['xesam:title']
    elif 'xesam:url' in metadata:
        # TODO : Support for full path
        return os.path.basename(urllib.parse.unquote_plus(metadata['xesam:url']))
    else:
        return None


class Player:
    def __init__(self, tracker, bus_name):
        self.tracker = tracker
        self.bus_name = bus_name

        self.proxy = self.tracker.session.get(bus_name, PATH_MPRIS)
        self.properties = self.proxy[IFACE_PROPERTIES]
        self.mpris = self.proxy[IFACE_MPRIS]
        self.mpris_player = self.proxy[IFACE_MPRIS_PLAYER]

        self.filename = _get_filename(self.mpris_player.Metadata)
        self.status = self.mpris_player.PlaybackStatus
        self.subscription = self.properties.PropertiesChanged.connect(self._on_update)

    # trackma appears to receive PropertyChanged events multiple times
    # for each mpv instance(/sender?) that is being opened
    # and it does not cease to receive these events after the player is closed.
    # The sender remains.
    def _on_update(self, iface_name, properties, _rest):
        self.tracker.msg.debug(
            f">> PropertiesChanged | {self.bus_name=} | {iface_name=} | {properties=}"
        )
        if iface_name != IFACE_MPRIS_PLAYER:
            return

        updated = False

        if 'Metadata' in properties:
            # Player is playing a new video. We pass the title
            # to the tracker and start our playing timer.
            self.filename = _get_filename(properties['Metadata'])
            updated = True

        if 'PlaybackStatus' in properties:
            self.status = properties['PlaybackStatus']
            updated = True

        if updated:
            self.tracker._handle_player_update(self)

    def disconnect(self):
        self.subscription.disconnect()

    def __repr__(self):
        return f'Player({self.bus_name=}; {self.filename=}; {self.status=})'


class MPRISTracker(tracker.TrackerBase):

    name = 'Tracker (MPRIS)'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.re_players = re.compile(self.config['tracker_process'])
        # Maps "OwnerName"s to Player instances
        # for monitoring when one appears or disappears
        # via the `NameOwnerChanged` signal.
        self.players = {}
        self.timing = False
        self.active_player = None

    def observe(self, _config, _watch_dirs):
        self.msg.info("Using MPRIS.")

        self.session = SessionBus()
        self.bus = self.session.get('org.freedesktop.DBus')

        # Look for already running players and connect them
        for bus_name in self.bus.ListNames():
            if bus_name.startswith(BUS_NAME_PREFIX):
                self._connect(bus_name)

        # Connect signal for any new players that could appear
        self.bus.NameOwnerChanged.connect(self._new_name)

        # Run GLib loop
        loop = GLib.MainLoop()
        loop.run()

    def _connect(self, bus_name):
        if not self.re_players.search(bus_name):
            self.msg.info(f"Ignoring unknown player: {bus_name}")
            return

        try:
            sender = self.bus.GetNameOwner(bus_name)
        except GLib.Error:
            self.msg.warn(f"Bus was closed before access: {bus_name}")
            return

        self.msg.info(f"Connecting to MPRIS player: {bus_name} ({sender})")
        try:
            player = Player(self, bus_name)
            self.msg.debug(f"{player=}")
            self.players[sender] = player
            self._handle_player_update(player)

        except GLib.Error:
            self.msg.warn(f"Could not initialize player: {bus_name}")

    def _handle_player_update(self, player):
        # self.msg.debug(f"{self.active_player=} | {player=}")
        if player == self.active_player:
            if player.status == "Stopped":
                self._player_stopped()
            else:
                self._update_active_player(player)

        elif self.active_player and self.active_player.status == "Playing":
            self.msg.debug("Still playing on active player; ignoring update")
            return

        elif player.status != "Stopped":
            self._update_active_player(player)

    def _update_active_player(self, player):
        if player.status == "Playing":
            self._start_timer()
        else:
            self._stop_timer()

        if player.filename == self.last_filename:
            return
        self.msg.debug(f"New video: {player.filename}")

        (state, show_tuple) = self._get_playing_show(player.filename)
        if state == utils.Tracker.UNRECOGNIZED:
            self.msg.debug("Video not recognized")
            return
        elif state == utils.Tracker.NOVIDEO:
            self.msg.debug("No video loaded")
            return

        self.msg.debug(f"New tracker status: {state} (previously: {self.last_state})")
        self.update_show_if_needed(state, show_tuple)

        if player != self.active_player:
            self.msg.debug(f"Setting active player: {player}")
            self.active_player = player

    def _player_stopped(self):
        # Active player got closed!
        self.msg.debug(f"Clearing active player: {self.active_player}")
        self.active_player = None
        self.view_offset = None

        # TODO look through other playing players?
        (state, show_tuple) = self._get_playing_show(None)
        self.update_show_if_needed(state, show_tuple)

        self._stop_timer()

    def _new_name(self, bus_name, old_name, new_name):
        if not bus_name.startswith(IFACE_MPRIS):
            return
        self.msg.debug(f'>> NameOwnerChanged | {bus_name=} {old_name=} {new_name=}')
        if new_name:
            self._connect(bus_name)
        if old_name:
            self._disconnect(old_name)

    def _disconnect(self, sender):
        player = self.players.pop(sender, None)
        if not player:
            return
        self.msg.debug(f"Player disconnected: {player}")
        player.disconnect()
        if player == self.active_player:
            self._player_stopped()
            self.active_player = None

    def _start_timer(self):
        self.resume_timer()
        if not self.timing:
            self.msg.debug("Starting MPRIS timer.")
            self.timing = True

            self._on_timer()
            GLib.timeout_add_seconds(1, self._on_timer)

    def _stop_timer(self):
        self.pause_timer()
        self.timing = False

    def _on_timer(self):
        if self.active_player:
            self.view_offset = int(self.active_player.mpris_player.Position) / 1000
        if self.last_show_tuple:
            self.update_timer(self.last_state, self.last_show_tuple)
        if self.last_updated:
            self._stop_timer()
        return self.timing

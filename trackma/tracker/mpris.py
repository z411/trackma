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
from __future__ import annotations

import asyncio
import os
import re
import sys
import threading
import time
import urllib.parse
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from jeepney import DBusAddress, HeaderFields, Properties
from jeepney.bus_messages import MatchRule, message_bus
from jeepney.io.asyncio import DBusRouter, Proxy, open_dbus_router

from trackma import utils

from .tracker import (
    OnPlaybackCallback,
    OnStateCallback,
    OnTickCallback,
    TrackerBase,
    TrackerResolution,
)

__all__ = [
    'MprisTracker',
]


BUS_NAMESPACE = 'org.mpris.MediaPlayer2'
PATH_MPRIS = '/org/mpris/MediaPlayer2'
IFACE_PROPERTIES = 'org.freedesktop.DBus.Properties'
IFACE_MPRIS = 'org.mpris.MediaPlayer2'
IFACE_MPRIS_PLAYER = IFACE_MPRIS + '.Player'


class PlaybackStatus(str, Enum):
    PLAYING = 'Playing'
    PAUSED = 'Paused'
    STOPPED = 'Stopped'


def safe_get_dbus_value(pair, type_):
    """Assert the value's type before returning it None-safely."""
    if pair is None:
        return None
    if pair[0] != type_:
        msg = f"Expected type {type_!r} but found {pair[0]!r}; value: {pair[1]!r}"
        raise TypeError(msg)
    return pair[1]


async def collect_names(router) -> dict[str, str]:
    """Find all active buses in the known namespace mapped by their unique name."""
    message_proxy = Proxy(message_bus, router)
    resp = await message_proxy.ListNames()
    names = [name for name in resp[0] if name.startswith(BUS_NAMESPACE)]
    unique_names = await asyncio.gather(*(message_proxy.GetNameOwner(name) for name in names))
    name_map = {un[0]: n for un, n in zip(unique_names, names)}
    return name_map


@dataclass
class Player:
    config: dict[str, Any]
    router: DBusRouter
    wellknown_name: str
    unique_name: str
    playback_status: str | None = None
    title: str | None = None
    url: str | None = None

    @classmethod
    async def new(cls, config, router, wellknown_name, unique_name):
        player = Player(config, router, wellknown_name, unique_name)
        await asyncio.gather(
            player.update_filename(),
            player.update_playback_status(),
        )
        return player

    @property
    def filename(self):
        if self.url:
            unquoted_url = urllib.parse.unquote_plus(self.url)
            # We only trust URLs using the file protocol to be full paths.
            if self.config['library_full_path'] and unquoted_url.startswith('file://'):
                return unquoted_url.removeprefix('file://')
            return os.path.basename(unquoted_url)
        return self.title

    async def update_filename(self):
        msg = self._player_properties.get('Metadata')
        reply = await self.router.send_and_get_reply(msg)
        metadata = safe_get_dbus_value(reply.body[0], 'a{sv}')
        if metadata:
            self.title = safe_get_dbus_value(metadata.get('xesam:title'), 's')
            self.url = safe_get_dbus_value(metadata.get('xesam:url'), 's')
        else:
            self.title = None
            self.url = None

    async def update_playback_status(self):
        msg = self._player_properties.get('PlaybackStatus')
        reply = await self.router.send_and_get_reply(msg)
        self.playback_status = safe_get_dbus_value(reply.body[0], 's')

    async def get_position(self):
        msg = self._player_properties.get('Position')
        reply = await self.router.send_and_get_reply(msg)
        return safe_get_dbus_value(reply.body[0], 'x')

    @property
    def _player_properties(self):
        address = DBusAddress(PATH_MPRIS, bus_name=self.unique_name, interface=IFACE_MPRIS_PLAYER)
        return Properties(address)


class MprisDbusWatcher:

    def __init__(
        self,
        config: dict[str, Any],
        msg,
        resolve_playing_show: Callable[[str | None], TrackerResolution],
        on_state: OnStateCallback,
        on_playback: OnPlaybackCallback,
        on_tick: OnTickCallback,
    ):
        # Note: all these should be considered private.
        self.config = config
        self.msg = msg
        self.resolve_playing_show: Callable[[str | None], TrackerResolution] = resolve_playing_show
        self.on_state: OnStateCallback = on_state
        self.on_playback: OnPlaybackCallback = on_playback
        self.on_tick: OnTickCallback = on_tick

        self.re_players = re.compile(self.config['tracker_process'])
        # Map "OwnerName"s to Player instances
        # for monitoring when one appears or disappears
        # via the `NameOwnerChanged` signal.
        self.players: dict[str, Player] = {}
        self.active_player: Player | None = None
        self.active_filename: str | None = None
        self.active_resolution: TrackerResolution = TrackerResolution.NO_VIDEO()
        self.timing = False

    async def run(self):
        async with open_dbus_router() as router:
            name_owner_watcher_task = asyncio.create_task(self.name_owner_watcher(router))
            properties_watcher_task = asyncio.create_task(self.properties_watcher(router))
            timer_task = asyncio.create_task(self._timer())
            tasks = [name_owner_watcher_task, properties_watcher_task, timer_task]

            name_map = await collect_names(router)
            self.players = {
                unique_name: await Player.new(self.config, router, wellknown_name, unique_name)
                for unique_name, wellknown_name in name_map.items()
                if self.valid_player(wellknown_name)
            }
            ignored_players = [name for name in name_map.values() if not self.valid_player(name)]
            self.msg.debug(f"Ignoring players: {ignored_players}")
            for player in self.players.values():
                self.msg.debug(f"Player connected: {player.wellknown_name}")

            self.reselect()

            try:
                await asyncio.gather(*tasks)
            except Exception:
                self.msg.exception("Error in dbus watchers; cleaning up", sys.exc_info())
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks)

    async def name_owner_watcher(self, router):
        # Select name change signals for the well-known mpris service name.
        # We only consider players with such a well-known name
        # and thus treat any changes to the owned name
        # as a creation and a disappearance of a service.
        # Signals will be published by the service's unique name,
        # which is why we need to track it.
        match_rule = MatchRule(
            type='signal',
            sender=message_bus.bus_name,
            interface=message_bus.interface,
            member='NameOwnerChanged',
            path=message_bus.object_path,
        )
        match_rule.add_arg_condition(0, BUS_NAMESPACE, kind='namespace')

        message_proxy = Proxy(message_bus, router)
        await message_proxy.AddMatch(match_rule)

        with router.filter(match_rule, bufsize=20) as queue:
            while True:
                # https://dbus.freedesktop.org/doc/dbus-specification.html#bus-messages-name-owner-changed
                msg = await queue.get()
                (wellknown_name, old_name, new_name) = msg.body
                if old_name:
                    self.on_bus_removed(old_name)
                if new_name:
                    await self.on_bus_added(router, wellknown_name, new_name)

    async def on_bus_added(self, router, wellknown_name, unique_name):
        if not self.valid_player(wellknown_name):
            self.msg.debug("Ignoring new bus that does not match configured player:"
                           f" {wellknown_name}")
            return
        player = await Player.new(self.config, router, wellknown_name, unique_name)
        self.msg.debug(f"Player connected: {player.wellknown_name}")
        self.players[unique_name] = player
        self._handle_player_update(player)

    def on_bus_removed(self, unique_name):
        player = self.players.pop(unique_name, None)
        if not player:
            return
        self.msg.debug(f"Player disconnected: {player.wellknown_name}")
        if player == self.active_player:
            self.clear_state()
            self.reselect()

    async def properties_watcher(self, router):
        # Select PropertiesChanged signals for the mpris-player subinterface
        # for all senders.
        match_rule = MatchRule(
            type='signal',
            sender=None,
            interface=IFACE_PROPERTIES,
            member='PropertiesChanged',
            path=PATH_MPRIS,
        )
        match_rule.add_arg_condition(0, IFACE_MPRIS_PLAYER)

        message_proxy = Proxy(message_bus, router)
        await message_proxy.AddMatch(match_rule)

        with router.filter(match_rule, bufsize=10) as queue:
            while True:
                msg = await queue.get()
                self.handle_properties_changed(msg)

    def handle_properties_changed(self, msg):
        # https://dbus.freedesktop.org/doc/dbus-specification.html#standard-interfaces-properties
        (_, changed_properties, _) = msg.body
        sender = msg.header.fields[HeaderFields.sender]
        try:
            playback_status = safe_get_dbus_value(changed_properties.get('PlaybackStatus'), 's')
            if playback_status:
                self.on_playback_status_change(sender, playback_status)

            metadata = safe_get_dbus_value(changed_properties.get('Metadata'), 'a{sv}')
            if metadata and ('xesam:title' in metadata or 'xesam:url' in metadata):
                title = safe_get_dbus_value(metadata.get('xesam:title'), 's')
                url = safe_get_dbus_value(metadata.get('xesam:url'), 's')
                self.on_filename_change(sender, title, url)
        except TypeError as e:
            self.msg.warn(f"Failed to read properties for {sender}: {e}")

    def valid_player(self, wellknown_name: str) -> re.Match[str] | None:
        return self.re_players.search(wellknown_name)

    def reselect(self):
        # Prioritize active player if it is still playing.
        if (
            self.active_player
            and self.active_player.playback_status == PlaybackStatus.PLAYING
            and self._activate_player(self.active_player)
        ):
            return

        # Go through all connected players in random order
        # (or not since dicts are ordered now).
        for player in self.players.values():
            if player.playback_status == PlaybackStatus.PLAYING and self._activate_player(player):
                return

        self.clear_state()

    def on_playback_status_change(self, sender: str, playback_status: str) -> None:
        player = self.players.get(sender)
        if not player:
            return
        player.playback_status = playback_status
        self._handle_player_update(player)

    def on_filename_change(self, sender: str, title: str | None, url: str | None) -> None:
        player = self.players.get(sender)
        if not player:
            return
        player.title = title
        player.url = url
        self._handle_player_update(player)

    def _handle_player_update(self, player: Player) -> None:
        if player == self.active_player:
            if player.playback_status == PlaybackStatus.STOPPED:
                self.clear_state()
                self.reselect()
            else:
                resolution = self._resolve_player(player)
                self._commit_resolution(resolution)

        elif (
            self.active_player
            and self.active_player.playback_status == PlaybackStatus.PLAYING
            and self.active_resolution.state == utils.Tracker.PLAYING
        ):
            self.msg.debug("Still playing on active player; ignoring update")

        elif player.playback_status == PlaybackStatus.PLAYING:
            self._activate_player(player)

    def _activate_player(self, player: Player) -> bool:
        resolution = self._resolve_player(player)

        if player != self.active_player:
            self.msg.debug(f"Setting active player: {player.wellknown_name}")
            self.active_player = player

        self._commit_resolution(resolution)
        return resolution.state == utils.Tracker.PLAYING

    def _resolve_player(self, player: Player) -> TrackerResolution:
        filename = player.filename
        if filename == self.active_filename:
            return self.active_resolution

        return self.resolve_playing_show(filename)

    def _commit_resolution(
        self,
        resolution: TrackerResolution,
    ) -> None:
        if not self.active_player:
            return

        playing = (
            self.active_player.playback_status == PlaybackStatus.PLAYING
            and resolution.state == utils.Tracker.PLAYING
        )
        self._set_timer_state(playing)

        if resolution == self.active_resolution:
            return

        self.msg.debug(f"New tracker status: {resolution.state} (previously: {self.active_resolution[0]})")
        self.active_resolution = resolution
        self.active_filename = self.active_player.filename
        self.on_state(resolution, self.active_player.filename)

    def clear_state(self) -> None:
        if self.active_player:
            self.msg.debug(f"Clearing active player: {self.active_player.wellknown_name}")
        self.active_player = None
        self.active_filename = None
        self.active_resolution = TrackerResolution.NO_VIDEO()
        self.on_state(TrackerResolution.NO_VIDEO(), None)
        self._set_timer_state(False)

    def _set_timer_state(self, playing: bool) -> None:
        if playing and not self.timing:
            self.timing = True
            self.msg.debug("MPRIS timer started.")
            self.on_playback(True)
        elif not playing and self.timing:
            self.timing = False
            self.msg.debug("MPRIS timer paused.")
            self.on_playback(False)

    async def _timer(self):
        while True:
            if self.timing:
                await self._on_tick()
            await asyncio.sleep(1, True)

    async def _on_tick(self) -> None:
        if self.active_player:
            try:
                position = await self.active_player.get_position()
                view_offset = int(position) / 1000 if position is not None else None
            except TypeError:
                view_offset = None
        else:
            view_offset = None

        self.on_tick(view_offset)


class MprisTracker(TrackerBase):

    name = 'Tracker (MPRIS)'

    def __init__(self, *args, **kwargs):
        self.initialized = threading.Event()
        super().__init__(*args, **kwargs)

        self.watcher = MprisDbusWatcher(
            self.config,
            self.msg,
            resolve_playing_show=self.resolve_playing_show,
            on_state=self._on_tracker_state,
            on_playback=self._on_tracker_playback,
            on_tick=self._on_tracker_tick,
        )
        self.initialized.set()

    def update_list(self, *args, **kwargs):
        super().update_list(*args, **kwargs)
        self.watcher.clear_state()
        self.watcher.reselect()

    def observe(self, _config, _watch_dirs):
        self.msg.info("Using MPRIS.")
        self.initialized.wait()

        start_times = deque(maxlen=5)
        while len(start_times) < 5 or start_times[0] + 60 < time.time():
            start_times.append(time.time())
            asyncio.run(self.watcher.run())
            time.sleep(5)

        self.msg.warn("Reached restart limit for MPRIS tracker.")

    def _on_tracker_state(
        self,
        resolution: TrackerResolution,
        filename: str | None,
    ) -> None:
        self.update_show_if_needed(resolution, filename)

    def _on_tracker_playback(self, playing: bool) -> None:
        if playing:
            self.resume_timer()
        else:
            self.pause_timer()

    def _on_tracker_tick(self, view_offset: float | None) -> None:
        self.view_offset = view_offset
        self.update_timer()

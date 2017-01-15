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

import threading
import re
import time
import os

import ctypes

from trackma import messenger
from trackma import utils
from trackma.extras import AnimeInfoExtractor

class TrackerBase(object):
    msg = None
    active = True
    list = None
    last_show_tuple = None
    last_filename = None
    last_state = utils.TRACKER_NOVIDEO
    last_time = 0
    last_updated = False
    last_close_queue = None
    timer = None

    name = 'Tracker'

    signals = {
               'state': None,
               'detected': None,
               'playing': None,
               'removed': None,
               'update': None,
               'unrecognised': None,
              }

    def __init__(self, messenger, tracker_list, process_name, watch_dir, interval, update_wait, update_close, not_found_prompt):
        self.msg = messenger
        self.msg.info(self.name, 'Initializing...')

        self.list = tracker_list
        self.process_name = process_name

        tracker_args = (watch_dir, interval)
        self.wait_s = update_wait
        self.wait_close = update_close
        self.not_found_prompt = not_found_prompt
        tracker_t = threading.Thread(target=self.observe, args=tracker_args)
        tracker_t.daemon = True
        self.msg.debug(self.name, 'Enabling tracker...')
        tracker_t.start()

    def set_message_handler(self, message_handler):
        """Changes the message handler function on the fly."""
        self.msg = message_handler

    def disable(self):
        self.active = False

    def enable(self):
        self.active = True

    def update_list(self, tracker_list):
        self.list = tracker_list

    def connect_signal(self, signal, callback):
        try:
            self.signals[signal] = callback
        except KeyError:
            raise utils.EngineFatal("Invalid signal.")

    def observe(self, watch_dir, interval):
        raise NotImplementedError

    def get_status(self):
        return {
            'state': self.last_state,
            'timer': self.timer,
            'show': self.last_show_tuple,
            'filename': self.last_filename,
        }

    def _emit_signal(self, signal, *args):
        try:
            if self.signals[signal]:
                self.signals[signal](*args)
        except KeyError:
            raise Exception("Call to undefined signal.")

    def _update_show(self, state, show_tuple):
        (show, episode) = show_tuple
        self.timer = int(1 + self.wait_s - (time.time() - self.last_time))
        self._emit_signal('state', state, self.timer)

        if self.timer <= 0:
            # Perform show update
            self.last_updated = True
            action = None
            if state == utils.TRACKER_PLAYING:
                action = lambda: self._emit_signal('update', show['id'], episode)
            elif state == utils.TRACKER_NOT_FOUND:
                action = lambda: self._emit_signal('unrecognised', show, episode)

            if self.wait_close:
                self.msg.info(self.name, 'Waiting for the player to close.')
                self.last_close_queue = action
            elif action:
                action()

    def _update_state(self, state):
        # Call when show or state is changed. Perform queued update if any, and clear playing flag.
        if self.last_close_queue:
            self.last_close_queue()
            self.last_close_queue = None
        self.last_time = time.time()
        if self.last_show_tuple and self.last_state == utils.TRACKER_PLAYING:
            (last_show, last_show_ep) = self.last_show_tuple
            self._emit_signal('playing', last_show['id'], False, last_show_ep)

    def update_show_if_needed(self, state, show_tuple):
        # If the state and show are unchanged, skip to countdown
        if show_tuple and state == self.last_state and show_tuple == self.last_show_tuple and not self.last_updated:
            self._update_show(state, show_tuple)
            return

        if show_tuple and show_tuple != self.last_show_tuple:
            (show, episode) = show_tuple
            self._update_state(state)
            # There's a new show/ep detected, so let's save the show information
            self.last_show_tuple = show_tuple
            if state == utils.TRACKER_PLAYING:
                self._emit_signal('playing', show['id'], True, episode)
                # Check if we shouldn't update the show
                if episode != (show['my_progress'] + 1):
                    self.msg.warn(self.name, 'Player is not playing the next episode of %s. Ignoring.' % show['title'])
                    self.last_updated = True
                    self.last_state = utils.TRACKER_IGNORED
                    self._emit_signal('state', utils.TRACKER_IGNORED, None)
                    return

            # Start our countdown
            (show, episode) = show_tuple
            if state == utils.TRACKER_PLAYING:
                self.msg.info(self.name, 'Will update %s %d in %d seconds' % (show['title'], episode, self.wait_s))
            elif state == utils.TRACKER_NOT_FOUND:
                self.msg.info(self.name, 'Will add %s %d in %d seconds' % (show, episode, self.wait_s))
            self._update_show(state, show_tuple)

        elif self.last_state != state:
            self._update_state(state)

            # React depending on state
            if state == utils.TRACKER_NOVIDEO:  # No video is playing
                # Video didn't get to update phase before it was closed
                if self.last_state == utils.TRACKER_PLAYING and not self.last_updated:
                    self.msg.info(self.name, 'Player was closed before update.')
            elif state == utils.TRACKER_UNRECOGNIZED:  # There's a new video playing but the regex didn't recognize the format
                self.msg.warn(self.name, 'Found video but the file name format couldn\'t be recognized.')
            elif state == utils.TRACKER_NOT_FOUND:  # There's a new video playing but an associated show wasn't found
                self.msg.warn(self.name, 'Found player but show not in list.')

            self.last_show_tuple = None
            self.last_updated = False
            self.timer = None
            self._emit_signal('state', state, None)

        self.last_state = state

    def _get_playing_show(self, filename):
        if not self.active:
            # Don't do anything if the Tracker is disabled
            return (utils.TRACKER_NOVIDEO, None)

        if filename:
            if filename == self.last_filename:
                # It's the exact same filename, there's no need to do the processing again
                return (self.last_state, self.last_show_tuple)

            self.last_filename = filename

            # Do a regex to the filename to get
            # the show title and episode number
            aie = AnimeInfoExtractor(filename)
            (show_title, show_ep) = (aie.getName(), aie.getEpisode())
            if not show_title:
                return (utils.TRACKER_UNRECOGNIZED, None)  # Format not recognized

            playing_show = utils.guess_show(show_title, self.list)
            if playing_show:
                return (utils.TRACKER_PLAYING, (playing_show, show_ep))
            else:
                # Show not in list
                if self.not_found_prompt:
                    return (utils.TRACKER_NOT_FOUND, (show_title, show_ep))
                else:
                    return (utils.TRACKER_NOT_FOUND, None)
        else:
            self.last_filename = None
            return (utils.TRACKER_NOVIDEO, None)  # Not playing

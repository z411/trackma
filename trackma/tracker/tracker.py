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

<<<<<<< HEAD
    def __init__(self, messenger, tracker_list, process_name, watch_dir, interval, update_wait, update_close, not_found_prompt):
=======
    def __init__(self, messenger, tracker_list, config, watch_dirs, redirections=None):
>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34
        self.msg = messenger
        self.msg.info(self.name, 'Initializing...')

        self.list = tracker_list
<<<<<<< HEAD
        self.process_name = process_name

        tracker_args = (utils.expand_path(watch_dir), interval)
        self.wait_s = update_wait
        self.wait_close = update_close
        self.not_found_prompt = not_found_prompt
        tracker_t = threading.Thread(target=self.observe, args=tracker_args)
        tracker_t.daemon = True
=======
        self.config = config
        self.redirections = redirections
        # Reverse sorting for prefix matching
        self.watch_dirs = tuple(sorted(watch_dirs, reverse=True))
        self.wait_s = None

        self.timer = None
        self.timer_paused = None
        self.timer_offset = 0

        tracker_args = (config, watch_dirs)
        tracker_t = threading.Thread(target=self.observe, args=tracker_args)
        tracker_t.daemon = True

>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34
        self.msg.debug(self.name, 'Enabling tracker...')
        tracker_t.start()

    def set_message_handler(self, message_handler):
        """Changes the message handler function on the fly."""
        self.msg = message_handler

    def disable(self):
<<<<<<< HEAD
        self.active = False

    def enable(self):
        self.active = True

=======
        self.msg.info(self.name, 'Unloading...')
        self.active = False

>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34
    def update_list(self, tracker_list):
        self.list = tracker_list

    def connect_signal(self, signal, callback):
        try:
            self.signals[signal] = callback
        except KeyError:
            raise utils.EngineFatal("Invalid signal.")

<<<<<<< HEAD
    def observe(self, watch_dir, interval):
=======
    def observe(self, config, watch_dirs):
>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34
        raise NotImplementedError

    def get_status(self):
        return {
            'state': self.last_state,
            'timer': self.timer,
<<<<<<< HEAD
=======
            'paused': bool(self.timer_paused),
>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34
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
<<<<<<< HEAD
        (show, episode) = show_tuple
        self.timer = int(1 + self.wait_s - (time.time() - self.last_time))
        self._emit_signal('state', state, self.timer)
=======
        if self.timer_paused:
            return

        (show, episode) = show_tuple

        self.timer = int(1 + (self.wait_s or self.config['tracker_update_wait_s']) + self.timer_offset - (time.time() - self.last_time))
        self._emit_signal('state', self.get_status())
>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34

        if self.timer <= 0:
            # Perform show update
            self.last_updated = True
            action = None
            if state == utils.TRACKER_PLAYING:
<<<<<<< HEAD
                action = lambda: self._emit_signal('update', show['id'], episode)
            elif state == utils.TRACKER_NOT_FOUND:
                action = lambda: self._emit_signal('unrecognised', show['title'], episode)

            if self.wait_close:
=======
                action = lambda: self._emit_signal('update', show, episode)
            elif state == utils.TRACKER_NOT_FOUND:
                action = lambda: self._emit_signal('unrecognised', show, episode)

            if self.config['tracker_update_close']:
>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34
                self.msg.info(self.name, 'Waiting for the player to close.')
                self.last_close_queue = action
            elif action:
                action()

    def _ignore_current(self):
        # Stops attempt to update current episode
        self.last_updated = True
        self.last_state = utils.TRACKER_IGNORED
        self.timer = None
<<<<<<< HEAD
        self._emit_signal('state', utils.TRACKER_IGNORED, None)

    def _update_state(self, state):
        # Call when show or state is changed. Perform queued update if any, and clear playing flag.
        if self.last_close_queue:
            self.last_close_queue()
            self.last_close_queue = None
        self.last_time = time.time()
=======
        self._emit_signal('state', self.get_status())

    def _update_state(self, state):
        # Call when show or state is changed. Perform queued update if any.
        if self.last_close_queue:
            self.last_close_queue()
            self.last_close_queue = None

        # Clear up pause and set our new time offset
        self.timer_paused = None
        self.timer_offset = 0
        self.last_time = time.time()

        # Emit the new playing signal
>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34
        if self.last_show_tuple:
            (last_show, last_show_ep) = self.last_show_tuple
            if last_show['id']:
                self._emit_signal('playing', last_show['id'], False, last_show_ep)

<<<<<<< HEAD
=======
    def pause_timer(self):
        if not self.timer_paused:
            self.timer_paused = time.time()

            self._emit_signal('state', self.get_status())

    def resume_timer(self):
        if self.timer_paused:
            self.timer_offset += time.time() - self.timer_paused
            self.timer_paused = None

            self._emit_signal('state', self.get_status())

>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34
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
            self.last_updated = False
            if state == utils.TRACKER_PLAYING:
                self._emit_signal('playing', show['id'], True, episode)
                # Check if we shouldn't update the show
<<<<<<< HEAD
                if episode != (show['my_progress'] + 1):
                    self.msg.warn(self.name, 'Not playing the next episode of %s. Ignoring.' % show['title'])
                    self._ignore_current()
                    return
=======
                if self.config['tracker_ignore_not_next'] and episode != (show['my_progress'] + 1):
                    self.msg.warn(self.name, 'Not playing the next episode of %s. Ignoring.' % show['title'])
                    self._ignore_current()
                    return
                if episode == show['my_progress']:
                    self.msg.warn(self.name, 'Playing the current episode of %s. Ignoring.' % show['title'])
                    self._ignore_current()
                    return
>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34
                if episode < 1 or (show['total'] and episode > show['total']):
                    self.msg.warn(self.name, 'Playing an invalid episode of %s. Ignoring.' % show['title'])
                    self._ignore_current()
                    return

            # Start our countdown
            (show, episode) = show_tuple
            if state == utils.TRACKER_PLAYING:
<<<<<<< HEAD
                self.msg.info(self.name, 'Will update %s %d in %d seconds' % (show['title'], episode, self.wait_s))
            elif state == utils.TRACKER_NOT_FOUND:
                self.msg.info(self.name, 'Will add %s %d in %d seconds' % (show['title'], episode, self.wait_s))
            self._update_show(state, show_tuple)

=======
                self.msg.info(self.name, 'Will update %s %d' % (show['title'], episode))
            elif state == utils.TRACKER_NOT_FOUND:
                self.msg.info(self.name, 'Will add %s %d' % (show['title'], episode))

            self._update_show(state, show_tuple)
>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34
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
<<<<<<< HEAD
            self._emit_signal('state', state, None)

        self.last_state = state
=======

        self.last_state = state
        self._emit_signal('state', self.get_status())
>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34

    def _get_playing_show(self, filename):
        if not self.active:
            # Don't do anything if the Tracker is disabled
            return (utils.TRACKER_NOVIDEO, None)

        if filename:
<<<<<<< HEAD
            if filename == self.last_filename:
                # It's the exact same filename, there's no need to do the processing again
=======
            self.msg.debug(self.name, "Guessing filename: {}".format(filename))

            # Trim out watch dir
            if os.path.isabs(filename):
                for watch_prefix in self.watch_dirs:
                    if filename.startswith(watch_prefix):
                        filename = filename[len(watch_prefix):]
                        if filename.startswith(os.path.sep):
                            filename = filename[len(os.path.sep):]
                        break

            if filename == self.last_filename:
                # It's the exact same filename, there's no need to do the processing again
                self.msg.debug(self.name, "Same filename as before. Skipping.")
>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34
                return (self.last_state, self.last_show_tuple)

            self.last_filename = filename

            # Do a regex to the filename to get
            # the show title and episode number
            aie = AnimeInfoExtractor(filename)
            (show_title, show_ep) = (aie.getName(), aie.getEpisode())
            if not show_title:
                return (utils.TRACKER_UNRECOGNIZED, None)  # Format not recognized

            playing_show = utils.guess_show(show_title, self.list)
<<<<<<< HEAD
            if playing_show:
                return (utils.TRACKER_PLAYING, (playing_show, show_ep))
            else:
                # Show not in list
                if self.not_found_prompt:
=======
            self.msg.debug(self.name, "Show guess: {}: {}".format(show_title, playing_show))

            if playing_show:
                (playing_show, show_ep) = utils.redirect_show((playing_show, show_ep), self.redirections, self.list)

                return (utils.TRACKER_PLAYING, (playing_show, show_ep))
            else:
                # Show not in list
                if self.config['tracker_not_found_prompt']:
>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34
                    # Dummy show to search for
                    show = {'id': 0, 'title': show_title}
                    return (utils.TRACKER_NOT_FOUND, (show, show_ep))
                else:
                    return (utils.TRACKER_NOT_FOUND, None)
        else:
            self.last_filename = None
            return (utils.TRACKER_NOVIDEO, None)  # Not playing

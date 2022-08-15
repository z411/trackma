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
import threading
import time

from trackma import utils
from trackma.extras import AnimeInfoExtractor


class TrackerBase(object):
    msg = None
    active = True
    list = None
    last_show_tuple = None
    last_filename = None
    last_state = utils.Tracker.NOVIDEO
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

    def __init__(self, messenger, tracker_list, config, watch_dirs, redirections=None):
        self.msg = messenger.with_classname(self.name)
        self.msg.info('Initializing...')

        self.list = tracker_list
        self.config = config
        self.redirections = redirections
        # Reverse sorting for prefix matching
        self.watch_dirs = tuple(sorted(watch_dirs, reverse=True))
        self.wait_s = None

        self.timer = None
        self.timer_paused = None
        self.timer_offset = 0

        self.view_offset = None

        tracker_args = (config, watch_dirs)
        tracker_t = threading.Thread(target=self.observe, args=tracker_args)
        tracker_t.daemon = True

        self.msg.debug('Enabling tracker...')
        tracker_t.start()

    def set_message_handler(self, message_handler):
        """Changes the message handler function on the fly."""
        self.msg = message_handler.with_classname(self.name)

    def disable(self):
        self.msg.info('Unloading...')
        self.active = False

    def update_list(self, tracker_list):
        self.list = tracker_list

    def connect_signal(self, signal, callback):
        try:
            self.signals[signal] = callback
        except KeyError:
            raise utils.EngineFatal("Invalid signal.")

    def observe(self, config, watch_dirs):
        raise NotImplementedError

    def get_status(self):
        return {
            'state': self.last_state,
            'timer': self.timer,
            'viewOffset': self.view_offset,
            'paused': bool(self.timer_paused),
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
        if self.timer_paused:
            return

        (show, episode) = show_tuple

        self.timer = int(
            1 + (self.wait_s or self.config['tracker_update_wait_s']) + self.timer_offset - (time.time() - self.last_time))
        self._emit_signal('state', self.get_status())

        if self.timer <= 0:
            # Perform show update
            self.last_updated = True
            action = None
            if state == utils.Tracker.PLAYING:
                def action(): return self._emit_signal('update', show, episode)
            elif state == utils.Tracker.NOT_FOUND:
                def action(): return self._emit_signal('unrecognised', show, episode)

            if self.config['tracker_update_close']:
                self.msg.info('Waiting for the player to close.')
                self.last_close_queue = action
            elif action:
                action()

    def _ignore_current(self):
        # Stops attempt to update current episode
        self.last_updated = True
        self.last_state = utils.Tracker.IGNORED
        self.timer = None
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
        if self.last_show_tuple:
            (last_show, last_show_ep) = self.last_show_tuple
            if last_show['id']:
                self._emit_signal(
                    'playing', last_show['id'], False, last_show_ep)

    def pause_timer(self):
        if not self.timer_paused:
            self.timer_paused = time.time()

            self._emit_signal('state', self.get_status())

    def resume_timer(self):
        if self.timer_paused:
            self.timer_offset += time.time() - self.timer_paused
            self.timer_paused = None

            self._emit_signal('state', self.get_status())

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
            if state == utils.Tracker.PLAYING:
                self._emit_signal('playing', show['id'], True, episode)
                # Check if we shouldn't update the show
                expected_next_ep = show['my_progress'] + 1
                if self.config['tracker_ignore_not_next'] and episode != expected_next_ep:
                    self.msg.warn(
                        'Not playing the next episode of {} (expected: {}, found: {}). Ignoring.'
                            .format(show['title'], expected_next_ep, episode),
                    )
                    self._ignore_current()
                    return
                if episode == show['my_progress']:
                    self.msg.warn('Playing the current episode of %s. Ignoring.' % show['title'])
                    self._ignore_current()
                    return
                if episode < 1 or (show['total'] and episode > show['total']):
                    self.msg.warn('Playing an invalid episode of %s. Ignoring.' % show['title'])
                    self._ignore_current()
                    return

            # Start our countdown
            (show, episode) = show_tuple
            if state == utils.Tracker.PLAYING:
                self.msg.info('Will update %s %d' %
                              (show['title'], episode))
            elif state == utils.Tracker.NOT_FOUND:
                self.msg.info('Will add %s %d' %
                              (show['title'], episode))

            self._update_show(state, show_tuple)
        elif self.last_state != state:
            self._update_state(state)

            # React depending on state
            if state == utils.Tracker.NOVIDEO:  # No video is playing
                # Video didn't get to update phase before it was closed
                if self.last_state == utils.Tracker.PLAYING and not self.last_updated:
                    self.msg.info('Player was closed before update.')
            # There's a new video playing but the regex didn't recognize the format
            elif state == utils.Tracker.UNRECOGNIZED:
                self.msg.warn('Found video but the file name format couldn\'t be recognized.')
            elif state == utils.Tracker.NOT_FOUND:  # There's a new video playing but an associated show wasn't found
                self.msg.warn('Found player but show not in list.')

            self.last_show_tuple = None
            self.last_updated = False
            self.timer = None

        self.last_state = state
        self._emit_signal('state', self.get_status())

    def _get_playing_show(self, filename):
        if not self.active:
            # Don't do anything if the Tracker is disabled
            return (utils.Tracker.NOVIDEO, None)

        if filename:
            self.msg.debug("Guessing filename: {}".format(filename))

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
                self.msg.debug("Same filename as before. Skipping.")
                return (self.last_state, self.last_show_tuple)

            self.last_filename = filename

            # Do a regex to the filename to get
            # the show title and episode number
            aie = AnimeInfoExtractor(filename)
            (show_title, show_ep) = (aie.getName(), aie.getEpisode())
            if not show_title:
                # Format not recognized
                return (utils.Tracker.UNRECOGNIZED, None)

            playing_show = utils.guess_show(show_title, self.list)
            self.msg.debug("Show guess: {}: {} ({})".format(
                show_title, playing_show, show_ep))

            if playing_show:
                (redirected_show, redirected_ep) = utils.redirect_show(
                    (playing_show, show_ep), self.redirections, self.list)
                if (redirected_show, redirected_ep) != (playing_show, show_ep):
                    self.msg.debug("Redirected to: {} ({})".format(redirected_show, redirected_ep))
                    (playing_show, show_ep) = (redirected_show, redirected_ep)

                return (utils.Tracker.PLAYING, (playing_show, show_ep))
            else:
                # Show not in list
                if self.config['tracker_not_found_prompt']:
                    # Dummy show to search for
                    show = {'id': 0, 'title': show_title}
                    return (utils.Tracker.NOT_FOUND, (show, show_ep))
                else:
                    return (utils.Tracker.NOT_FOUND, None)
        else:
            self.last_filename = None
            return (utils.Tracker.NOVIDEO, None)  # Not playing

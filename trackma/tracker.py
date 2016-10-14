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

import subprocess
import threading
import re
import time
import os
import difflib

import ctypes

from trackma import messenger
from trackma import utils
from trackma.extras import plex
from trackma.extras import AnimeInfoExtractor

inotify_available = 0
INOTIFY_PYINOTIFY = 1  # seb-m/pyinotify - pyinotify on PyPi
INOTIFY_INOTIFY = 2    # dsoprea/PyInotify - inotify on PyPi

STATE_PLAYING = 0
STATE_NOVIDEO = 1
STATE_UNRECOGNIZED = 2
STATE_NOT_FOUND = 3

try:
    import inotify.adapters
    import inotify.constants
    inotify_available = INOTIFY_INOTIFY
except ImportError:
    try:
        import pyinotify
        inotify_available = INOTIFY_PYINOTIFY
    except:
        pass  # If we ignore this the tracker will just use lsof


class Tracker():
    msg = None
    active = True
    list = None
    last_show_tuple = None
    last_filename = None
    last_state = STATE_NOVIDEO
    last_time = 0
    last_updated = False
    last_close_queue = False
    plex_enabled = False
    plex_log = [None, None]

    name = 'Tracker'

    signals = {'detected': None,
               'playing': None,
               'removed': None,
               'update': None, }

    def __init__(self, messenger, tracker_list, process_name, watch_dir, interval, update_wait, update_close):
        self.msg = messenger
        self.msg.info(self.name, 'Initializing...')

        self.list = tracker_list
        self.process_name = process_name
        self.plex_enabled = plex.get_config()[0]

        tracker_args = (watch_dir, interval)
        self.wait_s = update_wait
        self.wait_close = update_close
        tracker_t = threading.Thread(target=self._tracker, args=tracker_args)
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

    def _emit_signal(self, signal, *args):
        try:
            if self.signals[signal]:
                self.signals[signal](*args)
        except KeyError:
            raise Exception("Call to undefined signal.")

    def _get_playing_file_lsof(self, players):
        try:
            lsof = subprocess.Popen(['lsof', '+w', '-n', '-c', ''.join(['/', players, '/']), '-Fn'], stdout=subprocess.PIPE)
        except OSError:
            self.msg.warn(self.name, "Couldn't execute lsof. Disabling tracker.")
            self.disable()
            return False

        output = lsof.communicate()[0].decode('utf-8')
        fileregex = re.compile("n(.*(\.mkv|\.mp4|\.avi))")

        for line in output.splitlines():
            match = fileregex.match(line)
            if match is not None:
                return os.path.basename(match.group(1))

        return False

    def _foreach_window(self, hwnd, lParam):
        # Get class name and window title of the current hwnd
        # and add it to the list of the found windows
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)

        buff_class = ctypes.create_unicode_buffer(32)
        buff_title = ctypes.create_unicode_buffer(length + 1)

        ctypes.windll.user32.GetClassNameW(hwnd, buff_class, 32)
        ctypes.windll.user32.GetWindowTextW(hwnd, buff_title, length + 1)

        self.win32_hwnd_list.append( (buff_class.value, buff_title.value) )
        return True

    def _get_playing_file_win32(self):
        # Enumerate all windows using the win32 API
        # This will call _foreach_window for each window handle
        # Then return the window title if the class name matches
        # Currently supporting MPC(-HC) and mpv

        self.win32_hwnd_list = []
        self.EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        ctypes.windll.user32.EnumWindows(self.EnumWindowsProc(self._foreach_window), 0)
        winregex = re.compile("(\.mkv|\.mp4|\.avi)")

        for classname, title in self.win32_hwnd_list:
            if classname == 'MediaPlayerClassicW' and winregex.search(title) is not None:
                return title
            elif classname == 'mpv' and winregex.search(title) is not None:
                return title.replace('mpv - ', '')

        return False

    def _get_plex_file(self):
        playing_file = plex.playing_file()
        return playing_file

    def _poll_lsof(self):
        filename = self._get_playing_file_lsof(self.process_name)
        (state, show_tuple) = self._get_playing_show(filename)
        self.update_show_if_needed(state, show_tuple)

    def _observe_inotify(self, watch_dir):
        # Note that this lib uses bytestrings for filenames and paths.
        self.msg.info(self.name, 'Using inotify.')
        mask = (inotify.constants.IN_OPEN
                | inotify.constants.IN_CLOSE
                | inotify.constants.IN_CREATE
                | inotify.constants.IN_MOVE
                | inotify.constants.IN_DELETE)
        i = inotify.adapters.InotifyTree(watch_dir, mask=mask)
        try:
            for event in i.event_gen():
                if event is not None:
                    # With inotifyx impl., only the event type was used,
                    # such that it only served to poll lsof when an
                    # open or close event was received.
                    (header, types, path, filename) = event
                    if 'IN_ISDIR' not in types:
                        # If the file is gone, we remove from library
                        if ('IN_MOVED_FROM' in types
                                or 'IN_DELETE' in types):
                            self._emit_signal('removed', str(path, 'utf-8'), str(filename, 'utf-8'))
                        # Otherwise we attempt to add it to library
                        # Would check for IN_MOVED_TO or IN_CREATE but no need
                        else:
                            self._emit_signal('detected', str(path, 'utf-8'), str(filename, 'utf-8'))
                        if ('IN_OPEN' in types
                                or 'IN_CLOSE_NOWRITE' in types
                                or 'IN_CLOSE_WRITE' in types):
                            self._poll_lsof()
                elif self.last_state != STATE_NOVIDEO:
                    # Default blocking duration is 1 second
                    # This will count down like inotifyx impl. did
                    self.update_show_if_needed(self.last_state, self.last_show_tuple)
        finally:
            self.msg.info(self.name, 'Tracker has stopped.')
            # inotify resource is cleaned-up automatically

    def _observe_pyinotify(self, watch_dir):
        self.msg.info(self.name, 'Using pyinotify.')
        wm = pyinotify.WatchManager()  # Watch Manager
        mask = (pyinotify.IN_OPEN
                | pyinotify.IN_CLOSE_NOWRITE
                | pyinotify.IN_CLOSE_WRITE
                | pyinotify.IN_CREATE
                | pyinotify.IN_MOVED_FROM
                | pyinotify.IN_MOVED_TO
                | pyinotify.IN_DELETE)

        class EventHandler(pyinotify.ProcessEvent):
            def my_init(self, parent=None):
                self.parent = parent

            def process_IN_OPEN(self, event):
                if not event.mask & pyinotify.IN_ISDIR:
                    self.parent._emit_signal('detected', event.path, event.name)
                    self.parent._poll_lsof()

            def process_IN_CLOSE_NOWRITE(self, event):
                if not event.mask & pyinotify.IN_ISDIR:
                    self.parent._emit_signal('detected', event.path, event.name)
                    self.parent._poll_lsof()

            def process_IN_CLOSE_WRITE(self, event):
                if not event.mask & pyinotify.IN_ISDIR:
                    self.parent._emit_signal('detected', event.path, event.name)
                    self.parent._poll_lsof()

            def process_IN_CREATE(self, event):
                if not event.mask & pyinotify.IN_ISDIR:
                    self.parent._emit_signal('detected', event.path, event.name)

            def process_IN_MOVED_TO(self, event):
                if not event.mask & pyinotify.IN_ISDIR:
                    self.parent._emit_signal('detected', event.path, event.name)

            def process_IN_MOVED_FROM(self, event):
                if not event.mask & pyinotify.IN_ISDIR:
                    self.parent._emit_signal('removed', event.path, event.name)

            def process_IN_DELETE(self, event):
                if not event.mask & pyinotify.IN_ISDIR:
                    self.parent._emit_signal('removed', event.path, event.name)

        handler = EventHandler(parent=self)
        notifier = pyinotify.Notifier(wm, handler)
        wdd = wm.add_watch(watch_dir, mask, rec=True, auto_add=True)

        try:
            #notifier.loop()
            timeout = None
            while self.active:
                if notifier.check_events(timeout):
                    notifier.read_events()
                    notifier.process_events()
                    if self.last_state == STATE_NOVIDEO:
                        timeout = None  # Block indefinitely
                    else:
                        timeout = 1000  # Check each second for counting
                else:
                    self.update_show_if_needed(self.last_state, self.last_show_tuple)
        finally:
            notifier.stop()
            self.msg.info(self.name, 'Tracker has stopped.')

    def _observe_polling(self, interval):
        self.msg.info(self.name, "pyinotify not available; using polling (slow).")
        while self.active:
            # This runs the tracker and update the playing show if necessary
            self._poll_lsof()

            # Wait for the interval before running check again
            time.sleep(interval)

    def _observe_win32(self, interval):
        self.msg.info(self.name, "Using Win32.")

        while self.active:
            # This runs the tracker and update the playing show if necessary
            filename = self._get_playing_file_win32()
            (state, show_tuple) = self._get_playing_show(filename)
            self.update_show_if_needed(state, show_tuple)

            # Wait for the interval before running check again
            time.sleep(1)

    def _observe_plex(self, interval):
        self.msg.info(self.name, "Using Plex.")

        while self.active:
            # This stores the last two states of the plex server and only
            # updates if it's ACTIVE.
            plex_status = plex.status()
            self.plex_log.append(plex_status)

            if self.plex_log[-1] == "ACTIVE" or self.plex_log[-1] == "IDLE":
                self.wait_s = plex.timer_from_file()
                filename = self._get_plex_file()
                (state, show_tuple) = self._get_playing_show(filename)
                self.update_show_if_needed(state, show_tuple)
            elif (self.plex_log[-2] != "NOT_RUNNING" and self.plex_log[-1] == "NOT_RUNNING"):
                self.msg.warn(self.name, "Plex Media Server is not running.")

            del self.plex_log[0]
            # Wait for the interval before running check again
            time.sleep(30)

    def _tracker(self, watch_dir, interval):
        if self.plex_enabled:
            self._observe_plex(interval)
        else:
            if os.name == 'nt':
                self._observe_win32(interval)
            elif inotify_available == INOTIFY_INOTIFY:
                self._observe_inotify(watch_dir.encode('utf-8'))
            elif inotify_available == INOTIFY_PYINOTIFY:
                self._observe_pyinotify(watch_dir)
            else:
                self._observe_polling(interval)

    def update_show_if_needed(self, state, show_tuple):
        if show_tuple:
            (show, episode) = show_tuple

            if not self.last_show_tuple or show['id'] != self.last_show_tuple[0]['id'] or episode != self.last_show_tuple[1]:
                # There's a new show detected, so
                # let's save the show information and
                # the time we detected it first

                # But if we're watching a new show, let's make sure turn off
                # the Playing flag on that one first
                if self.last_show_tuple and self.last_show_tuple[0] != show:
                    self._emit_signal('playing', self.last_show_tuple[0]['id'], False, 0)

                self.last_show_tuple = (show, episode)
                self._emit_signal('playing', show['id'], True, episode)

                self.last_time = time.time()
                self.last_updated = False

            if not self.last_updated:
                # Check if we need to update the show yet
                if episode == (show['my_progress'] + 1):
                    timedif = time.time() - self.last_time

                    if timedif > self.wait_s:
                        # Time has passed, let's update
                        if self.wait_close:
                            # Queue update for when the player closes
                            self.msg.info(self.name, 'Waiting for the player to close.')
                            self.last_close_queue = True
                            self.last_updated = True
                        else:
                            # Update now
                            self._emit_signal('update', show['id'], episode)
                            self.last_updated = True
                    else:
                        self.msg.info(self.name, 'Will update %s %d in %d seconds' % (show['title'], episode, self.wait_s-timedif+1))
                else:
                    # We shouldn't update to this episode!
                    self.msg.warn(self.name, 'Player is not playing the next episode of %s. Ignoring.' % show['title'])
                    self.last_updated = True
            else:
                # The episode was updated already. do nothing
                pass
        elif self.last_state != state:
            # React depending on state
            # STATE_NOVIDEO : No video is playing anymroe
            # STATE_UNRECOGNIZED : There's a new video playing but the regex didn't recognize the format
            # STATE_NOT_FOUND : There's a new video playing but an associated show wasn't found
            if state == STATE_NOVIDEO and self.last_show_tuple:
                # Update now if there's an update queued
                if self.last_close_queue:
                    self._emit_signal('update', self.last_show_tuple[0]['id'], self.last_show_tuple[1])
                elif not self.last_updated:
                    self.msg.info(self.name, 'Player was closed before update.')
            elif state == STATE_UNRECOGNIZED:
                self.msg.warn(self.name, 'Found video but the file name format couldn\'t be recognized.')
            elif state == STATE_NOT_FOUND:
                self.msg.warn(self.name, 'Found player but show not in list.')

            # Clear any show previously playing
            if self.last_show_tuple:
                self._emit_signal('playing', self.last_show_tuple[0]['id'], False, self.last_show_tuple[1])
                self.last_updated = False
                self.last_close_queue = False
                self.last_time = 0
                self.last_show_tuple = None

        self.last_state = state

    def _get_playing_show(self, filename):
        if not self.active:
            # Don't do anything if the Tracker is disabled
            return (STATE_NOVIDEO, None)

        if filename:
            if filename == self.last_filename:
                # It's the exact same filename, there's no need to do the processing again
                return (4, self.last_show_tuple)

            self.last_filename = filename

            # Do a regex to the filename to get
            # the show title and episode number
            aie = AnimeInfoExtractor(filename)
            (show_title, show_ep) = (aie.getName(), aie.getEpisode())
            if not show_title:
                return (STATE_UNRECOGNIZED, None) # Format not recognized

            playing_show = utils.guess_show(show_title, self.list)
            if playing_show:
                return (STATE_PLAYING, (playing_show, show_ep))
            else:
                return (STATE_NOT_FOUND, None) # Show not in list
        else:
            self.last_filename = None
            return (STATE_NOVIDEO, None) # Not playing

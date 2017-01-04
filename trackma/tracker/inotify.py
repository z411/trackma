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

import inotify.adapters
import inotify.constants

from trackma.tracker import tracker
from trackma import utils

class inotifyTracker(tracker.TrackerBase):
    name = 'Tracker (inotify)'
    open_pathname = None

    def __init__(self, messenger, tracker_list, process_name, watch_dir, interval, update_wait, update_close, not_found_prompt):
        super().__init__(messenger, tracker_list, process_name, watch_dir, interval, update_wait, update_close, not_found_prompt)

        self.re_players = re.compile(self.process_name.encode('utf-8'))

    def _is_being_played(self, filename):
        """
        This function makes sure that the filename is being played
        by the player specified in players.

        It uses procfs so if we're using inotify that means we're using Linux
        thus we should be safe.
        """

        for p in os.listdir("/proc/"):
            if not p.isdigit(): continue
            d = "/proc/%s/fd/" % p
            try:
                for fd in os.listdir(d):
                    f = os.readlink(d+fd)
                    if f == filename:
                        # Get process name
                        with open('/proc/%s/cmdline' % p, 'rb') as f:
                            pname = f.read()

                        # Check if it's our process
                        if self.re_players.match(pname):
                            return True
            except OSError:
                pass

        return False

    def _proc_open(self, path, filename):
        pathname = "/".join([path, filename])

        if self._is_being_played(pathname):
            self.open_pathname = pathname

            (state, show_tuple) = self._get_playing_show(filename)
            self.update_show_if_needed(state, show_tuple)

    def _proc_close(self, path, filename):
        pathname = "/".join([path, filename])

        if pathname == self.open_pathname:
            self.open_pathname = None

            (state, show_tuple) = self._get_playing_show(None)
            self.update_show_if_needed(state, show_tuple)

    def observe(self, watch_dir, interval):
        # Note that this lib uses bytestrings for filenames and paths.
        self.msg.info(self.name, 'Using inotify.')

        watch_dir = watch_dir.encode('utf-8')
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

                        if 'IN_OPEN' in types:
                            self._proc_open(str(path, 'utf-8'), str(filename, 'utf-8'))
                        elif ('IN_CLOSE_NOWRITE' in types
                              or 'IN_CLOSE_WRITE' in types):
                            self._proc_close(str(path, 'utf-8'), str(filename, 'utf-8'))
                elif self.last_state != utils.TRACKER_NOVIDEO and not self.last_updated:
                    # Default blocking duration is 1 second
                    # This will count down like inotifyx impl. did
                    self.update_show_if_needed(self.last_state, self.last_show_tuple)
        finally:
            self.msg.info(self.name, 'Tracker has stopped.')
            # inotify resource is cleaned-up automatically


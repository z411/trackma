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
import time

from trackma.tracker import tracker
from trackma import utils

class inotifyBase(tracker.TrackerBase):
    open_file = (None, None, None)

    def __init__(self, messenger, tracker_list, config, watch_dirs, redirections=None):
        super().__init__(messenger, tracker_list, config, watch_dirs, redirections)

        self.re_players = re.compile(config['tracker_process'].encode('utf-8'))

    def _proc_poll(self):
        """
        This function scans proc to see if there's any player
        already open. If it is, and it has a media file open,
        return its first instance as a filename.
        """

        time.sleep(0.01)

        for p in os.listdir("/proc/"):
            if not p.isdigit(): continue

            # Get process name
            with open('/proc/%s/cmdline' % p, 'rb') as f:
                cmdline = f.read()
                pname = cmdline.partition(b'\x00')[0]

            # It's not one of our players
            if not self.re_players.search(pname):
                continue

            d = "/proc/%s/fd/" % p
            try:
                for fd in os.listdir(d):
                    f = os.readlink(d+fd)
                    if utils.is_media(f):
                        return os.path.split(f)
            except OSError:
                pass

        return None

    def _is_being_played(self, filename):
        """
        This function makes sure that the filename is being played
        by the player specified in players.

        It uses procfs so if we're using inotify that means we're using Linux
        thus we should be safe.
        """

        time.sleep(0.01)
        for p in os.listdir("/proc/"):
            if not p.isdigit(): continue
            d = "/proc/%s/fd/" % p
            try:
                for fd in os.listdir(d):
                    f = os.readlink(d+fd)
                    if f == filename:
                        # Get process name
                        with open('/proc/%s/cmdline' % p, 'rb') as f:
                            cmdline = f.read()
                            pname = cmdline.partition(b'\x00')[0]
                        self.msg.debug(self.name, 'Playing process: {} {} ({})'.format(p, pname, cmdline))

                        # Check if it's our process
                        if self.re_players.search(pname):
                            return p, fd
                        else:
                            self.msg.debug(self.name, "Not read by player ({})".format(pname))
            except OSError:
                pass

        self.msg.debug(self.name, "Couldn't find playing process.")
        return None, None

    def _closed_handle(self, pid, fd):
        """ Check if this pid has closed this handle (or never opened it) """
        d = "/proc/%s/fd/%s" % (pid, fd)
        time.sleep(0.01) # TODO : If we don't wait the filehandle will still be there
        return not os.path.islink(d)

    def _proc_open(self, path, name):
        self.msg.debug(self.name, 'Got OPEN event: {} {}'.format(path, name))
        pathname = os.path.join(path, name)

        pid, fd = self._is_being_played(pathname)

        if pid:
            self._emit_signal('detected', path, name)
            self.open_file = (pathname, pid, fd)

            if self.config['library_full_path']:
                (state, show_tuple) = self._get_playing_show(pathname)
            else:
                (state, show_tuple) = self._get_playing_show(name)
            self.msg.debug(self.name, "Got status: {} {}".format(state, show_tuple))
            self.update_show_if_needed(state, show_tuple)
        else:
            self.msg.debug(self.name, "Not played by player, ignoring.")

    def _proc_close(self, path, name):
        self.msg.debug(self.name, 'Got CLOSE event: {} {}'.format(path, name))
        pathname = os.path.join(path, name)

        open_pathname, pid, fd = self.open_file

        if pathname != open_pathname:
            self.msg.debug(self.name, "A different file was closed.")
            return

        if not self._closed_handle(pid, fd):
            self.msg.debug(self.name, "Our pid hasn't closed the file.")
            return

        self._emit_signal('detected', path, name)
        self.open_file = (None, None, None)

        (state, show_tuple) = self._get_playing_show(None)
        self.update_show_if_needed(state, show_tuple)


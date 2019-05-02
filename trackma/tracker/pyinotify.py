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

import pyinotify

from trackma.tracker import inotifyBase
from trackma import utils

class pyinotifyTracker(inotifyBase.inotifyBase):
    name = 'Tracker (pyinotify)'

    def observe(self, config, watch_dirs):
        self.msg.info(self.name, 'Using pyinotify.')

        self.msg.debug(self.name, 'Checking if there are open players...')
        opened = self._proc_poll()
        if opened:
            self._proc_open(*opened)

        wm = pyinotify.WatchManager()  # Watch Manager
        mask = (pyinotify.IN_OPEN #pylint: disable=no-member
                | pyinotify.IN_CLOSE_NOWRITE #pylint: disable=no-member
                | pyinotify.IN_CLOSE_WRITE #pylint: disable=no-member
                | pyinotify.IN_CREATE #pylint: disable=no-member
                | pyinotify.IN_MOVED_FROM #pylint: disable=no-member
                | pyinotify.IN_MOVED_TO #pylint: disable=no-member
                | pyinotify.IN_DELETE) #pylint: disable=no-member

        class EventHandler(pyinotify.ProcessEvent):
            def my_init(self, parent=None):
                self.parent = parent

            def process_IN_OPEN(self, event):
                if not event.mask & pyinotify.IN_ISDIR: #pylint: disable=no-member
                    self.parent._proc_open(event.path, event.name)

            def process_IN_CLOSE_NOWRITE(self, event):
                if not event.mask & pyinotify.IN_ISDIR: #pylint: disable=no-member
                    self.parent._proc_close(event.path, event.name)

            def process_IN_CLOSE_WRITE(self, event):
                if not event.mask & pyinotify.IN_ISDIR: #pylint: disable=no-member
                    self.parent._proc_close(event.path, event.name)

            def process_IN_CREATE(self, event):
                if not event.mask & pyinotify.IN_ISDIR: #pylint: disable=no-member
                    self.parent._emit_signal('detected', event.path, event.name)

            def process_IN_MOVED_TO(self, event):
                if not event.mask & pyinotify.IN_ISDIR: #pylint: disable=no-member
                    self.parent._emit_signal('detected', event.path, event.name)

            def process_IN_MOVED_FROM(self, event):
                if not event.mask & pyinotify.IN_ISDIR: #pylint: disable=no-member
                    self.parent._emit_signal('removed', event.path, event.name)

            def process_IN_DELETE(self, event):
                if not event.mask & pyinotify.IN_ISDIR: #pylint: disable=no-member
                    self.parent._emit_signal('removed', event.path, event.name)

        handler = EventHandler(parent=self)
        notifier = pyinotify.Notifier(wm, handler)
        for path in watch_dirs:
            self.msg.debug(self.name, 'Watching directory {}'.format(path))
            wm.add_watch(path, mask, rec=True, auto_add=True)

        try:
            #notifier.loop()
            timeout = None
            while self.active:
                if notifier.check_events(timeout):
                    # Check again to avoid notifying while inactive
                    if not self.active:
                        return

                    notifier.read_events()
                    notifier.process_events()
                    if self.last_state == utils.TRACKER_NOVIDEO or self.last_updated:
                        timeout = None  # Block indefinitely
                    else:
                        timeout = 1000  # Check each second for counting
                elif self.active:
                    self.msg.debug(self.name, "Sending last state {} {}".format(self.last_state, self.last_show_tuple))
                    self.update_show_if_needed(self.last_state, self.last_show_tuple)
        finally:
            notifier.stop()
            self.msg.info(self.name, 'Tracker has stopped.')


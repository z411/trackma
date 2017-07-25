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

    def observe(self, watch_dir, interval):
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
                    self.parent._proc_open(event.path, event.name)

            def process_IN_CLOSE_NOWRITE(self, event):
                if not event.mask & pyinotify.IN_ISDIR:
                    self.parent._proc_close(event.path, event.name)

            def process_IN_CLOSE_WRITE(self, event):
                if not event.mask & pyinotify.IN_ISDIR:
                    self.parent._proc_close(event.path, event.name)

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
        self.msg.debug(self.name, 'Watching directory {}'.format(watch_dir))
        wdd = wm.add_watch(watch_dir, mask, rec=True, auto_add=True)

        try:
            #notifier.loop()
            timeout = None
            while self.active:
                if notifier.check_events(timeout):
                    notifier.read_events()
                    notifier.process_events()
                    if self.last_state == utils.TRACKER_NOVIDEO or self.last_updated:
                        timeout = None  # Block indefinitely
                    else:
                        timeout = 1000  # Check each second for counting
                else:
                    self.msg.debug(self.name, "Sending last state {} {}".format(self.last_state, self.last_show_tuple))
                    self.update_show_if_needed(self.last_state, self.last_show_tuple)
        finally:
            notifier.stop()
            self.msg.info(self.name, 'Tracker has stopped.')


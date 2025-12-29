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

import traceback

TYPE_DEBUG = 1
TYPE_INFO = 2
# TYPE_ERROR = 3
# TYPE_FATAL = 4
TYPE_WARN = 5


class Messenger:
    _handler = None

    def __init__(self, handler, classname):
        self._handler = handler
        self.classname = classname

    def set_handler(self, handler):
        self._handler = handler

    def with_classname(self, classname):
        return Messenger(self._handler, classname)

    def _call_handler(self, msgs, msg_type):
        if self._handler:
            cn, msg = self._parse_msgs(msgs)
            self._handler(cn, msg_type, msg)

    def _parse_msgs(self, msgs):
        if len(msgs) >= 2:
            return (msgs[0], " ".join(msgs[1:]) if msgs[2:] else msgs[1])
        return (self.classname, msgs[0])

    def debug(self, *msgs):
        self._call_handler(msgs, TYPE_DEBUG)

    def info(self, *msgs):
        self._call_handler(msgs, TYPE_INFO)

    def warn(self, *msgs):
        self._call_handler(msgs, TYPE_WARN)

    def exception(self, *msgs):
        if not self._handler:
            return
        cn, exc_info = self._parse_msgs(msgs[:2])
        exc_type, exc_value, exc_traceback = exc_info
        for block in traceback.format_exception(exc_type, exc_value, exc_traceback):
            for line in block.splitlines():
                self._handler(cn, TYPE_DEBUG, line)

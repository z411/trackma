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

TYPE_DEBUG = 1
TYPE_INFO = 2
#TYPE_ERROR = 3
#TYPE_FATAL = 4
TYPE_WARN = 5

class Messenger:
    _handler = None

    def __init__(self, handler):
        self._handler = handler

    def set_handler(self, handler):
        self._handler = handler

    def debug(self, classname, msg):
        if self._handler:
            self._handler(classname, TYPE_DEBUG, msg)

    def info(self, classname, msg):
        if self._handler:
            self._handler(classname, TYPE_INFO, msg)

    def warn(self, classname, msg):
        if self._handler:
            self._handler(classname, TYPE_WARN, msg)

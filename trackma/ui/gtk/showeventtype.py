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

from gi.repository import GObject


class ShowEventType(GObject.GEnum):
    NONE = 0
    DETAILS = 1
    OPEN_WEBSITE = 2
    OPEN_FOLDER = 3
    COPY_TITLE = 4
    CHANGE_ALTERNATIVE_TITLE = 5
    REMOVE = 6
    PLAY_NEXT = 7
    PLAY_EPISODE = 8
    PLAY_RANDOM = 9

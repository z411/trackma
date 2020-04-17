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

from PyQt5 import QtGui

from trackma import utils

class FilterBar():
    """
    Constants relating to filter bar settings can live here.
    """
    # Position
    PositionHidden = 0
    PositionAboveLists = 1
    PositionBelowLists = 2

def getIcon(icon_name):
    fallback = QtGui.QIcon(utils.DATADIR + '/qtui/{}.png'.format(icon_name))
    return QtGui.QIcon.fromTheme(icon_name, fallback)

def getColor(colorString):
    # Takes a color string in either #RRGGBB format or group,role format (using QPalette int values)
    if colorString[0] == "#":
        return QtGui.QColor(colorString)
    else:
        (group, role) = [int(i) for i in colorString.split(',')]
        if (0 <= group <= 2) and (0 <= role <= 19):
            return QtGui.QColor(QtGui.QPalette().color(group, role))
        else:
            # Failsafe - return black
            return QtGui.QColor()


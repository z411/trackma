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
os.environ['PYQT4'] = 'True'
<<<<<<< HEAD:trackma/ui/qt4ui.py
from trackma.ui import qtui

def main():
    qtui.main()

if __name__ == '__main__':
    main()
=======
import trackma.ui.qt

if __name__ == '__main__':
    trackma.ui.qt.main()
>>>>>>> 4d45ab9ce62be93169cf75644673abe458aeec34:trackma/ui/qt/qt4ui.py

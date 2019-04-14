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


import sys
import os

debug = False
force_qt4 = False

from trackma import utils

print("Trackma-qt v{}".format(utils.VERSION))

if '-h' in sys.argv:
    print("Usage: trackma-qt [options]")
    print()
    print('Options:')
    print(' -d  Shows debugging information')
    print(' -4  Force Qt4')
    print(' -h  Shows this help')
    sys.exit(0)
if '-d' in sys.argv:
    print('Showing debug information.')
    debug = True
if '-4' in sys.argv:
    print('Forcing Qt4.')
    force_qt4 = True

if not force_qt4:
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        os.environ['PYQT5'] = "1"
    except ImportError:
        print("Couldn't import Qt5 dependencies. "
              "Make sure you installed the PyQt5 package.")
              
if 'PYQT5' not in os.environ:
    try:
        import sip
        sip.setapi('QVariant', 2)
        from PyQt4.QtGui import QApplication, QMessageBox
    except ImportError:
        print("Couldn't import Qt4 dependencies. "
              "Make sure you installed the PyQt4 package.")
        sys.exit(-1)

from trackma import messenger
from trackma.ui.qt.mainwindow import MainWindow

try:
    from PIL import Image
    os.environ['imaging_available'] = "1"
except ImportError:
    try:
        import Image
        os.environ['imaging_available'] = "1"
    except ImportError:
        print("Warning: PIL or Pillow isn't available. "
              "Preview images will be disabled.")


def main():
    app = QApplication(sys.argv)
    try:
        mainwindow = MainWindow(debug)
        sys.exit(app.exec_())
    except utils.TrackmaFatal as e:
        QMessageBox.critical(None, 'Fatal Error', "{0}".format(e), QMessageBox.Ok)

if __name__ == '__main__':
    main()

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
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GObject
from trackma.ui.gtk.window import TrackmaWindow
from trackma import utils


def main():
    debug = False

    print("Trackma-gtk v{}".format(utils.VERSION))

    if '-h' in sys.argv:
        print("Usage: trackma-qt [options]")
        print()
        print('Options:')
        print(' -d  Shows debugging information')
        print(' -h  Shows this help')
        return
    if '-d' in sys.argv:
        debug = True

    app = TrackmaWindow(debug)
    try:
        GObject.threads_init()
        Gdk.threads_init()
        Gdk.threads_enter()
        app.main()
        Gtk.main()
    except utils.TrackmaFatal as e:
        md = Gtk.MessageDialog(None,
                               Gtk.DialogFlags.DESTROY_WITH_PARENT,
                               Gtk.MessageType.ERROR,
                               Gtk.ButtonsType.CLOSE, str(e))
        md.run()
        md.destroy()
    finally:
        Gdk.threads_leave()


if __name__ == '__main__':
    main()


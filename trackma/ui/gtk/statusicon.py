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

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, Gtk, GObject
from trackma import utils


class TrackmaStatusIcon(Gtk.StatusIcon):
    __gtype_name__ = 'TrackmaStatusIcon'

    __gsignals__ = {
        'hide-clicked': (GObject.SIGNAL_RUN_FIRST, None,
                         ()),
        'about-clicked': (GObject.SIGNAL_RUN_FIRST, None,
                          ()),
        'quit-clicked': (GObject.SIGNAL_RUN_FIRST, None,
                         ()),
    }

    def __init__(self):
        Gtk.StatusIcon.__init__(self)
        self.set_from_file(utils.DATADIR + '/icon.png')
        self.set_tooltip_text('Trackma-gtk ' + utils.VERSION)
        self.connect('activate', self._tray_status_event)
        self.connect('popup-menu', self._tray_status_menu_event)

    def _tray_status_event(self, widget):
        self.emit('hide-clicked')

    def _tray_status_menu_event(self, icon, button, time):
        # Called when the tray icon is right-clicked
        menu = Gtk.Menu()
        mb_show = Gtk.MenuItem("Show/Hide")
        mb_about = Gtk.ImageMenuItem('About', Gtk.Image.new_from_icon_name(Gtk.STOCK_ABOUT, 0))
        mb_quit = Gtk.ImageMenuItem('Quit', Gtk.Image.new_from_icon_name(Gtk.STOCK_QUIT, 0))

        mb_show.connect("activate", self._tray_status_event)
        mb_about.connect("activate", self._on_mb_about)
        mb_quit.connect("activate", self._on_mb_quit)

        menu.append(mb_show)
        menu.append(mb_about)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(mb_quit)
        menu.show_all()

        menu.popup(None, None, None, self._pos, button, time)

    def _on_mb_about(self, menu_item):
        self.emit('about-clicked')

    def _on_mb_quit(self, menu_item):
        self.emit('quit-clicked')

    def _pos(self, menu, icon):
        return Gtk.StatusIcon.position_menu(menu, icon)

    @staticmethod
    def is_tray_available():
        # Icon tray isn't available in Wayland
        return not Gdk.Display.get_default().get_name().lower().startswith('wayland')

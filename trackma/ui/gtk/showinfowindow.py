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
from gi.repository import Gtk, Gdk
from trackma.ui.gtk.showinfobox import ShowInfoBox


class ShowInfoWindow(Gtk.Window):
    def __init__(self, engine, show):
        self.engine = engine
        self._show = show

        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Show Details')
        self.set_border_width(10)

        fullbox = Gtk.VBox()

        # Info box
        info = ShowInfoBox(engine)
        info.set_size(600, 500)

        # Bottom line (buttons)
        alignment = Gtk.Alignment(xalign=1.0, xscale=0)
        bottombar = Gtk.HBox(False, 5)

        web_button = Gtk.Button('Open web')
        web_button.connect("clicked", self.__do_web)
        close_button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        close_button.connect("clicked", self.__do_close)

        bottombar.pack_start(web_button, False, False, 0)
        bottombar.pack_start(close_button, False, False, 0)
        alignment.add(bottombar)

        fullbox.pack_start(info, True, True, 0)
        fullbox.pack_start(alignment, False, False, 0)

        self.add(fullbox)
        self.show_all()

        info.load(show)

    def __do_close(self, widget):
        self.destroy()

    def __do_web(self, widget):
        if self._show['url']:
            Gtk.show_uri(None, self._show['url'], Gdk.CURRENT_TIME)



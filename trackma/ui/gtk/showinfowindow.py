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
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
from trackma.ui.gtk import gtk_dir
from trackma.ui.gtk.gi_composites import GtkTemplate
from trackma.ui.gtk.showinfobox import ShowInfoBox


@GtkTemplate(ui=os.path.join(gtk_dir, 'data/showinfowindow.ui'))
class ShowInfoWindow(Gtk.Dialog):
    __gtype_name__ = 'ShowInfoWindow'

    info_container = GtkTemplate.Child()

    def __init__(self, engine, show_data, transient_for=None):
        Gtk.Dialog.__init__(self, transient_for=transient_for)
        self.init_template()

        self._engine = engine
        self._show = show_data

        # Info box
        info = ShowInfoBox(engine)
        self.info_container.pack_start(info, True, True, 0)
        info.load(show_data)
        self.show_all()

    @GtkTemplate.Callback
    def _on_dialog_close(self, widget):
        self.destroy()

    @GtkTemplate.Callback
    def _on_btn_website_clicked(self, btn):
        if self._show['url']:
            Gtk.show_uri(None, self._show['url'], Gdk.CURRENT_TIME)

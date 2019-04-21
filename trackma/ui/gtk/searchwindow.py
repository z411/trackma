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
import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk, Gdk, GObject
from trackma.ui.gtk import gtk_dir
from trackma.ui.gtk.gi_composites import GtkTemplate
from trackma.ui.gtk.showinfobox import ShowInfoBox
from trackma import utils


class SearchThread(threading.Thread):
    def __init__(self, engine, search_text, callback):
        threading.Thread.__init__(self)
        self._entries = []
        self._error = None
        self._engine = engine
        self._search_text = search_text
        self._callback = callback
        self._stop_request = threading.Event()

    def run(self):
        try:
            self._entries = self._engine.search(self._search_text)
        except utils.TrackmaError as e:
            self._entries = []
            self._error = e

        if not self._stop_request.is_set():
            GLib.idle_add(self._callback, self._entries, self._error)

    def stop(self):
        self._stop_request.set()


@GtkTemplate(ui=os.path.join(gtk_dir, 'data/searchwindow.ui'))
class SearchWindow(Gtk.Window):
    __gtype_name__ = 'SearchWindow'

    __gsignals__ = {
        'search-error': (GObject.SIGNAL_RUN_FIRST, None,
                         (str,))
    }

    btn_add_show = GtkTemplate.Child()
    search_paned = GtkTemplate.Child()
    shows_viewport = GtkTemplate.Child()
    show_info_container = GtkTemplate.Child()

    def __init__(self, engine, colors, current_status, transient_for=None):
        Gtk.Window.__init__(self, transient_for=transient_for)
        self.init_template()

        self._entries = []
        self._selected_show = None
        self._showdict = None

        self._engine = engine
        self._current_status = current_status
        self._search_thread = None

        self.showlist = SearchTreeView(colors)
        self.showlist.get_selection().connect("changed", self._on_selection_changed)

        self.info = ShowInfoBox(engine)
        self.info.set_size_request(200, 350)

        self.shows_viewport.add(self.showlist)
        self.show_info_container.pack_start(self.info, True, True, 0)

        self.search_paned.set_position(400)

    @GtkTemplate.Callback
    def _on_search_entry_search_changed(self, search_entry):
        self._search(search_entry.get_text())

    def _search(self, text):
        if self._search_thread:
            self._search_thread.stop()

        self._search_thread = SearchThread(self._engine,
                                           text,
                                           self._search_finish_idle)
        self._search_thread.start()

    def _search_finish_idle(self, entries, error):
        if error:
            self.emit('search-error', error)
            return

        self._entries = entries
        self._showdict = dict()

        self.showlist.append_start()
        for show in entries:
            self._showdict[show['id']] = show
            self.showlist.append(show)
        self.showlist.append_finish()

        self.btn_add_show.set_sensitive(False)

    @GtkTemplate.Callback
    def _on_btn_add_show_clicked(self, btn):
        show = self._get_full_selected_show()

        if show is not None:
            self._add_show(show)

    def _get_full_selected_show(self):
        for item in self._entries:
            if item['id'] == self._selected_show:
                return item

        return None

    def _add_show(self, show):
        try:
            self._engine.add_show(show, self._current_status)
        except utils.TrackmaError as e:
            self.emit('search-error', e)

    def _on_selection_changed(self, selection):
        # Get selected show ID
        (tree_model, tree_iter) = selection.get_selected()
        if not tree_iter:
            return

        self._selected_show = int(tree_model.get(tree_iter, 0)[0])
        if self._selected_show in self._showdict:
            self.info.load(self._showdict[self._selected_show])
            self.btn_add_show.set_sensitive(True)


class SearchTreeView(Gtk.TreeView):
    def __init__(self, colors):
        Gtk.TreeView.__init__(self)

        self.cols = dict()
        i = 1
        for name in ('Title', 'Type', 'Total'):
            self.cols[name] = Gtk.TreeViewColumn(name)
            self.cols[name].set_sort_column_id(i)
            self.append_column(self.cols[name])
            i += 1

        #renderer_id = Gtk.CellRendererText()
        #self.cols['ID'].pack_start(renderer_id, False)
        #self.cols['ID'].add_attribute(renderer_id, 'text', 0)

        renderer_title = Gtk.CellRendererText()
        self.cols['Title'].pack_start(renderer_title, False)
        self.cols['Title'].set_resizable(True)
        #self.cols['Title'].set_expand(True)
        self.cols['Title'].add_attribute(renderer_title, 'text', 1)
        self.cols['Title'].add_attribute(renderer_title, 'foreground', 4)

        renderer_type = Gtk.CellRendererText()
        self.cols['Type'].pack_start(renderer_type, False)
        self.cols['Type'].add_attribute(renderer_type, 'text', 2)

        renderer_total = Gtk.CellRendererText()
        self.cols['Total'].pack_start(renderer_total, False)
        self.cols['Total'].add_attribute(renderer_total, 'text', 3)

        self.store = Gtk.ListStore(str, str, str, str, str)
        self.set_model(self.store)

        self.colors = colors

    def append_start(self):
        self.freeze_child_notify()
        self.store.clear()

    def append(self, show):
        if show['status'] == 1:
            color = self.colors['is_airing']
        elif show['status'] == 3:
            color = self.colors['not_aired']
        else:
            color = None

        row = [
            str(show['id']),
            str(show['title']),
            str(show['type']),
            str(show['total']),
            color]
        self.store.append(row)

    def append_finish(self):
        self.thaw_child_notify()
        self.store.set_sort_column_id(1, Gtk.SortType.ASCENDING)

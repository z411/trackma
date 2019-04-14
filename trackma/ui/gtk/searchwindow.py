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


import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GObject
from trackma.ui.gtk.showinfobox import ShowInfoBox
from trackma import utils


class SearchWindow(Gtk.Window):
    def __init__(self, engine, colors, current_status):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)

        self.entries = []
        self.selected_show = None
        self.showdict = None

        self.engine = engine
        self.current_status = current_status

        fullbox = Gtk.HPaned()

        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Search')
        self.set_border_width(10)

        vbox = Gtk.VBox(False, 10)

        searchbar = Gtk.HBox(False, 5)
        searchbar.pack_start(Gtk.Label('Search'), False, False, 0)
        self.searchtext = Gtk.Entry()
        self.searchtext.set_max_length(100)
        self.searchtext.connect("activate", self.__do_search)
        searchbar.pack_start(self.searchtext, True, True, 0)
        self.search_button = Gtk.Button('Search')
        self.search_button.connect("clicked", self.__do_search)
        searchbar.pack_start(self.search_button, False, False, 0)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_size_request(450, 350)

        alignment = Gtk.Alignment(xalign=1.0, xscale=0)
        bottombar = Gtk.HBox(False, 5)
        self.add_button = Gtk.Button('Add')
        self.add_button.set_image(Gtk.Image.new_from_icon_name(Gtk.STOCK_APPLY, 0))
        self.add_button.connect("clicked", self._do_add)
        self.add_button.set_sensitive(False)
        close_button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        close_button.connect("clicked", self.__do_close)
        bottombar.pack_start(self.add_button, False, False, 0)
        bottombar.pack_start(close_button, False, False, 0)
        alignment.add(bottombar)

        self.showlist = SearchTreeView(colors)
        self.showlist.get_selection().connect("changed", self.select_show)

        sw.add(self.showlist)

        self.info = ShowInfoBox(engine)
        self.info.set_size(400, 350)

        vbox.pack_start(searchbar, False, False, 0)
        vbox.pack_start(sw, True, True, 0)
        vbox.pack_start(alignment, False, False, 0)
        fullbox.pack1(vbox)
        fullbox.pack2(self.info)
        self.add(fullbox)

    def _do_add(self, widget, path=None, view_column=None):
        # Get show dictionary
        show = None
        for item in self.entries:
            if item['id'] == self.selected_show:
                show = item
                break

        if show is not None:
            try:
                self.engine.add_show(show, self.current_status)
                #self.__do_close()
            except utils.TrackmaError as e:
                self.error_push(e)

    def __do_search(self, widget):
        threading.Thread(target=self.task_search).start()

    def __do_close(self, widget=None):
        self.destroy()

    def select_show(self, widget):
        # Get selected show ID
        (tree_model, tree_iter) = widget.get_selected()
        if not tree_iter:
            self.allow_buttons_push(False) # (False, lists_too=False)
            return

        self.selected_show = int(tree_model.get(tree_iter, 0)[0])
        if self.selected_show in self.showdict:
            self.info.load(self.showdict[self.selected_show])
            self.add_button.set_sensitive(True)

    def task_search(self):
        self.allow_buttons(False)

        try:
            self.entries = self.engine.search(self.searchtext.get_text())
        except utils.TrackmaError as e:
            self.entries = []
            self.error(e)

        self.showdict = dict()

        Gdk.threads_enter()
        self.showlist.append_start()
        for show in self.entries:
            self.showdict[show['id']] = show
            self.showlist.append(show)
        self.showlist.append_finish()
        Gdk.threads_leave()

        self.allow_buttons(True)
        self.add_button.set_sensitive(False)

    def allow_buttons_push(self, boolean):
        self.search_button.set_sensitive(boolean)

    def allow_buttons(self, boolean):
        # Thread safe
        GObject.idle_add(self.allow_buttons_push, boolean)

    def error(self, msg):
        # Thread safe
        GObject.idle_add(self.error_push, msg)

    def error_push(self, msg):
        dialog = Gtk.MessageDialog(self, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, str(msg))
        dialog.show_all()
        dialog.connect("response", self.modal_close)

    def modal_close(self, widget, response_id):
        widget.destroy()


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


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

from gi.repository import GLib, GObject, Gtk

from trackma import utils
from trackma.ui.gtk import gtk_dir
from trackma.ui.gtk.showinfobox import ShowInfoBox


class SearchThread(threading.Thread):
    def __init__(self, engine, query, callback):
        threading.Thread.__init__(self)
        self._entries = []
        self._error = None
        self._engine = engine
        if isinstance(query, (tuple,)):
            self._search_text, self._page = query
        else:
            self._search_text, self._page = (query, 1)
        self._callback = callback
        self._stop_request = threading.Event()

    def run(self):
        try:
            self._entries = self._engine.search(self._search_text, page=self._page)
        except utils.TrackmaError as e:
            self._entries = []
            self._error = e

        if not self._stop_request.is_set():
            GLib.idle_add(self._callback, self._entries, self._error)

    def stop(self):
        self._stop_request.set()


@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/searchwindow.ui'))
class SearchWindow(Gtk.Window):
    __gtype_name__ = 'SearchWindow'

    __gsignals__ = {
        'search-error': (GObject.SignalFlags.RUN_FIRST, None,
                         (str,))
    }

    btn_add_show = Gtk.Template.Child()
    search_paned = Gtk.Template.Child()
    shows_viewport = Gtk.Template.Child()
    show_info_container = Gtk.Template.Child()
    progress_spinner = Gtk.Template.Child()
    headerbar = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()

    # pagination
    paginator    = Gtk.Template.Child()
    next_page    = Gtk.Template.Child()
    prev_page    = Gtk.Template.Child()
    select_page  = Gtk.Template.Child()
    page_popover = Gtk.Template.Child()
    page_entry   = Gtk.Template.Child()

    def __init__(self, engine, colors, current_status, transient_for=None):
        Gtk.Window.__init__(self, transient_for=transient_for)
        self.init_template()
        self._entries = []
        self._pages = 1
        self._page = 1
        self._results = 0
        self._selected_show = None
        self._showdict = None

        self._engine = engine
        self._current_status = current_status
        self._search_thread = None

        self.showlist = SearchTreeView(colors)
        self.showlist.get_selection().connect("changed", self._on_selection_changed)
        self.showlist.set_size_request(250, 350)
        self.showlist.show()

        self.info = ShowInfoBox(engine, orientation=Gtk.Orientation.VERTICAL)
        self.info.set_size_request(200, 350)
        self.info.show()

        self.shows_viewport.add(self.showlist)
        self.show_info_container.pack_start(self.info, True, True, 0)
        self.search_paned.set_position(400)
        self.set_size_request(450, 350)

    @Gtk.Template.Callback()
    def _on_search_entry_search_changed(self, search_entry):
        self._search(1)
        
    def _search(self, page):
        text = self.search_entry.get_text().strip()
        self.progress_spinner.start()

        if text == "":
            if self._search_thread:
                self._search_thread.stop()
            self._search_finish()
            return

        if self._search_thread:
            self._search_thread.stop()

        self.headerbar.set_subtitle("Searching: \"%s\"" % text)
        self._search_thread = SearchThread(self._engine,
                                           (text, page),
                                           self._search_finish_idle)
        self._search_thread.start()

    def _search_finish(self):
        self.headerbar.set_subtitle(
            "%s result%s." % ((self._results, 's') if self._results > 0
                              else ('No', ''))
        )
        self.progress_spinner.stop()

    def _search_finish_idle(self, entries, error):
        if isinstance(entries, (tuple,)):
            self._entries, self._results, self._page, self._pages = entries
        else:
            self._entries, self._results, self._page, self._pages = (
                entries, len(entries), 1, 1
            )

        self._showdict = dict()
        self._search_finish()
        self.showlist.append_start()
        for show in self._entries:
            self._showdict[show['id']] = show
            self.showlist.append(show)
        self.showlist.append_finish()

        self.btn_add_show.set_sensitive(False)
        self.paginator.props.visible = self._pages > 1
        self.select_page.props.sensitive = self._pages > 1

        if self.paginator.props.visible:
            self.prev_page.props.sensitive = self._page > 1
            self.next_page.props.sensitive = self._page < self._pages
            self.select_page.props.label = '{} / {}'.format(self._page, self._pages)

        if error:
            self.emit('search-error', error)

    @Gtk.Template.Callback()
    def _on_btn_add_show_clicked(self, btn):
        show = self._get_full_selected_show()

        if show is not None:
            self._add_show(show)

    @Gtk.Template.Callback()
    def _on_prev_page_clicked(self, btn):
        self._search(self._page - 1)

    @Gtk.Template.Callback()
    def _on_next_page_clicked(self, btn):
        self._search(self._page + 1)

    @Gtk.Template.Callback()
    def _on_select_page_clicked(self, btn):
        popover = self.page_popover.props
        entry   = self.page_entry.props
        popover.relative_to    = btn
        popover.position       = Gtk.PositionType.BOTTOM

        entry.text                 = str(self._page)
        entry.placeholder_text     = "1 <= page <= {}".format(self._pages)
        (entry.secondary_icon_tooltip_text,
        entry.secondary_icon_name) = ('', '')

        self.page_popover.show()
        self.page_entry.grab_focus()

    @Gtk.Template.Callback()
    def _on_page_change(self, *args):
        props = self.page_entry.props

        if not props.text.isdigit():
            props.secondary_icon_name = 'dialog-error'
            props.secondary_icon_tooltip_text = 'Not a number.'
            return False
        elif not 1 <= int(self.page_entry.props.text) <= self._pages:
            props.secondary_icon_name = 'dialog-error'
            props.secondary_icon_tooltip_text = 'Not in range 1 <= page <= {}'.format(self._pages)
            return False
        elif props.secondary_icon_name:
            props.secondary_icon_name = ''
            props.secondary_icon_tooltip_text = ''

        self.page_popover.hide()
        self._search(int(props.text))

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

        # renderer_id = Gtk.CellRendererText()
        # self.cols['ID'].pack_start(renderer_id, False)
        # self.cols['ID'].add_attribute(renderer_id, 'text', 0)

        renderer_title = Gtk.CellRendererText()
        self.cols['Title'].pack_start(renderer_title, False)
        self.cols['Title'].set_resizable(True)
        self.cols['Title'].set_expand(False)
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

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

import html
import os
import threading

from gi.repository import GLib, GObject, Gdk, Gtk

from trackma import messenger
from trackma import utils
from trackma.ui.gtk import gtk_dir
from trackma.ui.gtk.imagebox import ImageBox
from trackma.ui.gtk.showeventtype import ShowEventType
from trackma.ui.gtk.showtreeview import ShowListFilter, ShowListStore, ShowTreeView


@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/mainview.ui'))
class MainView(Gtk.Box):

    __gtype_name__ = 'MainView'

    __gsignals__ = {
        'error': (GObject.SignalFlags.RUN_FIRST, None,
                  (str, )),
        'success': (GObject.SignalFlags.RUN_CLEANUP, None,
                    ()),
        'error-fatal': (GObject.SignalFlags.RUN_FIRST, None,
                        (str,)),
        'show-action': (GObject.SignalFlags.RUN_FIRST, None,
                        (int, object)),
    }

    image_container_box = Gtk.Template.Child()
    top_box = Gtk.Template.Child()
    show_title = Gtk.Template.Child()
    api_icon = Gtk.Template.Child()
    api_user = Gtk.Template.Child()
    btn_episode_remove = Gtk.Template.Child()
    btn_episode_show_entry = Gtk.Template.Child()
    entry_popover = Gtk.Template.Child()
    entry_episode = Gtk.Template.Child()
    entry_done = Gtk.Template.Child()
    btn_episode_add = Gtk.Template.Child()
    btn_play_next = Gtk.Template.Child()
    spinbtn_score = Gtk.Template.Child()
    btn_score_set = Gtk.Template.Child()
    statusbox = Gtk.Template.Child()
    statusmodel = Gtk.Template.Child()
    notebook = Gtk.Template.Child()

    def __init__(self, config, debug=False):
        Gtk.Box.__init__(self)
        self.init_template()

        self._configfile = utils.to_config_path('ui-Gtk.json')
        self._config = config
        self._engine = None
        self._account = None
        self._list = ShowListStore(colors=config['colors'])
        self._debug = debug

        self._image_thread = None
        self._current_page = None
        self.statusbox_handler = None
        self.notebook_switch_handler = None
        self._hovering_over_tabs = None
        self._pages = {}
        self._page_handler_ids = {}

        self._init_widgets()
        self._init_signals()

    def load_engine_account(self, engine, account):
        self._engine = engine
        self._account = account

        self._engine_start()
        self._init_signals_engine()

    def load_account_mediatype(self, account, mediatype, extern_widget):
        if account:
            self._account = account

        self._engine_reload(account, mediatype, extern_widget)

    def _init_widgets(self):
        self.image_box = ImageBox(100, 150)
        self.image_box.show()
        self.image_container_box.pack_start(self.image_box, False, False, 0)

        self.notebook.set_scrollable(True)
        self.notebook.add_events(Gdk.EventMask.SCROLL_MASK |
                                 Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.notebook.connect('scroll-event', self._notebook_handle_events)
        self.notebook.connect('enter-notify-event',
                              self._notebook_handle_events)
        self.notebook.connect('leave-notify-event',
                              self._notebook_handle_events)

        self.statusbar = Gtk.Statusbar()
        self.statusbar.push(0, 'Trackma GTK ' + utils.VERSION)
        self.statusbar.show()
        self.pack_start(self.statusbar, False, False, 0)

    def _init_signals(self):
        self.btn_episode_remove.connect(
            "clicked", self._on_btn_episode_remove_clicked)
        self.btn_episode_show_entry.connect(
            "clicked", self._show_episode_entry)
        self.entry_episode.connect("activate", self._on_entry_episode_activate)
        self.entry_done.connect("clicked", self._on_entry_episode_activate)
        self.entry_popover.connect("focus-out-event", self._hide_episode_entry)
        self.btn_episode_add.connect(
            "clicked", self._on_btn_episode_add_clicked)
        self.btn_play_next.connect(
            "clicked", self._on_btn_play_next_clicked, True)
        self.spinbtn_score.connect("activate", self._on_spinbtn_score_activate)
        self.btn_score_set.connect("clicked", self._on_spinbtn_score_activate)
        self.statusbox_handler = self.statusbox.connect(
            "changed", self._on_statusbox_changed)
        self.notebook_switch_handler = self.notebook.connect(
            "switch-page", self._on_switch_notebook_page)

    def _init_signals_engine(self):
        self._engine.connect_signal(
            'episode_changed', self._on_changed_show_idle)
        self._engine.connect_signal(
            'score_changed', self._on_changed_show_idle)
        self._engine.connect_signal(
            'status_changed', self._on_changed_show_status_idle)
        self._engine.connect_signal('playing', self._on_playing_show_idle)
        self._engine.connect_signal(
            'show_added', self._on_changed_show_status_idle)
        self._engine.connect_signal(
            'show_deleted', self._on_changed_show_status_idle)
        self._engine.connect_signal(
            'prompt_for_update', self._on_prompt_update_next_idle)

    def _engine_start(self):
        threading.Thread(target=self._engine_start_task).start()

    def _engine_start_task(self):
        if self._engine.loaded:
            return

        try:
            self._engine.start()
        except utils.TrackmaFatal as e:
            self.emit('error-fatal', e)
            return

        GLib.idle_add(self._update_widgets)

    def _engine_reload(self, account, mediatype, extern_widget):
        self.set_buttons_sensitive(False)
        threading.Thread(target=self._engine_reload_task,
                         args=[account, mediatype, extern_widget]).start()

    def _engine_reload_task(self, account, mediatype, extern_widget):
        try:
            self._engine.reload(account, mediatype)
        except utils.TrackmaError as e:
            self.emit('error', e)
        except utils.TrackmaFatal as e:
            self.emit('error-fatal', e)
            return

        GLib.idle_add(self._update_widgets, extern_widget)

    def _update_widgets(self, extern_widget=None):
        self.statusbox.handler_block(self.statusbox_handler)
        self._reset_widgets()
        self._create_notebook_pages()
        self._set_score_ranges()
        self.populate_all_pages()
        self._populate_statusbox()
        self.statusbox.handler_unblock(self.statusbox_handler)
        if extern_widget is not None:
            extern_widget.set_subtitle(self._engine.api_info['name'] + " (" +
                                       self._engine.api_info['mediatype'] + ")")

        self.set_status_idle("Ready.")
        self.emit('success')
        self.set_buttons_sensitive_idle(True)

    def _reset_widgets(self):
        self.show_title.set_text('<span size="14000"><b>Trackma</b></span>')
        self.show_title.set_use_markup(True)
        self.image_box.reset()

        current_api = utils.available_libs[self._account['api']]
        api_iconfile = current_api[1]

        self.api_icon.set_from_file(api_iconfile)

        self.api_user.set_text("%s" % self._engine.get_userconfig('username'))

        can_play = self._engine.mediainfo['can_play']
        can_update = self._engine.mediainfo['can_update']

        self.btn_play_next.set_sensitive(can_play)
        self.btn_episode_show_entry.set_sensitive(can_update)
        self.entry_episode.set_sensitive(can_update)
        self.entry_done.set_sensitive(can_update)
        self.btn_episode_add.set_sensitive(can_update)

    def _notebook_handle_events(self, widget, event):
        if event.type in (Gdk.EventType.LEAVE_NOTIFY, Gdk.EventType.ENTER_NOTIFY):
            self._hovering_over_tabs = event.type == Gdk.EventType.ENTER_NOTIFY
        elif self._hovering_over_tabs and event.type == Gdk.EventType.SCROLL:
            page = self.notebook.get_current_page()
            npage = self.notebook.get_n_pages() - 1
            if event.delta_y < 0 and page > 0:
                self.notebook.prev_page()
            elif event.delta_y > 0 and page < npage:
                self.notebook.next_page()
            return event.delta_y < 0 and page > 0 or event.delta_y > 0 and page < npage
        return False

    def _create_notebook_pages(self):
        statuses_nums = self._engine.mediainfo['statuses'].copy()
        statuses_names = self._engine.mediainfo['statuses_dict'].copy()
        statuses_nums.append(None)
        statuses_names[None] = 'All'
        self.notebook.handler_block(self.notebook_switch_handler)
        # Clear notebook
        for i in range(self.notebook.get_n_pages()):
            self.notebook.remove_page(-1)

        self._pages = {}
        self._page_handler_ids = {}

        # Insert pages
        for status in statuses_nums:
            page_title = Gtk.Label(label=statuses_names[status])
            self._pages[status] = NotebookPage(self._engine,
                                               self.notebook.get_n_pages(),
                                               status,
                                               self._config,
                                               self._list,
                                               page_title)

            self._page_handler_ids[status] = []
            self._page_handler_ids[status].append(
                self._pages[status].connect('show-selected', self._on_show_selected))
            self._page_handler_ids[status].append(
                self._pages[status].connect('show-action', self._on_show_action))
            self._page_handler_ids[status].append(
                self._pages[status].connect('column-toggled', self._on_column_toggled))
            self.notebook.append_page(self._pages[status],
                                      page_title)

        self.notebook.handler_unblock(self.notebook_switch_handler)
        self.notebook.show_all()

    def populate_all_pages(self):
        for status in self._pages:
            self._block_handlers_for_status(status)
            tree_view = self._pages[status].show_tree_view
            tree_view.freeze_child_notify()

        self._list.clear()
        library = self._engine.library()
        for show in self._engine.get_list():
            self._list.append(show,
                              self._engine.altname(show['id']),
                              library.get(show['id']))

        self._list.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        for status in self._pages:
            tree_view = self._pages[status].show_tree_view
            tree_view.thaw_child_notify()
            self._unblock_handlers_for_status(status)

    def _block_handlers_for_status(self, status):
        for handler_id in self._page_handler_ids[status]:
            self._pages[status].handler_block(handler_id)

    def _unblock_handlers_for_status(self, status):
        for handler_id in self._page_handler_ids[status]:
            self._pages[status].handler_unblock(handler_id)

    def _populate_statusbox(self):
        statuses_nums = self._engine.mediainfo['statuses']
        statuses_names = self._engine.mediainfo['statuses_dict']

        self.statusmodel.clear()
        for status in statuses_nums:
            self.statusmodel.append([str(status), statuses_names[status]])
        self.statusbox.set_model(self.statusmodel)
        self.statusbox.show_all()

    def _set_score_ranges(self):
        score_decimal_places = 0
        if isinstance(self._engine.mediainfo['score_step'], float):
            score_decimal_places = len(
                str(self._engine.mediainfo['score_step']).split('.')[1])

        self.spinbtn_score.set_value(0)
        self.spinbtn_score.set_digits(score_decimal_places)
        self.spinbtn_score.set_range(0, self._engine.mediainfo['score_max'])
        self.spinbtn_score.get_adjustment().set_step_increment(
            self._engine.mediainfo['score_step'])

        for view in self._pages.values():
            view.decimals = score_decimal_places

    def set_status_idle(self, msg):
        # Thread safe
        GLib.idle_add(self._set_status, msg)

    def _set_status(self, msg):
        print(msg)
        self.statusbar.push(0, msg)

    def set_buttons_sensitive_idle(self, boolean):
        # Thread safe
        GLib.idle_add(self.set_buttons_sensitive, boolean)

    def set_buttons_sensitive(self, boolean, lists_too=True):
        if lists_too:
            self.notebook.set_sensitive(boolean)

        if (self._current_page and self._current_page.selected_show) or not boolean:
            if self._engine.mediainfo['can_play']:
                self.btn_play_next.set_sensitive(boolean)

            if self._engine.mediainfo['can_update']:
                self.btn_episode_show_entry.set_sensitive(boolean)
                self.entry_episode.set_sensitive(boolean)
                self.entry_done.set_sensitive(boolean)
                self.btn_episode_add.set_sensitive(boolean)
                self.btn_episode_remove.set_sensitive(boolean)

            self.btn_score_set.set_sensitive(boolean)
            self.spinbtn_score.set_sensitive(boolean)
            self.statusbox.set_sensitive(boolean)

    def _on_btn_episode_remove_clicked(self, widget):
        self.emit('show-action',
                  ShowEventType.EPISODE_REMOVE,
                  (self._current_page.selected_show,))

    def _show_episode_entry(self, widget):
        self.entry_popover.set_relative_to(widget)
        self.entry_popover.set_position(Gtk.PositionType.BOTTOM)
        self.entry_episode.set_text(self.btn_episode_show_entry.get_label())
        self.entry_popover.show()
        self.entry_episode.grab_focus()

    def _on_entry_episode_activate(self, widget):
        try:
            episode = int(self.entry_episode.get_text())
            self.emit('show-action',
                      ShowEventType.EPISODE_SET,
                      (self._current_page.selected_show, episode))
            self._hide_episode_entry()
        except ValueError:
            pass

    def _hide_episode_entry(self, *args):
        self.entry_popover.hide()

    def _on_btn_episode_add_clicked(self, widget):
        self.emit('show-action',
                  ShowEventType.EPISODE_ADD,
                  (self._current_page.selected_show,))

    def _on_btn_play_next_clicked(self, widget, playnext, ep=None):
        self.emit('show-action',
                  ShowEventType.PLAY_NEXT,
                  (self._current_page.selected_show,))

    def _on_spinbtn_score_activate(self, widget):
        score = self.spinbtn_score.get_value()
        self.emit('show-action',
                  ShowEventType.SET_SCORE,
                  (self._current_page.selected_show, score))

    def _on_statusbox_changed(self, widget):
        statusiter = self.statusbox.get_active_iter()
        status = self.statusmodel.get(statusiter, 0)[0]
        self.emit('show-action',
                  ShowEventType.SET_STATUS,
                  (self._current_page.selected_show, status))

    def message_handler(self, classname, msgtype, msg):
        # Thread safe
        if msgtype == messenger.TYPE_WARN:
            self.set_status_idle("%s warning: %s" % (classname, msg))
        elif msgtype != messenger.TYPE_DEBUG:
            self.set_status_idle("%s: %s" % (classname, msg))
        elif self._debug:
            print('[D] {}: {}'.format(classname, msg))

    def _on_changed_show_idle(self, show):
        GLib.idle_add(self._update_show, show)

    def _update_show(self, show):
        status = show['my_status']
        self._list.update(show)
        if self._current_page and show['id'] == self._current_page.selected_show:
            self.btn_episode_show_entry.set_label(str(show['my_progress']))
            self.spinbtn_score.set_value(show['my_score'])

    def change_show_title_idle(self, show, altname):
        GLib.idle_add(self._update_show_title, show, altname)

    def _update_show_title(self, show, altname):
        self._list.update_title(show, altname)

    def _on_changed_show_status_idle(self, show, old_status=None):
        GLib.idle_add(self._update_show_status, show, old_status)

    def _update_show_status(self, show, old_status):
        # Rebuild lists
        status = show['my_status']
        try:
            self._engine.get_show_info(showid=show['id'])
            self._list.update_or_append(show)
        except utils.EngineError:
            self._list.remove(show)
        pagenumber = self._pages[status].pagenumber
        current_page = self.notebook.get_current_page()
        if current_page != pagenumber:
            if current_page != self._pages[None].pagenumber:
                self.notebook.set_current_page(pagenumber)
                self._pages[status].show_tree_view.select(show)
            else:
                self._pages[None].show_tree_view.select(show)

    def _on_playing_show_idle(self, show, is_playing, episode):
        GLib.idle_add(self._set_show_playing, show, is_playing, episode)

    def _set_show_playing(self, show, is_playing, episode):
        self._list.playing(show, is_playing)

    def _on_prompt_update_next_idle(self, show, played_ep):
        GLib.idle_add(self._prompt_update_next, show, played_ep)

    def _prompt_update_next(self, show, played_ep):
        dialog = Gtk.MessageDialog(self.get_toplevel(),
                                   Gtk.DialogFlags.MODAL,
                                   Gtk.MessageType.QUESTION,
                                   Gtk.ButtonsType.YES_NO,
                                   "Update %s to episode %d?" % (show['title'], played_ep))
        dialog.show_all()
        dialog.connect(
            "response", self._on_response_update_next, show, played_ep)

    def _on_response_update_next(self, widget, response, show, played_ep):
        widget.destroy()
        if response == Gtk.ResponseType.YES:
            self.emit('show-action',
                      ShowEventType.EPISODE_SET,
                      (show['id'], played_ep))

    def _on_switch_notebook_page(self, notebook, page, page_num):
        self._current_page = page
        self._update_widgets_for_selected_show()

    def _on_show_selected(self, page, selected_show):
        self._update_widgets_for_selected_show()

    def _update_widgets_for_selected_show(self):
        if not (self._current_page and self._current_page.selected_show):
            self.set_buttons_sensitive(False, lists_too=False)
            return

        self.set_buttons_sensitive(True, lists_too=False)
        try:
            show = self._engine.get_show_info(self._current_page.selected_show)
        except utils.EngineError:
            self._list.remove(show_id=self._current_page.selected_show)
            self.set_buttons_sensitive(False, lists_too=False)
            return

        # Block handlers
        self.statusbox.handler_block(self.statusbox_handler)

        if self._image_thread is not None:
            self._image_thread.cancel()

        self.show_title.set_text(
            '<span size="14000"><b>{0}</b></span>'.format(html.escape(show['title'])))
        self.show_title.set_use_markup(True)

        # Episode selector
        self.btn_episode_show_entry.set_label(str(show['my_progress']))

        # Status selector
        for i in self.statusmodel:
            if str(i[0]) == str(show['my_status']):
                self.statusbox.set_active_iter(i.iter)
                break

        # Score selector
        self.spinbtn_score.set_value(show['my_score'])

        # Image
        if show.get('image_thumb') or show.get('image'):
            utils.make_dir(utils.to_cache_path())
            filename = utils.to_cache_path(
                "%s_%s_%s.jpg" % (self._engine.api_info['shortname'],
                                  self._engine.api_info['mediatype'],
                                  show['id']))

            if os.path.isfile(filename):
                self.image_box.set_image(filename)
            else:
                self.image_box.set_image_remote(show.get('image_thumb') or show['image'],
                                                filename)
        else:
            self.image_box.set_text('No Image')

        # Unblock handlers
        self.statusbox.handler_unblock(self.statusbox_handler)

    def _on_show_action(self, page, event_type, data):
        self.emit('show-action', event_type, data)

    def get_current_status(self):
        print(self._engine.mediainfo['statuses'])
        return self._current_page.status if self._current_page.status is not None else self._engine.mediainfo['statuses'][-1]

    def get_selected_show(self):
        if not self._current_page:
            return None

        return self._current_page.selected_show

    def _on_column_toggled(self, page, column_name, visible):
        if visible:
            # Make column visible
            self._config['visible_columns'].append(column_name)
        else:
            # Make column invisible
            if len(self._config['visible_columns']) <= 1:
                return  # There should be at least 1 column visible

            self._config['visible_columns'].remove(column_name)

        for page in self._pages.values():
            page.set_column_visible(column_name, visible)

        utils.save_config(self._config, self._configfile)


class NotebookPage(Gtk.ScrolledWindow):
    __gtype_name__ = 'NotebookPage'

    __gsignals__ = {
        'show-selected': (GObject.SignalFlags.RUN_FIRST, None,
                          (int, )),
        'show-action': (GObject.SignalFlags.RUN_FIRST, None,
                        (int, object)),
        'column-toggled': (GObject.SignalFlags.RUN_FIRST, None,
                           (str, bool)),
    }

    def __init__(self, engine, page_num, status, config, _list=None, title=None):
        super().__init__()
        self._engine = engine
        self._page_number = page_num
        self._status = status
        self._selected_show = 0
        self._list = _list
        self._title = title
        self._title_text = self._engine.mediainfo['statuses_dict'][status] if status in self._engine.mediainfo['statuses_dict'].keys(
        ) else 'All'
        self._init_widgets(page_num, status, config)

    def _init_widgets(self, page_num, status, config):
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.set_size_request(550, 300)
        self.set_border_width(5)

        self._show_tree_view = ShowTreeView(
            config['colors'],
            config['visible_columns'],
            config['episodebar_style'])
        self._show_tree_view.set_model(
            Gtk.TreeModelSort(
                model=ShowListFilter(
                    status=self.status,
                    child_model=self._list
                )
            )
        )
        self._title.set_text('%s (%d)' % (
            self._title_text,
            len(self._show_tree_view.props.model)
        ))
        self._show_tree_view.get_selection().connect(
            "changed", self._on_selection_changed)
        self._show_tree_view.connect("row-activated", self._on_row_activated)
        self._show_tree_view.connect("column-toggled", self._on_column_toggled)
        self._show_tree_view.connect(
            "button-press-event", self._on_show_context_menu)
        self._show_tree_view.get_model().connect("row-inserted", self._update_title)
        self._show_tree_view.get_model().connect("row-deleted", self._update_title)

        self.add(self._show_tree_view)

    def set_column_visible(self, column_name, visible):
        self._show_tree_view.cols[column_name].set_visible(visible)

    def _update_title(self, model, *args):
        self._title.set_text('%s (%d)' % (
            self._title_text,
            len(model)
        ))

    @property
    def decimals(self):
        return self._list.decimals

    @decimals.setter
    def decimals(self, decimals):
        self._list.decimals = decimals

    @property
    def status(self):
        return self._status

    @property
    def pagenumber(self):
        return self._page_number

    @property
    def selected_show(self):
        return self._selected_show

    @property
    def show_tree_view(self):
        return self._show_tree_view

    def _on_selection_changed(self, selection):
        (tree_model, tree_iter) = selection.get_selected()
        if not tree_iter:
            self._selected_show = 0
            return

        try:
            self._selected_show = int(tree_model.get(tree_iter, 0)[0])
        except ValueError:
            self._selected_show = tree_model.get(tree_iter, 0)[0]

        self.emit('show-selected', self._selected_show)

    def _on_row_activated(self, tree_view, path, column):
        self.emit('show-action', ShowEventType.DETAILS, (self.selected_show,))

    def _on_column_toggled(self, tree_view, column_name, visible):
        self.emit('column-toggled', column_name, visible)

    def _on_show_context_menu(self, tree_view, event):
        x = int(event.x)
        y = int(event.y)
        pthinfo = tree_view.get_path_at_pos(x, y)

        if (event.type == Gdk.EventType.BUTTON_PRESS and
                event.button == Gdk.BUTTON_SECONDARY and pthinfo):
            path, col, cellx, celly = pthinfo
            tree_view.grab_focus()
            tree_view.set_cursor(path, col, 0)
            self._view_context_menu(event)
            return True

        return False

    def _view_context_menu(self, event):
        show = self._engine.get_show_info(self._selected_show)

        menu = Gtk.Menu()
        mb_play = Gtk.ImageMenuItem('Play Next',
                                    Gtk.Image.new_from_icon_name(
                                        "media-playback-start", Gtk.IconSize.MENU))
        mb_play.connect("activate",
                        self._on_mb_activate,
                        ShowEventType.PLAY_NEXT)
        mb_info = Gtk.MenuItem("Show details...")
        mb_info.connect("activate",
                        self._on_mb_activate,
                        ShowEventType.DETAILS)
        mb_web = Gtk.MenuItem("Open web site")
        mb_web.connect("activate",
                       self._on_mb_activate,
                       ShowEventType.OPEN_WEBSITE)
        mb_folder = Gtk.MenuItem("Open containing folder")
        mb_folder.connect("activate",
                          self._on_mb_activate,
                          ShowEventType.OPEN_FOLDER)
        mb_copy = Gtk.MenuItem("Copy title to clipboard")
        mb_copy.connect("activate",
                        self._on_mb_activate,
                        ShowEventType.COPY_TITLE)
        mb_alt_title = Gtk.MenuItem("Set alternate title...")
        mb_alt_title.connect("activate",
                             self._on_mb_activate,
                             ShowEventType.CHANGE_ALTERNATIVE_TITLE)
        mb_delete = Gtk.ImageMenuItem('Delete',
                                      Gtk.Image.new_from_icon_name(
                                          "edit-delete", Gtk.IconSize.MENU))
        mb_delete.connect("activate",
                          self._on_mb_activate,
                          ShowEventType.REMOVE)

        menu.append(mb_play)

        menu_eps = self._build_episode_menu(show)

        mb_playep = Gtk.MenuItem("Play episode")
        mb_playep.set_submenu(menu_eps)
        mb_playep.set_sensitive(bool(menu_eps.get_children()))
        menu.append(mb_playep)

        menu.append(mb_info)
        menu.append(mb_web)
        menu.append(mb_folder)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(mb_copy)
        menu.append(mb_alt_title)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(mb_delete)

        menu.show_all()
        menu.popup_at_pointer(event)

    def _build_episode_menu(self, show):
        library_episodes = set(self._engine.library().get(show['id'], ()))
        total = show['total'] or max(
            show['my_progress'],
            *library_episodes,
            utils.estimate_aired_episodes(show)
        )
        next_ep = show['my_progress'] + 1

        menu_eps = Gtk.Menu()
        for i in range(1, total + 1):
            mb_playep = Gtk.CheckMenuItem(str(i))
            if i == next_ep:
                mb_playep.set_label(str(i) + " - Next")
                mb_playep.set_margin_left(10)
                menu_eps.set_focus_child(mb_playep)
            mb_playep.set_inconsistent(i < next_ep)
            mb_playep.set_active(i in library_episodes)
            mb_playep.set_draw_as_radio(True)
            mb_playep.connect("activate",
                              self._on_mb_activate,
                              ShowEventType.PLAY_EPISODE, i)
            menu_eps.append(mb_playep)

        return menu_eps

    def _on_mb_activate(self, menu_item, event_type, data=None):
        data = (self._selected_show,) if data is None else (
            self._selected_show, data)
        self.emit('show-action', event_type, data)

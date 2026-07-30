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

from gi.repository import GLib, Gdk, Gio, Gtk

from hakubun import messenger
from hakubun import utils
from hakubun.accounts import AccountManager
from hakubun.engine import Engine
from hakubun.ui.gtk import gtk_dir
from hakubun.ui.gtk.accountswindow import AccountsWindow
from hakubun.ui.gtk.mainview import MainView
from hakubun.ui.gtk.searchwindow import SearchWindow
from hakubun.ui.gtk.settingswindow import SettingsWindow
from hakubun.ui.gtk.showeventtype import ShowEventType
from hakubun.ui.gtk.showinfowindow import ShowInfoWindow
from hakubun.ui.gtk.statusicon import TrackmaStatusIcon


@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/window.ui'))
class TrackmaWindow(Gtk.ApplicationWindow):
    __gtype_name__ = 'TrackmaWindow'

    btn_appmenu = Gtk.Template.Child()
    btn_search = Gtk.Template.Child()
    mediatype_box = Gtk.Template.Child()
    header_bar = Gtk.Template.Child()

    def __init__(self, app, debug=False):
        Gtk.ApplicationWindow.__init__(self, application=app)
        self.init_template()

        # GtkHeaderBar's end-packing order isn't reliably controllable via
        # <packing> position in the .ui file (verified empirically -- it's
        # silently ignored there), so force it here instead. Lower
        # "position" among pack-type=end children sits closer to the true
        # edge, so appmenu (position 0) ends up rightmost.
        self.header_bar.child_set_property(self.btn_appmenu, 'position', 0)
        self.header_bar.child_set_property(self.mediatype_box, 'position', 1)

        self._debug = debug
        self._configfile = utils.to_config_path('ui-Gtk.json')
        self._config = utils.parse_config(self._configfile, utils.gtk_defaults)

        self.statusicon = None
        self._main_view = None
        self._modals = []

        self._account = None
        self._engine = None
        self.close_thread = None
        self.hidden = False

        self._init_widgets()

    def init_account_selection(self):
        manager = AccountManager()

        # Use the remembered account if there's one
        if manager.get_default():
            self._create_engine(manager.get_default())
        else:
            self._show_accounts(switch=False)

    def _init_widgets(self):
        Gtk.Window.set_default_icon_from_file(utils.DATADIR + '/icon.png')
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Trackma')

        if self._config['remember_geometry']:
            self.resize(self._config['last_width'],
                        self._config['last_height'])

        if not self._main_view:
            self._main_view = MainView(self._config)
            self._main_view.connect('error', self._on_main_view_error)
            self._main_view.connect(
                'success', lambda x: self._set_buttons_sensitive(True))
            self._main_view.connect(
                'error-fatal', self._on_main_view_error_fatal)
            self._main_view.connect('show-action', self._on_show_action)

            # The filter bar lives directly below the header bar (outside
            # MainView's own margined layout) so revealing it visually
            # drops down from the very top of the window, full width,
            # instead of appearing squeezed in among the show details.
            self.search_entry = Gtk.SearchEntry()
            self.search_entry.set_placeholder_text('Filter shows...')
            self.search_entry.set_width_chars(48)
            self.search_bar = Gtk.SearchBar()
            self.search_bar.add(self.search_entry)
            self.search_bar.connect_entry(self.search_entry)
            self.search_entry.connect('search-changed', self._on_search_changed)

            content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            content_box.pack_start(self.search_bar, False, False, 0)
            content_box.pack_start(self._main_view, True, True, 0)
            content_box.show_all()
            self.add(content_box)

        self.connect('delete_event', self._on_delete_event)
        self.connect('key-press-event', self._on_key_press)

        builder = Gtk.Builder.new_from_file(
            os.path.join(gtk_dir, 'data/shortcuts.ui'))
        help_overlay = builder.get_object('shortcuts-window')
        self.set_help_overlay(help_overlay)

        # Status icon
        if TrackmaStatusIcon.is_tray_available():
            self.statusicon = TrackmaStatusIcon()
            self.statusicon.connect('hide-clicked', self._on_tray_hide_clicked)
            self.statusicon.connect(
                'about-clicked', self._on_tray_about_clicked)
            self.statusicon.connect('quit-clicked', self._on_tray_quit_clicked)

            if self._config['show_tray']:
                self.statusicon.set_visible(True)
            else:
                self.statusicon.set_visible(False)

        # Don't show the main window if start in tray option is set
        if self.statusicon and self._config['show_tray'] and self._config['start_in_tray']:
            self.hidden = True
        else:
            self.present()

    def _on_tray_hide_clicked(self, status_icon):
        self._destroy_modals()

        if self.hidden:
            self.deiconify()
            self.present()

            if not self._engine:
                self._show_accounts(switch=False)
        else:
            self.hide()

        self.hidden = not self.hidden

    def _destroy_modals(self):
        self.get_help_overlay().hide()

        for modal_window in self._modals:
            modal_window.destroy()

        self._modals = []

    def _on_tray_about_clicked(self, status_icon):
        self._on_about(None, None)

    def _on_tray_quit_clicked(self, status_icon):
        self._quit()

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_slash:
            focus = self.get_focus()
            if isinstance(focus, (Gtk.Entry, Gtk.TextView)):
                return False
            self.reveal_search()
            return True
        return False

    def _on_filter(self, action, param):
        self.reveal_search()

    def reveal_search(self):
        """Shows (or focuses, if already shown) the show-list filter bar."""
        self.search_bar.set_search_mode(True)
        self.search_entry.grab_focus()

    def _on_search_changed(self, entry):
        self._main_view.filter_shows(entry.get_text())

    def _on_delete_event(self, widget, event, data=None):
        if self.statusicon and self.statusicon.get_visible() and self._config['close_to_tray']:
            self.hidden = True
            self.hide()
        else:
            self._quit()
        return True

    def _create_engine(self, account):
        self._engine = Engine(account, self._message_handler)
        self._engine.connect_signal(
            'undo_stack_changed', self._on_undo_stack_changed)

        self._main_view.load_engine_account(self._engine, account)
        self._set_actions()
        self._set_mediatypes_buttons()
        self._update_widgets(account)
        self._set_buttons_sensitive(True)

    def _set_actions(self):
        builder = Gtk.Builder.new_from_file(
            os.path.join(gtk_dir, 'data/app-menu.ui'))
        settings = Gtk.Settings.get_default()
        if not settings.get_property("gtk-shell-shows-menubar"):
            self.btn_appmenu.set_menu_model(builder.get_object('app-menu'))
        else:
            self.get_application().set_menubar(builder.get_object('menu-bar'))
            self.btn_appmenu.set_property('visible', False)

        def add_action(name, callback):
            action = Gio.SimpleAction.new(name, None)
            action.connect('activate', callback)
            self.add_action(action)

        add_action('search', self._on_search)
        add_action('synchronize', self._on_synchronize)
        add_action('upload', self._on_upload)
        add_action('download', self._on_download)
        add_action('scanfiles', self._on_scanfiles)
        add_action('accounts', self._on_accounts)
        add_action('preferences', self._on_preferences)
        add_action('about', self._on_about)

        add_action('filter', self._on_filter)

        self.action_undo = Gio.SimpleAction.new('undo', None)
        self.action_undo.connect('activate', self._on_undo)
        self.action_undo.set_enabled(False)
        self.add_action(self.action_undo)
        self.action_redo = Gio.SimpleAction.new('redo', None)
        self.action_redo.connect('activate', self._on_redo)
        self.action_redo.set_enabled(False)
        self.add_action(self.action_redo)

        add_action('play_next', self._on_action_play_next)
        add_action('play_random', self._on_action_play_random)
        add_action('episode_add', self._on_action_episode_add)
        add_action('episode_remove', self._on_action_episode_remove)
        add_action('delete', self._on_action_delete)
        add_action('copy', self._on_action_copy)

    def _set_mediatypes_buttons(self):
        """
        Media type (anime/manga/etc) switcher, shown as plain toggle
        buttons directly on the title bar instead of a menu -- there are
        only ever a handful of these, and burying them behind a click
        just to see (let alone change) the current one isn't worth it.
        """
        for child in self.mediatype_box.get_children():
            self.mediatype_box.remove(child)

        mediatypes = self._engine.api_info['supported_mediatypes']

        if len(mediatypes) <= 1:
            self.mediatype_box.hide()
            return

        current = self._engine.api_info['mediatype']
        group = None
        for mediatype in mediatypes:
            btn = Gtk.RadioButton.new_with_label_from_widget(group, mediatype.capitalize())
            # Draw as a plain button, not a radio button with a dot.
            btn.set_mode(False)
            if group is None:
                group = btn
            btn.set_active(mediatype == current)
            btn.connect('toggled', self._on_mediatype_button_toggled, mediatype)
            btn.show()
            self.mediatype_box.add(btn)

        self.mediatype_box.show()

    def _update_widgets(self, account):
        current_api = utils.available_libs[account['api']]
        api_iconpath = 1
        api_iconfile = current_api[api_iconpath]

        self.header_bar.set_subtitle(self._engine.api_info['name'] + " (" +
                                     self._engine.api_info['mediatype'] + ")")

        if self.statusicon and self._config['tray_api_icon']:
            self.statusicon.set_from_file(api_iconfile)

    def _on_mediatype_button_toggled(self, button, mediatype):
        if not button.get_active():
            return
        if mediatype == self._engine.api_info['mediatype']:
            return
        self._set_buttons_sensitive(False)
        self._main_view.load_account_mediatype(
            None, mediatype, self.header_bar)

    def _on_search(self, action, param):
        current_status = self._main_view.get_current_status()
        win = SearchWindow(
            self._engine, self._config['colors'], current_status, transient_for=self)
        win.connect('search-error', self._on_search_error)
        win.connect('go-to-show', self._on_go_to_show)
        win.connect('destroy', self._on_modal_destroy)
        win.present()
        self._modals.append(win)

    def _on_search_error(self, search_window, error_msg):
        print(error_msg)

    def _on_go_to_show(self, search_window, showid):
        self._main_view.go_to_show(showid)
        search_window.destroy()

    def _on_synchronize(self, action, param):
        threading.Thread(target=self._synchronization_task,
                         args=(True, True)).start()

    def _on_upload(self, action, param):
        threading.Thread(target=self._synchronization_task,
                         args=(True, False)).start()

    def _on_undo(self, action, param):
        # The setter called internally (set_status/set_episode/etc.) emits
        # its usual signal, which the existing per-show refresh handlers
        # already pick up -- no extra UI refresh needed here.
        try:
            self._engine.undo()
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _on_redo(self, action, param):
        try:
            self._engine.redo()
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _on_undo_stack_changed(self):
        GLib.idle_add(self._update_undo_redo_sensitivity)

    def _update_undo_redo_sensitivity(self):
        self.action_undo.set_enabled(self._engine.can_undo())
        self.action_redo.set_enabled(self._engine.can_redo())

    def _on_download(self, action, param):
        def _download_lists():
            threading.Thread(target=self._synchronization_task,
                             args=(False, True)).start()

        def _on_download_response(_dialog, response):
            _dialog.destroy()

            if response == Gtk.ResponseType.YES:
                _download_lists()

        queue = self._engine.get_queue()
        if queue:
            dialog = Gtk.MessageDialog(self,
                                       Gtk.DialogFlags.MODAL,
                                       Gtk.MessageType.QUESTION,
                                       Gtk.ButtonsType.YES_NO,
                                       "There are %d queued changes in your list. If you retrieve the remote list now you will lose your queued changes. Are you sure you want to continue?" % len(queue))
            dialog.show_all()
            dialog.connect("response", _on_download_response)
        else:
            # If the user doesn't have any queued changes
            # just go ahead
            _download_lists()

    def _synchronization_task(self, send, retrieve):
        self._set_buttons_sensitive_idle(False)

        try:
            if send:
                self._engine.list_upload()
            if retrieve:
                self._engine.list_download()

            # GLib.idle_add(self._set_score_ranges)
            GLib.idle_add(self._main_view.populate_all_pages)
        except utils.TrackmaError as e:
            self._error_dialog_idle(e)
        except utils.TrackmaFatal as e:
            self._show_accounts_idle(switch=False, forget=True)
            self._error_dialog_idle("Fatal engine error: %s" % e)
            return

        self._main_view.set_status_idle("Ready.")
        self._set_buttons_sensitive_idle(True)

    def _on_scanfiles(self, action, param):
        threading.Thread(target=self._scanfiles_task).start()

    def _scanfiles_task(self):
        self._set_buttons_sensitive_idle(False)
        try:
            self._engine.scan_library(rescan=True)
        except utils.TrackmaError as e:
            self._error_dialog_idle(e)

        GLib.idle_add(self._main_view.populate_all_pages)

        self._main_view.set_status_idle("Ready.")
        self._set_buttons_sensitive_idle(True)

    def _on_accounts(self, action, param):
        self._show_accounts()

    def _show_accounts_idle(self, switch=True, forget=False):
        GLib.idle_add(self._show_accounts, switch, forget)

    def _show_accounts(self, switch=True, forget=False):
        manager = AccountManager()

        if forget:
            manager.set_default(None)

        accountsel = AccountsWindow(manager, transient_for=self)
        accountsel.connect('account-open', self._on_account_open)
        accountsel.connect('account-cancel', self._on_account_cancel, switch)
        accountsel.connect('destroy', self._on_modal_destroy)
        accountsel.present()
        self._modals.append(accountsel)

    def _on_account_open(self, accounts_window, account_num, remember):
        manager = AccountManager()
        account = manager.get_account(account_num)

        if remember:
            manager.set_default(account_num)
        else:
            manager.set_default(None)

        # Reload the engine if already started,
        # start it otherwise
        self._set_buttons_sensitive(False)
        if self._engine and self._engine.loaded:
            self._main_view.load_account_mediatype(account, None, None)
        else:
            self._create_engine(account)

    def _on_account_cancel(self, _accounts_window, switch):
        manager = AccountManager()

        if not switch or not manager.get_accounts():
            self._quit()

    def _on_preferences(self, _action, _param):
        win = SettingsWindow(self._engine, self._config,
                             self._configfile, transient_for=self)
        win.connect('destroy', self._on_modal_destroy)
        win.connect('settings-saved', self._on_settings_saved)
        win.present()
        self._modals.append(win)

    def _on_settings_saved(self, _settings_window):
        if self._engine.get_config('sync_on_settings_apply'):
            threading.Thread(target=self._synchronization_task,
                             args=(True, False)).start()

    def _on_about(self, _action, _param):
        about = Gtk.AboutDialog(parent=self)
        about.set_modal(True)
        about.set_transient_for(self)
        about.set_program_name("Trackma GTK")
        about.set_version(utils.VERSION)
        about.set_license_type(Gtk.License.GPL_3_0_ONLY)
        about.set_comments(
            "Trackma is an open source client for media tracking websites.\nThanks to all contributors.")
        about.set_website("https://github.com/z411/trackma")
        about.set_copyright("© z411, et al.")
        about.set_authors(["See AUTHORS file"])
        about.set_artists(["shuuichi"])
        about.connect('destroy', self._on_modal_destroy)
        about.connect('response', lambda dialog, response: dialog.destroy())
        about.present()
        self._modals.append(about)

    def _on_modal_destroy(self, modal_window):
        self._modals.remove(modal_window)

    def _quit(self):
        if self._config['remember_geometry']:
            self._store_geometry()

        if not self._engine:
            self.get_application().quit()
            return

        if self.close_thread is None:
            self._set_buttons_sensitive_idle(False)
            self.close_thread = threading.Thread(target=self._unload_task)
            self.close_thread.start()

    def _unload_task(self):
        self._engine.unload()
        GLib.idle_add(self.get_application().quit)

    def _store_geometry(self):
        (width, height) = self.get_size()
        self._config['last_width'] = width
        self._config['last_height'] = height
        utils.save_config(self._config, self._configfile)

    def _message_handler(self, classname, msgtype, msg):
        # Thread safe
        # print("%s: %s" % (classname, msg))
        if msgtype == messenger.TYPE_WARN:
            self._main_view.set_status_idle(
                "%s warning: %s" % (classname, msg))
        elif msgtype != messenger.TYPE_DEBUG:
            self._main_view.set_status_idle("%s: %s" % (classname, msg))
        elif self._debug:
            print('[D] {}: {}'.format(classname, msg))

    def _on_main_view_error(self, main_view, error_msg):
        self._error_dialog_idle(error_msg)

    def _on_main_view_error_fatal(self, main_view, error_msg):
        self._show_accounts_idle(switch=False, forget=True)
        self._error_dialog_idle(error_msg)

    def _error_dialog_idle(self, msg, icon=Gtk.MessageType.ERROR):
        # Thread safe
        GLib.idle_add(self._error_dialog, msg, icon)

    def _error_dialog(self, msg, icon=Gtk.MessageType.ERROR):
        def error_dialog_response(widget, response_id):
            widget.destroy()

        dialog = Gtk.MessageDialog(self,
                                   Gtk.DialogFlags.MODAL,
                                   icon,
                                   Gtk.ButtonsType.OK,
                                   str(msg))
        dialog.show_all()
        dialog.connect("response", error_dialog_response)
        print('Error: {}'.format(msg))

    def _on_action_play_next(self, action, param):
        selected_show = self._main_view.get_selected_show()

        if selected_show:
            self._play_next(selected_show)

    def _on_action_play_random(self, action, param):
        self._play_random()

    def _on_action_episode_add(self, action, param):
        selected_show = self._main_view.get_selected_show()

        if selected_show:
            self._episode_add(selected_show)

    def _on_action_episode_remove(self, action, param):
        selected_show = self._main_view.get_selected_show()

        if selected_show:
            self._episode_remove(selected_show)

    def _on_action_delete(self, action, param):
        selected_show = self._main_view.get_selected_show()

        if selected_show:
            self._remove_show(selected_show)

    def _on_action_copy(self, action, param):
        selected_show = self._main_view.get_selected_show()

        if selected_show:
            self._copy_title(selected_show)

    def _on_show_action(self, main_view, event_type, data):
        if event_type == ShowEventType.PLAY_NEXT:
            self._play_next(*data)
        elif event_type == ShowEventType.PLAY_EPISODE:
            self._play_episode(*data)
        elif event_type == ShowEventType.PLAY_EPISODE_PICK:
            self._play_episode_pick(*data)
        elif event_type == ShowEventType.EPISODE_REMOVE:
            self._episode_remove(*data)
        elif event_type == ShowEventType.EPISODE_SET:
            self._episode_set(*data)
        elif event_type == ShowEventType.EPISODE_ADD:
            self._episode_add(*data)
        elif event_type == ShowEventType.SET_SCORE:
            self._set_score(*data)
        elif event_type == ShowEventType.SET_STATUS:
            self._set_status(*data)
        elif event_type == ShowEventType.DETAILS:
            self._open_details(*data)
        elif event_type == ShowEventType.OPEN_WEBSITE:
            self._open_website(*data)
        elif event_type == ShowEventType.OPEN_FOLDER:
            self._open_folder(*data)
        elif event_type == ShowEventType.SET_FOLDER:
            self._set_folder(*data)
        elif event_type == ShowEventType.CLEAR_FOLDER:
            self._clear_folder(*data)
        elif event_type == ShowEventType.COPY_TITLE:
            self._copy_title(*data)
        elif event_type == ShowEventType.CHANGE_ALTERNATIVE_TITLE:
            self._change_alternative_title(*data)
        elif event_type == ShowEventType.REMOVE:
            self._remove_show(*data)

    def _play_next(self, show_id):
        show = self._engine.get_show_info(show_id)
        try:
            args = self._engine.play_episode(show)
            utils.spawn_process(args)
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _play_episode(self, show_id, episode):
        show = self._engine.get_show_info(show_id)
        try:
            if not episode:
                episode = self.show_ep_num.get_value_as_int()
            args = self._engine.play_episode(show, episode)
            utils.spawn_process(args)
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _play_episode_pick(self, show_id):
        show = self._engine.get_show_info(show_id)
        total = show['total'] or utils.estimate_aired_episodes(show) or 0
        ep_max = total if total > 0 else 100000
        ep_default = min(show['my_progress'] + 1, ep_max)

        dialog = Gtk.MessageDialog(
            self,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.QUESTION,
            Gtk.ButtonsType.OK_CANCEL,
            None)
        dialog.set_markup('Play <b>episode</b> of %s' %
                          GLib.markup_escape_text(show['title']))
        adjustment = Gtk.Adjustment(
            value=ep_default, lower=1, upper=ep_max,
            step_increment=1, page_increment=10)
        spin = Gtk.SpinButton()
        spin.set_adjustment(adjustment)
        spin.set_numeric(True)
        spin.connect(
            "activate", lambda entry: dialog.response(Gtk.ResponseType.OK))
        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label("Episode:"), False, 5, 5)
        hbox.pack_end(spin, True, True, 0)
        dialog.vbox.pack_end(hbox, True, True, 0)
        dialog.show_all()
        retval = dialog.run()

        if retval == Gtk.ResponseType.OK:
            self._play_episode(show_id, spin.get_value_as_int())

        dialog.destroy()

    def _play_random(self):
        try:
            args = self._engine.play_random()
            utils.spawn_process(args)
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _episode_add(self, show_id):
        show = self._engine.get_show_info(show_id)
        self._episode_set(show_id, show['my_progress'] + 1)

    def _episode_remove(self, show_id):
        show = self._engine.get_show_info(show_id)
        self._episode_set(show_id, show['my_progress'] - 1)

    def _episode_set(self, show_id, episode):
        try:
            self._engine.set_episode(show_id, episode)
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _set_score(self, show_id, score):
        try:
            self._engine.set_score(show_id, score)
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _set_status(self, show_id, status):
        try:
            self._engine.set_status(show_id, status)
        except utils.TrackmaError as e:
            self._error_dialog(e)

    def _open_details(self, show_id):
        show = self._engine.get_show_info(show_id)
        win = ShowInfoWindow(self._engine, show, transient_for=self)
        win.connect('destroy', self._on_modal_destroy)
        win.present()
        self._modals.append(win)

    def _open_website(self, show_id):
        show = self._engine.get_show_info(show_id)
        if show['url']:
            Gtk.show_uri(None, show['url'], Gdk.CURRENT_TIME)

    def _open_folder(self, show_id):
        try:
            self._engine.open_show_folder(show_id)
        except utils.EngineError as e:
            self._error_dialog_idle(e.args[0])

    def _set_folder(self, show_id):
        show = self._engine.get_show_info(show_id)
        current = self._engine.get_show_folder(show_id)
        dialog = Gtk.FileChooserDialog(
            title='Select folder for %s' % show['title'],
            parent=self, action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                           Gtk.STOCK_OK, Gtk.ResponseType.OK)
        if current:
            dialog.set_filename(current)
        response = dialog.run()
        folder = dialog.get_filename() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        if not folder:
            return
        threading.Thread(target=self._set_folder_task,
                         args=(show_id, folder)).start()

    def _set_folder_task(self, show_id, folder):
        # Manually pointing a show at a folder bypasses filename
        # guessing for it -- the escape hatch for a folder the parser
        # can't (or shouldn't have to) make sense of. Mirrors
        # _scanfiles_task: runs off the main thread since it walks the
        # folder immediately, same as any other library scan.
        self._set_buttons_sensitive_idle(False)
        try:
            self._engine.set_show_folder(show_id, folder)
        except utils.HakubunError as e:
            self._error_dialog_idle(e)
        finally:
            self._set_buttons_sensitive_idle(True)

    def _clear_folder(self, show_id):
        self._engine.unset_show_folder(show_id)
        self._main_view.set_status_idle('Folder cleared.')

    def _copy_title(self, show_id):
        show = self._engine.get_show_info(show_id)
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(show['title'], -1)

        self._main_view.set_status_idle('Title copied to clipboard.')

    def _change_alternative_title(self, show_id):
        show = self._engine.get_show_info(show_id)
        current_altname = self._engine.altname(show_id)

        def altname_response(entry, dialog, response):
            dialog.response(response)

        dialog = Gtk.MessageDialog(
            self,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.QUESTION,
            Gtk.ButtonsType.OK_CANCEL,
            None)
        dialog.set_markup('Set the <b>alternate title</b> for the show.')
        entry = Gtk.Entry()
        entry.set_text(current_altname)
        entry.connect("activate", altname_response,
                      dialog, Gtk.ResponseType.OK)
        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label("Alternate Title:"), False, 5, 5)
        hbox.pack_end(entry, True, True, 0)
        dialog.format_secondary_markup(
            "Use this if the tracker is unable to find this show. Leave blank to disable.")
        dialog.vbox.pack_end(hbox, True, True, 0)
        dialog.show_all()
        retval = dialog.run()

        if retval == Gtk.ResponseType.OK:
            text = entry.get_text()
            self._engine.altname(show_id, text)
            self._main_view.change_show_title_idle(show, text)

        dialog.destroy()

    def _remove_show(self, show_id):
        try:
            show = self._engine.get_show_info(show_id)
            self._engine.delete_show(show)
        except utils.TrackmaError as e:
            self._error_dialog_idle(e)

    def _set_buttons_sensitive_idle(self, sensitive):
        GLib.idle_add(self._set_buttons_sensitive, sensitive)
        self._main_view.set_buttons_sensitive_idle(sensitive)

    def _set_buttons_sensitive(self, sensitive):
        actions_names = ['search',
                         'synchronize',
                         'upload',
                         'download',
                         'scanfiles',
                         'accounts',
                         'play_next',
                         'play_random',
                         'episode_add',
                         'episode_remove',
                         'delete',
                         'copy']

        for action_name in actions_names:
            action = self.lookup_action(action_name)

            if action is not None:
                action.set_enabled(sensitive)

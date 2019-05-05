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
import subprocess
import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gio, Gtk, Gdk
from trackma.ui.gtk import gtk_dir
from trackma.ui.gtk.gi_composites import GtkTemplate
from trackma.ui.gtk.accountswindow import AccountsWindow
from trackma.ui.gtk.mainview import MainView
from trackma.ui.gtk.searchwindow import SearchWindow
from trackma.ui.gtk.settingswindow import SettingsWindow
from trackma.ui.gtk.showeventtype import ShowEventType
from trackma.ui.gtk.showinfowindow import ShowInfoWindow
from trackma.ui.gtk.statusicon import TrackmaStatusIcon
from trackma.engine import Engine
from trackma.accounts import AccountManager
from trackma import messenger
from trackma import utils


@GtkTemplate(ui=os.path.join(gtk_dir, 'data/window.ui'))
class TrackmaWindow(Gtk.ApplicationWindow):
    __gtype_name__ = 'TrackmaWindow'

    btn_appmenu = GtkTemplate.Child()
    btn_mediatype = GtkTemplate.Child()

    show_lists = dict()
    image_thread = None
    close_thread = None
    hidden = False
    quit = False

    def __init__(self, debug=False):
        Gtk.ApplicationWindow.__init__(self)
        self.init_template()

        self._debug = debug
        self._configfile = utils.to_config_path('ui-Gtk.json')
        self._config = utils.parse_config(self._configfile, utils.gtk_defaults)

        self.statusicon = None
        self._main_view = None
        self._modals = []

        self._account = None
        self._engine = None

        self._init_widgets()

    def main(self):
        """Start the Account Selector"""
        manager = AccountManager()

        # Use the remembered account if there's one
        if manager.get_default():
            self._create_engine(manager.get_default())
        else:
            self._show_accounts(switch=False)

    def _init_widgets(self):
        Gtk.Window.set_default_icon_from_file(utils.DATADIR + '/icon.png')
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Trackma-gtk ' + utils.VERSION)

        if self._config['remember_geometry']:
            self.resize(self._config['last_width'], self._config['last_height'])

        if not self._main_view:
            self._main_view = MainView(self._config)
            self._main_view.connect('error', self._on_main_view_error)
            self._main_view.connect('error-fatal', self._on_main_view_error_fatal)
            self._main_view.connect('show-action', self._on_show_action)
            self.add(self._main_view)

        self.connect('delete_event', self._on_delete_event)

        # Status icon
        if TrackmaStatusIcon.is_tray_available():
            self.statusicon = TrackmaStatusIcon()
            self.statusicon.connect('hide-clicked', self._on_tray_hide_clicked)
            self.statusicon.connect('about-clicked', self._on_tray_about_clicked)
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
            self.present()

            if not self._engine:
                self._show_accounts(switch=False)
        else:
            self.hide()

        self.hidden = not self.hidden

    def _destroy_modals(self):
        for modal_window in self._modals:
            modal_window.destroy()

        self._modals = []

    def _on_tray_about_clicked(self, status_icon):
        self._on_about(None, None)

    def _on_tray_quit_clicked(self, status_icon):
        self._quit()

    def _on_delete_event(self, widget, event, data=None):
        if self.statusicon and self.statusicon.get_visible() and self._config['close_to_tray']:
            self.hidden = True
            self.hide()
        else:
            self._quit()
        return True

    def _create_engine(self, account):
        self._engine = Engine(account, self._message_handler)

        self._main_view.load_engine_account(self._engine, account)
        self._set_actions()
        self._set_mediatypes_menu()
        self._update_widgets(account)

    def _set_actions(self):
        builder = Gtk.Builder.new_from_file(os.path.join(gtk_dir, 'data/app-menu.ui'))
        self.btn_appmenu.set_menu_model(builder.get_object('app-menu'))

        def add_action(name, callback):
            action = Gio.SimpleAction.new(name, None)
            action.connect('activate', callback)
            self.add_action(action)

        add_action('search', self._on_search)
        add_action('syncronize', self._on_synchronize)
        add_action('upload', self._on_upload)
        add_action('download', self._on_download)
        add_action('scanfiles', self._on_scanfiles)
        add_action('accounts', self._on_accounts)
        add_action('preferences', self._on_preferences)
        add_action('about', self._on_about)
        add_action('quit', self._on_quit)

    def _set_mediatypes_action(self):
        action_name = 'change-mediatype'
        if self.has_action(action_name):
            self.remove_action(action_name)

        state = GLib.Variant.new_string(self._engine.api_info['mediatype'])
        action = Gio.SimpleAction.new_stateful(action_name,
                                               state.get_type(),
                                               state)
        action.connect('change-state', self._on_change_mediatype)
        self.add_action(action)

    def _set_mediatypes_menu(self):
        self._set_mediatypes_action()
        menu = Gio.Menu()

        for mediatype in self._engine.api_info['supported_mediatypes']:
            variant = GLib.Variant.new_string(mediatype)
            menu_item = Gio.MenuItem()
            menu_item.set_label(mediatype)
            menu_item.set_action_and_target_value('win.change-mediatype', variant)
            menu.append_item(menu_item)

        self.btn_mediatype.set_menu_model(menu)

        if len(self._engine.api_info['supported_mediatypes']) <= 1:
            self.btn_mediatype.hide()

    def _update_widgets(self, account):
        current_api = utils.available_libs[account['api']]
        api_iconpath = 1
        api_iconfile = current_api[api_iconpath]

        self.set_title('Trackma-gtk %s [%s (%s)]' % (
            utils.VERSION,
            self._engine.api_info['name'],
            self._engine.api_info['mediatype']))

        if self.statusicon and self._config['tray_api_icon']:
            self.statusicon.set_from_file(api_iconfile)

    def _on_change_mediatype(self, action, value):
        action.set_state(value)
        mediatype = value.get_string()
        self._main_view.load_account_mediatype(None, mediatype)

    def _on_search(self, action, param):
        current_status = self._main_view.get_current_status()
        win = SearchWindow(self._engine, self._config['colors'], current_status, transient_for=self)
        win.connect('search-error', self._on_search_error)
        win.connect('destroy', self._on_modal_destroy)
        win.present()
        self._modals.append(win)

    def _on_search_error(self, search_window, error_msg):
        print(error_msg)

    def _on_synchronize(self, action, param):
        threading.Thread(target=self._synchronization_task, args=(True, True)).start()

    def _on_upload(self, action, param):
        threading.Thread(target=self._synchronization_task, args=(True, False)).start()

    def _on_download(self, action, param):
        def _download_lists():
            threading.Thread(target=self._synchronization_task, args=(False, True)).start()

        def _on_download_response(_dialog, response):
            _dialog.destroy()

            if response == Gtk.ResponseType.YES:
                _download_lists()

        queue = self._engine.get_queue()
        if not queue:
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
        self._main_view.set_buttons_sensitive_idle(False)

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
        self._main_view.set_buttons_sensitive_idle(True)

    def _on_scanfiles(self, action, param):
        threading.Thread(target=self._scanfiles_task).start()

    def _scanfiles_task(self):
        try:
            self._engine.scan_library(rescan=True)
        except utils.TrackmaError as e:
            self._error_dialog_idle(e)

        GLib.idle_add(self._main_view.populate_all_pages)

        self._main_view.set_status_idle("Ready.")
        self._main_view.set_buttons_sensitive_idle(True)

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
        if self._engine and self._engine.loaded:
            self._main_view.load_account_mediatype(account, None)
        else:
            self._create_engine(account)

    def _on_account_cancel(self, accounts_window, switch):
        manager = AccountManager()

        if not switch or not manager.get_accounts():
            self._quit()

    def _on_preferences(self, action, param):
        win = SettingsWindow(self._engine, self._config, self._configfile, transient_for=self)
        win.connect('destroy', self._on_modal_destroy)
        win.present()
        self._modals.append(win)

    def _on_about(self, action, param):
        about = Gtk.AboutDialog(parent=self)
        about.set_modal(True)
        about.set_transient_for(self)
        about.set_program_name("Trackma-gtk")
        about.set_version(utils.VERSION)
        about.set_license_type(Gtk.License.GPL_3_0_ONLY)
        about.set_comments("Trackma is an open source client for media tracking websites.\nThanks to all contributors.")
        about.set_website("http://github.com/z411/trackma")
        about.set_copyright("© z411, et al.")
        about.set_authors(["See AUTHORS file"])
        about.set_artists(["shuuichi"])
        about.connect('destroy', self._on_modal_destroy)
        about.present()
        self._modals.append(about)

    def _on_modal_destroy(self, modal_window):
        self._modals.remove(modal_window)

    def _on_quit(self, action, param):
        self._quit()

    def _quit(self):
        if self._config['remember_geometry']:
            self._store_geometry()

        if not self._engine:
            Gtk.main_quit()
            return

        if self.close_thread is None:
            self._main_view.set_buttons_sensitive_idle(False)
            self.close_thread = threading.Thread(target=self._unload_task)
            self.close_thread.start()

    def _unload_task(self):
        self._engine.unload()
        self._destroy_idle()

    def _destroy_idle(self):
        GLib.idle_add(self._destroy_push)

    def _destroy_push(self):
        self.quit = True
        self.destroy()
        Gtk.main_quit()

    def _store_geometry(self):
        (width, height) = self.get_size()
        self._config['last_width'] = width
        self._config['last_height'] = height
        utils.save_config(self._config, self._configfile)

    def _message_handler(self, classname, msgtype, msg):
        # Thread safe
        # print("%s: %s" % (classname, msg))
        if msgtype == messenger.TYPE_WARN:
            self._main_view.set_status_idle("%s warning: %s" % (classname, msg))
        elif msgtype != messenger.TYPE_DEBUG:
            self._main_view.set_status_idle("%s: %s" % (classname, msg))
        elif self._debug:
            print('[D] {}: {}'.format(classname, msg))

    def _on_main_view_error(self, main_view, error_msg):
        self._error_dialog_idle(error_msg)

    def _on_main_view_error_fatal(self, main_view, error_msg):
        self._show_accounts_idle(switch=False, forget=True)
        self._error_dialog_idle(error_msg)

    def _column_toggled(self, w, column_name, visible):
        if visible:
            # Make column visible
            self._config['visible_columns'].append(column_name)

            for view in self.show_lists.values():
                view.cols[column_name].set_visible(True)
        else:
            # Make column invisible
            if len(self._config['visible_columns']) <= 1:
                return # There should be at least 1 column visible

            self._config['visible_columns'].remove(column_name)
            for view in self.show_lists.values():
                view.cols[column_name].set_visible(False)

        utils.save_config(self._config, self._configfile)

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

    def _on_show_action(self, main_view, event_type, selected_show, data):
        if event_type == ShowEventType.PLAY_NEXT:
            self._play_next(selected_show)
        elif event_type == ShowEventType.PLAY_EPISODE:
            self._play_episode(selected_show, data)
        elif event_type == ShowEventType.DETAILS:
            self._open_details(selected_show)
        elif event_type == ShowEventType.OPEN_WEBSITE:
            self._open_website(selected_show)
        elif event_type == ShowEventType.OPEN_FOLDER:
            self._open_folder(selected_show)
        elif event_type == ShowEventType.COPY_TITLE:
            self._copy_title(selected_show)
        elif event_type == ShowEventType.CHANGE_ALTERNATIVE_TITLE:
            self._change_alternative_title(selected_show)
        elif event_type == ShowEventType.REMOVE:
            self._remove_show(selected_show)

    def _play_next(self, show_id):
        threading.Thread(target=self._play_task, args=[show_id, True, None]).start()

    def _play_episode(self, show_id, episode):
        threading.Thread(target=self._play_task, args=[show_id, False, episode]).start()

    def _play_task(self, show_id, playnext, episode):
        self._main_view.set_buttons_sensitive_idle(False)

        show = self._engine.get_show_info(show_id)
        try:
            if playnext:
                self._engine.play_episode(show)
            else:
                if not episode:
                    episode = self.show_ep_num.get_value_as_int()
                self._engine.play_episode(show, episode)
        except utils.TrackmaError as e:
            self._error_dialog_idle(e)

        self._main_view.set_status_idle("Ready.")
        self._main_view.set_buttons_sensitive_idle(True)

    def _play_random(self):
        # TODO: Reimplement functionality in GUI
        threading.Thread(target=self._play_random_task).start()

    def _play_random_task(self):
        self._main_view.set_buttons_sensitive_idle(False)

        try:
            self._engine.play_random()
        except utils.TrackmaError as e:
            self._error_dialog_idle(e)

        self._main_view.set_status_idle("Ready.")
        self._main_view.set_buttons_sensitive_idle(True)

    def _open_details(self, show_id):
        show = self._engine.get_show_info(show_id)
        win = ShowInfoWindow(self._engine, show, transient_for=self)
        win.connect('destroy', self._on_modal_destroy)
        self._modals.append(win)

    def _open_website(self, show_id):
        show = self._engine.get_show_info(show_id)
        if show['url']:
            Gtk.show_uri(None, show['url'], Gdk.CURRENT_TIME)

    def _open_folder(self, show_id):
        show = self._engine.get_show_info(show_id)
        try:
            filename = self._engine.get_episode_path(show, 1)
            with open(os.devnull, 'wb') as DEVNULL:
                subprocess.Popen(["/usr/bin/xdg-open", os.path.dirname(filename)],
                                 stdout=DEVNULL,
                                 stderr=DEVNULL)
        except OSError:
            # xdg-open failed.
            raise utils.EngineError("Could not open folder.")

        except utils.EngineError:
            # Show not in library.
            self._error_dialog_idle("No folder found.")

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
        entry.connect("activate", altname_response, dialog, Gtk.ResponseType.OK)
        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label("Alternate Title:"), False, 5, 5)
        hbox.pack_end(entry, True, True, 0)
        dialog.format_secondary_markup("Use this if the tracker is unable to find this show. Leave blank to disable.")
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

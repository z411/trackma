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
try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    from gi.repository import Gdk
    from gi.repository import GdkPixbuf
    from gi.repository import Pango
    from gi.repository import GObject
except ImportError as ex:
    print("Couldn't import GTK dependencies. Make sure you "
          "installed the PyGTK package and %s module." % ex.name)
    sys.exit(-1)

Gdk.threads_init() # We'll use threads

import webbrowser
import os
import subprocess
import cgi
import time
import threading
import urllib.request
from io import BytesIO

try:
    import Image
    imaging_available = True
except ImportError:
    try:
        from PIL import Image
        imaging_available = True
    except ImportError:
        print("Warning: PIL or Pillow isn't available. Preview images will be disabled.")
        imaging_available = False

from trackma.engine import Engine
from trackma.accounts import AccountManager
from trackma import utils
from trackma import messenger

class Trackma_gtk():
    engine = None
    config = None
    show_lists = dict()
    image_thread = None
    close_thread = None
    hidden = False
    quit = False

    def main(self):
        """Start the Account Selector"""
        self.configfile = utils.get_root_filename('ui-Gtk.json')
        self.config = utils.parse_config(self.configfile, utils.gtk_defaults)

        manager = AccountManager()

        # Use the remembered account if there's one
        if manager.get_default():
            self.start(manager.get_default())
        else:
            self.accountsel = AccountSelect(manager)
            self.accountsel.use_button.connect("clicked", self.use_account)
            self.accountsel.create()

        Gtk.main()

    def __do_switch_account(self, widget, switch=True):
        manager = AccountManager()
        self.accountsel = AccountSelect(manager = AccountManager(), switch=switch)
        self.accountsel.use_button.connect("clicked", self.use_account)
        self.accountsel.create()

    def use_account(self, widget):
        """Start the main application with the following account"""
        accountid = self.accountsel.get_selected_id()
        account = self.accountsel.manager.get_account(accountid)
        # If remember box is checked, set as default account
        if self.accountsel.is_remember():
            self.accountsel.manager.set_default(accountid)
        else:
            self.accountsel.manager.set_default(None)

        self.accountsel.destroy()

        # Reload the engine if already started,
        # start it otherwise
        if self.engine and self.engine.loaded:
            self.__do_reload(None, account, None)
        else:
            self.start(account)

    def start(self, account):
        """Create the main window"""
        # Create engine
        self.account = account
        self.engine = Engine(account)

        self.main = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        self.main.set_position(Gtk.WindowPosition.CENTER)
        self.main.connect('delete_event', self.delete_event)
        self.main.connect('destroy', self.on_destroy)
        self.main.set_title('Trackma-gtk ' + utils.VERSION)
        Gtk.Window.set_default_icon_from_file(utils.datadir + '/data/icon.png')
        if self.config['remember_geometry']:
            self.main.resize(self.config['last_width'], self.config['last_height'])

        # Menus
        mb_show = Gtk.Menu()
        self.mb_play = Gtk.ImageMenuItem('Play', Gtk.Image.new_from_icon_name(Gtk.STOCK_MEDIA_PLAY, 0))
        self.mb_play.connect("activate", self.__do_play, True)
        mb_scanlibrary = Gtk.MenuItem('Re-scan library')
        self.mb_folder = Gtk.MenuItem("Open containing folder")
        self.mb_folder.connect("activate", self.do_containingFolder)
        mb_scanlibrary.connect("activate", self.__do_scanlibrary)
        self.mb_info = Gtk.MenuItem('Show details...')
        self.mb_info.connect("activate", self.__do_info)
        self.mb_web = Gtk.MenuItem("Open web site")
        self.mb_web.connect("activate", self.__do_web)
        self.mb_copy = Gtk.MenuItem("Copy title to clipboard")
        self.mb_copy.connect("activate", self.__do_copytoclip)
        self.mb_alt_title = Gtk.MenuItem("Set alternate title...")
        self.mb_alt_title.connect("activate", self.__do_altname)
        self.mb_delete = Gtk.ImageMenuItem('Delete', Gtk.Image.new_from_icon_name(Gtk.STOCK_DELETE, 0))
        self.mb_delete.connect("activate", self.__do_delete)
        self.mb_exit = Gtk.ImageMenuItem('Quit', Gtk.Image.new_from_icon_name(Gtk.STOCK_QUIT, 0))
        self.mb_exit.connect("activate", self.__do_quit, None)
        self.mb_addsearch = Gtk.ImageMenuItem("Add/Search Shows", Gtk.Image.new_from_icon_name(Gtk.STOCK_ADD, 0))
        self.mb_addsearch.connect("activate", self._do_addsearch)

        mb_show.append(self.mb_addsearch)
        mb_show.append(Gtk.SeparatorMenuItem())
        mb_show.append(self.mb_play)
        mb_show.append(self.mb_info)
        mb_show.append(self.mb_web)
        mb_show.append(self.mb_folder)
        mb_show.append(Gtk.SeparatorMenuItem())
        mb_show.append(self.mb_copy)
        mb_show.append(self.mb_alt_title)
        mb_show.append(Gtk.SeparatorMenuItem())
        mb_show.append(self.mb_delete)
        mb_show.append(Gtk.SeparatorMenuItem())
        mb_show.append(self.mb_exit)

        mb_list = Gtk.Menu()
        self.mb_sync = Gtk.ImageMenuItem('Sync', Gtk.Image.new_from_icon_name(Gtk.STOCK_REFRESH, 0))
        self.mb_sync.connect("activate", self.__do_sync)
        self.mb_retrieve = Gtk.ImageMenuItem("Retrieve list")
        self.mb_retrieve.connect("activate", self.__do_retrieve_ask)
        self.mb_send = Gtk.MenuItem('Send changes')
        self.mb_send.connect("activate", self.__do_send)

        mb_list.append(self.mb_sync)
        mb_list.append(Gtk.SeparatorMenuItem())
        mb_list.append(self.mb_retrieve)
        mb_list.append(self.mb_send)
        mb_list.append(Gtk.SeparatorMenuItem())
        mb_list.append(mb_scanlibrary)

        mb_options = Gtk.Menu()
        self.mb_switch_account = Gtk.MenuItem('Switch Account...')
        self.mb_switch_account.connect("activate", self.__do_switch_account)
        self.mb_settings = Gtk.MenuItem('Global Settings...')
        self.mb_settings.connect("activate", self.__do_settings)

        mb_options.append(self.mb_switch_account)
        mb_options.append(Gtk.SeparatorMenuItem())
        mb_options.append(self.mb_settings)

        self.mb_mediatype_menu = Gtk.Menu()

        mb_help = Gtk.Menu()
        mb_about = Gtk.ImageMenuItem('About', Gtk.Image.new_from_icon_name(Gtk.STOCK_ABOUT, 0))
        mb_about.connect("activate", self.on_about)
        mb_help.append(mb_about)

        # Root menubar
        root_menu1 = Gtk.MenuItem("Show")
        root_menu1.set_submenu(mb_show)
        root_list = Gtk.MenuItem("List")
        root_list.set_submenu(mb_list)
        root_options = Gtk.MenuItem("Options")
        root_options.set_submenu(mb_options)
        mb_mediatype = Gtk.MenuItem("Mediatype")
        mb_mediatype.set_submenu(self.mb_mediatype_menu)
        root_menu2 = Gtk.MenuItem("Help")
        root_menu2.set_submenu(mb_help)

        mb = Gtk.MenuBar()
        mb.append(root_menu1)
        mb.append(root_list)
        mb.append(mb_mediatype)
        mb.append(root_options)
        mb.append(root_menu2)

        # Create vertical box
        vbox = Gtk.VBox(False, 0)
        self.main.add(vbox)

        vbox.pack_start(mb, False, False, 0)

        # Toolbar
        #toolbar = Gtk.Toolbar()
        #toolbar.insert_stock(Gtk.STOCK_REFRESH, "Sync", "Sync", None, None, 0)
        #toolbar.insert_stock(Gtk.STOCK_ADD, "Sync", "Sync", None, None, 1)
        #toolbar.insert_stock(Gtk.STOCK_MEDIA_PLAY, "Sync", "Sync", None, None, 2)
        #vbox.pack_start(toolbar, False, False, 0)

        self.top_hbox = Gtk.HBox(False, 10)
        self.top_hbox.set_border_width(5)

        self.show_image = ImageView(100, 149)
        self.top_hbox.pack_start(self.show_image, False, False, 0)

        # Right box
        top_right_box = Gtk.VBox(False, 0)

        # Line 1: Title
        line1 = Gtk.HBox(False, 5)
        self.show_title = Gtk.Label()
        self.show_title.set_use_markup(True)
        self.show_title.set_alignment(0, 0.5)
        self.show_title.set_ellipsize(Pango.EllipsizeMode.END)

        line1.pack_start(self.show_title, True, True, 0)

        # API info
        api_hbox = Gtk.HBox(False, 5)
        self.api_icon = Gtk.Image()
        self.api_user = Gtk.Label()
        api_hbox.pack_start(self.api_icon, True, True, 0)
        api_hbox.pack_start(self.api_user, True, True, 0)

        alignment1 = Gtk.Alignment(xalign=1, yalign=0, xscale=0)
        alignment1.add(api_hbox)
        line1.pack_start(alignment1, False, False, 0)

        top_right_box.pack_start(line1, True, True, 0)

        # Line 2: Episode
        line2 = Gtk.HBox(False, 5)
        line2_t = Gtk.Label('  Progress')
        line2_t.set_size_request(70, -1)
        line2_t.set_alignment(0, 0.5)
        line2.pack_start(line2_t, False, False, 0)

        # Buttons
        top_buttons = Gtk.HBox(False, 5)

        rem_icon = Gtk.Image()
        rem_icon.set_from_stock(Gtk.STOCK_REMOVE, Gtk.IconSize.BUTTON)
        self.rem_epp_button = Gtk.Button()
        self.rem_epp_button.set_image(rem_icon)
        self.rem_epp_button.connect("clicked", self.__do_rem_epp)
        self.rem_epp_button.set_sensitive(False)
        line2.pack_start(self.rem_epp_button, False, False, 0)

        self.show_ep_button = Gtk.Button()
        self.show_ep_button.set_relief(Gtk.ReliefStyle.NONE)
        self.show_ep_button.connect("clicked", self._show_episode_entry)
        self.show_ep_button.set_label("-")
        self.show_ep_button.set_size_request(40, -1)
        line2.pack_start(self.show_ep_button, False, False, 0)

        self.show_ep_num = Gtk.Entry()
        self.show_ep_num.set_sensitive(False)
        self.show_ep_num.connect("activate", self.__do_update)
        self.show_ep_num.connect("focus-out-event", self._hide_episode_entry)
        self.show_ep_num.set_size_request(40, -1)
        line2.pack_start(self.show_ep_num, False, False, 0)

        add_icon = Gtk.Image()
        add_icon.set_from_stock(Gtk.STOCK_ADD, Gtk.IconSize.BUTTON)
        self.add_epp_button = Gtk.Button()
        self.add_epp_button.set_image(add_icon)
        self.add_epp_button.connect("clicked", self._do_add_epp)
        self.add_epp_button.set_sensitive(False)
        line2.pack_start(self.add_epp_button, False, False, 0)

        self.play_next_button = Gtk.Button('Play Next')
        self.play_next_button.connect("clicked", self.__do_play, True)
        self.play_next_button.set_sensitive(False)
        line2.pack_start(self.play_next_button, False, False, 0)

        top_right_box.pack_start(line2, True, False, 0)

        # Line 3: Score
        line3 = Gtk.HBox(False, 5)
        line3_t = Gtk.Label('  Score')
        line3_t.set_size_request(70, -1)
        line3_t.set_alignment(0, 0.5)
        line3.pack_start(line3_t, False, False, 0)
        self.show_score = Gtk.SpinButton()
        self.show_score.set_adjustment(Gtk.Adjustment(upper=10, step_incr=1))
        self.show_score.set_sensitive(False)
        self.show_score.connect("activate", self.__do_score)
        line3.pack_start(self.show_score, False, False, 0)

        self.scoreset_button = Gtk.Button('Set')
        self.scoreset_button.connect("clicked", self.__do_score)
        self.scoreset_button.set_sensitive(False)
        line3.pack_start(self.scoreset_button, False, False, 0)

        top_right_box.pack_start(line3, True, False, 0)

        # Line 4: Status
        line4 = Gtk.HBox(False, 5)
        line4_t = Gtk.Label('  Status')
        line4_t.set_size_request(70, -1)
        line4_t.set_alignment(0, 0.5)
        line4.pack_start(line4_t, False, False, 0)

        self.statusmodel = Gtk.ListStore(str, str)

        self.statusbox = Gtk.ComboBox.new_with_model(self.statusmodel)
        cell = Gtk.CellRendererText()
        self.statusbox.pack_start(cell, True)
        self.statusbox.add_attribute(cell, 'text', 1)
        self.statusbox_handler = self.statusbox.connect("changed", self.__do_status)
        self.statusbox.set_sensitive(False)

        alignment = Gtk.Alignment(xalign=0, yalign=0.5, xscale=0)
        alignment.add(self.statusbox)

        line4.pack_start(alignment, False, False, 0)

        top_right_box.pack_start(line4, True, False, 0)

        self.top_hbox.pack_start(top_right_box, True, True, 0)
        vbox.pack_start(self.top_hbox, False, False, 0)

        # Notebook for lists
        self.notebook = Gtk.Notebook()
        self.notebook.set_tab_pos(Gtk.PositionType.TOP)
        self.notebook.set_scrollable(True)
        self.notebook.set_border_width(3)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_size_request(550, 300)
        sw.set_border_width(5)
        self.notebook.append_page(sw, Gtk.Label("Status"))

        vbox.pack_start(self.notebook, True, True, 0)

        self.statusbar = Gtk.Statusbar()
        self.statusbar.push(0, 'Trackma-gtk ' + utils.VERSION)
        vbox.pack_start(self.statusbar, False, False, 0)

        vbox.show_all()

        # Accelerators
        accelgrp = Gtk.AccelGroup()

        key, mod = Gtk.accelerator_parse("<Control>N")
        self.mb_play.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>A")
        self.mb_addsearch.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>S")
        self.mb_sync.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>E")
        self.mb_send.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>R")
        self.mb_retrieve.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>Right")
        self.add_epp_button.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        self.add_epp_button.set_tooltip_text("Ctrl+Right")
        key, mod = Gtk.accelerator_parse("<Control>Left")
        self.rem_epp_button.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        self.rem_epp_button.set_tooltip_text("Ctrl+Left")
        key, mod = Gtk.accelerator_parse("<Control>L")
        mb_scanlibrary.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>W")
        self.mb_web.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>D")
        self.mb_info.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>Delete")
        self.mb_delete.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>Q")
        self.mb_exit.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>O")
        self.mb_settings.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>Y")
        self.mb_copy.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Shift>A")
        self.mb_alt_title.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Shift>C")
        self.mb_switch_account.add_accelerator("activate", accelgrp, key, mod, Gtk.AccelFlags.VISIBLE)

        self.main.add_accel_group(accelgrp)

        # Status icon
        self.statusicon = Gtk.StatusIcon()
        self.statusicon.set_from_file(utils.datadir + '/data/icon.png')
        self.statusicon.set_tooltip_text('Trackma-gtk ' + utils.VERSION)
        self.statusicon.connect('activate', self.status_event)
        self.statusicon.connect('popup-menu', self.status_menu_event)
        if self.config['show_tray']:
            self.statusicon.set_visible(True)
        else:
            self.statusicon.set_visible(False)

        # Engine configuration
        self.engine.set_message_handler(self.message_handler)
        self.engine.connect_signal('episode_changed', self.changed_show)
        self.engine.connect_signal('score_changed', self.changed_show)
        self.engine.connect_signal('status_changed', self.changed_show_status)
        self.engine.connect_signal('playing', self.playing_show)
        self.engine.connect_signal('show_added', self.changed_show_status)
        self.engine.connect_signal('show_deleted', self.changed_show_status)
        self.engine.connect_signal('prompt_for_update', self.__do_update_next)

        self.selected_show = 0

        if not imaging_available:
            self.show_image.pholder_show("PIL library\nnot available")

        self.allow_buttons(False)

        # Don't show the main dialog if start in tray option is set
        if self.config['show_tray'] and self.config['start_in_tray']:
            self.hidden = True
        else:
            self.main.show()

        self.show_ep_num.hide()

        self.start_engine()

    def _clear_gui(self):
        self.show_title.set_text('<span size="14000"><b>Trackma</b></span>')
        self.show_title.set_use_markup(True)
        self.show_image.pholder_show("Trackma")

        current_api = utils.available_libs[self.account['api']]
        api_iconfile = current_api[1]

        self.main.set_title('Trackma-gtk %s [%s (%s)]' % (
            utils.VERSION,
            self.engine.api_info['name'],
            self.engine.api_info['mediatype']))
        self.api_icon.set_from_file(api_iconfile)
        if self.config['tray_api_icon']:
            self.statusicon.set_from_file(api_iconfile)
        self.api_user.set_text("%s (%s)" % (
            self.engine.get_userconfig('username'),
            self.engine.api_info['mediatype']))

        self.score_decimal_places = 0
        if isinstance( self.engine.mediainfo['score_step'], float ):
            self.score_decimal_places = len(str(self.engine.mediainfo['score_step']).split('.')[1])

        self.show_score.set_value(0)
        self.show_score.set_digits(self.score_decimal_places)
        self.show_score.set_range(0, self.engine.mediainfo['score_max'])
        self.show_score.get_adjustment().set_step_increment(self.engine.mediainfo['score_step'])

        can_play = self.engine.mediainfo['can_play']
        can_update = self.engine.mediainfo['can_update']

        self.play_next_button.set_sensitive(can_play)

        self.show_ep_button.set_sensitive(can_update)
        self.show_ep_num.set_sensitive(can_update)
        self.add_epp_button.set_sensitive(can_update)

    def _create_lists(self):
        statuses_nums = self.engine.mediainfo['statuses']
        statuses_names = self.engine.mediainfo['statuses_dict']

        # Statusbox
        self.statusmodel.clear()
        for status in statuses_nums:
            self.statusmodel.append([str(status), statuses_names[status]])
        self.statusbox.set_model(self.statusmodel)
        self.statusbox.show_all()

        # Clear notebook
        for i in range(self.notebook.get_n_pages()):
            self.notebook.remove_page(-1)

        # Insert pages
        for status in statuses_nums:
            name = statuses_names[status]

            sw = Gtk.ScrolledWindow()
            sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            sw.set_size_request(550, 300)
            sw.set_border_width(5)

            self.show_lists[status] = ShowView(
                    status,
                    self.config['colors'],
                    self.config['visible_columns'],
                    self.score_decimal_places,
                    self.config['episodebar_style'])
            self.show_lists[status].get_selection().connect("changed", self.select_show)
            self.show_lists[status].connect("row-activated", self.__do_info)
            self.show_lists[status].connect("button-press-event", self.showview_context_menu)
            self.show_lists[status].connect("column-toggled", self._column_toggled)
            self.show_lists[status].pagenumber = self.notebook.get_n_pages()
            sw.add(self.show_lists[status])

            self.notebook.append_page(sw, Gtk.Label(name))
            self.notebook.show_all()
            self.show_lists[status].realize()

        self.notebook.connect("switch-page", self.select_show)

    def _column_toggled(self, w, column_name, visible):
        if visible:
            # Make column visible
            self.config['visible_columns'].append(column_name)

            for view in self.show_lists.values():
                view.cols[column_name].set_visible(True)
        else:
            # Make column invisible
            if len(self.config['visible_columns']) <= 1:
                return # There should be at least 1 column visible

            self.config['visible_columns'].remove(column_name)
            for view in self.show_lists.values():
                view.cols[column_name].set_visible(False)

        utils.save_config(self.config, self.configfile)

    def _show_episode_entry(self, *args):
        self.show_ep_button.hide()
        self.show_ep_num.set_text(self.show_ep_button.get_label())
        self.show_ep_num.show()
        self.show_ep_num.grab_focus()

    def _hide_episode_entry(self, *args):
        self.show_ep_num.hide()
        self.show_ep_button.show()

    def idle_destroy(self):
        GObject.idle_add(self.idle_destroy_push)

    def idle_destroy_push(self):
        self.quit = True
        self.main.destroy()

    def idle_restart(self):
        GObject.idle_add(self.idle_restart_push)

    def idle_restart_push(self):
        self.quit = False
        self.main.destroy()
        self.__do_switch_account(None, False)

    def on_destroy(self, widget):
        if self.quit:
            Gtk.main_quit()

    def status_event(self, widget):
        # Called when the tray icon is left-clicked
        if self.hidden:
            self.main.show()
            self.hidden = False
        else:
            self.main.hide()
            self.hidden = True

    def status_menu_event(self, icon, button, time):
        # Called when the tray icon is right-clicked
        menu = Gtk.Menu()
        mb_show = Gtk.MenuItem("Show/Hide")
        mb_about = Gtk.ImageMenuItem('About', Gtk.Image.new_from_icon_name(Gtk.STOCK_ABOUT, 0))
        mb_quit = Gtk.ImageMenuItem('Quit', Gtk.Image.new_from_icon_name(Gtk.STOCK_QUIT, 0))

        mb_show.connect("activate", self.status_event)
        mb_about.connect("activate", self.on_about)
        mb_quit.connect("activate", self.__do_quit)

        menu.append(mb_show)
        menu.append(mb_about)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(mb_quit)
        menu.show_all()

        def pos(menu, icon):
                return (Gtk.StatusIcon.position_menu(menu, icon))
        menu.popup(None, None, None, pos, button, time)

    def delete_event(self, widget, event, data=None):
        if self.statusicon.get_visible() and self.config['close_to_tray']:
            self.hidden = True
            self.main.hide()
        else:
            self.__do_quit()
        return True

    def __do_quit(self, widget=None, event=None, data=None):
        if self.config['remember_geometry']:
            self.__do_store_geometry()
        if self.close_thread is None:
            self.close_thread = threading.Thread(target=self.task_unload).start()

    def __do_store_geometry(self):
        (width, height) = self.main.get_size()
        self.config['last_width'] = width
        self.config['last_height'] = height
        utils.save_config(self.config, self.configfile)

    def _do_addsearch(self, widget):
        page = self.notebook.get_current_page()
        current_status = self.engine.mediainfo['statuses'][page]

        win = ShowSearch(self.engine, self.config['colors'], current_status)
        win.show_all()

    def __do_settings(self, widget):
        win = Settings(self.engine, self.config, self.configfile)
        win.show_all()

    def __do_reload(self, widget, account, mediatype):
        self.selected_show = 0

        threading.Thread(target=self.task_reload, args=[account, mediatype]).start()

    def __do_play(self, widget, playnext, ep=None):
        threading.Thread(target=self.task_play, args=(playnext,ep)).start()

    def __do_scanlibrary(self, widget):
        threading.Thread(target=self.task_scanlibrary).start()

    def __do_delete(self, widget):
        try:
            show = self.engine.get_show_info(self.selected_show)
            self.engine.delete_show(show)
        except utils.TrackmaError as e:
            self.error(e)

    def __do_info(self, widget, d1=None, d2=None):
        show = self.engine.get_show_info(self.selected_show)
        win = InfoDialog(self.engine, show)

    def _do_add_epp(self, widget):
        show = self.engine.get_show_info(self.selected_show)
        try:
            show = self.engine.set_episode(self.selected_show, show['my_progress'] + 1)
        except utils.TrackmaError as e:
            self.error(e)

    def __do_rem_epp(self, widget):
        show = self.engine.get_show_info(self.selected_show)
        try:
            show = self.engine.set_episode(self.selected_show, show['my_progress'] - 1)
        except utils.TrackmaError as e:
            self.error(e)

    def __do_update(self, widget):
        self._hide_episode_entry()
        ep = self.show_ep_num.get_text()
        try:
            show = self.engine.set_episode(self.selected_show, ep)
        except utils.TrackmaError as e:
            self.error(e)

    def __do_score(self, widget):
        score = self.show_score.get_value()
        try:
            show = self.engine.set_score(self.selected_show, score)
        except utils.TrackmaError as e:
            self.error(e)

    def __do_status(self, widget):
        statusiter = self.statusbox.get_active_iter()
        status = self.statusmodel.get(statusiter, 0)[0]

        try:
            show = self.engine.set_status(self.selected_show, status)
        except utils.TrackmaError as e:
            self.error(e)

    def __do_update_next(self, show, played_ep):
        GObject.idle_add(self.task_update_next, show, played_ep)

    def changed_show(self, show):
        GObject.idle_add(self.task_changed_show, show)

    def changed_show_title(self, show, altname):
        GObject.idle_add(self.task_changed_show_title, show, altname)

    def changed_show_status(self, show, old_status=None):
        GObject.idle_add(self.task_changed_show_status, show, old_status)

    def playing_show(self, show, is_playing, episode):
        GObject.idle_add(self.task_playing_show, show, is_playing, episode)

    def task_changed_show(self, show):
        status = show['my_status']
        self.show_lists[status].update(show)
        if show['id'] == self.selected_show:
            self.show_ep_button.set_label(str(show['my_progress']))
            self.show_score.set_value(show['my_score'])

    def task_changed_show_title(self, show, altname):
        status = show['my_status']
        self.show_lists[status].update_title(show, altname)

    def task_changed_show_status(self, show, old_status):
        # Rebuild lists
        status = show['my_status']

        self.build_list(status)
        if old_status:
            self.build_list(old_status)

        pagenumber = self.show_lists[status].pagenumber
        self.notebook.set_current_page(pagenumber)

        self.show_lists[status].select(show)

    def task_playing_show(self, show, is_playing, episode):
        status = show['my_status']
        self.show_lists[status].playing(show, is_playing)

    def task_update_next(self, show, played_ep):
        dialog = Gtk.MessageDialog(self.main,
                    Gtk.DialogFlags.MODAL,
                    Gtk.MessageType.QUESTION,
                    Gtk.ButtonsType.YES_NO,
                    "Update %s to episode %d?" % (show['title'], played_ep))
        dialog.show_all()
        dialog.connect("response", self.task_update_next_response, show, played_ep)

    def task_update_next_response(self, widget, response, show, played_ep):
        widget.destroy()
        # Update show to the played episode
        if response == Gtk.ResponseType.YES:
            try:
                show = self.engine.set_episode(show['id'], played_ep)
                status = show['my_status']
                self.show_lists[status].update(show)
            except utils.TrackmaError as e:
                self.error(e)

    def task_play(self, playnext, ep):
        self.allow_buttons(False)

        show = self.engine.get_show_info(self.selected_show)

        try:
            if playnext:
                self.engine.play_episode(show)
            else:
                if not ep:
                    ep = self.show_ep_num.get_value_as_int()
                self.engine.play_episode(show, ep)
        except utils.TrackmaError as e:
            self.error(e)

        self.status("Ready.")
        self.allow_buttons(True)

    def task_scanlibrary(self):
        self.allow_buttons(False)

        try:
            result = self.engine.scan_library(rescan=True)
        except utils.TrackmaError as e:
            self.error(e)

        GObject.idle_add(self.build_list, self.engine.mediainfo['status_start'])

        self.status("Ready.")
        self.allow_buttons(True)

    def task_unload(self):
        self.allow_buttons(False)
        self.engine.unload()

        self.idle_destroy()

    def __do_retrieve_ask(self, widget):
        queue = self.engine.get_queue()

        if len(queue) > 0:
            dialog = Gtk.MessageDialog(self.main,
                Gtk.DialogFlags.MODAL,
                Gtk.MessageType.QUESTION,
                Gtk.ButtonsType.YES_NO,
                "There are %d queued changes in your list. If you retrieve the remote list now you will lose your queued changes. Are you sure you want to continue?" % len(queue))
            dialog.show_all()
            dialog.connect("response", self.__do_retrieve)
        else:
            # If the user doesn't have any queued changes
            # just go ahead
            self.__do_retrieve()

    def __do_retrieve(self, widget=None, response=Gtk.ResponseType.YES):
        if widget:
            widget.destroy()

        if response == Gtk.ResponseType.YES:
            threading.Thread(target=self.task_sync, args=(False,True)).start()

    def __do_send(self, widget):
        threading.Thread(target=self.task_sync, args=(True,False)).start()

    def __do_sync(self, widget):
        threading.Thread(target=self.task_sync, args=(True,True)).start()

    def task_sync(self, send, retrieve):
        self.allow_buttons(False)

        if send:
            self.engine.list_upload()
        if retrieve:
            self.engine.list_download()

        GObject.idle_add(self.build_all_lists)

        self.status("Ready.")
        self.allow_buttons(True)

    def start_engine(self):
        threading.Thread(target=self.task_start_engine).start()

    def task_start_engine(self):
        if not self.engine.loaded:
            try:
                self.engine.start()
            except utils.TrackmaFatal as e:
                print("Fatal engine error: %s" % e)
                self.idle_restart()
                self.error("Fatal engine error: %s" % e)
                return

        Gdk.threads_enter()
        self.statusbox.handler_block(self.statusbox_handler)
        self._clear_gui()
        self._create_lists()
        self.build_all_lists()

        # Clear and build API and mediatypes menus
        for i in self.mb_mediatype_menu.get_children():
            self.mb_mediatype_menu.remove(i)

        for mediatype in self.engine.api_info['supported_mediatypes']:
            item = Gtk.RadioMenuItem(label=mediatype)
            if mediatype == self.engine.api_info['mediatype']:
                item.set_active(True)
            item.connect("activate", self.__do_reload, None, mediatype)
            self.mb_mediatype_menu.append(item)
            item.show()

        self.statusbox.handler_unblock(self.statusbox_handler)
        Gdk.threads_leave()

        self.status("Ready.")
        self.allow_buttons(True)

    def task_reload(self, account, mediatype):
        try:
            self.engine.reload(account, mediatype)
        except utils.TrackmaError as e:
            self.error(e)
        except utils.TrackmaFatal as e:
            print("Fatal engine error: %s" % e)
            self.idle_restart()
            self.error("Fatal engine error: %s" % e)
            return

        if account:
            self.account = account

        # Refresh the GUI
        self.task_start_engine()

    def select_show(self, widget, page=None, page_num=None):
        page = page_num

        if page is None:
            page = self.notebook.get_current_page()

        selection = self.notebook.get_nth_page(page).get_child().get_selection()

        (tree_model, tree_iter) = selection.get_selected()
        if not tree_iter:
            self.allow_buttons_push(False, lists_too=False)
            return

        try:
            self.selected_show = int(tree_model.get(tree_iter, 0)[0])
        except ValueError:
            self.selected_show = tree_model.get(tree_iter, 0)[0]

        self.allow_buttons_push(True, lists_too=False)

        show = self.engine.get_show_info(self.selected_show)

        # Block handlers
        self.statusbox.handler_block(self.statusbox_handler)

        if self.image_thread is not None:
            self.image_thread.cancel()

        self.show_title.set_text('<span size="14000"><b>{0}</b></span>'.format(cgi.escape(show['title'])))
        self.show_title.set_use_markup(True)

        # Episode selector
        self.show_ep_button.set_label(str(show['my_progress']))
        self._hide_episode_entry()

        # Status selector
        for i in self.statusmodel:
            if str(i[0]) == str(show['my_status']):
                self.statusbox.set_active_iter(i.iter)
                break

        # Score selector
        self.show_score.set_value(show['my_score'])

        # Image
        if show.get('image_thumb') or show.get('image'):
            utils.make_dir('cache')
            filename = utils.get_filename('cache', "%s_%s_%s.jpg" % (self.engine.api_info['shortname'], self.engine.api_info['mediatype'], show['id']))

            if os.path.isfile(filename):
                self.show_image.image_show(filename)
            else:
                if imaging_available:
                    self.show_image.pholder_show('Loading...')
                    self.image_thread = ImageTask(self.show_image, show.get('image_thumb') or show['image'], filename, (100, 149))
                    self.image_thread.start()
                else:
                    self.show_image.pholder_show("PIL library\nnot available")

        # Unblock handlers
        self.statusbox.handler_unblock(self.statusbox_handler)

    def build_all_lists(self):
        for status in self.show_lists.keys():
            self.build_list(status)

    def build_list(self, status):
        widget = self.show_lists[status]
        widget.append_start()

        if status == self.engine.mediainfo['status_start']:
            library = self.engine.library()
            for show in self.engine.filter_list(widget.status_filter):
                widget.append(show, self.engine.altname(show['id']), library.get(show['id']))
        else:
            for show in self.engine.filter_list(widget.status_filter):
                widget.append(show, self.engine.altname(show['id']))

        widget.append_finish()

    def on_about(self, widget):
        about = Gtk.AboutDialog()
        about.set_program_name("Trackma-gtk")
        about.set_version(utils.VERSION)
        about.set_comments("Trackma is an open source client for media tracking websites.")
        about.set_website("http://github.com/z411/trackma")
        about.set_copyright("Thanks to all contributors. See AUTHORS file.\n(c) z411 - Icon by shuuichi")
        about.run()
        about.destroy()

    def message_handler(self, classname, msgtype, msg):
        # Thread safe
        print("%s: %s" % (classname, msg))
        if msgtype == messenger.TYPE_WARN:
            GObject.idle_add(self.status_push, "%s warning: %s" % (classname, msg))
        elif msgtype != messenger.TYPE_DEBUG:
            GObject.idle_add(self.status_push, "%s: %s" % (classname, msg))

    def error(self, msg, icon=Gtk.MessageType.ERROR):
        # Thread safe
        GObject.idle_add(self.error_push, msg, icon)

    def error_push(self, msg, icon=Gtk.MessageType.ERROR):
        dialog = Gtk.MessageDialog(self.main, Gtk.DialogFlags.MODAL, icon, Gtk.ButtonsType.OK, str(msg))
        dialog.show_all()
        dialog.connect("response", self.modal_close)

    def modal_close(self, widget, response_id):
        widget.destroy()

    def status(self, msg):
        # Thread safe
        GObject.idle_add(self.status_push, msg)

    def status_push(self, msg):
        self.statusbar.push(0, msg)

    def allow_buttons(self, boolean):
        # Thread safe
        GObject.idle_add(self.allow_buttons_push, boolean)

    def allow_buttons_push(self, boolean, lists_too=True):
        if lists_too:
            for widget in self.show_lists.values():
                widget.set_sensitive(boolean)

        if self.selected_show or not boolean:
            if self.engine.mediainfo['can_play']:
                self.play_next_button.set_sensitive(boolean)
                self.mb_play.set_sensitive(boolean)

            if self.engine.mediainfo['can_update']:
                self.show_ep_button.set_sensitive(boolean)
                self.show_ep_num.set_sensitive(boolean)
                self.add_epp_button.set_sensitive(boolean)
                self.rem_epp_button.set_sensitive(boolean)

            self.scoreset_button.set_sensitive(boolean)
            self.show_score.set_sensitive(boolean)
            self.statusbox.set_sensitive(boolean)
            self.mb_copy.set_sensitive(boolean)
            self.mb_delete.set_sensitive(boolean)
            self.mb_alt_title.set_sensitive(boolean)
            self.mb_info.set_sensitive(boolean)
            self.mb_web.set_sensitive(boolean)
            self.mb_folder.set_sensitive(boolean)

    def __do_copytoclip(self, widget):
        # Copy selected show title to clipboard
        show = self.engine.get_show_info(self.selected_show)

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(show['title'], -1)

        self.status('Title copied to clipboard.')

    def __do_altname(self,widget):
        show = self.engine.get_show_info(self.selected_show)
        current_altname = self.engine.altname(self.selected_show)

        dialog = Gtk.MessageDialog(
            None,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.QUESTION,
            Gtk.ButtonsType.OK_CANCEL,
            None)
        dialog.set_markup('Set the <b>alternate title</b> for the show.')
        entry = Gtk.Entry()
        entry.set_text(current_altname)
        entry.connect("activate", self.altname_response, dialog, Gtk.ResponseType.OK)
        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label("Alternate Title:"), False, 5, 5)
        hbox.pack_end(entry, True, True, 0)
        dialog.format_secondary_markup("Use this if the tracker is unable to find this show. Leave blank to disable.")
        dialog.vbox.pack_end(hbox, True, True, 0)
        dialog.show_all()
        retval = dialog.run()

        if retval == Gtk.ResponseType.OK:
            text = entry.get_text()
            self.engine.altname(self.selected_show, text)
            self.changed_show_title(show, text)

        dialog.destroy()

    def do_containingFolder(self, widget):

        #get needed show info
        show = self.engine.get_show_info(self.selected_show)
        try:
            filename = self.engine.get_episode_path(show, 1)
            with open(os.devnull, 'wb') as DEVNULL:
                subprocess.Popen(["/usr/bin/xdg-open",
                    os.path.dirname(filename)], stdout=DEVNULL, stderr=DEVNULL)
        except OSError:
            # xdg-open failed.
            raise utils.EngineError("Could not open folder.")

        except utils.EngineError:
            # Show not in library.
            self.error("No folder found.")

    def altname_response(self, entry, dialog, response):
        dialog.response(response)

    def __do_web(self, widget):
        show = self.engine.get_show_info(self.selected_show)
        if show['url']:
            Gtk.show_uri(None, show['url'], Gdk.CURRENT_TIME)

    def showview_context_menu(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor(path, col, 0)
                show = self.engine.get_show_info(self.selected_show)

                menu = Gtk.Menu()
                mb_play = Gtk.ImageMenuItem('Play', Gtk.Image.new_from_icon_name(Gtk.STOCK_MEDIA_PLAY, 0))
                mb_play.connect("activate", self.__do_play, True)
                mb_info = Gtk.MenuItem("Show details...")
                mb_info.connect("activate", self.__do_info)
                mb_web = Gtk.MenuItem("Open web site")
                mb_web.connect("activate", self.__do_web)
                mb_folder = Gtk.MenuItem("Open containing folder")
                mb_folder.connect("activate", self.do_containingFolder)
                mb_copy = Gtk.MenuItem("Copy title to clipboard")
                mb_copy.connect("activate", self.__do_copytoclip)
                mb_alt_title = Gtk.MenuItem("Set alternate title...")
                mb_alt_title.connect("activate", self.__do_altname)
                mb_delete = Gtk.ImageMenuItem('Delete', Gtk.Image.new_from_icon_name(Gtk.STOCK_DELETE, 0))
                mb_delete.connect("activate", self.__do_delete)

                menu.append(mb_play)

                if show['total']:
                    menu_eps = Gtk.Menu()
                    for i in range(1, show['total'] + 1):
                        mb_playep = Gtk.MenuItem(str(i))
                        mb_playep.connect("activate", self.__do_play, False, i)
                        menu_eps.append(mb_playep)
                    mb_playep = Gtk.MenuItem("Play episode")
                    mb_playep.set_submenu(menu_eps)
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
                menu.popup(None, None, None, None, event.button, event.time)

class ImageTask(threading.Thread):
    cancelled = False

    def __init__(self, show_image, remote, local, size=None):
        self.show_image = show_image
        self.remote = remote
        self.local = local
        self.size = size
        threading.Thread.__init__(self)

    def run(self):
        self.cancelled = False

        time.sleep(1)

        if self.cancelled:
            return

        # If there's a better solution for this please tell me/implement it.

        # If there's a size specified, thumbnail with PIL library
        # otherwise download and save it as it is
        req = urllib.request.Request(self.remote)
        req.add_header("User-agent", "TrackmaImage/{}".format(utils.VERSION))
        img_file = BytesIO(urllib.request.urlopen(req).read())
        if self.size:
            im = Image.open(img_file)
            im.thumbnail((self.size[0], self.size[1]), Image.ANTIALIAS)
            im.save(self.local)
        else:
            with open(self.local, 'wb') as f:
                f.write(img_file.read())

        if self.cancelled:
            return

        Gdk.threads_enter()
        self.show_image.image_show(self.local)
        Gdk.threads_leave()

    def cancel(self):
        self.cancelled = True

class ImageView(Gtk.HBox):
    def __init__(self, w, h):
        Gtk.HBox.__init__(self)

        self.w = w
        self.h = h
        self.showing_pholder = False

        self.w_image = Gtk.Image()
        self.w_image.set_size_request(w, h)

        self.w_pholder = Gtk.Label()
        self.w_pholder.set_size_request(w, h)

        self.pack_start(self.w_image, False, False, 0)

    def image_show(self, filename):
        if self.showing_pholder:
            self.remove(self.w_pholder)
            self.pack_start(self.w_image, False, False, 0)
            self.w_image.show()
            self.showing_pholder = False

        pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
        w, h = scale(pixbuf.get_width(), pixbuf.get_height(), self.w, self.h)
        scaled_buf = pixbuf.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
        self.w_image.set_from_pixbuf(scaled_buf)

    def pholder_show(self, msg):
        if not self.showing_pholder:
            self.pack_end(self.w_pholder, False, False, 0)
            self.remove(self.w_image)
            self.w_pholder.show()
            self.showing_pholder = True

        self.w_pholder.set_text(msg)

class ShowView(Gtk.TreeView):
    __gsignals__ = {'column-toggled': (GObject.SIGNAL_RUN_LAST, \
            GObject.TYPE_PYOBJECT, (GObject.TYPE_STRING, GObject.TYPE_BOOLEAN) )}

    def __init__(self, status, colors, visible_columns, decimals=0, progress_style=1):
        Gtk.TreeView.__init__(self)

        self.colors = colors
        self.visible_columns = visible_columns
        self.decimals = decimals
        self.status_filter = status
        self.progress_style = progress_style

        self.set_enable_search(True)
        self.set_search_column(1)

        self.cols = dict()
        self.available_columns = (
                ('Title', 1),
                ('Progress', 2),
                ('Score', 3),
                ('Percent', 10),
                ('Start', 11),
                ('End', 12),
                ('My start', 13),
                ('My end', 14),
        )

        for (name, sort) in self.available_columns:
            self.cols[name] = Gtk.TreeViewColumn(name)
            self.cols[name].set_sort_column_id(sort)

            # This is a hack to allow for right-clickable header
            label = Gtk.Label(name)
            label.show()
            self.cols[name].set_widget(label)

            self.append_column(self.cols[name])

            w = self.cols[name].get_widget()
            while not isinstance(w, Gtk.Button):
                w = w.get_parent()

            w.connect('button-press-event', self._header_button_press)

            if name not in self.visible_columns:
                self.cols[name].set_visible(False)

        #renderer_id = Gtk.CellRendererText()
        #self.cols['ID'].pack_start(renderer_id, False, True, 0)
        #self.cols['ID'].set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        #self.cols['ID'].set_expand(False)
        #self.cols['ID'].add_attribute(renderer_id, 'text', 0)

        renderer_title = Gtk.CellRendererText()
        self.cols['Title'].pack_start(renderer_title, False)
        self.cols['Title'].set_resizable(True)
        self.cols['Title'].set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.cols['Title'].set_expand(True)
        self.cols['Title'].add_attribute(renderer_title, 'text', 1)
        self.cols['Title'].add_attribute(renderer_title, 'foreground', 9) # Using foreground-gdk does not work, possibly due to the timing of it being set
        renderer_title.set_property('ellipsize', Pango.EllipsizeMode.END)

        renderer_progress = Gtk.CellRendererText()
        self.cols['Progress'].pack_start(renderer_progress, False)
        self.cols['Progress'].add_attribute(renderer_progress, 'text', 4)
        self.cols['Progress'].set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self.cols['Progress'].set_expand(False)

        if self.progress_style == 0:
            renderer_percent = Gtk.CellRendererProgress()
            self.cols['Percent'].pack_start(renderer_percent, False)
            self.cols['Percent'].add_attribute(renderer_percent, 'value', 10)
        else:
            renderer_percent = ProgressCellRenderer(self.colors)
            self.cols['Percent'].pack_start(renderer_percent, False)
            self.cols['Percent'].add_attribute(renderer_percent, 'value', 2)
            self.cols['Percent'].add_attribute(renderer_percent, 'total', 6)
            self.cols['Percent'].add_attribute(renderer_percent, 'subvalue', 7)
            self.cols['Percent'].add_attribute(renderer_percent, 'eps', 8)
        renderer_percent.set_fixed_size(100, -1)

        renderer = Gtk.CellRendererText()
        self.cols['Score'].pack_start(renderer, False)
        self.cols['Score'].add_attribute(renderer, 'text', 5)
        renderer = Gtk.CellRendererText()
        self.cols['Start'].pack_start(renderer, False)
        self.cols['Start'].add_attribute(renderer, 'text', 11)
        renderer = Gtk.CellRendererText()
        self.cols['End'].pack_start(renderer, False)
        self.cols['End'].add_attribute(renderer, 'text', 12)
        renderer = Gtk.CellRendererText()
        self.cols['My start'].pack_start(renderer, False)
        self.cols['My start'].add_attribute(renderer, 'text', 13)
        renderer = Gtk.CellRendererText()
        self.cols['My end'].pack_start(renderer, False)
        self.cols['My end'].add_attribute(renderer, 'text', 14)

        self.store = Gtk.ListStore(
            int,                   # ID
            str,                   # Title
            int,                   # Episodes
            float,                 # Score
            str,                   # Episodes_str
            str,                   # Score_str
            int,                   # Total
            int,                   # Subvalue
            GObject.TYPE_PYOBJECT, # Eps
            str,                   # Color
            int,                   # Progress%
            str,                   # start_date
            str,                   # end_date
            str,                   # my_start_date
            str)                   # my_finish_date
        self.set_model(self.store)

    def _header_button_press(self, button, event):
        if event.button == 3:
            menu = Gtk.Menu()
            for name, sort in self.available_columns:
                is_active = name in self.visible_columns

                item = Gtk.CheckMenuItem(name)
                item.set_active(is_active)
                item.connect('activate', self._header_menu_item, name, not is_active)
                menu.append(item)
                item.show()

            menu.popup(None, None, None, None, event.button, event.time)
            return True

    def _header_menu_item(self, w, column_name, visible):
        self.emit('column-toggled', column_name, visible)

    def _format_date(self, date):
        if date:
            try:
                return date.strftime('%Y-%m-%d')
            except ValueError:
                return '?'
        else:
            return '-'

    def _get_color(self, show, eps):
        if show.get('queued'):
            return self.colors['is_queued']
        elif eps and max(eps) > show['my_progress']:
            return self.colors['new_episode']
        elif show['status'] == utils.STATUS_AIRING:
            return self.colors['is_airing']
        elif show['status'] == utils.STATUS_NOTYET:
            return self.colors['not_aired']
        else:
            return None

    def append_start(self):
        self.freeze_child_notify()
        self.store.clear()

    def append(self, show, altname=None, eps=None):
        episodes_str = "%d / %d" % (show['my_progress'], show['total'])
        if show['total'] and show['my_progress'] <= show['total']:
            progress = (float(show['my_progress']) / show['total']) * 100
        else:
            progress = 0

        title_str = show['title']
        if altname:
            title_str += " [%s]" % altname

        score_str = "%0.*f" % (self.decimals, show['my_score'])
        aired_eps = utils.estimate_aired_episodes(show)
        if not aired_eps:
            aired_eps = 0

        if eps:
            available_eps = eps.keys()
        else:
            available_eps = []

        start_date =     self._format_date(show['start_date'])
        end_date =       self._format_date(show['end_date'])
        my_start_date =  self._format_date(show['my_start_date'])
        my_finish_date = self._format_date(show['my_finish_date'])

        row = [show['id'],
               title_str,
               show['my_progress'],
               show['my_score'],
               episodes_str,
               score_str,
               show['total'],
               aired_eps,
               available_eps,
               self._get_color(show, available_eps),
               progress,
               start_date,
               end_date,
               my_start_date,
               my_finish_date]
        self.store.append(row)

    def append_finish(self):
        self.thaw_child_notify()
        self.store.set_sort_column_id(1, Gtk.SortType.ASCENDING)

    def update(self, show):
        for row in self.store:
            if int(row[0]) == show['id']:
                episodes_str = "%d / %d" % (show['my_progress'], show['total'])
                row[2] = show['my_progress']
                row[4] = episodes_str

                score_str = "%0.*f" % (self.decimals, show['my_score'])

                row[3] = show['my_score']
                row[5] = score_str
                row[9] = self._get_color(show, row[8])
                return

        #print("Warning: Show ID not found in ShowView (%d)" % show['id'])

    def update_title(self, show, altname=None):
        for row in self.store:
            if int(row[0]) == show['id']:
                if altname:
                    title_str = "%s [%s]" % (show['title'], altname)
                else:
                    title_str = show['title']

                row[1] = title_str
                return

    def playing(self, show, is_playing):
        # Change the color if the show is currently playing
        for row in self.store:
            if int(row[0]) == show['id']:
                if is_playing:
                    row[9] = self.colors['is_playing']
                else:
                    row[9] = self._get_color(show, row[8])
                return

    def select(self, show):
        """Select specified row"""
        for row in self.store:
            if int(row[0]) == show['id']:
                selection = self.get_selection()
                selection.select_iter(row.iter)
                break

class AccountSelect(Gtk.Window):
    default = None

    def __init__(self, manager, switch=False):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)
        self.use_button = Gtk.Button('Switch')
        self.use_button.set_sensitive(False)

        self.manager = manager
        self.switch = switch

    def create(self):
        self.pixbufs = {}
        for (libname, lib) in utils.available_libs.items():
            self.pixbufs[libname] = GdkPixbuf.Pixbuf.new_from_file(lib[1])

        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Select Account')
        self.set_border_width(10)
        self.connect('delete-event', self.on_delete)

        vbox = Gtk.VBox(False, 10)

        # Treeview
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_size_request(400, 200)

        self.accountlist = Gtk.TreeView()

        col_user = Gtk.TreeViewColumn('Username')
        col_user.set_expand(True)
        self.accountlist.append_column(col_user)
        col_site = Gtk.TreeViewColumn('Site')
        self.accountlist.append_column(col_site)

        renderer_user = Gtk.CellRendererText()
        col_user.pack_start(renderer_user, False)
        col_user.add_attribute(renderer_user, 'text', 1)
        renderer_icon = Gtk.CellRendererPixbuf()
        col_site.pack_start(renderer_icon, False)
        col_site.add_attribute(renderer_icon, 'pixbuf', 3)
        renderer_site = Gtk.CellRendererText()
        col_site.pack_start(renderer_site, False)
        col_site.add_attribute(renderer_site, 'text', 2)

        self.store = Gtk.ListStore(int, str, str, GdkPixbuf.Pixbuf, bool)
        self.accountlist.set_model(self.store)

        self.accountlist.get_selection().connect("changed", self.on_account_changed)
        self.accountlist.connect("row-activated", self.on_row_activated)

        # Bottom buttons
        alignment = Gtk.Alignment(xalign=1.0, xscale=0)
        bottombar = Gtk.HBox(False, 5)

        self.remember = Gtk.CheckButton('Remember')
        if self.manager.get_default() is not None:
            self.remember.set_active(True)
        add_button = Gtk.Button('Add')
        add_button.set_image(Gtk.Image.new_from_icon_name(Gtk.STOCK_APPLY, Gtk.IconSize.BUTTON))
        add_button.connect("clicked", self._do_add)
        self.delete_button = Gtk.Button('Delete')
        self.delete_button.set_sensitive(False)
        self.delete_button.connect("clicked", self.__do_delete)
        self.delete_button.set_image(Gtk.Image.new_from_icon_name(Gtk.STOCK_DELETE, Gtk.IconSize.BUTTON))
        close_button = Gtk.Button('Close')
        close_button.set_image(Gtk.Image.new_from_icon_name(Gtk.STOCK_CLOSE, Gtk.IconSize.BUTTON))
        close_button.connect("clicked", self.__do_close)

        bottombar.pack_start(self.remember, False, False, 0)
        bottombar.pack_start(self.use_button, False, False, 0)
        bottombar.pack_start(add_button, False, False, 0)
        bottombar.pack_start(self.delete_button, False, False, 0)
        bottombar.pack_start(close_button, False, False, 0)
        alignment.add(bottombar)

        sw.add(self.accountlist)

        vbox.pack_start(sw, True, True, 0)
        vbox.pack_start(alignment, False, False, 0)
        self.add(vbox)

        self._refresh_list()
        self.show_all()

    def _refresh_list(self):
        self.store.clear()
        for k, account in self.manager.get_accounts():
            libname = account['api']
            try:
                api = utils.available_libs[libname]
                self.store.append([k, account['username'], api[0], self.pixbufs[libname], True])
            except KeyError:
                # Invalid API
                self.store.append([k, account['username'], 'N/A', None, False])


    def is_remember(self):
        # Return the state of the checkbutton if there's no default account
        if self.default is None:
            return self.remember.get_active()
        else:
            return True

    def get_selected(self):
        selection = self.accountlist.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)
        return selection.get_selected()

    def get_selected_id(self):
        if self.default is not None:
            return self.default
        else:
            tree_model, tree_iter = self.get_selected()
            return tree_model.get_value(tree_iter, 0)

    def on_account_changed(self, widget):
        tree_model, tree_iter = self.get_selected()
        if tree_iter:
            is_selectable = tree_model.get_value(tree_iter, 4)
        else:
            is_selectable = False

        self.use_button.set_sensitive(is_selectable)
        self.delete_button.set_sensitive(True)

    def on_row_activated(self, treeview, iter, path):
        self.use_button.emit("clicked")

    def _do_add(self, widget):
        """Create Add Account window"""
        self.add_win = AccountSelectAdd(self.pixbufs)
        self.add_win.add_button.connect("clicked", self.add_account)

    def add_account(self, widget):
        """Closes Add Account window and tells the manager to add
        the account to the database"""
        username =  self.add_win.txt_user.get_text().strip()
        password = self.add_win.txt_passwd.get_text()
        apiiter = self.add_win.cmb_api.get_active_iter()

        if not username:
            self.error('Please enter a username.')
            return
        if not password:
            self.error('Please enter a password.')
            return
        if not apiiter:
            self.error('Please select a website.')
            return

        api = self.add_win.model_api.get(apiiter, 0)[0]
        self.add_win.destroy()

        self.manager.add_account(username, password, api)
        self._refresh_list()

    def __do_delete(self, widget):
        selectedid = self.get_selected_id()
        dele = self.manager.delete_account(selectedid)

        self._refresh_list()

    def error(self, msg):
        md = Gtk.MessageDialog(None,
            Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CLOSE, str(msg))
        md.run()
        md.destroy()

    def modal_close(self, widget, response_id):
        widget.destroy()

    def __do_close(self, widget):
        self.destroy()
        if not self.switch:
            Gtk.main_quit()

    def on_delete(self, widget, data):
        self.__do_close(None)
        return False

class InfoDialog(Gtk.Window):
    def __init__(self, engine, show):
        self.engine = engine
        self._show = show

        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Show Details')
        self.set_border_width(10)

        fullbox = Gtk.VBox()

        # Info box
        info = InfoWidget(engine)
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


class InfoWidget(Gtk.VBox):
    def __init__(self, engine):
        Gtk.VBox.__init__(self)

        self.engine = engine

        # Title line
        self.w_title = Gtk.Label('')
        self.w_title.set_ellipsize(Pango.EllipsizeMode.END)

        # Middle line (sidebox)
        eventbox_sidebox = Gtk.EventBox()
        self.scrolled_sidebox = Gtk.ScrolledWindow()
        self.scrolled_sidebox.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sidebox = Gtk.HBox()

        alignment_image = Gtk.Alignment(yalign=0.0, xscale=0, yscale=0)
        self.w_image = ImageView(225, 350)
        alignment_image.add(self.w_image)

        self.w_content = Gtk.Label()

        sidebox.pack_start(alignment_image, False, False, 5)
        sidebox.pack_start(self.w_content, True, True, 5)

        eventbox_sidebox.add(sidebox)

        self.scrolled_sidebox.add_with_viewport(eventbox_sidebox)

        self.pack_start(self.w_title, False, False, 0)
        self.pack_start(self.scrolled_sidebox, True, True, 5)

    def set_size(self, w, h):
        self.scrolled_sidebox.set_size_request(w, h)

    def load(self, show):
        self._show = show

        # Load image
        imagefile = utils.get_filename('cache', "f_%d.jpg" % show['id'])
        imagefile = utils.get_filename('cache', "%s_%s_f_%s.jpg" % (self.engine.api_info['shortname'], self.engine.api_info['mediatype'], show['id']))


        if os.path.isfile(imagefile):
            self.w_image.image_show(imagefile)
        else:
            self.w_image.pholder_show('Loading...')
            self.image_thread = ImageTask(self.w_image, show['image'], imagefile)
            self.image_thread.start()

        # Start info loading thread
        threading.Thread(target=self.task_load).start()

    def task_load(self):
        # Thread to ask the engine for show details

        try:
            self.details = self.engine.get_show_details(self._show)
        except utils.TrackmaError as e:
            self.details = None
            self.details_e = e

        GObject.idle_add(self._done)

    def _done(self):
        if self.details:
            # Put the returned details into the lines VBox
            self.w_title.set_text('<span size="14000"><b>{0}</b></span>'.format(cgi.escape(self.details['title'])))
            self.w_title.set_use_markup(True)

            detail = list()
            for line in self.details['extra']:
                if line[0] and line[1]:
                    detail.append("<b>%s</b>\n%s" % (cgi.escape(str(line[0])), cgi.escape(str(line[1]))))

            self.w_content.set_text("\n\n".join(detail))
            self.w_content.set_use_markup(True)
            self.w_content.set_size_request(340, -1)

            self.show_all()
        else:
            self.w_title.set_text('Error while getting details.')
            if self.details_e:
                self.w_content.set_text(str(self.details_e))

        self.w_content.set_alignment(0, 0)
        self.w_content.set_line_wrap(True)
        self.w_content.set_size_request(340, -1)

class Settings(Gtk.Window):
    def __init__(self, engine, config, configfile):
        self.engine = engine

        self.config = config
        self.configfile = configfile

        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)

        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Global Settings')
        self.set_border_width(10)

        ### Play Next ###
        lbl_player = Gtk.Label('Media Player')
        lbl_player.set_size_request(120, -1)
        lbl_player.set_xalign(0)
        self.txt_player = Gtk.Entry()
        self.txt_player.set_max_length(4096)
        playerbrowse_button = Gtk.Button('Browse...')
        playerbrowse_button.connect("clicked", self.__do_browse, 'Select player', self.txt_player)

        header0 = Gtk.Label()
        header0.set_text('<b>Play Next</b>')
        header0.set_use_markup(True)
        header0.set_xalign(0)

        line0 = Gtk.HBox(False, 5)
        line0.pack_start(lbl_player, False, False, 5)
        line0.pack_start(self.txt_player, True, True, 0)
        line0.pack_start(playerbrowse_button, False, False, 0)

        ### Tracker ###

        # Labels
        lbl_process = Gtk.Label('Process Name')
        lbl_process.set_size_request(120, -1)
        lbl_process.set_xalign(0)
        lbl_searchdir = Gtk.Label('Library Directory')
        lbl_searchdir.set_size_request(120, -1)
        lbl_searchdir.set_xalign(0)
        lbl_tracker_enabled = Gtk.Label('Enable Tracker')
        lbl_tracker_enabled.set_size_request(120, -1)
        lbl_tracker_enabled.set_xalign(0)
        lbl_tracker_plex_host_port = Gtk.Label('Host and Port')
        lbl_tracker_plex_host_port.set_size_request(120, -1)
        lbl_tracker_plex_host_port.set_xalign(0)
        lbl_tracker_update_wait = Gtk.Label('Wait before update')
        lbl_tracker_update_wait.set_size_request(120, -1)
        lbl_tracker_update_wait.set_xalign(0)
        lbl_tracker_update_options = Gtk.Label('Update options')
        lbl_tracker_update_options.set_size_request(120, -1)
        lbl_tracker_update_options.set_xalign(0)

        # Entries
        self.txt_process = Gtk.Entry()
        self.txt_process.set_max_length(4096)
        self.txt_searchdir = Gtk.Entry()
        self.txt_searchdir.set_max_length(4096)
        self.browse_button = Gtk.Button('Browse...')
        self.browse_button.connect("clicked", self.__do_browse, 'Select search directory', self.txt_searchdir, True)
        self.chk_tracker_enabled = Gtk.CheckButton()
        self.txt_plex_host = Gtk.Entry()
        self.txt_plex_host.set_max_length(4096)
        self.txt_plex_port = Gtk.Entry()
        self.txt_plex_port.set_max_length(5)
        self.txt_plex_port.set_width_chars(5)
        self.chk_tracker_enabled.connect("toggled", self.tracker_type_sensitive)
        self.spin_tracker_update_wait = Gtk.SpinButton()
        self.spin_tracker_update_wait.set_adjustment(Gtk.Adjustment(value=5, lower=0, upper=500, step_incr=1, page_incr=10))
        self.chk_tracker_update_close = Gtk.CheckButton('Wait for the player to close')
        self.chk_tracker_update_prompt = Gtk.CheckButton('Ask before updating')

        # Radio buttons
        self.rbtn_tracker_local = Gtk.RadioButton.new_with_label_from_widget(None, 'Local')
        self.rbtn_tracker_plex = Gtk.RadioButton.new_with_label_from_widget(self.rbtn_tracker_local, 'Plex Media Server')
        self.rbtn_tracker_plex.connect("toggled", self.tracker_type_sensitive)
        self.rbtn_tracker_local.connect("toggled", self.tracker_type_sensitive)

        # Buttons
        alignment = Gtk.Alignment(xalign=0.5, xscale=0)
        bottombar = Gtk.HBox(False, 5)
        self.apply_button = Gtk.Button(stock=Gtk.STOCK_APPLY)
        self.apply_button.connect("clicked", self.__do_apply)
        close_button = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        close_button.connect("clicked", self.__do_close)
        bottombar.pack_start(self.apply_button, False, False, 0)
        bottombar.pack_start(close_button, False, False, 0)
        alignment.add(bottombar)

        # HBoxes
        header1 = Gtk.Label()
        header1.set_text('<b>Tracker Options</b>')
        header1.set_use_markup(True)
        header1.set_xalign(0)

        line1 = Gtk.HBox(False, 5)
        line1.pack_start(lbl_searchdir, False, False, 5)
        line1.pack_start(self.txt_searchdir, True, True, 0)
        line1.pack_start(self.browse_button, False, False, 0)

        line2 = Gtk.HBox(False, 5)
        line2.pack_start(lbl_process, False, False, 5)
        line2.pack_start(self.txt_process, True, True, 0)

        line7 = Gtk.HBox(False, 5)
        line7.pack_start(lbl_tracker_plex_host_port, False, False, 5)
        line7.pack_start(self.txt_plex_host, True, True, 0)
        line7.pack_start(self.txt_plex_port, True, True, 0)

        line3 = Gtk.HBox(False, 5)
        line3.pack_start(lbl_tracker_enabled, False, False, 5)
        line3.pack_start(self.chk_tracker_enabled, False, False, 0)
        line3.pack_start(self.rbtn_tracker_local, False, False, 0)
        line3.pack_start(self.rbtn_tracker_plex, False, False, 0)

        line8 = Gtk.HBox(False, 5)
        line8.pack_start(lbl_tracker_update_wait, False, False, 5)
        line8.pack_start(self.spin_tracker_update_wait, False, False, 0)
        line8.pack_start(Gtk.Label('seconds'), False, False, 0)

        line9 = Gtk.HBox(False, 5)
        line9.pack_start(lbl_tracker_update_options, False, False, 5)
        line9.pack_start(self.chk_tracker_update_close, False, False, 0)
        line9.pack_start(self.chk_tracker_update_prompt, False, False, 0)

        ### Auto-retrieve ###
        header2 = Gtk.Label()
        header2.set_text('<b>Auto-retrieve</b>')
        header2.set_use_markup(True)
        header2.set_xalign(0)

        # Radio buttons
        self.rbtn_autoret_off = Gtk.RadioButton.new_with_label_from_widget(None, 'Disabled')
        self.rbtn_autoret_always = Gtk.RadioButton.new_with_label_from_widget(self.rbtn_autoret_off, 'Always at start')

        self.rbtn_autoret_days = Gtk.RadioButton.new_with_label_from_widget(self.rbtn_autoret_off, 'After')
        self.spin_autoret_days = Gtk.SpinButton()
        self.spin_autoret_days.set_adjustment(Gtk.Adjustment(value=3, lower=1, upper=100, step_incr=1, page_incr=10))
        self.spin_autoret_days.set_sensitive(False)
        self.rbtn_autoret_days.connect("toggled", self.radio_toggled, self.spin_autoret_days)
        lbl_autoret_days = Gtk.Label('days')
        line_autoret_days = Gtk.HBox(False, 5)
        line_autoret_days.pack_start(self.rbtn_autoret_days, False, False, 0)
        line_autoret_days.pack_start(self.spin_autoret_days, False, False, 0)
        line_autoret_days.pack_start(lbl_autoret_days, False, False, 0)

        line4 = Gtk.VBox(False, 5)
        line4.pack_start(self.rbtn_autoret_off, False, False, 0)
        line4.pack_start(self.rbtn_autoret_always, False, False, 0)
        line4.pack_start(line_autoret_days, False, False, 0)

        ### Auto-send ###
        header3 = Gtk.Label()
        header3.set_text('<b>Auto-send</b>')
        header3.set_use_markup(True)
        header3.set_xalign(0)

        # Radio buttons
        self.rbtn_autosend_off = Gtk.RadioButton.new_with_label_from_widget(None, 'Disabled')
        self.rbtn_autosend_always = Gtk.RadioButton.new_with_label_from_widget(self.rbtn_autosend_off, 'After every change')
        self.rbtn_autosend_at_exit = Gtk.CheckButton('Auto-send at exit')

        self.rbtn_autosend_minutes = Gtk.RadioButton.new_with_label_from_widget(self.rbtn_autosend_off, 'After')
        self.spin_autosend_minutes = Gtk.SpinButton()
        self.spin_autosend_minutes.set_adjustment(Gtk.Adjustment(value=60, lower=1, upper=1000, step_incr=1, page_incr=10))
        self.spin_autosend_minutes.set_sensitive(False)
        self.rbtn_autosend_minutes.connect("toggled", self.radio_toggled, self.spin_autosend_minutes)
        lbl_autosend_minutes = Gtk.Label('minutes')
        line_autosend_minutes = Gtk.HBox(False, 5)
        line_autosend_minutes.pack_start(self.rbtn_autosend_minutes, False, False, 0)
        line_autosend_minutes.pack_start(self.spin_autosend_minutes, False, False, 0)
        line_autosend_minutes.pack_start(lbl_autosend_minutes, False, False, 0)

        self.rbtn_autosend_size = Gtk.RadioButton.new_with_label_from_widget(self.rbtn_autosend_off, 'After the queue is larger than')
        self.spin_autosend_size = Gtk.SpinButton()
        self.spin_autosend_size.set_adjustment(Gtk.Adjustment(value=5, lower=1, upper=1000, step_incr=1, page_incr=10))
        self.spin_autosend_size.set_sensitive(False)
        self.rbtn_autosend_size.connect("toggled", self.radio_toggled, self.spin_autosend_size)
        lbl_autosend_size = Gtk.Label('entries')
        line_autosend_size = Gtk.HBox(False, 5)
        line_autosend_size.pack_start(self.rbtn_autosend_size, False, False, 0)
        line_autosend_size.pack_start(self.spin_autosend_size, False, False, 0)
        line_autosend_size.pack_start(lbl_autosend_size, False, False, 0)

        line5 = Gtk.VBox(False, 5)
        line5.pack_start(self.rbtn_autosend_off, False, False, 0)
        line5.pack_start(self.rbtn_autosend_always, False, False, 0)
        line5.pack_start(line_autosend_minutes, False, False, 0)
        line5.pack_start(line_autosend_size, False, False, 0)
        line5.pack_start(self.rbtn_autosend_at_exit, False, False, 0)

        ### Additional options
        header_additional = Gtk.Label()
        header_additional.set_text('<b>Additional options</b>')
        header_additional.set_use_markup(True)
        header_additional.set_xalign(0)

        self.chk_auto_status_change = Gtk.CheckButton('Change status automatically')
        self.chk_auto_status_change_if_scored = Gtk.CheckButton('Change status automatically only if scored')
        self.chk_auto_status_change_if_scored.set_sensitive(False)
        self.chk_auto_status_change.connect("toggled", self.radio_toggled, self.chk_auto_status_change_if_scored)
        self.chk_auto_date_change = Gtk.CheckButton('Change start and finish dates automatically')
        line_auto_status_change_if_scored = Gtk.HBox(False, 5)
        line_auto_status_change_if_scored.pack_start(self.chk_auto_status_change_if_scored, False, False, 20)
        line_additional = Gtk.VBox(False, 5)
        line_additional.pack_start(self.chk_auto_status_change, False, False, 0)
        line_additional.pack_start(line_auto_status_change_if_scored, False, False, 0)
        line_additional.pack_start(self.chk_auto_date_change, False, False, 0)

        ### GTK Interface ###
        header4 = Gtk.Label()
        header4.set_text('<b>GTK Interface</b>')
        header4.set_use_markup(True)
        header4.set_xalign(0)

        self.chk_show_tray = Gtk.CheckButton('Show Tray Icon')
        self.chk_close_to_tray = Gtk.CheckButton('Close to Tray')
        self.chk_start_in_tray = Gtk.CheckButton('Start Minimized to Tray')
        self.chk_tray_api_icon = Gtk.CheckButton('Use API Icon in Tray')
        self.chk_remember_geometry = Gtk.CheckButton('Remember Window Geometry')
        self.chk_classic_progress = Gtk.CheckButton('Use Classic Progress Bar')
        self.chk_close_to_tray.set_sensitive(False)
        self.chk_start_in_tray.set_sensitive(False)
        self.chk_tray_api_icon.set_sensitive(False)
        self.chk_show_tray.connect("toggled", self.radio_toggled, self.chk_close_to_tray)
        self.chk_show_tray.connect("toggled", self.radio_toggled, self.chk_start_in_tray)
        self.chk_show_tray.connect("toggled", self.radio_toggled, self.chk_tray_api_icon)

        line_close_to_tray = Gtk.HBox(False, 5)
        line_close_to_tray.pack_start(self.chk_close_to_tray, False, False, 20)
        line_start_in_tray = Gtk.HBox(False, 5)
        line_start_in_tray.pack_start(self.chk_start_in_tray, False, False, 20)
        line_tray_api_icon = Gtk.HBox(False, 5)
        line_tray_api_icon.pack_start(self.chk_tray_api_icon, False, False, 20)

        line6 = Gtk.VBox(False, 5)
        line6.pack_start(self.chk_show_tray, False, False, 0)
        line6.pack_start(line_close_to_tray, False, False, 0)
        line6.pack_start(line_start_in_tray, False, False, 0)
        line6.pack_start(line_tray_api_icon, False, False, 0)
        line6.pack_start(self.chk_remember_geometry, False, False, 0)
        line6.pack_start(self.chk_classic_progress, False, False, 0)

        ### Colors ###
        header5 = Gtk.Label()
        header5.set_text('<b>Color Scheme</b>')
        header5.set_use_markup(True)
        header5.set_xalign(0)
        self.colors = {}
        pages = [('rows',    'Row text'),
                 ('progress','Progress widget')]

        self.colors['rows'] = [('is_playing',  'Playing'),
                               ('is_queued',   'Queued'),
                               ('new_episode', 'New Episode'),
                               ('is_airing',   'Airing'),
                               ('not_aired',   'Unaired')]
        self.colors['progress'] = [('progress_bg',       'Background'),
                                   ('progress_fg',       'Watched bar'),
                                   ('progress_sub_bg',   'Aired episodes'),
                                   ('progress_sub_fg',   'Stored episodes'),
                                   ('progress_complete', 'Complete')]
        self.col_pickers = {}

        col_notebook = Gtk.Notebook()
        for (key,tab_title) in pages:
            rows = Gtk.VBox(False, 5)
            rows.set_border_width(10)
            rows_lines = []
            for (c_key,text) in self.colors[key]: # Generate widgets for each color
                line = Gtk.HBox(False, 5)
                label = Gtk.Label(text, xalign=0)
                picker = Gtk.ColorButton.new_with_color(getColor(self.config['colors'][c_key]))
                self.col_pickers[c_key] = picker
                line.pack_start(label, True, True, 0)
                line.pack_end(picker, False, False, 0)
                rows.pack_start(line, False, False, 0)
                rows_lines.append(line)
            col_notebook.append_page(rows, Gtk.Label(tab_title))


        # Join HBoxes
        mainbox = Gtk.VBox(False, 10)
        notebook = Gtk.Notebook()

        page0 = Gtk.VBox(False, 10)
        page0.set_border_width(10)
        page0.pack_start(header0, False, False, 0)
        page0.pack_start(line0, False, False, 0)
        page0.pack_start(header1, False, False, 0)
        page0.pack_start(line3, False, False, 0)
        page0.pack_start(line1, False, False, 0)
        page0.pack_start(line2, False, False, 0)
        page0.pack_start(line7, False, False, 0)
        page0.pack_start(line8, False, False, 0)
        page0.pack_start(line9, False, False, 0)

        page1 = Gtk.VBox(False, 10)
        page1.set_border_width(10)
        page1.pack_start(header2, False, False, 0)
        page1.pack_start(line4, False, False, 0)
        page1.pack_start(header3, False, False, 0)
        page1.pack_start(line5, False, False, 0)
        page1.pack_start(header_additional, False, False, 0)
        page1.pack_start(line_additional, False, False, 0)

        page2 = Gtk.VBox(False, 10)
        page2.set_border_width(10)
        page2.pack_start(header4, False, False, 0)
        page2.pack_start(line6, False, False, 0)
        page2.pack_start(header5, False, False, 0)
        page2.pack_start(col_notebook, False, False, 0)

        notebook.append_page(page0, Gtk.Label('Media'))
        notebook.append_page(page1, Gtk.Label('Sync'))
        notebook.append_page(page2, Gtk.Label('User Interface'))
        mainbox.pack_start(notebook, True, True, 0)
        mainbox.pack_start(alignment, False, False, 0)

        self.add(mainbox)
        self.load_config()

    def load_config(self):
        """Engine Configuration"""
        self.txt_player.set_text(self.engine.get_config('player'))
        self.txt_process.set_text(self.engine.get_config('tracker_process'))
        self.txt_searchdir.set_text(self.engine.get_config('searchdir'))
        self.txt_plex_host.set_text(self.engine.get_config('plex_host'))
        self.txt_plex_port.set_text(self.engine.get_config('plex_port'))
        self.chk_tracker_enabled.set_active(self.engine.get_config('tracker_enabled'))
        self.rbtn_autosend_at_exit.set_active(self.engine.get_config('autosend_at_exit'))
        self.spin_tracker_update_wait.set_value(self.engine.get_config('tracker_update_wait_s'))
        self.chk_tracker_update_close.set_active(self.engine.get_config('tracker_update_close'))
        self.chk_tracker_update_prompt.set_active(self.engine.get_config('tracker_update_prompt'))

        if self.engine.get_config('tracker_type') == 'local':
            self.rbtn_tracker_local.set_active(True)
            self.txt_plex_host.set_sensitive(False)
            self.txt_plex_port.set_sensitive(False)
        elif self.engine.get_config('tracker_type') == 'plex':
            self.rbtn_tracker_plex.set_active(True)
            self.txt_process.set_sensitive(False)

        if self.engine.get_config('autoretrieve') == 'always':
            self.rbtn_autoret_always.set_active(True)
        elif self.engine.get_config('autoretrieve') == 'days':
            self.rbtn_autoret_days.set_active(True)

        if self.engine.get_config('autosend') == 'always':
            self.rbtn_autosend_always.set_active(True)
        elif self.engine.get_config('autosend') in ('minutes', 'hours'):
            self.rbtn_autosend_minutes.set_active(True)
        elif self.engine.get_config('autosend') == 'size':
            self.rbtn_autosend_size.set_active(True)

        self.spin_autoret_days.set_value(self.engine.get_config('autoretrieve_days'))
        self.spin_autosend_minutes.set_value(self.engine.get_config('autosend_minutes'))
        self.spin_autosend_size.set_value(self.engine.get_config('autosend_size'))

        self.chk_auto_status_change.set_active(self.engine.get_config('auto_status_change'))
        self.chk_auto_status_change_if_scored.set_active(self.engine.get_config('auto_status_change_if_scored'))
        self.chk_auto_date_change.set_active(self.engine.get_config('auto_date_change'))

        """GTK Interface Configuration"""
        self.chk_show_tray.set_active(self.config['show_tray'])
        self.chk_close_to_tray.set_active(self.config['close_to_tray'])
        self.chk_start_in_tray.set_active(self.config['start_in_tray'])
        self.chk_tray_api_icon.set_active(self.config['tray_api_icon'])
        self.chk_remember_geometry.set_active(self.config['remember_geometry'])
        self.chk_classic_progress.set_active(not self.config['episodebar_style'])

    def save_config(self):
        """Engine Configuration"""
        self.engine.set_config('player', self.txt_player.get_text())
        self.engine.set_config('tracker_process', self.txt_process.get_text())
        self.engine.set_config('searchdir', self.txt_searchdir.get_text())
        self.engine.set_config('plex_host', self.txt_plex_host.get_text())
        self.engine.set_config('plex_port', self.txt_plex_port.get_text())
        self.engine.set_config('tracker_enabled', self.chk_tracker_enabled.get_active())
        self.engine.set_config('autosend_at_exit', self.rbtn_autosend_at_exit.get_active())
        self.engine.set_config('tracker_update_wait_s', self.spin_tracker_update_wait.get_value())
        self.engine.set_config('tracker_update_close', self.chk_tracker_update_close.get_active())
        self.engine.set_config('tracker_update_prompt', self.chk_tracker_update_prompt.get_active())

        # Tracker type
        if self.rbtn_tracker_local.get_active():
            self.engine.set_config('tracker_type', 'local')
        elif self.rbtn_tracker_plex.get_active():
            self.engine.set_config('tracker_type', 'plex')

        # Auto-retrieve
        if self.rbtn_autoret_always.get_active():
            self.engine.set_config('autoretrieve', 'always')
        elif self.rbtn_autoret_days.get_active():
            self.engine.set_config('autoretrieve', 'days')
        else:
            self.engine.set_config('autoretrieve', 'off')

        # Auto-send
        if self.rbtn_autosend_always.get_active():
            self.engine.set_config('autosend', 'always')
        elif self.rbtn_autosend_minutes.get_active():
            self.engine.set_config('autosend', 'minutes')
        elif self.rbtn_autosend_size.get_active():
            self.engine.set_config('autosend', 'size')
        else:
            self.engine.set_config('autosend', 'off')

        self.engine.set_config('autoretrieve_days', self.spin_autoret_days.get_value_as_int())
        self.engine.set_config('autosend_minutes', self.spin_autosend_minutes.get_value_as_int())
        self.engine.set_config('autosend_size', self.spin_autosend_size.get_value_as_int())

        self.engine.set_config('auto_status_change', self.chk_auto_status_change.get_active())
        self.engine.set_config('auto_status_change_if_scored', self.chk_auto_status_change_if_scored.get_active())
        self.engine.set_config('auto_date_change', self.chk_auto_date_change.get_active())
        self.engine.save_config()

        """GTK Interface configuration"""
        self.config['show_tray'] = self.chk_show_tray.get_active()

        if self.chk_show_tray.get_active():
            self.config['close_to_tray'] = self.chk_close_to_tray.get_active()
            self.config['start_in_tray'] = self.chk_start_in_tray.get_active()
            self.config['tray_api_icon'] = self.chk_tray_api_icon.get_active()
        else:
            self.config['close_to_tray'] = False
            self.config['start_in_tray'] = False
            self.config['tray_api_icon'] = False

        self.config['remember_geometry'] = self.chk_remember_geometry.get_active()
        self.config['episodebar_style'] = int(not self.chk_classic_progress.get_active())

        """Update Colors"""
        self.config['colors'] = {key: reprColor(col.get_color()) for key,col in self.col_pickers.items()}

        utils.save_config(self.config, self.configfile)

    def radio_toggled(self, widget, spin):
        spin.set_sensitive(widget.get_active())

    def tracker_type_sensitive(self, widget):
        if self.chk_tracker_enabled.get_active():
            if self.rbtn_tracker_local.get_active():
                self.txt_process.set_sensitive(True)
                self.txt_plex_host.set_sensitive(False)
                self.txt_plex_port.set_sensitive(False)
            elif self.rbtn_tracker_plex.get_active():
                self.txt_plex_host.set_sensitive(True)
                self.txt_plex_port.set_sensitive(True)
                self.txt_process.set_sensitive(False)
            self.spin_tracker_update_wait.set_sensitive(True)
        else:
            self.txt_process.set_sensitive(False)
            self.spin_tracker_update_wait.set_sensitive(False)
            self.txt_plex_host.set_sensitive(False)
            self.txt_plex_port.set_sensitive(False)

    def __do_browse(self, widget, title, entry, dironly=False):
        browsew = Gtk.FileChooserDialog(title,
                                        None,
                                        Gtk.FileChooserAction.OPEN,
                                        (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        browsew.set_default_response(Gtk.ResponseType.OK)

        if dironly:
            browsew.set_action(Gtk.FileChooserAction.SELECT_FOLDER)

        response = browsew.run()
        if response == Gtk.ResponseType.OK:
            entry.set_text(browsew.get_filename())
        browsew.destroy()

    def __do_apply(self, widget):
        self.save_config()
        self.destroy()

    def __do_close(self, widget):
        self.destroy()

class AccountSelectAdd(Gtk.Window):
    def __init__(self, pixbufs):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)

        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Create Account')
        self.set_border_width(10)

        # Labels
        self.lbl_user = Gtk.Label('Username')
        self.lbl_user.set_size_request(70, -1)
        self.lbl_passwd = Gtk.Label('Password')
        self.lbl_passwd.set_size_request(70, -1)
        lbl_api = Gtk.Label('Website')
        lbl_api.set_size_request(70, -1)

        # Entries
        self.txt_user = Gtk.Entry()
        self.txt_user.set_max_length(128)
        self.txt_passwd = Gtk.Entry()
        self.txt_passwd.set_max_length(128)
        self.txt_passwd.set_visibility(False)

        # Combobox
        self.model_api = Gtk.ListStore(str, str, GdkPixbuf.Pixbuf)

        for (libname, lib) in sorted(utils.available_libs.items()):
            self.model_api.append([libname, lib[0], pixbufs[libname]])

        self.cmb_api = Gtk.ComboBox.new_with_model(self.model_api)
        cell_icon = Gtk.CellRendererPixbuf()
        cell_name = Gtk.CellRendererText()
        self.cmb_api.pack_start(cell_icon, False)
        self.cmb_api.pack_start(cell_name, True)
        self.cmb_api.add_attribute(cell_icon, 'pixbuf', 2)
        self.cmb_api.add_attribute(cell_name, 'text', 1)
        self.cmb_api.connect("changed", self._refresh)

        # Buttons
        self.btn_auth = Gtk.Button("Request PIN")
        self.btn_auth.connect("clicked", self.__do_auth)

        alignment = Gtk.Alignment(xalign=0.5, xscale=0)
        bottombar = Gtk.HBox(False, 5)
        self.add_button = Gtk.Button(stock=Gtk.STOCK_APPLY)
        close_button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        close_button.connect("clicked", self.__do_close)
        bottombar.pack_start(self.add_button, False, False, 0)
        bottombar.pack_start(close_button, False, False, 0)
        alignment.add(bottombar)

        # HBoxes
        line1 = Gtk.HBox(False, 5)
        line1.pack_start(self.lbl_user, False, False, 0)
        line1.pack_start(self.txt_user, True, True, 0)

        line2 = Gtk.HBox(False, 5)
        line2.pack_start(self.lbl_passwd, False, False, 0)
        line2.pack_start(self.txt_passwd, True, True, 0)
        line2.pack_start(self.btn_auth, False, False, 0)

        line3 = Gtk.HBox(False, 5)
        line3.pack_start(lbl_api, False, False, 0)
        line3.pack_start(self.cmb_api, True, True, 0)

        # Join HBoxes
        vbox = Gtk.VBox(False, 10)
        vbox.pack_start(line3, False, False, 0)
        vbox.pack_start(line1, False, False, 0)
        vbox.pack_start(line2, False, False, 0)
        vbox.pack_start(alignment, False, False, 0)

        self.add(vbox)
        self.show_all()
        self.btn_auth.hide()

    def _refresh(self, widget):
        self.txt_user.set_text("")
        self.txt_passwd.set_text("")

        apiiter = self.cmb_api.get_active_iter()
        api = self.model_api.get(apiiter, 0)[0]
        if utils.available_libs[api][2] == utils.LOGIN_OAUTH:
            self.lbl_user.set_text("Name")
            self.lbl_passwd.set_text("PIN")
            self.txt_passwd.set_visibility(True)
            self.btn_auth.show()
        else:
            self.lbl_user.set_text("Username")
            self.lbl_passwd.set_text("Password")
            self.txt_passwd.set_visibility(False)
            self.btn_auth.hide()

    def __do_auth(self, widget):
        apiiter = self.cmb_api.get_active_iter()
        api = self.model_api.get(apiiter, 0)[0]
        url = utils.available_libs[api][4]

        webbrowser.open(url, 2, True)

    def __do_close(self, widget):
        self.destroy()


class ShowSearch(Gtk.Window):
    def __init__(self, engine, colors, current_status):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)

        self.entries = []

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

        self.showlist = ShowSearchView(colors)
        self.showlist.get_selection().connect("changed", self.select_show)

        sw.add(self.showlist)

        self.info = InfoWidget(engine)
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


class ShowSearchView(Gtk.TreeView):
    def __init__(self, colors):
        Gtk.TreeView.__init__(self)

        self.cols = dict()
        i = 0
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

class ProgressCellRenderer(Gtk.CellRenderer):
    value = 0
    subvalue = 0
    total = 0
    eps = []
    _subheight = 5

    __gproperties__ = {
        "value": (GObject.TYPE_INT, "Value",
        "Progress percentage", 0, 1000, 0,
        GObject.PARAM_READWRITE),

        "subvalue": (GObject.TYPE_INT, "Subvalue",
        "Sub percentage", 0, 1000, 0,
        GObject.PARAM_READWRITE),

        "total": (GObject.TYPE_INT, "Total",
        "Total percentage", 0, 1000, 0,
        GObject.PARAM_READWRITE),

        "eps": (GObject.TYPE_PYOBJECT, "Episodes",
        "Available episodes", GObject.PARAM_READWRITE),
    }

    def __init__(self, colors):
        Gtk.CellRenderer.__init__(self)
        self.colors = colors
        self.value = self.get_property("value")
        self.subvalue = self.get_property("subvalue")
        self.total = self.get_property("total")
        self.eps = self.get_property("eps")

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_render(self, cr, widget, background_area, cell_area, flags):
        (x, y, w, h) = self.do_get_size(widget, cell_area)

        cr.set_source_rgb(*self.__getColor(self.colors['progress_bg'])) #set_source_rgb(0.9, 0.9, 0.9)
        cr.rectangle(x, y, w, h)
        cr.fill()

        if not self.total:
            return

        if self.subvalue:
            if self.subvalue > self.total:
                mid = w
            else:
                mid = int(w / float(self.total) * self.subvalue)

            cr.set_source_rgb(*self.__getColor(self.colors['progress_sub_bg'])) #set_source_rgb(0.7, 0.7, 0.7)
            cr.rectangle(x, y+h-self._subheight, mid, h-(h-self._subheight))
            cr.fill()

        if self.value:
            if self.value >= self.total:
                cr.set_source_rgb(*self.__getColor(self.colors['progress_complete'])) #set_source_rgb(0.6, 0.8, 0.7)
                cr.rectangle(x, y, w, h)
            else:
                mid = int(w / float(self.total) * self.value)
                cr.set_source_rgb(*self.__getColor(self.colors['progress_fg'])) #set_source_rgb(0.6, 0.7, 0.8)
                cr.rectangle(x, y, mid, h)
            cr.fill()

        if self.eps:
            cr.set_source_rgb(*self.__getColor(self.colors['progress_sub_fg'])) #set_source_rgb(0.4, 0.5, 0.6)
            for episode in self.eps:
                if episode > 0 and episode <= self.total:
                    start = int(w / float(self.total) * (episode - 1))
                    finish = int(w / float(self.total) * episode)
                    cr.rectangle(x+start, y+h-self._subheight, finish-start, h-(h-self._subheight))
                    cr.fill()

    def do_get_size(self, widget, cell_area):
        if cell_area == None:
            return (0, 0, 0, 0)
        x = cell_area.x
        y = cell_area.y
        w = cell_area.width
        h = cell_area.height
        return (x, y, w, h)

    def __getColor(self, colorString):
        color = Gdk.color_parse(colorString)
        return color.red_float, color.green_float, color.blue_float

def reprColor(gdkColor):
    return '#%02x%02x%02x' % (
        round(gdkColor.red_float * 255),
        round(gdkColor.green_float * 255),
        round(gdkColor.blue_float * 255))

def getColor(colorString):
    # Takes a color string in either #RRGGBB format TODO: or group,role format (using GTK int values)
    # Returns gdk color
    if colorString[0] == "#":
        return Gdk.color_parse(colorString)
    #else:
        #(group, role) = [int(i) for i in colorString.split(',')]
        #if (0 <= group <= 2) and (0 <= role <= 19):
            #return QtGui.QColor( QPalette().color(group, role) )
        #else:
            ## Failsafe - return black
            #return QtGui.QColor()

def scale(w, h, x, y, maximum=True):
    nw = y * w / h
    nh = x * h / w
    if maximum ^ (nw >= x):
        return nw or 1, y
    return x, nh or 1

def main():
    app = Trackma_gtk()
    try:
        Gdk.threads_enter()
        app.main()
    except utils.TrackmaFatal as e:
        md = Gtk.MessageDialog(None,
            Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CLOSE, str(e))
        md.run()
        md.destroy()
    finally:
        Gdk.threads_leave()

if __name__ == '__main__':
    main()

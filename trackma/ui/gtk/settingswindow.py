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
from trackma import utils


# Icon tray isn't available in Wayland
tray_available = not Gdk.Display.get_default().get_name().lower().startswith('wayland')


def reprColor(gdkColor):
    return '#%02x%02x%02x' % (
        round(gdkColor.red_float * 255),
        round(gdkColor.green_float * 255),
        round(gdkColor.blue_float * 255))


def getColor(colorString):
    # Takes a color string in either #RRGGBB format
    # TODO: Take a group, role format (using GTK int values)
    # Returns gdk color
    if colorString[0] == "#":
        return Gdk.color_parse(colorString)

    return Gdk.color_parse("#000000")


class SettingsWindow(Gtk.Window):
    def __init__(self, engine, config, configfile):
        self.engine = engine

        self.config = config
        self.configfile = configfile

        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)

        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Global Settings')
        self.set_border_width(10)

        ### Library ###
        header0 = Gtk.Label()
        header0.set_text('<b>Library</b>')
        header0.set_use_markup(True)
        header0.set_xalign(0)

        lbl_player = Gtk.Label('Media Player')
        lbl_player.set_size_request(120, -1)
        lbl_player.set_xalign(0)
        self.txt_player = Gtk.Entry()
        self.txt_player.set_max_length(4096)
        playerbrowse_button = Gtk.Button('Browse...')
        playerbrowse_button.connect("clicked", self.__do_browse, 'Select player', self.txt_player.set_text)

        line0 = Gtk.HBox(False, 5)
        line0.pack_start(lbl_player, False, False, 5)
        line0.pack_start(self.txt_player, True, True, 0)
        line0.pack_start(playerbrowse_button, False, False, 0)

        lbl_searchdirs = Gtk.Label('Library Directories')
        lbl_searchdirs.set_size_request(120, -1)
        lbl_searchdirs.set_xalign(0)
        self.lst_searchdirs = Gtk.ListBox()
        sw = Gtk.ScrolledWindow()
        sw.set_size_request(-1, 100)
        sw.add(self.lst_searchdirs)

        # Buttons
        sd_alignment = Gtk.Alignment(yalign=0, yscale=0)
        buttonbar = Gtk.VBox(False, 5)
        self.dir_add_button = Gtk.Button('Add...')
        self.dir_add_button.connect("clicked", self.__do_browse, 'Select library directory', self._add_dirs, True)
        self.dir_del_button = Gtk.Button('Remove')
        self.dir_del_button.connect("clicked", self.__do_dir_del)
        buttonbar.pack_start(self.dir_add_button, False, False, 0)
        buttonbar.pack_start(self.dir_del_button, False, False, 0)
        sd_alignment.add(buttonbar)

        line1 = Gtk.HBox(False, 5)
        line1.pack_start(lbl_searchdirs, False, False, 5)
        line1.pack_start(sw, True, True, 0)
        line1.pack_start(sd_alignment, False, False, 0)

        lbl_library_options = Gtk.Label('Library options')
        lbl_library_options.set_size_request(120, -1)
        lbl_library_options.set_xalign(0)
        self.chk_library_autoscan = Gtk.CheckButton('Rescan library at startup')
        self.chk_scan_whole_list  = Gtk.CheckButton('Scan through whole list')
        self.chk_library_full_path  = Gtk.CheckButton('Take subdirectory name into account')

        lin_library_options = Gtk.HBox(False, 5)
        lin_library_options.pack_start(lbl_library_options, False, False, 5)
        lin_library_options_v = Gtk.VBox(False, 0)
        lin_library_options_v.pack_start(self.chk_library_autoscan, False, False, 0)
        lin_library_options_v.pack_start(self.chk_scan_whole_list, False, False, 0)
        lin_library_options_v.pack_start(self.chk_library_full_path, False, False, 0)
        lin_library_options.pack_start(lin_library_options_v, False, False, 0)

        ### Tracker ###

        # Labels
        lbl_process = Gtk.Label('Process Name')
        lbl_process.set_size_request(120, -1)
        lbl_process.set_xalign(0)
        lbl_tracker_enabled = Gtk.Label('Enable Tracker')
        lbl_tracker_enabled.set_size_request(120, -1)
        lbl_tracker_enabled.set_xalign(0)
        lbl_tracker_update_wait = Gtk.Label('Wait before update')
        lbl_tracker_update_wait.set_size_request(120, -1)
        lbl_tracker_update_wait.set_xalign(0)
        lbl_tracker_update_options = Gtk.Label('Update options')
        lbl_tracker_update_options.set_size_request(120, -1)
        lbl_tracker_update_options.set_xalign(0)

        # Entries
        self.txt_process = Gtk.Entry()
        self.txt_process.set_max_length(4096)
        self.chk_tracker_enabled = Gtk.CheckButton()
        self.chk_tracker_enabled.connect("toggled", self.tracker_type_sensitive)
        self.spin_tracker_update_wait = Gtk.SpinButton()
        self.spin_tracker_update_wait.set_adjustment(Gtk.Adjustment(value=5, lower=0, upper=500, step_incr=1, page_incr=10))
        self.chk_tracker_update_close = Gtk.CheckButton('Wait for the player to close')
        self.chk_tracker_update_prompt = Gtk.CheckButton('Ask before updating')
        self.chk_tracker_not_found_prompt = Gtk.CheckButton('Ask to add if not in list')

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
        header1.set_text('<b>Tracker</b>')
        header1.set_use_markup(True)
        header1.set_xalign(0)

        line2 = Gtk.HBox(False, 5)
        line2.pack_start(lbl_process, False, False, 5)
        line2.pack_start(self.txt_process, True, True, 0)

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
        line9a = Gtk.VBox(False, 0)
        line9a.pack_start(self.chk_tracker_update_close, False, False, 0)
        line9a.pack_start(self.chk_tracker_update_prompt, False, False, 0)
        line9a.pack_start(self.chk_tracker_not_found_prompt, False, False, 0)
        line9.pack_start(line9a, False, False, 0)

        ### Plex ###
        header6 = Gtk.Label()
        header6.set_text('<b>Plex Media Server</b>')
        header6.set_use_markup(True)
        header6.set_xalign(0)

        # Labels
        lbl_tracker_plex_host_port = Gtk.Label('Host and Port')
        lbl_tracker_plex_host_port.set_size_request(120, -1)
        lbl_tracker_plex_host_port.set_xalign(0)
        lbl_tracker_plex_obey_wait = Gtk.Label('Use "wait before update" time')
        lbl_tracker_plex_obey_wait.set_size_request(120, -1)
        lbl_tracker_plex_obey_wait.set_xalign(0)
        lbl_tracker_plex_login = Gtk.Label('myPlex login (claimed server)')
        lbl_tracker_plex_login.set_size_request(120, -1)
        lbl_tracker_plex_login.set_xalign(0)

        # Entries
        self.txt_plex_host = Gtk.Entry()
        self.txt_plex_host.set_max_length(4096)
        self.txt_plex_port = Gtk.Entry()
        self.txt_plex_port.set_max_length(5)
        self.txt_plex_port.set_width_chars(5)
        self.txt_plex_user = Gtk.Entry()
        self.txt_plex_user.set_max_length(4096)
        self.txt_plex_passw = Gtk.Entry()
        self.txt_plex_passw.set_max_length(128)
        self.txt_plex_passw.set_visibility(False)
        self.chk_tracker_plex_obey_wait = Gtk.CheckButton()

        # HBoxes
        line7 = Gtk.HBox(False, 5)
        line7.pack_start(lbl_tracker_plex_host_port, False, False, 5)
        line7.pack_start(self.txt_plex_host, True, True, 0)
        line7.pack_start(self.txt_plex_port, True, True, 0)
        line10 = Gtk.HBox(False, 5)
        line10.pack_start(lbl_tracker_plex_obey_wait, False, False, 5)
        line10.pack_start(self.chk_tracker_plex_obey_wait, False, False, 0)
        line11 = Gtk.HBox(False, 5)
        line11.pack_start(lbl_tracker_plex_login, False, False, 5)
        line11.pack_start(self.txt_plex_user, True, True, 0)
        line11.pack_start(self.txt_plex_passw, True, True, 0)

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

        if not tray_available:
            self.chk_show_tray.set_label('Show Tray Icon (Not supported in this environment)')
            self.chk_show_tray.set_sensitive(False)

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
        page0.pack_start(line1, False, False, 0)
        page0.pack_start(lin_library_options, False, False, 0)
        page0.pack_start(header1, False, False, 0)
        page0.pack_start(line3, False, False, 0)
        page0.pack_start(line2, False, False, 0)
        page0.pack_start(line8, False, False, 0)
        page0.pack_start(line9, False, False, 0)
        page0.pack_start(header6, False, False, 0)
        page0.pack_start(line7, False, False, 0)
        page0.pack_start(line10, False, False, 0)
        page0.pack_start(line11, False, False, 0)

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
        self.chk_library_autoscan.set_active(self.engine.get_config('library_autoscan'))
        self.chk_scan_whole_list.set_active(self.engine.get_config('scan_whole_list'))
        self.chk_library_full_path.set_active(self.engine.get_config('library_full_path'))
        self.txt_plex_host.set_text(self.engine.get_config('plex_host'))
        self.txt_plex_port.set_text(self.engine.get_config('plex_port'))
        self.chk_tracker_plex_obey_wait.set_active(self.engine.get_config('plex_obey_update_wait_s'))
        self.txt_plex_user.set_text(self.engine.get_config('plex_user'))
        self.txt_plex_passw.set_text(self.engine.get_config('plex_passwd'))
        self.chk_tracker_enabled.set_active(self.engine.get_config('tracker_enabled'))
        self.rbtn_autosend_at_exit.set_active(self.engine.get_config('autosend_at_exit'))
        self.spin_tracker_update_wait.set_value(self.engine.get_config('tracker_update_wait_s'))
        self.chk_tracker_update_close.set_active(self.engine.get_config('tracker_update_close'))
        self.chk_tracker_update_prompt.set_active(self.engine.get_config('tracker_update_prompt'))
        self.chk_tracker_not_found_prompt.set_active(self.engine.get_config('tracker_not_found_prompt'))

        self._add_dirs(self.engine.get_config('searchdir'))

        if self.engine.get_config('tracker_type') == 'local':
            self.rbtn_tracker_local.set_active(True)
            self.txt_plex_host.set_sensitive(False)
            self.txt_plex_port.set_sensitive(False)
            self.chk_tracker_plex_obey_wait.set_sensitive(False)
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
        if tray_available:
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
        self.engine.set_config('library_autoscan',
                               self.chk_library_autoscan.get_active())
        self.engine.set_config('scan_whole_list',
                               self.chk_scan_whole_list.get_active())
        self.engine.set_config('library_full_path',
                               self.chk_library_full_path.get_active())
        self.engine.set_config('plex_host', self.txt_plex_host.get_text())
        self.engine.set_config('plex_port', self.txt_plex_port.get_text())
        self.engine.set_config('plex_obey_update_wait_s', self.chk_tracker_plex_obey_wait.get_active())
        self.engine.set_config('plex_user', self.txt_plex_user.get_text())
        self.engine.set_config('plex_passwd', self.txt_plex_passw.get_text())
        self.engine.set_config('tracker_enabled', self.chk_tracker_enabled.get_active())
        self.engine.set_config('autosend_at_exit', self.rbtn_autosend_at_exit.get_active())
        self.engine.set_config('tracker_update_wait_s', self.spin_tracker_update_wait.get_value())
        self.engine.set_config('tracker_update_close', self.chk_tracker_update_close.get_active())
        self.engine.set_config('tracker_update_prompt', self.chk_tracker_update_prompt.get_active())
        self.engine.set_config('tracker_not_found_prompt', self.chk_tracker_not_found_prompt.get_active())

        self.engine.set_config('searchdir', [row.data for row in self.lst_searchdirs])

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
                self.chk_tracker_plex_obey_wait.set_sensitive(False)
            elif self.rbtn_tracker_plex.get_active():
                self.txt_plex_host.set_sensitive(True)
                self.txt_plex_port.set_sensitive(True)
                self.chk_tracker_plex_obey_wait.set_sensitive(True)
                self.txt_process.set_sensitive(False)
            self.spin_tracker_update_wait.set_sensitive(True)
        else:
            self.txt_process.set_sensitive(False)
            self.spin_tracker_update_wait.set_sensitive(False)
            self.txt_plex_host.set_sensitive(False)
            self.txt_plex_port.set_sensitive(False)
            self.chk_tracker_plex_obey_wait.set_sensitive(False)

    def _add_dirs(self, paths):
        if isinstance(paths, str):
            paths = [paths]
        for path in paths:
            row = Gtk.ListBoxRow()
            row.data = path
            row.add(Gtk.Label(path))
            self.lst_searchdirs.add(row)
        self.lst_searchdirs.show_all()

    def __do_dir_del(self, widget):
        row = self.lst_searchdirs.get_selected_row()
        if row:
            self.lst_searchdirs.remove(row)

    def __do_browse(self, widget, title, callback, dironly=False):
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
            callback(browsew.get_filename())
        browsew.destroy()

    def __do_apply(self, widget):
        self.save_config()
        self.destroy()

    def __do_close(self, widget):
        self.destroy()


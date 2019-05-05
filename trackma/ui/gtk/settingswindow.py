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
from gi.repository import Gtk, Gdk, GObject, Pango
from trackma.ui.gtk import gtk_dir
from trackma.ui.gtk.statusicon import TrackmaStatusIcon
from trackma.ui.gtk.gi_composites import GtkTemplate
from trackma import utils


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


@GtkTemplate(ui=os.path.join(gtk_dir, 'data/settingswindow.ui'))
class SettingsWindow(Gtk.Window):

    __gtype_name__ = 'SettingsWindow'

    btn_save = GtkTemplate.Child()
    switch_tracker = GtkTemplate.Child()

    radio_tracker_local = GtkTemplate.Child()
    entry_player_process = GtkTemplate.Child()
    btn_file_chooser_executable = GtkTemplate.Child()
    listbox_directories = GtkTemplate.Child()
    btn_add_directory = GtkTemplate.Child()
    checkbox_library_startup = GtkTemplate.Child()
    checkbox_library_entire_list = GtkTemplate.Child()
    checkbox_library_full_path = GtkTemplate.Child()

    radio_tracker_plex = GtkTemplate.Child()
    entry_plex_host = GtkTemplate.Child()
    spin_plex_port = GtkTemplate.Child()
    entry_plex_username = GtkTemplate.Child()
    entry_plex_password = GtkTemplate.Child()
    checkbox_plex_obey_wait = GtkTemplate.Child()
    spin_tracker_update_wait = GtkTemplate.Child()

    checkbox_tracker_update_close = GtkTemplate.Child()
    checkbox_tracker_update_prompt = GtkTemplate.Child()
    checkbox_tracker_not_found_prompt = GtkTemplate.Child()

    radiobutton_download_days = GtkTemplate.Child()
    radiobutton_download_always = GtkTemplate.Child()
    radiobutton_download_off = GtkTemplate.Child()

    radiobutton_upload_minutes = GtkTemplate.Child()
    radiobutton_upload_size = GtkTemplate.Child()
    radiobutton_upload_always = GtkTemplate.Child()
    radiobutton_upload_off = GtkTemplate.Child()
    checkbox_upload_exit = GtkTemplate.Child()

    spinbutton_download_days = GtkTemplate.Child()
    spinbutton_upload_minutes = GtkTemplate.Child()
    spinbutton_upload_size = GtkTemplate.Child()

    checkbox_auto_status_change = GtkTemplate.Child()
    checkbox_auto_status_change_if_scored = GtkTemplate.Child()
    checkbox_auto_date_change = GtkTemplate.Child()

    checkbox_show_tray = GtkTemplate.Child()
    checkbox_close_to_tray = GtkTemplate.Child()
    checkbox_start_in_tray = GtkTemplate.Child()
    checkbox_tray_api_icon = GtkTemplate.Child()
    checkbox_remember_geometry = GtkTemplate.Child()
    checkbox_classic_progress = GtkTemplate.Child()

    colorbutton_rows_playing = GtkTemplate.Child()
    colorbutton_rows_queued = GtkTemplate.Child()
    colorbutton_rows_new_episode = GtkTemplate.Child()
    colorbutton_rows_is_airing = GtkTemplate.Child()
    colorbutton_rows_not_aired = GtkTemplate.Child()

    colorbutton_progress_bg = GtkTemplate.Child()
    colorbutton_progress_fg = GtkTemplate.Child()
    colorbutton_progress_sub_bg = GtkTemplate.Child()
    colorbutton_progress_sub_fg = GtkTemplate.Child()
    colorbutton_progress_complete = GtkTemplate.Child()

    def __init__(self, engine, config, configfile, transient_for=None):
        Gtk.Window.__init__(self, transient_for=transient_for)
        self.init_template()

        self.engine = engine
        self.config = config
        self.configfile = configfile

        self._color_buttons = {
            'is_playing':        self.colorbutton_rows_playing,
            'is_queued':         self.colorbutton_rows_queued,
            'new_episode':       self.colorbutton_rows_new_episode,
            'is_airing':         self.colorbutton_rows_is_airing,
            'not_aired':         self.colorbutton_rows_not_aired,
            'progress_bg':       self.colorbutton_progress_bg,
            'progress_fg':       self.colorbutton_progress_fg,
            'progress_sub_bg':   self.colorbutton_progress_sub_bg,
            'progress_sub_fg':   self.colorbutton_progress_sub_fg,
            'progress_complete': self.colorbutton_progress_complete
        }

        self.radiobutton_download_days.connect("toggled", self._button_toggled, self.spinbutton_download_days)
        self.radiobutton_upload_minutes.connect("toggled", self._button_toggled, self.spinbutton_upload_minutes)
        self.radiobutton_upload_size.connect("toggled", self._button_toggled, self.spinbutton_upload_size)
        self.checkbox_auto_status_change.connect("toggled", self._button_toggled, self.checkbox_auto_status_change_if_scored)
        self.checkbox_show_tray.connect("toggled", self._button_toggled, self.checkbox_close_to_tray)
        self.checkbox_show_tray.connect("toggled", self._button_toggled, self.checkbox_start_in_tray)
        self.checkbox_show_tray.connect("toggled", self._button_toggled, self.checkbox_tray_api_icon)

        self._load_config()

    def _load_config(self):
        """Engine Configuration"""
        self.switch_tracker.set_active(self.engine.get_config('tracker_enabled'))

        if self.engine.get_config('tracker_type') == 'local':
            self.radio_tracker_local.set_active(True)
        elif self.engine.get_config('tracker_type') == 'plex':
            self.radio_tracker_plex.set_active(True)

        self.entry_player_process.set_text(self.engine.get_config('tracker_process'))
        self.btn_file_chooser_executable.set_filename(self.engine.get_config('player'))
        self.checkbox_library_startup.set_active(self.engine.get_config('library_autoscan'))
        self.checkbox_library_entire_list.set_active(self.engine.get_config('scan_whole_list'))
        self.checkbox_library_full_path.set_active(self.engine.get_config('library_full_path'))
        self._load_directories(self.engine.get_config('searchdir'))

        self.entry_plex_host.set_text(self.engine.get_config('plex_host'))
        self.spin_plex_port.set_value(int(self.engine.get_config('plex_port')))
        self.entry_plex_username.set_text(self.engine.get_config('plex_user'))
        self.entry_plex_password.set_text(self.engine.get_config('plex_passwd'))
        self.checkbox_plex_obey_wait.set_active(self.engine.get_config('plex_obey_update_wait_s'))

        self.spin_tracker_update_wait.set_value(self.engine.get_config('tracker_update_wait_s'))
        self.checkbox_tracker_update_close.set_active(self.engine.get_config('tracker_update_close'))
        self.checkbox_tracker_update_prompt.set_active(self.engine.get_config('tracker_update_prompt'))
        self.checkbox_tracker_not_found_prompt.set_active(self.engine.get_config('tracker_not_found_prompt'))

        if self.engine.get_config('autoretrieve') == 'always':
            self.radiobutton_download_always.set_active(True)
        elif self.engine.get_config('autoretrieve') == 'days':
            self.radiobutton_download_days.set_active(True)
        else:
            self.radiobutton_download_off.set_active(True)

        if self.engine.get_config('autosend') == 'always':
            self.radiobutton_upload_always.set_active(True)
        elif self.engine.get_config('autosend') in ('minutes', 'hours'):
            self.radiobutton_upload_minutes.set_active(True)
        elif self.engine.get_config('autosend') == 'size':
            self.radiobutton_upload_size.set_active(True)
        else:
            self.radiobutton_upload_off.set_active(True)

        self.checkbox_upload_exit.set_active(self.engine.get_config('autosend_at_exit'))

        self.spinbutton_download_days.set_value(self.engine.get_config('autoretrieve_days'))
        self.spinbutton_upload_minutes.set_value(self.engine.get_config('autosend_minutes'))
        self.spinbutton_upload_size.set_value(self.engine.get_config('autosend_size'))

        self.checkbox_auto_status_change.set_active(self.engine.get_config('auto_status_change'))
        self.checkbox_auto_status_change_if_scored.set_active(self.engine.get_config('auto_status_change_if_scored'))
        self.checkbox_auto_date_change.set_active(self.engine.get_config('auto_date_change'))

        self.checkbox_show_tray.set_active(self.config['show_tray'])
        self.checkbox_close_to_tray.set_active(self.config['close_to_tray'])
        self.checkbox_start_in_tray.set_active(self.config['start_in_tray'])
        self.checkbox_tray_api_icon.set_active(self.config['tray_api_icon'])

        """GTK Interface configuration"""
        self.checkbox_remember_geometry.set_active(self.config['remember_geometry'])
        self.checkbox_classic_progress.set_active(not self.config['episodebar_style'])

        for color_key, color_button in self._color_buttons.items():
            color = getColor(self.config['colors'][color_key])
            color_button.set_color(color)

        self._set_tracker_radio_buttons()
        self._button_toggled(self.radiobutton_download_days, self.spinbutton_download_days)
        self._button_toggled(self.radiobutton_upload_minutes, self.spinbutton_upload_minutes)
        self._button_toggled(self.radiobutton_upload_size, self.spinbutton_upload_size)
        self._button_toggled(self.checkbox_auto_status_change, self.checkbox_auto_status_change_if_scored)
        self._button_toggled(self.checkbox_show_tray, self.checkbox_close_to_tray)
        self._button_toggled(self.checkbox_show_tray, self.checkbox_start_in_tray)
        self._button_toggled(self.checkbox_show_tray, self.checkbox_tray_api_icon)

        if not TrackmaStatusIcon.is_tray_available():
            self.checkbox_show_tray.set_label('Show tray icon (Not supported in this environment)')
            self.checkbox_show_tray.set_sensitive(False)
            self.checkbox_close_to_tray.set_sensitive(False)
            self.checkbox_start_in_tray.set_sensitive(False)
            self.checkbox_tray_api_icon.set_sensitive(False)

    def _button_toggled(self, widget, spin):
        spin.set_sensitive(widget.get_active())

    @GtkTemplate.Callback
    def _on_btn_save_clicked(self, btn):
        self.save_config()
        self.destroy()

    @GtkTemplate.Callback
    def _on_switch_tracker_state_set(self, switch, state):
        self.radio_tracker_local.set_sensitive(state)
        self.radio_tracker_plex.set_sensitive(state)

        if state:
            self._set_tracker_radio_buttons()
        else:
            self._enable_local(state)
            self._enable_plex(state)

        self.checkbox_tracker_update_close.set_sensitive(state)
        self.checkbox_tracker_update_prompt.set_sensitive(state)
        self.checkbox_tracker_not_found_prompt.set_sensitive(state)

    @GtkTemplate.Callback
    def _on_radio_tracker_local_toggled(self, radio_button):
        self._set_tracker_radio_buttons()

    @GtkTemplate.Callback
    def _on_radio_tracker_plex_toggled(self, radio_button):
        self._set_tracker_radio_buttons()

    def _set_tracker_radio_buttons(self):
        if self.radio_tracker_local.get_active():
            self._enable_local(True)
            self._enable_plex(False)
        else:
            self._enable_local(False)
            self._enable_plex(True)

    def _enable_local(self, enable):
        self.entry_player_process.set_sensitive(enable)
        self.btn_file_chooser_executable.set_sensitive(enable)
        self.checkbox_library_startup.set_sensitive(enable)
        self.checkbox_library_entire_list.set_sensitive(enable)
        self.checkbox_library_full_path.set_sensitive(enable)

    def _enable_plex(self, enable):
        self.entry_plex_host.set_sensitive(enable)
        self.spin_plex_port.set_sensitive(enable)
        self.entry_plex_username.set_sensitive(enable)
        self.entry_plex_password.set_sensitive(enable)
        self.checkbox_plex_obey_wait.set_sensitive(enable)

    def _load_directories(self, paths):
        if isinstance(paths, str):
            paths = [paths]

        for path in paths:
            self._add_row_listbox_directory(path)

    def _add_row_listbox_directory(self, path):
        row = DirectoryRow(path)
        self.listbox_directories.add(row)

    @GtkTemplate.Callback
    def _on_btn_add_directory_clicked(self, btn):
        chooser_dialog = Gtk.FileChooserDialog('Select a directory',
                                               self.get_parent_window(),
                                               Gtk.FileChooserAction.OPEN,
                                               (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                                Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        chooser_dialog.set_default_response(Gtk.ResponseType.OK)
        chooser_dialog.set_action(Gtk.FileChooserAction.SELECT_FOLDER)

        response = chooser_dialog.run()
        if response == Gtk.ResponseType.OK:
            self._add_row_listbox_directory(chooser_dialog.get_filename())
        chooser_dialog.destroy()

    def save_config(self):
        """Engine Configuration"""
        self.engine.set_config('player', self.btn_file_chooser_executable.get_filename() or '')
        self.engine.set_config('tracker_process', self.entry_player_process.get_text())
        self.engine.set_config('library_autoscan',
                               self.checkbox_library_startup.get_active())
        self.engine.set_config('scan_whole_list',
                               self.checkbox_library_entire_list.get_active())
        self.engine.set_config('library_full_path',
                               self.checkbox_library_full_path.get_active())
        self.engine.set_config('plex_host', self.entry_plex_host.get_text())
        self.engine.set_config('plex_port', str(int(self.spin_plex_port.get_value())))
        self.engine.set_config('plex_obey_update_wait_s', self.checkbox_plex_obey_wait.get_active())
        self.engine.set_config('plex_user', self.entry_plex_username.get_text())
        self.engine.set_config('plex_passwd', self.entry_plex_password.get_text())
        self.engine.set_config('tracker_enabled', self.switch_tracker.get_active())
        self.engine.set_config('autosend_at_exit', self.checkbox_upload_exit.get_active())
        self.engine.set_config('tracker_update_wait_s', self.spin_tracker_update_wait.get_value())
        self.engine.set_config('tracker_update_close', self.checkbox_tracker_update_close.get_active())
        self.engine.set_config('tracker_update_prompt', self.checkbox_tracker_update_prompt.get_active())
        self.engine.set_config('tracker_not_found_prompt', self.checkbox_tracker_not_found_prompt.get_active())

        self.engine.set_config('searchdir', [row.directory for row in self.listbox_directories.get_children()])

        # Tracker type
        if self.radio_tracker_local.get_active():
            self.engine.set_config('tracker_type', 'local')
        elif self.radio_tracker_plex.get_active():
            self.engine.set_config('tracker_type', 'plex')

        # Auto-retrieve
        if self.radiobutton_download_always.get_active():
            self.engine.set_config('autoretrieve', 'always')
        elif self.radiobutton_download_days.get_active():
            self.engine.set_config('autoretrieve', 'days')
        else:
            self.engine.set_config('autoretrieve', 'off')

        # Auto-send
        if self.radiobutton_upload_always.get_active():
            self.engine.set_config('autosend', 'always')
        elif self.radiobutton_upload_minutes.get_active():
            self.engine.set_config('autosend', 'minutes')
        elif self.radiobutton_upload_size.get_active():
            self.engine.set_config('autosend', 'size')
        else:
            self.engine.set_config('autosend', 'off')

        self.engine.set_config('autoretrieve_days', self.spinbutton_download_days.get_value_as_int())
        self.engine.set_config('autosend_minutes', self.spinbutton_upload_minutes.get_value_as_int())
        self.engine.set_config('autosend_size', self.spinbutton_upload_size.get_value_as_int())

        self.engine.set_config('auto_status_change', self.checkbox_auto_status_change.get_active())
        self.engine.set_config('auto_status_change_if_scored', self.checkbox_auto_status_change_if_scored.get_active())
        self.engine.set_config('auto_date_change', self.checkbox_auto_date_change.get_active())
        self.engine.save_config()

        """GTK Interface configuration"""
        self.config['show_tray'] = self.checkbox_show_tray.get_active()

        if self.checkbox_show_tray.get_active():
            self.config['close_to_tray'] = self.checkbox_close_to_tray.get_active()
            self.config['start_in_tray'] = self.checkbox_start_in_tray.get_active()
            self.config['tray_api_icon'] = self.checkbox_tray_api_icon.get_active()
        else:
            self.config['close_to_tray'] = False
            self.config['start_in_tray'] = False
            self.config['tray_api_icon'] = False

        self.config['remember_geometry'] = self.checkbox_remember_geometry.get_active()
        self.config['episodebar_style'] = int(not self.checkbox_classic_progress.get_active())

        """Update Colors"""
        self.config['colors'] = {key: reprColor(col.get_color()) for key, col in self._color_buttons.items()}

        utils.save_config(self.config, self.configfile)


class DirectoryRow(Gtk.ListBoxRow):
    def __init__(self, directory):
        Gtk.ListBoxRow.__init__(self)

        self.directory = directory

        label = Gtk.Label(directory)
        label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

        image_button = Gtk.Image.new_from_icon_name('window-close-symbolic', 1)
        button_remove = Gtk.Button()
        button_remove.set_image(image_button)
        button_remove.connect('clicked', self._on_button_remove_click)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        box.pack_start(label, False, False, 0)
        box.pack_end(button_remove, False, False, 0)

        self.set_activatable(False)
        self.set_margin_bottom(5)
        self.set_margin_left(16)
        self.set_margin_right(16)
        self.set_margin_top(5)

        self.add(box)
        self.show_all()

    def _on_button_remove_click(self, btn):
        self.destroy()

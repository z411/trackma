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

pyqt_version = 5

from PyQt5 import QtCore
from PyQt5.QtWidgets import (
    QDialog, QGridLayout, QListWidget, QListWidgetItem, QAbstractItemView,
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QCheckBox, QRadioButton,
    QSpinBox, QLineEdit, QLabel, QPushButton, QComboBox, QTabWidget, QSplitter,
    QFrame, QStackedWidget, QDialogButtonBox, QColorDialog, QFileDialog)

from trackma.ui.qt.delegates import ShowsTableDelegate
from trackma.ui.qt.themedcolorpicker import ThemedColorPicker
from trackma.ui.qt.util import getIcon, getColor, FilterBar

from trackma import utils

class SettingsDialog(QDialog):
    worker = None
    config = None
    configfile = None

    saved = QtCore.pyqtSignal()

    def __init__(self, parent, worker, config, configfile):
        QDialog.__init__(self, parent)

        self.worker = worker
        self.config = config
        self.configfile = configfile
        self.setStyleSheet("QGroupBox { font-weight: bold; } ")
        self.setWindowTitle('Settings')
        layout = QGridLayout()

        # Categories
        self.category_list = QListWidget()
        category_media = QListWidgetItem(getIcon('media-playback-start'), 'Media', self.category_list)
        category_sync = QListWidgetItem(getIcon('view-refresh'), 'Sync', self.category_list)
        category_ui = QListWidgetItem(getIcon('window-new'), 'User Interface', self.category_list)
        category_theme = QListWidgetItem(getIcon('applications-graphics'), 'Theme', self.category_list)
        self.category_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.category_list.setCurrentRow(0)
        self.category_list.setMaximumWidth(self.category_list.sizeHintForColumn(0) + 15)
        self.category_list.setFocus()
        self.category_list.currentItemChanged.connect(self.s_switch_page)

        # Media tab
        page_media = QWidget()
        page_media_layout = QVBoxLayout()
        page_media_layout.setAlignment(QtCore.Qt.AlignTop)

        # Group: Media settings
        g_media = QGroupBox('Media settings')
        g_media.setFlat(True)
        g_media_layout = QFormLayout()
        self.tracker_enabled = QCheckBox()
        self.tracker_enabled.toggled.connect(self.tracker_type_change)

        self.tracker_type = QComboBox()
        for (n, label) in utils.available_trackers:
            self.tracker_type.addItem(label, n)
        self.tracker_type.currentIndexChanged.connect(self.tracker_type_change)

        self.tracker_interval = QSpinBox()
        self.tracker_interval.setRange(5, 1000)
        self.tracker_interval.setMaximumWidth(60)
        self.tracker_process = QLineEdit()
        self.tracker_update_wait = QSpinBox()
        self.tracker_update_wait.setRange(0, 1000)
        self.tracker_update_wait.setMaximumWidth(60)
        self.tracker_update_close = QCheckBox()
        self.tracker_update_prompt = QCheckBox()
        self.tracker_not_found_prompt = QCheckBox()

        g_media_layout.addRow('Enable tracker', self.tracker_enabled)
        g_media_layout.addRow('Tracker type', self.tracker_type)
        g_media_layout.addRow('Tracker interval (seconds)', self.tracker_interval)
        g_media_layout.addRow('Process name (regex)', self.tracker_process)
        g_media_layout.addRow('Wait before updating (seconds)', self.tracker_update_wait)
        g_media_layout.addRow('Wait until the player is closed', self.tracker_update_close)
        g_media_layout.addRow('Ask before updating', self.tracker_update_prompt)
        g_media_layout.addRow('Ask to add new shows', self.tracker_not_found_prompt)

        g_media.setLayout(g_media_layout)

        # Group: Plex settings
        g_plex = QGroupBox('Plex Media Server')
        g_plex.setFlat(True)
        self.plex_host = QLineEdit()
        self.plex_port = QLineEdit()
        self.plex_user = QLineEdit()
        self.plex_passw = QLineEdit()
        self.plex_passw.setEchoMode(QLineEdit.Password)
        self.plex_obey_wait = QCheckBox()

        g_plex_layout = QGridLayout()
        g_plex_layout.addWidget(QLabel('Host and Port'),                   0, 0, 1, 1)
        g_plex_layout.addWidget(self.plex_host,                            0, 1, 1, 1)
        g_plex_layout.addWidget(self.plex_port,                            0, 2, 1, 2)
        g_plex_layout.addWidget(QLabel('Use "wait before updating" time'), 1, 0, 1, 1)
        g_plex_layout.addWidget(self.plex_obey_wait,                       1, 2, 1, 1)
        g_plex_layout.addWidget(QLabel('myPlex login (claimed server)'),   2, 0, 1, 1)
        g_plex_layout.addWidget(self.plex_user,                            2, 1, 1, 1)
        g_plex_layout.addWidget(self.plex_passw,                           2, 2, 1, 2)

        g_plex.setLayout(g_plex_layout)

        # Group: Library
        g_playnext = QGroupBox('Library')
        g_playnext.setFlat(True)
        self.player = QLineEdit()
        self.player_browse = QPushButton('Browse...')
        self.player_browse.clicked.connect(self.s_player_browse)
        lbl_searchdirs = QLabel('Media directories')
        lbl_searchdirs.setAlignment(QtCore.Qt.AlignTop)
        self.searchdirs = QListWidget()
        self.searchdirs_add = QPushButton('Add...')
        self.searchdirs_add.clicked.connect(self.s_searchdirs_add)
        self.searchdirs_remove = QPushButton('Remove')
        self.searchdirs_remove.clicked.connect(self.s_searchdirs_remove)
        self.searchdirs_buttons = QVBoxLayout()
        self.searchdirs_buttons.setAlignment(QtCore.Qt.AlignTop)
        self.searchdirs_buttons.addWidget(self.searchdirs_add)
        self.searchdirs_buttons.addWidget(self.searchdirs_remove)
        self.searchdirs_buttons.addWidget(QSplitter())
        self.library_autoscan = QCheckBox()
        self.scan_whole_list = QCheckBox()
        self.library_full_path = QCheckBox()


        g_playnext_layout = QGridLayout()
        g_playnext_layout.addWidget(QLabel('Player'),                    0, 0, 1, 1)
        g_playnext_layout.addWidget(self.player,                         0, 1, 1, 1)
        g_playnext_layout.addWidget(self.player_browse,                  0, 2, 1, 1)
        g_playnext_layout.addWidget(lbl_searchdirs,                      1, 0, 1, 1)
        g_playnext_layout.addWidget(self.searchdirs,                     1, 1, 1, 1)
        g_playnext_layout.addLayout(self.searchdirs_buttons,             1, 2, 1, 1)
        g_playnext_layout.addWidget(QLabel('Rescan Library at startup'), 2, 0, 1, 2)
        g_playnext_layout.addWidget(self.library_autoscan,               2, 2, 1, 1)
        g_playnext_layout.addWidget(QLabel('Scan through whole list'),   3, 0, 1, 2)
        g_playnext_layout.addWidget(self.scan_whole_list,                3, 2, 1, 1)
        g_playnext_layout.addWidget(QLabel('Take subdirectory name into account'), 4, 0, 1, 2)
        g_playnext_layout.addWidget(self.library_full_path,              4, 2, 1, 1)

        g_playnext.setLayout(g_playnext_layout)

        # Media form
        page_media_layout.addWidget(g_media)
        page_media_layout.addWidget(g_plex)
        page_media_layout.addWidget(g_playnext)
        page_media.setLayout(page_media_layout)

        # Sync tab
        page_sync = QWidget()
        page_sync_layout = QVBoxLayout()
        page_sync_layout.setAlignment(QtCore.Qt.AlignTop)

        # Group: Autoretrieve
        g_autoretrieve = QGroupBox('Autoretrieve')
        g_autoretrieve.setFlat(True)
        self.autoretrieve_off = QRadioButton('Disabled')
        self.autoretrieve_always = QRadioButton('Always at start')
        self.autoretrieve_days = QRadioButton('After n days')
        self.autoretrieve_days.toggled.connect(self.s_autoretrieve_days)
        self.autoretrieve_days_n = QSpinBox()
        self.autoretrieve_days_n.setRange(1, 100)
        g_autoretrieve_layout = QGridLayout()
        g_autoretrieve_layout.setColumnStretch(0, 1)
        g_autoretrieve_layout.addWidget(self.autoretrieve_off,    0, 0, 1, 1)
        g_autoretrieve_layout.addWidget(self.autoretrieve_always, 1, 0, 1, 1)
        g_autoretrieve_layout.addWidget(self.autoretrieve_days,   2, 0, 1, 1)
        g_autoretrieve_layout.addWidget(self.autoretrieve_days_n, 2, 1, 1, 1)
        g_autoretrieve.setLayout(g_autoretrieve_layout)

        # Group: Autosend
        g_autosend = QGroupBox('Autosend')
        g_autosend.setFlat(True)
        self.autosend_off = QRadioButton('Disabled')
        self.autosend_always = QRadioButton('Immediately after every change')
        self.autosend_minutes = QRadioButton('After n minutes')
        self.autosend_minutes.toggled.connect(self.s_autosend_minutes)
        self.autosend_minutes_n = QSpinBox()
        self.autosend_minutes_n.setRange(1, 1000)
        self.autosend_size = QRadioButton('After the queue reaches n items')
        self.autosend_size.toggled.connect(self.s_autosend_size)
        self.autosend_size_n = QSpinBox()
        self.autosend_size_n.setRange(2, 20)
        self.autosend_at_exit = QCheckBox('At exit')
        g_autosend_layout = QGridLayout()
        g_autosend_layout.setColumnStretch(0, 1)
        g_autosend_layout.addWidget(self.autosend_off,      0, 0, 1, 1)
        g_autosend_layout.addWidget(self.autosend_always,   1, 0, 1, 1)
        g_autosend_layout.addWidget(self.autosend_minutes,    2, 0, 1, 1)
        g_autosend_layout.addWidget(self.autosend_minutes_n,  2, 1, 1, 1)
        g_autosend_layout.addWidget(self.autosend_size,     3, 0, 1, 1)
        g_autosend_layout.addWidget(self.autosend_size_n,   3, 1, 1, 1)
        g_autosend_layout.addWidget(self.autosend_at_exit,  4, 0, 1, 1)
        g_autosend.setLayout(g_autosend_layout)

        # Group: Extra
        g_extra = QGroupBox('Additional options')
        g_extra.setFlat(True)
        self.auto_status_change = QCheckBox('Change status automatically')
        self.auto_status_change.toggled.connect(self.s_auto_status_change)
        self.auto_status_change_if_scored = QCheckBox('Change status automatically only if scored')
        self.auto_date_change = QCheckBox('Change start and finish dates automatically')
        g_extra_layout = QVBoxLayout()
        g_extra_layout.addWidget(self.auto_status_change)
        g_extra_layout.addWidget(self.auto_status_change_if_scored)
        g_extra_layout.addWidget(self.auto_date_change)
        g_extra.setLayout(g_extra_layout)

        # Sync layout
        page_sync_layout.addWidget(g_autoretrieve)
        page_sync_layout.addWidget(g_autosend)
        page_sync_layout.addWidget(g_extra)
        page_sync.setLayout(page_sync_layout)

        # UI tab
        page_ui = QWidget()
        page_ui_layout = QFormLayout()
        page_ui_layout.setAlignment(QtCore.Qt.AlignTop)

        # Group: Icon
        g_icon = QGroupBox('Notification Icon')
        g_icon.setFlat(True)
        self.tray_icon = QCheckBox('Show tray icon')
        self.tray_icon.toggled.connect(self.s_tray_icon)
        self.close_to_tray = QCheckBox('Close to tray')
        self.start_in_tray = QCheckBox('Start minimized to tray')
        self.tray_api_icon = QCheckBox('Use API icon as tray icon')
        self.notifications = QCheckBox('Show notification when tracker detects new media')
        g_icon_layout = QVBoxLayout()
        g_icon_layout.addWidget(self.tray_icon)
        g_icon_layout.addWidget(self.close_to_tray)
        g_icon_layout.addWidget(self.start_in_tray)
        g_icon_layout.addWidget(self.tray_api_icon)
        g_icon_layout.addWidget(self.notifications)
        g_icon.setLayout(g_icon_layout)

        # Group: Window
        g_window = QGroupBox('Window')
        g_window.setFlat(True)
        self.remember_geometry = QCheckBox('Remember window size and position')
        self.remember_columns = QCheckBox('Remember column layouts and widths')
        self.columns_per_api = QCheckBox('Use different visible columns per API')
        g_window_layout = QVBoxLayout()
        g_window_layout.addWidget(self.remember_geometry)
        g_window_layout.addWidget(self.remember_columns)
        g_window_layout.addWidget(self.columns_per_api)
        g_window.setLayout(g_window_layout)

        # Group: Lists
        g_lists = QGroupBox('Lists')
        g_lists.setFlat(True)
        self.filter_bar_position = QComboBox()
        filter_bar_positions = [(FilterBar.PositionHidden,     'Hidden'),
                                (FilterBar.PositionAboveLists, 'Above lists'),
                                (FilterBar.PositionBelowLists, 'Below lists')]
        for (n, label) in filter_bar_positions:
            self.filter_bar_position.addItem(label, n)
        self.inline_edit = QCheckBox('Enable in-line editing')
        g_lists_layout = QFormLayout()
        g_lists_layout.addRow('Filter bar position:', self.filter_bar_position)
        g_lists_layout.addRow(self.inline_edit)
        g_lists.setLayout(g_lists_layout)

        # UI layout
        page_ui_layout.addWidget(g_icon)
        page_ui_layout.addWidget(g_window)
        page_ui_layout.addWidget(g_lists)
        page_ui.setLayout(page_ui_layout)

        # Theming tab
        page_theme = QWidget()
        page_theme_layout = QFormLayout()
        page_theme_layout.setAlignment(QtCore.Qt.AlignTop)

        # Group: Episode Bar
        g_ep_bar = QGroupBox('Episode Bar')
        g_ep_bar.setFlat(True)
        self.ep_bar_style = QComboBox()
        ep_bar_styles = [(ShowsTableDelegate.BarStyleBasic,  'Basic'),
                         (ShowsTableDelegate.BarStyle04,     'Trackma'),
                         (ShowsTableDelegate.BarStyleHybrid, 'Hybrid')]
        for (n, label) in ep_bar_styles:
            self.ep_bar_style.addItem(label, n)
        self.ep_bar_style.currentIndexChanged.connect(self.s_ep_bar_style)
        self.ep_bar_text = QCheckBox('Show text label')
        g_ep_bar_layout = QFormLayout()
        g_ep_bar_layout.addRow('Style:', self.ep_bar_style)
        g_ep_bar_layout.addRow(self.ep_bar_text)
        g_ep_bar.setLayout(g_ep_bar_layout)

        # Group: Colour scheme
        g_scheme = QGroupBox('Color Scheme')
        g_scheme.setFlat(True)
        col_tabs = [('rows',     '&Row highlights'),
                    ('progress', '&Progress widget')]
        self.colors = {}
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
        self.color_buttons = []
        self.syscolor_buttons = []
        g_scheme_layout = QGridLayout()
        tw_scheme = QTabWidget()
        for (key, tab_title) in col_tabs:
            page = QFrame()
            page_layout = QGridLayout()
            col = 0
            # Generate widgets from the keys and values
            for (key, label) in self.colors[key]:
                self.color_buttons.append(QPushButton())
                # self.color_buttons[-1].setStyleSheet('background-color: ' + getColor(self.config['colors'][key]).name())
                self.color_buttons[-1].setFocusPolicy(QtCore.Qt.NoFocus)
                self.color_buttons[-1].clicked.connect(self.s_color_picker(key, False))
                self.syscolor_buttons.append(QPushButton('System Colors'))
                self.syscolor_buttons[-1].clicked.connect(self.s_color_picker(key, True))
                page_layout.addWidget(QLabel(label),             col, 0, 1, 1)
                page_layout.addWidget(self.color_buttons[-1],    col, 1, 1, 1)
                page_layout.addWidget(self.syscolor_buttons[-1], col, 2, 1, 1)
                col += 1
            page.setLayout(page_layout)
            tw_scheme.addTab(page, tab_title)
        g_scheme_layout.addWidget(tw_scheme)
        g_scheme.setLayout(g_scheme_layout)

        # UI layout
        page_theme_layout.addWidget(g_ep_bar)
        page_theme_layout.addWidget(g_scheme)
        page_theme.setLayout(page_theme_layout)

        # Content
        self.contents = QStackedWidget()
        self.contents.addWidget(page_media)
        self.contents.addWidget(page_sync)
        self.contents.addWidget(page_ui)
        self.contents.addWidget(page_theme)
        if pyqt_version is not 5:
            self.contents.layout().setMargin(0)

        # Bottom buttons
        bottombox = QDialogButtonBox(
            QDialogButtonBox.Ok
            | QDialogButtonBox.Apply
            | QDialogButtonBox.Cancel
        )
        bottombox.accepted.connect(self.s_save)
        bottombox.button(QDialogButtonBox.Apply).clicked.connect(self._save)
        bottombox.rejected.connect(self.reject)

        # Main layout finish
        layout.addWidget(self.category_list,  0, 0, 1, 1)
        layout.addWidget(self.contents,       0, 1, 1, 1)
        layout.addWidget(bottombox,           1, 0, 1, 2)
        layout.setColumnStretch(1, 1)

        self._load()
        self.update_colors()

        self.setLayout(layout)

    def _add_dir(self, path):
        self.searchdirs.addItem(path)

    def _load(self):
        engine = self.worker.engine
        tracker_type = self.tracker_type.findData(engine.get_config('tracker_type'))
        autoretrieve = engine.get_config('autoretrieve')
        autosend = engine.get_config('autosend')

        self.tracker_enabled.setChecked(engine.get_config('tracker_enabled'))
        self.tracker_type.setCurrentIndex(max(0, tracker_type))
        self.tracker_interval.setValue(engine.get_config('tracker_interval'))
        self.tracker_process.setText(engine.get_config('tracker_process'))
        self.tracker_update_wait.setValue(engine.get_config('tracker_update_wait_s'))
        self.tracker_update_close.setChecked(engine.get_config('tracker_update_close'))
        self.tracker_update_prompt.setChecked(engine.get_config('tracker_update_prompt'))
        self.tracker_not_found_prompt.setChecked(engine.get_config('tracker_not_found_prompt'))

        self.player.setText(engine.get_config('player'))
        self.library_autoscan.setChecked(engine.get_config('library_autoscan'))
        self.scan_whole_list.setChecked(engine.get_config('scan_whole_list'))
        self.library_full_path.setChecked(engine.get_config('library_full_path'))
        self.plex_host.setText(engine.get_config('plex_host'))
        self.plex_port.setText(engine.get_config('plex_port'))
        self.plex_obey_wait.setChecked(engine.get_config('plex_obey_update_wait_s'))
        self.plex_user.setText(engine.get_config('plex_user'))
        self.plex_passw.setText(engine.get_config('plex_passwd'))

        for path in engine.get_config('searchdir'):
            self._add_dir(path)

        if autoretrieve == 'always':
            self.autoretrieve_always.setChecked(True)
        elif autoretrieve == 'days':
            self.autoretrieve_days.setChecked(True)
        else:
            self.autoretrieve_off.setChecked(True)

        self.autoretrieve_days_n.setValue(engine.get_config('autoretrieve_days'))

        if autosend == 'always':
            self.autosend_always.setChecked(True)
        elif autosend in ('minutes', 'hours'):
            self.autosend_minutes.setChecked(True)
        elif autosend == 'size':
            self.autosend_size.setChecked(True)
        else:
            self.autosend_off.setChecked(True)

        self.autosend_minutes_n.setValue(engine.get_config('autosend_minutes'))
        self.autosend_size_n.setValue(engine.get_config('autosend_size'))

        self.autosend_at_exit.setChecked(engine.get_config('autosend_at_exit'))
        self.auto_status_change.setChecked(engine.get_config('auto_status_change'))
        self.auto_status_change_if_scored.setChecked(engine.get_config('auto_status_change_if_scored'))
        self.auto_date_change.setChecked(engine.get_config('auto_date_change'))

        self.tray_icon.setChecked(self.config['show_tray'])
        self.close_to_tray.setChecked(self.config['close_to_tray'])
        self.start_in_tray.setChecked(self.config['start_in_tray'])
        self.tray_api_icon.setChecked(self.config['tray_api_icon'])
        self.notifications.setChecked(self.config['notifications'])
        self.remember_geometry.setChecked(self.config['remember_geometry'])
        self.remember_columns.setChecked(self.config['remember_columns'])
        self.columns_per_api.setChecked(self.config['columns_per_api'])
        self.filter_bar_position.setCurrentIndex(self.filter_bar_position.findData(self.config['filter_bar_position']))
        self.inline_edit.setChecked(self.config['inline_edit'])

        self.ep_bar_style.setCurrentIndex(self.ep_bar_style.findData(self.config['episodebar_style']))
        self.ep_bar_text.setChecked(self.config['episodebar_text'])

        self.autoretrieve_days_n.setEnabled(self.autoretrieve_days.isChecked())
        self.autosend_minutes_n.setEnabled(self.autosend_minutes.isChecked())
        self.autosend_size_n.setEnabled(self.autosend_size.isChecked())
        self.close_to_tray.setEnabled(self.tray_icon.isChecked())
        self.start_in_tray.setEnabled(self.tray_icon.isChecked())
        self.notifications.setEnabled(self.tray_icon.isChecked())

        self.color_values = self.config['colors'].copy()

        self.tracker_type_change(None)

    def _save(self):
        engine = self.worker.engine

        engine.set_config('tracker_enabled',       self.tracker_enabled.isChecked())
        engine.set_config('tracker_type',          self.tracker_type.itemData(self.tracker_type.currentIndex()))
        engine.set_config('tracker_interval',      self.tracker_interval.value())
        engine.set_config('tracker_process',       str(self.tracker_process.text()))
        engine.set_config('tracker_update_wait_s', self.tracker_update_wait.value())
        engine.set_config('tracker_update_close',  self.tracker_update_close.isChecked())
        engine.set_config('tracker_update_prompt', self.tracker_update_prompt.isChecked())
        engine.set_config('tracker_not_found_prompt', self.tracker_not_found_prompt.isChecked())

        engine.set_config('player',            self.player.text())
        engine.set_config('library_autoscan',  self.library_autoscan.isChecked())
        engine.set_config('scan_whole_list', self.scan_whole_list.isChecked())
        engine.set_config('library_full_path', self.library_full_path.isChecked())
        engine.set_config('plex_host',         self.plex_host.text())
        engine.set_config('plex_port',         self.plex_port.text())
        engine.set_config('plex_obey_update_wait_s', self.plex_obey_wait.isChecked())
        engine.set_config('plex_user',         self.plex_user.text())
        engine.set_config('plex_passwd',       self.plex_passw.text())

        engine.set_config('searchdir',         [self.searchdirs.item(i).text() for i in range(self.searchdirs.count())])

        if self.autoretrieve_always.isChecked():
            engine.set_config('autoretrieve', 'always')
        elif self.autoretrieve_days.isChecked():
            engine.set_config('autoretrieve', 'days')
        else:
            engine.set_config('autoretrieve', 'off')

        engine.set_config('autoretrieve_days',   self.autoretrieve_days_n.value())

        if self.autosend_always.isChecked():
            engine.set_config('autosend', 'always')
        elif self.autosend_minutes.isChecked():
            engine.set_config('autosend', 'minutes')
        elif self.autosend_size.isChecked():
            engine.set_config('autosend', 'size')
        else:
            engine.set_config('autosend', 'off')

        engine.set_config('autosend_minutes', self.autosend_minutes_n.value())
        engine.set_config('autosend_size',  self.autosend_size_n.value())

        engine.set_config('autosend_at_exit',   self.autosend_at_exit.isChecked())
        engine.set_config('auto_status_change', self.auto_status_change.isChecked())
        engine.set_config('auto_status_change_if_scored', self.auto_status_change_if_scored.isChecked())
        engine.set_config('auto_date_change',   self.auto_date_change.isChecked())

        engine.save_config()

        self.config['show_tray'] = self.tray_icon.isChecked()
        self.config['close_to_tray'] = self.close_to_tray.isChecked()
        self.config['start_in_tray'] = self.start_in_tray.isChecked()
        self.config['tray_api_icon'] = self.tray_api_icon.isChecked()
        self.config['notifications'] = self.notifications.isChecked()
        self.config['remember_geometry'] = self.remember_geometry.isChecked()
        self.config['remember_columns'] = self.remember_columns.isChecked()
        self.config['columns_per_api'] = self.columns_per_api.isChecked()
        self.config['filter_bar_position'] = self.filter_bar_position.itemData(self.filter_bar_position.currentIndex())
        self.config['inline_edit'] = self.inline_edit.isChecked()

        self.config['episodebar_style'] = self.ep_bar_style.itemData(self.ep_bar_style.currentIndex())
        self.config['episodebar_text'] = self.ep_bar_text.isChecked()

        self.config['colors'] = self.color_values

        utils.save_config(self.config, self.configfile)

        self.saved.emit()

    def s_save(self):
        self._save()
        self.accept()

    def tracker_type_change(self, checked):
        if self.tracker_enabled.isChecked():
            self.tracker_interval.setEnabled(True)
            self.tracker_update_wait.setEnabled(True)
            self.tracker_type.setEnabled(True)
            if self.tracker_type.itemData(self.tracker_type.currentIndex()) == 'plex':
                self.plex_host.setEnabled(True)
                self.plex_port.setEnabled(True)
                self.plex_obey_wait.setEnabled(True)
                self.plex_user.setEnabled(True)
                self.plex_passw.setEnabled(True)
                self.tracker_process.setEnabled(False)
            else:
                self.tracker_process.setEnabled(True)
                self.plex_host.setEnabled(False)
                self.plex_port.setEnabled(False)
                self.plex_user.setEnabled(False)
                self.plex_passw.setEnabled(False)
                self.plex_obey_wait.setEnabled(False)
        else:
            self.tracker_type.setEnabled(False)
            self.plex_host.setEnabled(False)
            self.plex_port.setEnabled(False)
            self.plex_user.setEnabled(False)
            self.plex_passw.setEnabled(False)
            self.plex_obey_wait.setEnabled(False)
            self.tracker_process.setEnabled(False)
            self.tracker_interval.setEnabled(False)
            self.tracker_update_wait.setEnabled(False)

    def s_autoretrieve_days(self, checked):
        self.autoretrieve_days_n.setEnabled(checked)

    def s_autosend_minutes(self, checked):
        self.autosend_minutes_n.setEnabled(checked)

    def s_autosend_size(self, checked):
        self.autosend_size_n.setEnabled(checked)

    def s_tray_icon(self, checked):
        self.close_to_tray.setEnabled(checked)
        self.start_in_tray.setEnabled(checked)
        self.tray_api_icon.setEnabled(checked)
        self.notifications.setEnabled(checked)

    def s_ep_bar_style(self, index):
        if self.ep_bar_style.itemData(index) == ShowsTableDelegate.BarStyle04:
            self.ep_bar_text.setEnabled(False)
        else:
            self.ep_bar_text.setEnabled(True)

    def s_auto_status_change(self, checked):
        self.auto_status_change_if_scored.setEnabled(checked)

    def s_player_browse(self):
        if pyqt_version is 5:
            self.player.setText(QFileDialog.getOpenFileName(caption='Choose player executable')[0])
        else:
            self.player.setText(QFileDialog.getOpenFileName(caption='Choose player executable'))

    def s_searchdirs_add(self):
        self._add_dir(QFileDialog.getExistingDirectory(caption='Choose media directory'))

    def s_searchdirs_remove(self):
        row = self.searchdirs.currentRow()
        if row != -1:
            self.searchdirs.takeItem(row)

    def s_switch_page(self, new, old):
        if not new:
            new = old

        self.contents.setCurrentIndex(self.category_list.row(new))

    def s_color_picker(self, key, system):
        return lambda: self.color_picker(key, system)

    def color_picker(self, key, system):
        if system is True:
            current = self.color_values[key]
            result = ThemedColorPicker.do()
            if result is not None and result is not current:
                self.color_values[key] = result
                self.update_colors()
        else:
            current = getColor(self.color_values[key])
            result = QColorDialog.getColor(current)
            if result.isValid() and result is not current:
                self.color_values[key] = str(result.name())
                self.update_colors()

    def update_colors(self):
        for ((key, label), color) in zip(self.colors['rows']+self.colors['progress'], self.color_buttons):
            color.setStyleSheet('background-color: ' + getColor(self.color_values[key]).name())

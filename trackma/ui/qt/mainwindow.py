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

import os
import datetime
import subprocess

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QFormLayout,
            QGridLayout, QHBoxLayout, QVBoxLayout,
            QAbstractItemView, QHeaderView, QListWidget,
            QListWidgetItem, QTabWidget, QTableWidget,
            QTableWidgetItem, QFrame, QScrollArea,
            QStackedWidget, QWidget, QCheckBox, QComboBox,
            QDoubleSpinBox, QGroupBox, QLineEdit,
            QPushButton, QRadioButton, QSpinBox,
            QStyleOptionButton, QToolButton, QProgressBar,
            QDialog, QColorDialog, QDialogButtonBox,
            QFileDialog, QInputDialog, QMessageBox,
            QAction, QActionGroup, QLabel, QMenu, QStyle,
            QSystemTrayIcon, QStyleOptionProgressBar
        )

from trackma.ui.qt.add import AddDialog
from trackma.ui.qt.accounts import AccountDialog
from trackma.ui.qt.details import DetailsDialog
from trackma.ui.qt.settings import SettingsDialog
from trackma.ui.qt.widgets import ShowsTableWidget, ShowItem, ShowItemNum, ShowItemDate, EpisodeBar
from trackma.ui.qt.workers import EngineWorker, ImageWorker
from trackma.ui.qt.util import getIcon, getColor, FilterBar

from trackma.accounts import AccountManager
from trackma import messenger
from trackma import utils


class MainWindow(QMainWindow):
    """
    Main GUI class

    """
    debug = False
    config = None
    tray = None
    accountman = None
    accountman_widget = None
    worker = None
    image_worker = None
    started = False
    selected_show_id = None
    show_lists = None
    finish = False
    was_maximized = False

    def __init__(self, debug=False):
        QMainWindow.__init__(self, None)
        self.debug = debug

        # Load QT specific configuration
        self.configfile = utils.get_root_filename('ui-qt.json')
        self.config = utils.parse_config(self.configfile, utils.qt_defaults)
        self.api_configfile = utils.get_root_filename('ui-qt.0.json')
        self.api_config = {}

        # Build UI
        QApplication.setWindowIcon(QtGui.QIcon(utils.datadir + '/data/icon.png'))
        self.setWindowTitle('Trackma-qt')

        self.accountman = AccountManager()

        # Go directly into the application if a default account is set
        # Open the selection dialog otherwise
        default = self.accountman.get_default()
        if default:
            self.start(default)
        else:
            self.accountman_create()
            self.accountman_widget.show()

    def accountman_create(self):
        self.accountman_widget = AccountDialog(None, self.accountman)
        self.accountman_widget.selected.connect(self.accountman_selected)

    def accountman_selected(self, account_num, remember):
        account = self.accountman.get_account(account_num)

        if remember:
            self.accountman.set_default(account_num)
        else:
            self.accountman.set_default(None)

        if self.started:
            self.reload(account)
        else:
            self.start(account)

    def start(self, account):
        """
        Start engine and everything

        """
        # Workers
        self.worker = EngineWorker(account)
        self.account = account

        # Timers
        self.image_timer = QtCore.QTimer()
        self.image_timer.setInterval(500)
        self.image_timer.setSingleShot(True)
        self.image_timer.timeout.connect(self.s_download_image)

        self.busy_timer = QtCore.QTimer()
        self.busy_timer.setInterval(100)
        self.busy_timer.setSingleShot(True)
        self.busy_timer.timeout.connect(self.s_busy)

        # Build menus
        action_play_next = QAction(getIcon('media-playback-start'), 'Play &Next', self)
        action_play_next.setStatusTip('Play the next unwatched episode.')
        action_play_next.setShortcut('Ctrl+N')
        action_play_next.triggered.connect(lambda: self.s_play(True))
        action_play_dialog = QAction('Play Episode...', self)
        action_play_dialog.setStatusTip('Select an episode to play.')
        action_play_dialog.triggered.connect(self.s_play_number)
        action_details = QAction('Show &details...', self)
        action_details.setStatusTip('Show detailed information about the selected show.')
        action_details.triggered.connect(self.s_show_details)
        action_altname = QAction('Change &alternate name...', self)
        action_altname.setStatusTip('Set an alternate title for the tracker.')
        action_altname.triggered.connect(self.s_altname)
        action_play_random = QAction('Play &random show', self)
        action_play_random.setStatusTip('Pick a random show with a new episode and play it.')
        action_play_random.setShortcut('Ctrl+R')
        action_play_random.triggered.connect(self.s_play_random)
        action_add = QAction(getIcon('edit-find'), 'Search/Add from Remote', self)
        action_add.setShortcut('Ctrl+A')
        action_add.triggered.connect(self.s_add)
        action_delete = QAction(getIcon('edit-delete'), '&Delete', self)
        action_delete.setStatusTip('Remove this show from your list.')
        action_delete.triggered.connect(self.s_delete)
        action_quit = QAction(getIcon('application-exit'), '&Quit', self)
        action_quit.setShortcut('Ctrl+Q')
        action_quit.setStatusTip('Exit Trackma.')
        action_quit.triggered.connect(self._exit)

        action_sync = QAction('&Sync', self)
        action_sync.setStatusTip('Send changes and then retrieve remote list')
        action_sync.setShortcut('Ctrl+S')
        action_sync.triggered.connect(lambda: self.s_send(True))
        action_send = QAction('S&end changes', self)
        action_send.setShortcut('Ctrl+E')
        action_send.setStatusTip('Upload any changes made to the list immediately.')
        action_send.triggered.connect(self.s_send)
        action_retrieve = QAction('Re&download list', self)
        action_retrieve.setShortcut('Ctrl+D')
        action_retrieve.setStatusTip('Discard any changes made to the list and re-download it.')
        action_retrieve.triggered.connect(self.s_retrieve)
        action_scan_library = QAction('Rescan &Library', self)
        action_scan_library.triggered.connect(self.s_scan_library)
        action_open_folder = QAction('Open containing folder', self)
        action_open_folder.triggered.connect(self.s_open_folder)

        action_reload = QAction('Switch &Account', self)
        action_reload.setStatusTip('Switch to a different account.')
        action_reload.triggered.connect(self.s_switch_account)
        action_settings = QAction('&Settings...', self)
        action_settings.triggered.connect(self.s_settings)

        action_about = QAction(getIcon('help-about'), 'About...', self)
        action_about.triggered.connect(self.s_about)
        action_about_qt = QAction('About Qt...', self)
        action_about_qt.triggered.connect(self.s_about_qt)

        menubar = self.menuBar()
        self.menu_show = menubar.addMenu('&Show')
        self.menu_show.addAction(action_play_next)
        self.menu_show.addAction(action_play_dialog)
        self.menu_show.addAction(action_details)
        self.menu_show.addAction(action_altname)
        self.menu_show.addSeparator()
        self.menu_show.addAction(action_play_random)
        self.menu_show.addSeparator()
        self.menu_show.addAction(action_add)
        self.menu_show.addAction(action_delete)
        self.menu_show.addSeparator()
        self.menu_show.addAction(action_quit)

        self.menu_play = QMenu('Play')

        # Context menu for right click on list item
        self.menu_show_context = QMenu()
        #self.menu_show_context.addAction(action_play_next)
        #self.menu_show_context.addAction(action_play_dialog)
        self.menu_show_context.addMenu(self.menu_play)
        self.menu_show_context.addAction(action_details)
        self.menu_show_context.addAction(action_open_folder)
        self.menu_show_context.addAction(action_altname)
        self.menu_show_context.addSeparator()
        self.menu_show_context.addAction(action_delete)

        # Context menu for right click on list header
        self.menu_columns = QMenu()
        self.available_columns = ['ID', 'Title', 'Progress', 'Score',
                'Percent', 'Next Episode', 'Start date', 'End date',
                'My start', 'My finish', 'Tags']
        self.column_keys = {'id': 0,
                            'title': 1,
                            'progress': 2,
                            'score': 3,
                            'percent': 4,
                            'next_ep': 5,
                            'date_start': 6,
                            'date_end': 7,
                            'my_start': 8,
                            'my_end': 9,
                            'tag': 10}

        self.menu_columns_group = QActionGroup(self, exclusive=False)
        self.menu_columns_group.triggered.connect(self.s_toggle_column)

        self.api_configfile = utils.get_root_filename('ui-qt.%s.json' % account['api'])
        self.api_config = utils.parse_config(self.api_configfile, utils.qt_per_api_defaults)
        if self.config['columns_per_api']:
            self.config['visible_columns'] = self.api_config['visible_columns']
            self.config['columns_state'] = self.api_config['columns_state']

        for column_name in self.available_columns:
            action = QAction(column_name, self, checkable=True)
            if column_name in self.config['visible_columns']:
                action.setChecked(True)

            self.menu_columns_group.addAction(action)
            self.menu_columns.addAction(action)

        # Make icons for viewed episodes
        rect = QtCore.QSize(16,16)
        buffer = QtGui.QPixmap(rect)
        ep_icon_states = {'all': QStyle.State_On,
                          'part': QStyle.State_NoChange,
                          'none': QStyle.State_Off}
        self.ep_icons = {}
        for key, state in ep_icon_states.items():
            buffer.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(buffer)
            opt = QStyleOptionButton()
            opt.state = state
            self.style().drawPrimitive(QStyle.PE_IndicatorMenuCheckMark, opt, painter)
            self.ep_icons[key] = QtGui.QIcon(buffer)
            painter.end()

        menu_list = menubar.addMenu('&List')
        menu_list.addAction(action_sync)
        menu_list.addSeparator()
        menu_list.addAction(action_send)
        menu_list.addAction(action_retrieve)
        menu_list.addSeparator()
        menu_list.addAction(action_scan_library)
        self.menu_mediatype = menubar.addMenu('&Mediatype')
        self.mediatype_actiongroup = QActionGroup(self, exclusive=True)
        self.mediatype_actiongroup.triggered.connect(self.s_mediatype)
        menu_options = menubar.addMenu('&Options')
        menu_options.addAction(action_reload)
        menu_options.addSeparator()
        menu_options.addAction(action_settings)
        menu_help = menubar.addMenu('&Help')
        menu_help.addAction(action_about)
        menu_help.addAction(action_about_qt)

        # Build layout
        main_layout = QVBoxLayout()
        top_hbox = QHBoxLayout()
        main_hbox = QHBoxLayout()
        self.list_box = QVBoxLayout()
        filter_bar_box_layout = QHBoxLayout()
        self.filter_bar_box = QWidget()
        left_box = QFormLayout()
        small_btns_hbox = QHBoxLayout()

        self.show_title = QLabel('Trackma-qt')
        show_title_font = QtGui.QFont()
        show_title_font.setBold(True)
        show_title_font.setPointSize(12)
        self.show_title.setFont(show_title_font)

        self.api_icon = QLabel('icon')
        self.api_user = QLabel('user')

        top_hbox.addWidget(self.show_title, 1)
        top_hbox.addWidget(self.api_icon)
        top_hbox.addWidget(self.api_user)

        self.notebook = QTabWidget()
        self.notebook.currentChanged.connect(self.s_tab_changed)
        self.show_filter = QLineEdit()
        self.show_filter.textChanged.connect(self.s_filter_changed)
        filter_tooltip = (
            "General Search: All fields (columns) of each show will be matched against the search term."
            "\nAdvanced Searching: A field can be specified by using its key followed by a colon"
            " e.g. 'title:My_Show date_start:2016'."
            "\n  Any field may be specified multiple times to match terms in any order e.g. 'tag:Battle+Shounen tag:Ecchi'. "
            "\n  + and _ are replaced with spaces when searching specific fields."
            "\n  If colon is used after something that is not a column key, it will treat it as a general term."
            "\n  ALL terms not attached to a field will be combined into a single general search term"
            "\n         - 'My date_end:2016 Show' will match shows that have 'My Show' in any field and 2016 in the End Date field."
            "\n  Available field keys are: "
        )
        colkeys = ', '.join(sorted(self.column_keys.keys()))
        self.show_filter.setToolTip(filter_tooltip + colkeys + '.')
        self.show_filter_invert = QCheckBox()
        self.show_filter_invert.stateChanged.connect(self.s_filter_changed)
        self.show_filter_casesens = QCheckBox()
        self.show_filter_casesens.stateChanged.connect(self.s_filter_changed)

        if self.config['remember_geometry']:
            self.resize(self.config['last_width'], self.config['last_height'])
            self.move(self.config['last_x'], self.config['last_y'])
        else:
            self.resize(740, 480)

        self.show_image = QLabel('Trackma-qt')
        self.show_image.setFixedHeight(149)
        self.show_image.setMinimumWidth(100)
        self.show_image.setAlignment(QtCore.Qt.AlignCenter)
        self.show_image.setStyleSheet("border: 1px solid #777;background-color:#999;text-align:center")
        show_progress_label = QLabel('Progress:')
        self.show_progress = QSpinBox()
        self.show_progress_bar = QProgressBar()
        self.show_progress_btn = QPushButton('Update')
        self.show_progress_btn.setToolTip('Set number of episodes watched to the value entered above')
        self.show_progress_btn.clicked.connect(self.s_set_episode)
        self.show_play_btn = QToolButton()
        self.show_play_btn.setIcon(getIcon('media-playback-start'))
        self.show_play_btn.setToolTip('Play the next unwatched episode\nHold to play other episodes')
        self.show_play_btn.clicked.connect(lambda: self.s_play(True))
        self.show_play_btn.setMenu(self.menu_play)
        self.show_inc_btn = QToolButton()
        self.show_inc_btn.setIcon(getIcon('list-add'))
        self.show_inc_btn.setShortcut('Ctrl+Right')
        self.show_inc_btn.setToolTip('Increment number of episodes watched')
        self.show_inc_btn.clicked.connect(self.s_plus_episode)
        self.show_dec_btn = QToolButton()
        self.show_dec_btn.setIcon(getIcon('list-remove'))
        self.show_dec_btn.clicked.connect(self.s_rem_episode)
        self.show_dec_btn.setShortcut('Ctrl+Left')
        self.show_dec_btn.setToolTip('Decrement number of episodes watched')
        show_score_label = QLabel('Score:')
        self.show_score = QDoubleSpinBox()
        self.show_score_btn = QPushButton('Set')
        self.show_score_btn.setToolTip('Set score to the value entered above')
        self.show_score_btn.clicked.connect(self.s_set_score)
        self.show_tags_btn = QPushButton('Edit Tags...')
        self.show_tags_btn.setToolTip('Open a dialog to edit your tags for this show')
        self.show_tags_btn.clicked.connect(self.s_set_tags)
        self.show_status = QComboBox()
        self.show_status.setToolTip('Change your watching status of this show')
        self.show_status.currentIndexChanged.connect(self.s_set_status)

        small_btns_hbox.addWidget(self.show_dec_btn)
        small_btns_hbox.addWidget(self.show_play_btn)
        small_btns_hbox.addWidget(self.show_inc_btn)
        small_btns_hbox.setAlignment(QtCore.Qt.AlignCenter)

        left_box.addRow(self.show_image)
        left_box.addRow(self.show_progress_bar)
        left_box.addRow(small_btns_hbox)
        left_box.addRow(show_progress_label)
        left_box.addRow(self.show_progress, self.show_progress_btn)
        left_box.addRow(show_score_label)
        left_box.addRow(self.show_score, self.show_score_btn)
        left_box.addRow(self.show_status)
        left_box.addRow(self.show_tags_btn)

        filter_bar_box_layout.addWidget(QLabel('Filter:'))
        filter_bar_box_layout.addWidget(self.show_filter)
        filter_bar_box_layout.addWidget(QLabel('Invert'))
        filter_bar_box_layout.addWidget(self.show_filter_invert)
        filter_bar_box_layout.addWidget(QLabel('Case Sensitive'))
        filter_bar_box_layout.addWidget(self.show_filter_casesens)
        self.filter_bar_box.setLayout(filter_bar_box_layout)

        if self.config['filter_bar_position'] is FilterBar.PositionHidden:
            self.list_box.addWidget(self.notebook)
            self.filter_bar_box.hide()
        elif self.config['filter_bar_position'] is FilterBar.PositionAboveLists:
            self.list_box.addWidget(self.filter_bar_box)
            self.list_box.addWidget(self.notebook)
        elif self.config['filter_bar_position'] is FilterBar.PositionBelowLists:
            self.list_box.addWidget(self.notebook)
            self.list_box.addWidget(self.filter_bar_box)

        main_hbox.addLayout(left_box)
        main_hbox.addLayout(self.list_box, 1)

        main_layout.addLayout(top_hbox)
        main_layout.addLayout(main_hbox)

        self.main_widget = QWidget(self)
        self.main_widget.setLayout(main_layout)
        self.setCentralWidget(self.main_widget)

        # Statusbar
        self.status_text = QLabel('Trackma-qt')
        self.tracker_text = QLabel('Tracker: N/A')
        self.tracker_text.setMinimumWidth(120)
        self.queue_text = QLabel('Unsynced items: N/A')
        self.statusBar().addWidget(self.status_text, 1)
        self.statusBar().addPermanentWidget(self.tracker_text)
        self.statusBar().addPermanentWidget(self.queue_text)

        # Tray icon
        tray_menu = QMenu(self)
        action_hide = QAction('Show/Hide', self)
        action_hide.triggered.connect(self.s_hide)
        tray_menu.addAction(action_hide)
        tray_menu.addAction(action_quit)

        self.tray = QSystemTrayIcon(self.windowIcon())
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self.s_tray_clicked)
        self._tray()

        # Connect worker signals
        self.worker.changed_status.connect(self.ws_changed_status)
        self.worker.raised_error.connect(self.error)
        self.worker.raised_fatal.connect(self.fatal)
        self.worker.changed_show.connect(self.ws_changed_show)
        self.worker.changed_list.connect(self.ws_changed_list)
        self.worker.changed_queue.connect(self.ws_changed_queue)
        self.worker.tracker_state.connect(self.ws_tracker_state)
        self.worker.playing_show.connect(self.ws_changed_show)
        self.worker.prompt_for_update.connect(self.ws_prompt_update)
        self.worker.prompt_for_add.connect(self.ws_prompt_add)

        # Show main window
        if not (self.config['show_tray'] and self.config['start_in_tray']):
            self.show()

        # Start loading engine
        self.started = True
        self._busy(False)
        self.worker_call('start', self.r_engine_loaded)

    def reload(self, account=None, mediatype=None):
        if account:
            self.account = account

        self.api_configfile = utils.get_root_filename('ui-qt.%s.json' % self.account['api'])
        self.api_config = utils.parse_config(self.api_configfile, utils.qt_per_api_defaults)
        if self.config['columns_per_api']:
            self.config['visible_columns'] = self.api_config['visible_columns']
        self.menu_columns_group.setEnabled(False)
        for action in self.menu_columns_group.actions():
            action.setChecked(action.text() in self.config['visible_columns'])
        self.menu_columns_group.setEnabled(True)

        self.show()
        self._busy(False)
        self.worker_call('reload', self.r_engine_loaded, account, mediatype)

    def closeEvent(self, event):
        if not self.started or not self.worker.engine.loaded:
            event.accept()
            if pyqt_version is 5 and self.finish:
                QApplication.instance().quit()
        elif self.config['show_tray'] and self.config['close_to_tray']:
            event.ignore()
            self.s_hide()
        else:
            event.ignore()
            self._exit()

    def status(self, message):
        self.status_text.setText(message)
        print(message)

    def error(self, msg):
        self.status('Error: {}'.format(msg))
        QMessageBox.critical(self, 'Error', str(msg), QMessageBox.Ok)

    def fatal(self, msg):
        QMessageBox.critical(self, 'Fatal Error', "Fatal Error! Reason:\n\n{0}".format(msg), QMessageBox.Ok)
        self.accountman.set_default(None)
        self._busy()
        self.finish = False
        self.worker_call('unload', self.r_engine_unloaded)

    def worker_call(self, function, ret_function, *args, **kwargs):
        # Run worker in a thread
        self.worker.set_function(function, ret_function, *args, **kwargs)
        self.worker.start()

    ### GUI Functions
    def _exit(self):
        self._busy()
        if self.config['remember_geometry']:
            self._store_geometry()
        if self.config['remember_columns']:
            self._store_columnstate()
        self.finish = True
        self.worker_call('unload', self.r_engine_unloaded)

    def _store_geometry(self):
        self.config['last_x'] = self.x()
        self.config['last_y'] = self.y()
        self.config['last_width'] = self.width()
        self.config['last_height'] = self.height()
        utils.save_config(self.config, self.configfile)

    def _store_columnstate(self):
        self.config['columns_state'] = dict()
        for status in self.statuses_nums:
            state = self.show_lists[status].horizontalHeader().saveState()
            self.config['columns_state'][status] = base64.b64encode(state).decode('ascii')
        if self.config['columns_per_api']:
            self.api_config['columns_state'] = self.config['columns_state']
            utils.save_config(self.api_config, self.api_configfile)
        else:
            utils.save_config(self.config, self.configfile)

    def _enable_widgets(self, enable):
        self.notebook.setEnabled(enable)
        self.menuBar().setEnabled(enable)

        if self.selected_show_id:
            self.show_progress_btn.setEnabled(enable)
            self.show_score_btn.setEnabled(enable)
            if 'can_tag' in self.mediainfo and self.mediainfo.get('can_tag'):
                self.show_tags_btn.setEnabled(enable)
            else:
                self.show_tags_btn.setEnabled(False)
            self.show_play_btn.setEnabled(enable)
            self.show_inc_btn.setEnabled(enable)
            self.show_dec_btn.setEnabled(enable)
            self.show_status.setEnabled(enable)

    def _update_queue_counter(self, queue):
        self.queue_text.setText("Unsynced items: %d" % queue)

    def _update_tracker_info(self, state, timer):
        if state == utils.TRACKER_NOVIDEO:
            st = 'Listen'
        elif state == utils.TRACKER_PLAYING:
            (m, s) = divmod(timer, 60)
            st = "+{0}:{1:02d}".format(m, s)
        elif state == utils.TRACKER_UNRECOGNIZED:
            st = 'Unrecognized'
        elif state == utils.TRACKER_NOT_FOUND:
            st = 'Not found'
        elif state == utils.TRACKER_IGNORED:
            st = 'Ignored'
        else:
            st = '???'

        self.tracker_text.setText("Tracker: {}".format(st))

    def _update_config(self):
        self._tray()
        self._filter_bar()
        # TODO: Reload listviews?

    def _tray(self):
        if self.tray.isVisible() and not self.config['show_tray']:
            self.tray.hide()
        elif not self.tray.isVisible() and self.config['show_tray']:
            self.tray.show()
        if self.tray.isVisible():
            if self.config['tray_api_icon']:
                self.tray.setIcon( QIcon( utils.available_libs[self.account['api']][1] ) )
            else:
                self.tray.setIcon( self.windowIcon() )

    def _filter_bar(self):
        self.list_box.removeWidget(self.filter_bar_box)
        self.list_box.removeWidget(self.notebook)
        self.filter_bar_box.show()
        if self.config['filter_bar_position'] is FilterBar.PositionHidden:
            self.list_box.addWidget(self.notebook)
            self.filter_bar_box.hide()
        elif self.config['filter_bar_position'] is FilterBar.PositionAboveLists:
            self.list_box.addWidget(self.filter_bar_box)
            self.list_box.addWidget(self.notebook)
        elif self.config['filter_bar_position'] is FilterBar.PositionBelowLists:
            self.list_box.addWidget(self.notebook)
            self.list_box.addWidget(self.filter_bar_box)

    def _busy(self, wait=False):
        if wait:
            self.busy_timer.start()
        else:
            self._enable_widgets(False)

    def _unbusy(self):
        if self.busy_timer.isActive():
            self.busy_timer.stop()
        else:
            self._enable_widgets(True)

    def _rebuild_lists(self, showlist, altnames, library):
        """
        Using a full showlist, rebuilds every QTreeView

        """

        # Set allowed ranges (this will be reported by the engine later)
        decimal_places = 0
        if isinstance(self.mediainfo['score_step'], float):
            decimal_places = len(str(self.mediainfo['score_step']).split('.')[1])

        self.show_score.setRange(0, self.mediainfo['score_max'])
        self.show_score.setDecimals(decimal_places)
        self.show_score.setSingleStep(self.mediainfo['score_step'])

        # Rebuild each available list
        statuses_nums = self.worker.engine.mediainfo['statuses']
        filtered_list = dict()
        for status in statuses_nums:
            filtered_list[status] = list()

        for show in showlist:
            filtered_list[show['my_status']].append(show)

        for status in statuses_nums:
            self._rebuild_list(status, filtered_list[status], altnames, library)

        self.s_filter_changed()

    def _rebuild_list(self, status, showlist=None, altnames=None, library=None):
        if not showlist:
            showlist = self.worker.engine.filter_list(status)
        if not altnames:
            altnames = self.worker.engine.altnames()
        if not library:
            library = self.worker.engine.library()

        widget = self.show_lists[status]

        widget.clear()
        widget.setSortingEnabled(False)
        widget.setRowCount(len(showlist))
        widget.setColumnCount(len(self.available_columns))
        widget.setHorizontalHeaderLabels(self.available_columns)

        # Hide invisible columns
        for i, column in enumerate(self.available_columns):
            if column not in self.config['visible_columns']:
                widget.setColumnHidden(i, True)

        if pyqt_version is 5:
            widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
            widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        else:
            widget.horizontalHeader().setResizeMode(1, QHeaderView.Stretch)
            widget.horizontalHeader().setResizeMode(2, QHeaderView.Fixed)
            widget.horizontalHeader().setResizeMode(3, QHeaderView.Fixed)

        widget.horizontalHeader().resizeSection(2, 70)
        widget.horizontalHeader().resizeSection(3, 55)
        widget.horizontalHeader().resizeSection(4, 100)

        if self.config['remember_columns'] and str(status) in self.config['columns_state']:
            state = QtCore.QByteArray(base64.b64decode(self.config['columns_state'][str(status)]))
            widget.horizontalHeader().restoreState(state)

        i = 0

        for show in showlist:
            self._update_row( widget, i, show, altnames.get(show['id']), library.get(show['id']) )
            i += 1

        widget.setSortingEnabled(True)
        widget.sortByColumn(self.config['sort_index'], self.config['sort_order'])

        # Update tab name with total
        tab_index = self.statuses_nums.index(status)
        tab_name = "%s (%d)" % (self.statuses_names[status], i)
        self.notebook.setTabText(tab_index, tab_name)

    def _update_row(self, widget, row, show, altname, library_episodes=None, is_playing=False):
        color = self._get_color(is_playing, show, library_episodes)

        title_str = show['title']
        if altname:
            title_str += " [%s]" % altname
        progress_str = "{} / {}".format(show['my_progress'], show['total'] or '?')
        percent_widget = EpisodeBar(self, self.config['colors'])
        percent_widget.setRange(0, 100)
        percent_widget.setBarStyle(self.config['episodebar_style'], self.config['episodebar_text'])
        tooltip = "Watched: %d<br>" % show['my_progress']

        if show['total'] > 0:
            percent_widget.setMaximum(show['total'])
        else:
            percent_widget.setMaximum((int(show['my_progress']/12)+1)*12) # Round up to the next cour
        percent_widget.setValue(show['my_progress'])

        aired_eps = utils.estimate_aired_episodes(show)
        if aired_eps:
            percent_widget.setSubValue(aired_eps)
            tooltip += "Aired (estimated): %d<br>" % aired_eps

        if library_episodes:
            eps = library_episodes.keys()
            tooltip += "Latest available: %d<br>" % max(eps)
            percent_widget.setEpisodes(eps)

        tooltip += "Total: %d" % show['total']
        percent_widget.setToolTip(tooltip)
        percent = percent_widget.value() / percent_widget.maximum()

        widget.setRowHeight(row, QtGui.QFontMetrics(widget.font()).height() + 2);
        widget.setItem(row, 0, ShowItem( str(show['id']), color ))
        widget.setItem(row, 1, ShowItem( title_str, color ))
        widget.setItem(row, 2, ShowItemNum( show['my_progress'], progress_str, color ))
        widget.setItem(row, 3, ShowItemNum( show['my_score'], str(show['my_score']), color ))
        widget.setItem(row, 4, ShowItemNum( percent, "{:.0%}".format(percent), color ))
        widget.setCellWidget(row, 4, percent_widget )
        if 'date_next_ep' in self.mediainfo \
        and self.mediainfo['date_next_ep'] \
        and 'next_ep_time' in show:
            delta = show['next_ep_time'] - datetime.datetime.utcnow()
            widget.setItem(row, 5, ShowItem( "%i days, %02d hrs." % (delta.days, delta.seconds/3600), color, QtCore.Qt.AlignHCenter ))
        else:
            widget.setItem(row, 5, ShowItem( "-", color, QtCore.Qt.AlignHCenter ))
        widget.setItem(row, 6, ShowItemDate( show['start_date'], color ))
        widget.setItem(row, 7, ShowItemDate( show['end_date'], color ))
        widget.setItem(row, 8, ShowItemDate( show['my_start_date'], color ))
        widget.setItem(row, 9, ShowItemDate( show['my_finish_date'], color ))
        try:
            tag_str = show['my_tags']
            if not tag_str:
                tag_str = '-'
        except:
            tag_str = '-'
        widget.setItem(row, 10, ShowItem( tag_str, color ))

    def _get_color(self, is_playing, show, eps):
        if is_playing:
            return getColor(self.config['colors']['is_playing'])
        elif show.get('queued'):
            return getColor(self.config['colors']['is_queued'])
        elif eps and max(eps) > show['my_progress']:
            return getColor(self.config['colors']['new_episode'])
        elif show['status'] == utils.STATUS_AIRING:
            return getColor(self.config['colors']['is_airing'])
        elif show['status'] == utils.STATUS_NOTYET:
            return getColor(self.config['colors']['not_aired'])
        else:
            return None

    def _get_row_from_showid(self, widget, showid):
        # identify the row this show is in the table
        for row in range(0, widget.rowCount()):
            if widget.item(row, 0).text() == str(showid):
                return row

        return None

    def _select_show(self, show):
        if not show:
            # Unselect any show
            self.selected_show_id = None

            self.show_title.setText('Trackma-qt')
            self.show_image.setText('Trackma-qt')
            self.show_progress.setValue(0)
            self.show_score.setValue(0)
            self.show_progress.setEnabled(False)
            self.show_score.setEnabled(False)
            self.show_progress_bar.setValue(0)
            self.show_progress_bar.setFormat('?/?')
            self.show_status.setEnabled(False)
            self.show_progress_btn.setEnabled(False)
            self.show_score_btn.setEnabled(False)
            self.show_tags_btn.setEnabled(False)
            self.show_play_btn.setEnabled(False)
            self.show_inc_btn.setEnabled(False)
            self.show_dec_btn.setEnabled(False)
            return

        # Block signals
        self.show_status.blockSignals(True)

        # Set proper ranges
        if show['total']:
            self.show_progress.setMaximum(show['total'])
            self.show_progress_bar.setFormat('%v/%m')
            self.show_progress_bar.setMaximum(show['total'])
            # Regenerate Play Episode Menu
            self.generate_episode_menus(self.menu_play, show['total'], show['my_progress'])
        else:
            self.show_progress.setMaximum(utils.estimate_aired_episodes(show) or 10000)
            self.generate_episode_menus(self.menu_play, utils.estimate_aired_episodes(show),show['my_progress'])
            self.show_progress_bar.setFormat('{}/?'.format(show['my_progress']))

        # Update information
        self.show_title.setText(show['title'])
        self.show_progress.setValue(show['my_progress'])
        self.show_status.setCurrentIndex(self.statuses_nums.index(show['my_status']))
        self.show_score.setValue(show['my_score'])

        # Enable relevant buttons
        self.show_progress.setEnabled(True)
        self.show_score.setEnabled(True)
        self.show_progress_btn.setEnabled(True)
        self.show_score_btn.setEnabled(True)
        if 'can_tag' in self.mediainfo and self.mediainfo.get('can_tag'):
            self.show_tags_btn.setEnabled(True)
        self.show_inc_btn.setEnabled(True)
        self.show_dec_btn.setEnabled(True)
        self.show_play_btn.setEnabled(True)
        self.show_status.setEnabled(True)

        # Download image or use cache
        if show.get('image_thumb') or show.get('image'):
            if self.image_worker is not None:
                self.image_worker.cancel()

            utils.make_dir('cache')
            filename = utils.get_filename('cache', "%s_%s_%s.jpg" % (self.api_info['shortname'], self.api_info['mediatype'], show['id']))

            if os.path.isfile(filename):
                self.s_show_image(filename)
            else:
                if "imaging_available" in os.environ:
                    self.show_image.setText('Waiting...')
                    self.image_timer.start()
                else:
                    self.show_image.setText('Not available')
        else:
            self.show_image.setText('No image')

        if show['total'] > 0:
            self.show_progress_bar.setValue( show['my_progress'] )
        else:
            self.show_progress_bar.setValue( 0 )

        # Make it global
        self.selected_show_id = show['id']

        # Unblock signals
        self.show_status.blockSignals(False)

    def _filter_check_row(self, table, row, expression, case_sensitive=False):
        # Determine if a show matches a filter. True -> match -> do not hide
        # Advanced search: Separate the expression into specific field terms, fail if any are not met
        if ':' in expression:
            exprs = expression.split(' ')
            expr_list = []
            for expr in exprs:
                if ':' in expr:
                    expr_terms = expr.split(':',1)
                    if expr_terms[0] in self.column_keys:
                        col = self.column_keys[expr_terms[0]]
                        sub_expr = expr_terms[1].replace('_', ' ').replace('+', ' ')
                        item = table.item(row, col)
                        if case_sensitive:
                            if not sub_expr in item.text():
                                return False
                        else:
                            if not sub_expr.lower() in item.text().lower():
                                return False
                    else: # If it's not a field key, let it be a regular search term
                        expr_list.append(expr)
                else:
                    expr_list.append(expr)
            expression = ' '.join(expr_list)

        # General case: if any fields match the remaining expression, success.
        for col in range(table.columnCount()):
            item = table.item(row, col)
            itemtext = item.text()
            if case_sensitive:
                if expression in itemtext:
                    return True
            else:
                if expression.lower() in itemtext.lower():
                    return True
        return False

    def generate_episode_menus(self, menu, max_eps=1, watched_eps=0):
        bp_top = 5  # No more than this many submenus/episodes in the root menu
        bp_mid = 10 # No more than this many submenus in submenus
        bp_btm = 13 # No more than this many episodes in the submenus
        # The number of episodes where we ditch the submenus entirely since Qt doesn't deserve this abuse
        breakpoint_no_menus = bp_top * bp_btm * bp_mid * bp_mid

        menu.clear()
        # Make basic actions
        action_play_next = QAction(getIcon('media-skip-forward'), 'Play &Next Episode', self)
        action_play_next.triggered.connect(lambda: self.s_play(True))
        action_play_last = QAction(getIcon('view-refresh'), 'Play Last Watched Ep (#%d)' % watched_eps, self)
        action_play_last.triggered.connect(lambda: self.s_play(False))
        action_play_dialog = QAction('Play Episode...', self)
        action_play_dialog.setStatusTip('Select an episode to play.')
        action_play_dialog.triggered.connect(self.s_play_number)

        menu.addAction(action_play_next)
        menu.addAction(action_play_last)

        if max_eps < 1 or max_eps > breakpoint_no_menus:
            menu.addAction(action_play_dialog)
            return menu
        menu.addSeparator()

        ep_actions = []
        for ep in range(1, max_eps+1):
                action = QAction('Ep. %d' % ep, self)
                action.triggered.connect(self.s_play_ep_number(action, ep))
                if ep <= watched_eps:
                    action.setIcon(self.ep_icons['all'])
                else:
                    action.setIcon(self.ep_icons['none'])
                ep_actions.append(action)

        if max_eps <= bp_top:
            # Just put the eps in the root menu
            for action in ep_actions:
                menu.addAction(action)

        else:
            # We need to go deeper. For now, put all the episodes into bottom-level submenus.
            self.play_ep_submenus = [] # I don't like this scoping. If you find a way to transfer ownership of the submenu to the menu feel free to fix this.
            current_actions = bp_btm + 1 # A bit hacky but avoids a special case for the first submenu
            for action in ep_actions:
                if current_actions >= bp_btm:
                    current_actions = 0
                    l = len(self.play_ep_submenus)
                    self.play_ep_submenus.append(QMenu('Episodes %d-%d:' % (l*bp_btm + 1, min((l+1)*bp_btm, max_eps))))
                    if watched_eps > min((l+1)*bp_btm, max_eps):
                        self.play_ep_submenus[-1].setIcon(self.ep_icons['all'])
                    elif watched_eps > l*bp_btm:
                        self.play_ep_submenus[-1].setIcon(self.ep_icons['part'])
                    else:
                        self.play_ep_submenus[-1].setIcon(self.ep_icons['none'])
                self.play_ep_submenus[-1].addAction(action)
                current_actions += 1

            # Now to put the bottom level menus into other things
            if len(self.play_ep_submenus) <= bp_top: # Straight into the root menu, easy!
                for submenu in self.play_ep_submenus:
                    menu.addMenu(submenu)
            else: # For now, put them into another level of submenus
                self.play_ep_sub2menus = []
                current_menus = bp_mid + 1
                for s in self.play_ep_submenus:
                    if current_menus >= bp_mid:
                        current_menus = 0
                        l = len(self.play_ep_sub2menus)
                        self.play_ep_sub2menus.append(QMenu('Episodes %d-%d:' % (l*bp_btm*bp_mid + 1, min((l+1)*bp_btm*bp_mid, max_eps))))
                    self.play_ep_sub2menus[-1].addMenu(s)
                    if watched_eps > min((l+1)*bp_btm*bp_mid, max_eps):
                        self.play_ep_sub2menus[-1].setIcon(self.ep_icons['all'])
                    elif watched_eps > l*bp_btm*bp_mid:
                        self.play_ep_sub2menus[-1].setIcon(self.ep_icons['part'])
                    else:
                        self.play_ep_sub2menus[-1].setIcon(self.ep_icons['none'])
                    current_menus += 1

                if len(self.play_ep_sub2menus) <= bp_top:
                    for submenu in self.play_ep_sub2menus:
                        menu.addMenu(submenu)
                else:
                    # I seriously hope this additional level is not needed, but maybe someone will want to set smaller breakpoints.
                    self.play_ep_sub3menus = []
                    current_menus = bp_mid + 1
                    for s in self.play_ep_sub2menus:
                        if current_menus >= bp_mid:
                            current_menus = 0
                            l = len(self.play_ep_sub3menus)
                            self.play_ep_sub3menus.append(QMenu('Episodes %d-%d:' % (l*bp_btm*bp_mid*bp_mid + 1, min((l+1)*bp_btm*bp_mid*bp_mid, max_eps))))
                        self.play_ep_sub3menus[-1].addMenu(s)
                        if watched_eps > min((l+1)*bp_btm*bp_mid*bp_mid, max_eps):
                            self.play_ep_sub3menus[-1].setIcon(self.ep_icons['all'])
                        elif watched_eps > l*bp_btm*bp_mid*bp_mid:
                            self.play_ep_sub3menus[-1].setIcon(self.ep_icons['part'])
                        else:
                            self.play_ep_sub3menus[-1].setIcon(self.ep_icons['none'])
                        current_menus += 1
                    # No more levels, our sanity check earlier ensured that.
                    for submenu in self.play_ep_sub3menus:
                        menu.addMenu(submenu)
        return menu

    ### Slots
    def s_hide(self):
        if self.isVisible():
            self.was_maximized = self.isMaximized()
            self.hide()
        else:
            self.setGeometry(self.geometry())
            if self.was_maximized:
                self.showMaximized()
            else:
                self.show()

    def s_tray_clicked(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.s_hide()

    def s_busy(self):
        self._enable_widgets(False)

    def s_show_selected(self, new, old=None):
        if new:
            index = new.row()
            selected_id = self.notebook.currentWidget().item( index, 0 ).text()

            # Attempt to convert to int if possible
            try:
                selected_id = int(selected_id)
            except ValueError:
                selected_id = str(selected_id)

            show = self.worker.engine.get_show_info(selected_id)
            self._select_show(show)
        else:
            self._select_show(None)

    def s_update_sort(self, index, order):
        self.config['sort_index'] = index
        self.config['sort_order'] = order

    def s_download_image(self):
        show = self.worker.engine.get_show_info(self.selected_show_id)
        self.show_image.setText('Downloading...')
        filename = utils.get_filename('cache', "%s_%s_%s.jpg" % (self.api_info['shortname'], self.api_info['mediatype'], show['id']))

        self.image_worker = ImageWorker(show.get('image_thumb') or show['image'], filename, (100, 140))
        self.image_worker.finished.connect(self.s_show_image)
        self.image_worker.start()

    def s_tab_changed(self):
        item = self.notebook.currentWidget().currentItem()
        if item:
            self.s_show_selected(item)
        self.s_filter_changed() # Refresh filter

    def s_filter_changed(self):
        tabs = []
        if self.config['filter_global']:
            tabs = range(len(self.notebook))
        else:
            tabs = [self.notebook.currentIndex()]
        expr = self.show_filter.text()
        casesens = self.show_filter_casesens.isChecked()
        for tab_index in tabs:
            table = self.notebook.widget(tab_index)
            shown = 0
            total = 0
            for row in range(table.rowCount()):
                if not expr:
                    table.setRowHidden(row, False)
                elif self.show_filter_invert.isChecked():
                    table.setRowHidden(row, self._filter_check_row(table, row, expr, casesens))
                else:
                    table.setRowHidden(row, not self._filter_check_row(table, row, expr, casesens))
                if not table.isRowHidden(row):
                    shown += 1
                total += 1
            # Update tab name with matches out of total
            status = self.statuses_nums[tab_index]
            if expr:
                tab_name = "%s (%d/%d)" % (self.statuses_names[status], shown, total)
            else:
                tab_name = "%s (%d)" % (self.statuses_names[status], total) # Filter disabled
            self.notebook.setTabText(tab_index, tab_name)

    def s_plus_episode(self):
        self._busy(True)
        self.worker_call('set_episode', self.r_generic, self.selected_show_id, self.show_progress.value()+1)

    def s_rem_episode(self):
        if not self.show_progress.value() <= 0:
            self._busy(True)
            self.worker_call('set_episode', self.r_generic, self.selected_show_id, self.show_progress.value()-1)

    def s_set_episode(self):
        self._busy(True)
        self.worker_call('set_episode', self.r_generic, self.selected_show_id, self.show_progress.value())

    def s_set_score(self):
        self._busy(True)
        self.worker_call('set_score', self.r_generic, self.selected_show_id, self.show_score.value())

    def s_set_status(self, index):
        if self.selected_show_id:
            self._busy(True)
            self.worker_call('set_status', self.r_generic, self.selected_show_id, self.statuses_nums[index])

    def s_set_tags(self):
        show = self.worker.engine.get_show_info(self.selected_show_id)
        if 'my_tags' in show and show['my_tags']:
            tags = show['my_tags']
        else:
            tags = ''
        tags, ok = QInputDialog.getText(self, 'Edit Tags',
            'Enter desired tags (comma separated)',
            text=tags)
        if ok:
            self.s_edit_tags(show, tags)

    def s_edit_tags(self, show, tags):
        self._busy(True)
        self.worker_call('set_tags', self.r_generic, show['id'], tags)

    def s_play(self, play_next, episode=0):
        if self.selected_show_id:
            show = self.worker.engine.get_show_info(self.selected_show_id)

            #episode = 0 # Engine plays next unwatched episode
            if not play_next and not episode:
                episode = self.show_progress.value()

            self._busy(True)
            self.worker_call('play_episode', self.r_generic, show, episode)

    def s_play_random(self):
        self._busy(True)
        self.worker_call('play_random', self.r_generic)

    def s_play_number(self):
        show = self.worker.engine.get_show_info(self.selected_show_id)
        ep_default = 1
        ep_min = 1
        ep_max = utils.estimate_aired_episodes(show)
        if not ep_max:
            # If we don't know the total just allow anything
            ep_max = show['total'] or 10000

        episode, ok = QInputDialog.getInt(self, 'Play Episode',
            'Enter an episode number of %s to play:' % show['title'],
            ep_default, ep_min, ep_max)

        if ok:
            self.s_play(False, episode)

    def s_play_ep_number(self, action, number):
        return lambda: [action.setIcon(self.ep_icons['part']), self.s_play(False, number)]

    def s_delete(self):
        show = self.worker.engine.get_show_info(self.selected_show_id)
        reply = QMessageBox.question(self, 'Confirmation',
            'Are you sure you want to delete %s?' % show['title'],
            QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.worker_call('delete_show', self.r_generic, show)

    def s_scan_library(self):
        self.worker_call('scan_library', self.r_library_scanned)

    def s_altname(self):
        show = self.worker.engine.get_show_info(self.selected_show_id)
        current_altname = self.worker.engine.altname(self.selected_show_id)

        new_altname, ok = QInputDialog.getText(self, 'Alternative title',
            'Set the new alternative title for %s (blank to remove):' % show['title'],
            text=current_altname)

        if ok:
            self.worker.engine.altname(self.selected_show_id, str(new_altname))
            self.ws_changed_show(show, altname=new_altname)

    def s_open_folder(self):
        show = self.worker.engine.get_show_info(self.selected_show_id)
        try:
            filename = self.worker.engine.get_episode_path(show, 1)
            with open(os.devnull, 'wb') as DEVNULL:
                subprocess.Popen(["/usr/bin/xdg-open",
                    os.path.dirname(filename)], stdout=DEVNULL, stderr=DEVNULL)
        except OSError:
            # xdg-open failed.
            raise utils.EngineError("Could not open folder.")

        except utils.EngineError:
            # Show not in library.
            self.error("No folder found.")

    def s_retrieve(self):
        queue = self.worker.engine.get_queue()

        if queue:
            reply = QMessageBox.question(self, 'Confirmation',
                'There are %d unsynced changes. Do you want to send them first? (Choosing No will discard them!)' % len(queue),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)

            if reply == QMessageBox.Yes:
                self.s_send(True)
            elif reply == QMessageBox.No:
                self._busy(True)
                self.worker_call('list_download', self.r_list_retrieved)
        else:
            self._busy(True)
            self.worker_call('list_download', self.r_list_retrieved)

    def s_send(self, retrieve=False):
        self._busy(True)
        if retrieve:
            self.worker_call('list_upload', self.s_retrieve)
        else:
            self.worker_call('list_upload', self.r_generic_ready)

    def s_switch_account(self):
        if not self.accountman_widget:
            self.accountman_create()
        else:
            self.accountman_widget.update()

        self.accountman_widget.setModal(True)
        self.accountman_widget.show()

    def s_show_image(self, filename):
        self.show_image.setPixmap( QtGui.QPixmap( filename ) )

    def s_show_details(self):
        if not self.selected_show_id:
            return

        show = self.worker.engine.get_show_info(self.selected_show_id)

        self.detailswindow = DetailsDialog(None, self.worker, show)
        self.detailswindow.setModal(True)
        self.detailswindow.show()

    def s_add(self):
        page = self.notebook.currentIndex()
        current_status = self.statuses_nums[page]

        self.addwindow = AddDialog(None, self.worker, current_status)
        self.addwindow.setModal(True)
        self.addwindow.show()

    def s_mediatype(self, action):
        index = action.data()
        mediatype = self.api_info['supported_mediatypes'][index]
        self.reload(None, mediatype)

    def s_settings(self):
        dialog = SettingsDialog(None, self.worker, self.config, self.configfile)
        dialog.saved.connect(self._update_config)
        dialog.exec_()

    def s_about(self):
        QMessageBox.about(self, 'About Trackma-qt %s' % utils.VERSION,
            '<p><b>About Trackma-qt %s</b></p><p>Trackma is an open source client for media tracking websites.</p>'
            '<p>This program is licensed under the GPLv3, for more information read COPYING file.</p>'
            '<p>Thanks to all contributors. To see all contributors see AUTHORS file.</p>'
            '<p>Copyright (C) z411 - Icon by shuuichi</p>'
            '<p><a href="http://github.com/z411/trackma">http://github.com/z411/trackma</a></p>' % utils.VERSION)

    def s_about_qt(self):
        QMessageBox.aboutQt(self, 'About Qt')

    def s_show_menu_columns(self, pos):
        globalPos = self.sender().mapToGlobal(pos)
        globalPos += QtCore.QPoint(3, 3)
        self.menu_columns.exec_(globalPos)

    def s_toggle_column(self, w):
        (column_name, visible) = (w.text(), w.isChecked())
        index = self.available_columns.index(column_name)
        MIN_WIDTH = 30  # Width to restore columns to if too small to see

        if visible:
            if column_name not in self.config['visible_columns']:
                self.config['visible_columns'].append(str(column_name))
        else:
            if column_name in self.config['visible_columns']:
                self.config['visible_columns'].remove(column_name)

        utils.save_config(self.config, self.configfile)
        if self.config['columns_per_api']:
            self.api_config['visible_columns'] = self.config['visible_columns']
            utils.save_config(self.api_config, self.api_configfile)

        for showlist in self.show_lists.values():
            showlist.setColumnHidden(index, not visible)
            if visible and showlist.columnWidth(index) < MIN_WIDTH:
                showlist.setColumnWidth(index, MIN_WIDTH)

    ### Worker slots
    def ws_changed_status(self, classname, msgtype, msg):
        if msgtype != messenger.TYPE_DEBUG:
            self.status('{}: {}'.format(classname, msg))
        elif self.debug:
            print('[D] {}: {}'.format(classname, msg))

    def ws_changed_show(self, show, is_playing=False, episode=None, altname=None):
        if show:
            if not self.show_lists:
                return # Lists not built yet; can be safely avoided

            widget = self.show_lists[show['my_status']]
            row = self._get_row_from_showid(widget, show['id'])

            if row is None:
                return # Row not in list yet; can be safely avoided

            library = self.worker.engine.library()

            widget.setSortingEnabled(False)
            self._update_row(widget, row, show, altname, library.get(show['id']), is_playing)
            widget.setSortingEnabled(True)

            if show['id'] == self.selected_show_id:
                self._select_show(show)

            if is_playing and self.config['show_tray'] and self.config['notifications']:
                if episode == (show['my_progress'] + 1):
                    delay = self.worker.engine.get_config('tracker_update_wait_s')
                    self.tray.showMessage('Trackma Tracker', "Playing %s %s. Will update in %d seconds." % (show['title'], episode, delay))

    def ws_changed_list(self, show, old_status=None):
        # Rebuild both new and old (if any) lists
        self._rebuild_list(show['my_status'])
        if old_status:
            self._rebuild_list(old_status)

        # Set notebook to the new page
        self.notebook.setCurrentIndex( self.statuses_nums.index(show['my_status']) )
        # Refresh filter
        self.s_filter_changed()

    def ws_changed_queue(self, queue):
        self._update_queue_counter(queue)

    def ws_tracker_state(self, state, timer):
        self._update_tracker_info(state, timer)

    def ws_prompt_update(self, show, episode):
        reply = QMessageBox.question(self, 'Message',
            'Do you want to update %s to %d?' % (show['title'], episode),
            QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.worker_call('set_episode', self.r_generic, show['id'], episode)

    def ws_prompt_add(self, show_title, episode):
        page = self.notebook.currentIndex()
        current_status = self.statuses_nums[page]

        addwindow = AddDialog(None, self.worker, current_status, default=show_title)
        addwindow.setModal(True)
        if addwindow.exec_():
            self.worker_call('set_episode', self.r_generic, addwindow.selected_show['id'], episode)

    ### Responses from the engine thread
    def r_generic(self):
        self._unbusy()

    def r_generic_ready(self):
        self._unbusy()
        self.status('Ready.')

    def r_engine_loaded(self, result):
        if result['success']:
            showlist = self.worker.engine.get_list()
            altnames = self.worker.engine.altnames()
            library = self.worker.engine.library()

            self.notebook.blockSignals(True)
            self.show_status.blockSignals(True)

            # Set globals
            self.notebook.clear()
            self.show_status.clear()
            self.show_lists = dict()

            self.api_info = self.worker.engine.api_info
            self.mediainfo = self.worker.engine.mediainfo

            self.statuses_nums = self.mediainfo['statuses']
            self.statuses_names = self.mediainfo['statuses_dict']

            # Build notebook
            for status in self.statuses_nums:
                name = self.statuses_names[status]

                self.show_lists[status] = ShowsTableWidget()
                self.show_lists[status].context_menu = self.menu_show_context
                self.show_lists[status].setSelectionMode(QAbstractItemView.SingleSelection)
                #self.show_lists[status].setFocusPolicy(QtCore.Qt.NoFocus)
                self.show_lists[status].setSelectionBehavior(QAbstractItemView.SelectRows)
                self.show_lists[status].setEditTriggers(QAbstractItemView.NoEditTriggers)
                self.show_lists[status].horizontalHeader().setHighlightSections(False)
                if pyqt_version is 5:
                    self.show_lists[status].horizontalHeader().setSectionsMovable(True)
                else:
                    self.show_lists[status].horizontalHeader().setMovable(True)
                self.show_lists[status].horizontalHeader().setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
                self.show_lists[status].horizontalHeader().customContextMenuRequested.connect(self.s_show_menu_columns)
                self.show_lists[status].horizontalHeader().sortIndicatorChanged.connect(self.s_update_sort)
                self.show_lists[status].verticalHeader().hide()
                self.show_lists[status].setGridStyle(QtCore.Qt.NoPen)
                self.show_lists[status].currentItemChanged.connect(self.s_show_selected)
                self.show_lists[status].doubleClicked.connect(self.s_show_details)

                self.notebook.addTab(self.show_lists[status], name)
                self.show_status.addItem(name)

            self.show_status.blockSignals(False)
            self.notebook.blockSignals(False)

            # Build mediatype menu
            for action in self.mediatype_actiongroup.actions():
                self.mediatype_actiongroup.removeAction(action)

            for n, mediatype in enumerate(self.api_info['supported_mediatypes']):
                action = QAction(mediatype, self, checkable=True)
                if mediatype == self.api_info['mediatype']:
                    action.setChecked(True)
                else:
                    action.setData(n)
                self.mediatype_actiongroup.addAction(action)
                self.menu_mediatype.addAction(action)

            # Show API info
            self.api_icon.setPixmap(QtGui.QPixmap(utils.available_libs[self.account['api']][1]))
            if self.config['tray_api_icon']:
                self.tray.setIcon(QIcon(utils.available_libs[self.account['api']][1]))
            self.api_user.setText(self.worker.engine.get_userconfig('username'))
            self.setWindowTitle("Trackma-qt %s [%s (%s)]" % (utils.VERSION, self.api_info['name'], self.api_info['mediatype']))

            # Show tracker info
            tracker_info = self.worker.engine.tracker_status()
            if tracker_info:
                self._update_tracker_info(tracker_info['state'], tracker_info['timer'])

            # Rebuild lists
            self._rebuild_lists(showlist, altnames, library)

            self.s_show_selected(None)

            self.status('Ready.')

        self._unbusy()

    def r_list_retrieved(self, result):
        if result['success']:
            showlist = self.worker.engine.get_list()
            altnames = self.worker.engine.altnames()
            library = self.worker.engine.library()
            self._rebuild_lists(showlist, altnames, library)

            self.status('Ready.')

        self._unbusy()

    def r_library_scanned(self, result):
        if result['success']:
            status = self.worker.engine.mediainfo['status_start']

            showlist = self.worker.engine.filter_list(status)
            altnames = self.worker.engine.altnames()
            library = self.worker.engine.library()
            self._rebuild_list(status, showlist, altnames, library)

            self.status('Ready.')

        self._unbusy()

    def r_engine_unloaded(self, result):
        if result['success']:
            self.close()
            if not self.finish:
                self.s_switch_account()

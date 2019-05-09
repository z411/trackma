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
import base64

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QFormLayout,
            QGridLayout, QHBoxLayout, QVBoxLayout,
            QAbstractItemView, QHeaderView, QListWidget,
            QListWidgetItem, QTabBar, QTableWidget,
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
from trackma.ui.qt.widgets import ShowsTableView
from trackma.ui.qt.workers import EngineWorker, ImageWorker
from trackma.ui.qt.util import getIcon, FilterBar

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
    mediainfo = None
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
        self.configfile = utils.to_config_path('ui-qt.json')
        self.config = utils.parse_config(self.configfile, utils.qt_defaults)

        # Build UI
        QApplication.setWindowIcon(QtGui.QIcon(utils.DATADIR + '/icon.png'))
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
        self.worker = EngineWorker()
        self.account = account

        # Get API specific configuration
        self.api_config = self._get_api_config(account['api'])

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
        self.action_play_next = QAction(getIcon('media-playback-start'), 'Play &Next', self)
        self.action_play_next.setStatusTip('Play the next unwatched episode.')
        self.action_play_next.setShortcut('Ctrl+N')
        self.action_play_next.triggered.connect(lambda: self.s_play(True))
        self.action_play_dialog = QAction('Play Episode...', self)
        self.action_play_dialog.setStatusTip('Select an episode to play.')
        self.action_play_dialog.triggered.connect(self.s_play_number)
        self.action_details = QAction('Show &details...', self)
        self.action_details.setStatusTip('Show detailed information about the selected show.')
        self.action_details.triggered.connect(self.s_show_details)
        self.action_altname = QAction('Change &alternate name...', self)
        self.action_altname.setStatusTip('Set an alternate title for the tracker.')
        self.action_altname.triggered.connect(self.s_altname)
        action_play_random = QAction('Play &random show', self)
        action_play_random.setStatusTip('Pick a random show with a new episode and play it.')
        action_play_random.setShortcut('Ctrl+R')
        action_play_random.triggered.connect(self.s_play_random)
        self.action_add = QAction(getIcon('edit-find'), 'Search/Add from Remote', self)
        self.action_add.setShortcut('Ctrl+A')
        self.action_add.triggered.connect(self.s_add)
        self.action_delete = QAction(getIcon('edit-delete'), '&Delete', self)
        self.action_delete.setStatusTip('Remove this show from your list.')
        self.action_delete.setShortcut(QtCore.Qt.Key_Delete)
        self.action_delete.triggered.connect(self.s_delete)
        action_quit = QAction(getIcon('application-exit'), '&Quit', self)
        action_quit.setShortcut('Ctrl+Q')
        action_quit.setStatusTip('Exit Trackma.')
        action_quit.triggered.connect(self._exit)

        self.action_sync = QAction('&Sync', self)
        self.action_sync.setStatusTip('Send changes and then retrieve remote list')
        self.action_sync.setShortcut('Ctrl+S')
        self.action_sync.triggered.connect(lambda: self.s_send(True))
        self.action_send = QAction('S&end changes', self)
        self.action_send.setShortcut('Ctrl+E')
        self.action_send.setStatusTip('Upload any changes made to the list immediately.')
        self.action_send.triggered.connect(self.s_send)
        self.action_retrieve = QAction('Re&download list', self)
        self.action_retrieve.setShortcut('Ctrl+D')
        self.action_retrieve.setStatusTip('Discard any changes made to the list and re-download it.')
        self.action_retrieve.triggered.connect(self.s_retrieve)
        action_scan_library = QAction('Rescan &Library (quick)', self)
        action_scan_library.setShortcut('Ctrl+L')
        action_scan_library.triggered.connect(self.s_scan_library)
        action_rescan_library = QAction('Rescan &Library (full)', self)
        action_rescan_library.triggered.connect(self.s_rescan_library)
        action_open_folder = QAction('Open containing folder', self)
        action_open_folder.triggered.connect(self.s_open_folder)

        self.action_reload = QAction('Switch &Account', self)
        self.action_reload.setStatusTip('Switch to a different account.')
        self.action_reload.triggered.connect(self.s_switch_account)
        action_settings = QAction('&Settings...', self)
        action_settings.triggered.connect(self.s_settings)

        action_about = QAction(getIcon('help-about'), 'About...', self)
        action_about.triggered.connect(self.s_about)
        action_about_qt = QAction('About Qt...', self)
        action_about_qt.triggered.connect(self.s_about_qt)

        menubar = self.menuBar()
        self.menu_show = menubar.addMenu('&Show')
        self.menu_show.addAction(self.action_play_next)
        self.menu_show.addAction(self.action_play_dialog)
        self.menu_show.addAction(self.action_details)
        self.menu_show.addAction(self.action_altname)
        self.menu_show.addSeparator()
        self.menu_show.addAction(action_play_random)
        self.menu_show.addSeparator()
        self.menu_show.addAction(self.action_add)
        self.menu_show.addAction(self.action_delete)
        self.menu_show.addSeparator()
        self.menu_show.addAction(action_quit)

        self.menu_play = QMenu('Play')

        # Context menu for right click on list item
        self.menu_show_context = QMenu()
        self.menu_show_context.addMenu(self.menu_play)
        self.menu_show_context.addAction(self.action_details)
        self.menu_show_context.addAction(action_open_folder)
        self.menu_show_context.addAction(self.action_altname)
        self.menu_show_context.addSeparator()
        self.menu_show_context.addAction(self.action_delete)

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
        menu_list.addAction(self.action_sync)
        menu_list.addSeparator()
        menu_list.addAction(self.action_send)
        menu_list.addAction(self.action_retrieve)
        menu_list.addSeparator()
        menu_list.addAction(action_scan_library)
        menu_list.addAction(action_rescan_library)
        self.menu_mediatype = menubar.addMenu('&Mediatype')
        self.mediatype_actiongroup = QActionGroup(self, exclusive=True)
        self.mediatype_actiongroup.triggered.connect(self.s_mediatype)
        menu_options = menubar.addMenu('&Options')
        menu_options.addAction(self.action_reload)
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

        # Create main models and view
        self.notebook = QTabBar()
        self.notebook.currentChanged.connect(self.s_tab_changed)

        self.view = ShowsTableView(palette=self.config['colors'])
        self.view.context_menu = self.menu_show_context
        self.view.horizontalHeader().customContextMenuRequested.connect(self.s_show_menu_columns)
        self.view.horizontalHeader().sortIndicatorChanged.connect(self.s_update_sort)
        self.view.selectionModel().currentRowChanged.connect(self.s_show_selected)
        self.view.itemDelegate().setBarStyle(self.config['episodebar_style'], self.config['episodebar_text'])
        self.view.middleClicked.connect(lambda: self.s_play(True))
        self.view.activated.connect(self.s_show_details)
        self._apply_view()

        self.view.model().sourceModel().progressChanged.connect(self.s_set_episode)
        self.view.model().sourceModel().scoreChanged.connect(self.s_set_score)

        # Context menu for right click on list header
        self.menu_columns = QMenu()
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

        for i, column_name in enumerate(self.view.model().sourceModel().columns):
            action = QAction(column_name, self, checkable=True)
            action.setData(i)
            if column_name in self.api_config['visible_columns']:
                action.setChecked(True)

            self.menu_columns_group.addAction(action)
            self.menu_columns.addAction(action)

        # Create filter list
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
            self.list_box.addWidget(self.view)
            self.filter_bar_box.hide()
        elif self.config['filter_bar_position'] is FilterBar.PositionAboveLists:
            self.list_box.addWidget(self.filter_bar_box)
            self.list_box.addWidget(self.notebook)
            self.list_box.addWidget(self.view)
        elif self.config['filter_bar_position'] is FilterBar.PositionBelowLists:
            self.list_box.addWidget(self.notebook)
            self.list_box.addWidget(self.view)
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
        self._apply_tray()

        # Connect worker signals
        self.worker.changed_status.connect(self.ws_changed_status)
        self.worker.raised_error.connect(self.error)
        self.worker.raised_fatal.connect(self.fatal)
        self.worker.changed_show.connect(self.ws_changed_show)
        self.worker.changed_show_status.connect(self.ws_changed_show_status)
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
        self.worker_call('start', self.r_engine_loaded, account)

    def reload(self, account=None, mediatype=None):
        if self.config['remember_columns']:
            self._store_columnstate()

        if account:
            self.account = account

            # Get API specific configuration
            self.api_config = self._get_api_config(account['api'])

        self.menu_columns_group.setEnabled(False)
        for action in self.menu_columns_group.actions():
            action.setChecked(action.text() in self.api_config['visible_columns'])
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
    def _get_api_config(self, api):
        if self.config['columns_per_api']:
            if 'api' not in self.config:
                self.config['api'] = {}
            if api not in self.config['api']:
                self.config['api'][api] = dict(utils.qt_per_api_defaults)
            return self.config['api'][api]
        else:
            # API settings are universal
            return self.config

    def _save_config(self):
        utils.save_config(self.config, self.configfile)

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
        columns_state = {}

        state = self.view.horizontalHeader().saveState()
        columns_state = base64.b64encode(state).decode('ascii')

        self.api_config['columns_state'] = columns_state
        self._save_config()

    def _enable_widgets(self, enable):
        self.view.setEnabled(enable)
        self._enable_show_widgets(bool(self.selected_show_id and enable))

        self.action_add.setEnabled(enable)
        self.action_sync.setEnabled(enable)
        self.action_send.setEnabled(enable)
        self.action_retrieve.setEnabled(enable)
        self.action_reload.setEnabled(enable)
     
    def _enable_show_widgets(self, enable):
        self.show_progress.setEnabled(enable)
        self.show_score.setEnabled(enable)
        self.show_progress_btn.setEnabled(enable)
        self.show_score_btn.setEnabled(enable)
        self.show_tags_btn.setEnabled(bool(self.mediainfo and self.mediainfo.get('can_tag') and enable))
        self.show_inc_btn.setEnabled(enable)
        self.show_dec_btn.setEnabled(enable)
        self.show_play_btn.setEnabled(enable)
        self.show_status.setEnabled(enable)
        self.action_play_next.setEnabled(enable)
        self.action_play_dialog.setEnabled(enable)
        self.action_altname.setEnabled(enable)
        self.action_delete.setEnabled(enable)
        self.action_details.setEnabled(enable)
        
    def _update_queue_counter(self, queue):
        self.queue_text.setText("Unsynced items: %d" % queue)

    def _update_tracker_info(self, status):
        state = status['state']
        timer = status['timer']
        paused = status['paused']

        if state == utils.TRACKER_NOVIDEO:
            st = 'Listen'
        elif state == utils.TRACKER_PLAYING:
            (m, s) = divmod(timer, 60)
            st = "+{0}:{1:02d}{2}".format(m, s, ' [P]' if paused else '')
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
        self._apply_view()
        self._apply_tray()
        self._apply_filter_bar()
        # TODO: Reload listviews?

    def _apply_view(self):
        if self.config['inline_edit']:
            self.view.setEditTriggers(QAbstractItemView.AllEditTriggers)
        else:
            self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)

    def _apply_tray(self):
        if self.tray.isVisible() and not self.config['show_tray']:
            self.tray.hide()
        elif not self.tray.isVisible() and self.config['show_tray']:
            self.tray.show()
        if self.tray.isVisible():
            if self.config['tray_api_icon']:
                self.tray.setIcon(QtGui.QIcon(utils.available_libs[self.account['api']][1]))
            else:
                self.tray.setIcon(self.windowIcon())

    def _apply_filter_bar(self):
        self.list_box.removeWidget(self.filter_bar_box)
        self.list_box.removeWidget(self.notebook)
        self.list_box.removeWidget(self.view)
        self.filter_bar_box.show()
        if self.config['filter_bar_position'] is FilterBar.PositionHidden:
            self.list_box.addWidget(self.notebook)
            self.list_box.addWidget(self.view)
            self.filter_bar_box.hide()
        elif self.config['filter_bar_position'] is FilterBar.PositionAboveLists:
            self.list_box.addWidget(self.filter_bar_box)
            self.list_box.addWidget(self.notebook)
            self.list_box.addWidget(self.view)
        elif self.config['filter_bar_position'] is FilterBar.PositionBelowLists:
            self.list_box.addWidget(self.notebook)
            self.list_box.addWidget(self.view)
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

    def _rebuild_statuses(self):
        # Rebuild statuses
        self.show_status.blockSignals(True)
        self.notebook.blockSignals(True)

        self.show_status.clear()

        # Clear notebook
        while self.notebook.count() > 0:
            self.notebook.removeTab(0)

        # Add one page per status
        for i, status in enumerate(self.mediainfo['statuses']):
            name = self.mediainfo['statuses_dict'][status]

            self.notebook.addTab(name)
            self.notebook.setTabData(i, status)

            self.show_status.addItem(name)

        self.notebook.addTab("All")

        self.show_status.blockSignals(False)
        self.notebook.blockSignals(False)

    def _recalculate_counts(self):
        showlist = self.worker.engine.get_list()

        self.counts = {status: 0 for status in self.mediainfo['statuses']}
        self.counts['!ALL'] = 0

        for show in showlist:
            self.counts[show['my_status']] += 1
            self.counts['!ALL'] += 1

        self._update_counts()

    def _update_counts(self):
        for page in range(self.notebook.count()):
            status = self.notebook.tabData(page)
            if status is not None:
                status_name = self.mediainfo['statuses_dict'][status]
            else:
                status_name = "All"
                status = "!ALL"

            self.notebook.setTabText(page, "{} ({})".format(
                status_name, self.counts[status]))

    def _rebuild_view(self):
        """
        Using a full showlist, rebuilds main view

        """
        showlist = self.worker.engine.get_list()
        altnames = self.worker.engine.altnames()
        library = self.worker.engine.library()

        # Set allowed ranges (this will be reported by the engine later)
        decimal_places = 0
        if isinstance(self.mediainfo['score_step'], float):
            decimal_places = len(str(self.mediainfo['score_step']).split('.')[1])

        self.show_score.setRange(0, self.mediainfo['score_max'])
        self.show_score.setDecimals(decimal_places)
        self.show_score.setSingleStep(self.mediainfo['score_step'])

        # Get the new list and pass it to our model
        self.view.setSortingEnabled(False)
        self.view.model().setFilterStatus(self.notebook.tabData(self.notebook.currentIndex()))
        self.view.model().sourceModel().setMediaInfo(self.mediainfo)
        self.view.model().sourceModel().setShowList(showlist, altnames, library)
        self.view.resizeRowsToContents()

        # Set view options
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(self.config['sort_index'], self.config['sort_order'])

        # Hide invisible columns
        for i, column in enumerate(self.view.model().sourceModel().columns):
            if column not in self.api_config['visible_columns']:
                self.view.setColumnHidden(i, True)

        if pyqt_version is 5:
            self.view.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            self.view.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
            self.view.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        else:
            self.view.horizontalHeader().setResizeMode(1, QHeaderView.Stretch)
            self.view.horizontalHeader().setResizeMode(2, QHeaderView.Fixed)
            self.view.horizontalHeader().setResizeMode(3, QHeaderView.Fixed)

        self.view.horizontalHeader().resizeSection(2, 70)
        self.view.horizontalHeader().resizeSection(3, 55)
        self.view.horizontalHeader().resizeSection(4, 100)

        self.s_filter_changed()

    def _select_show(self, show):
        # Stop any running image timer
        if self.image_timer is not None:
            self.image_timer.stop()

        # Unselect show
        if not show:
            self.selected_show_id = None

            self.show_title.setText('Trackma-qt')
            self.show_image.setText('Trackma-qt')
            self.show_progress.setValue(0)
            self.show_score.setValue(0)
            self.show_progress_bar.setValue(0)
            self.show_progress_bar.setFormat('?/?')
            self._enable_show_widgets(False)

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
        metrics = QtGui.QFontMetrics(self.show_title.font())
        title = metrics.elidedText(show['title'], QtCore.Qt.ElideRight, self.show_title.width())
        self.show_title.setText(title)

        self.show_progress.setValue(show['my_progress'])
        self.show_status.setCurrentIndex(self.mediainfo['statuses'].index(show['my_status']))
        self.show_score.setValue(show['my_score'])

        # Enable relevant buttons
        self._enable_show_widgets(True)

        # Download image or use cache
        if show.get('image_thumb') or show.get('image'):
            if self.image_worker is not None:
                self.image_worker.cancel()

            utils.make_dir(utils.to_cache_path())
            filename = utils.to_cache_path("%s_%s_%s.jpg" % (self.api_info['shortname'], self.api_info['mediatype'], show['id']))

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

        if show['total']:
            self.show_progress_bar.setValue( show['my_progress'] )
        else:
            self.show_progress_bar.setValue( 0 )

        # Make it global
        self.selected_show_id = show['id']

        # Unblock signals
        self.show_status.blockSignals(False)

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
            index = self.view.model().index(new.row(), 0)
            selected_id = self.view.model().data(index)

            if selected_id:
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
        filename = utils.to_cache_path("%s_%s_%s.jpg" % (self.api_info['shortname'], self.api_info['mediatype'], show['id']))

        self.image_worker = ImageWorker(show.get('image_thumb') or show['image'], filename, (100, 140))
        self.image_worker.finished.connect(self.s_show_image)
        self.image_worker.start()

    def s_tab_changed(self, index):
        # Change the filter of the main view to the specified status
        status = self.notebook.tabData(index)
        self.view.model().setFilterStatus(status)
        self.view.resizeRowsToContents() # TODOMVC : Find a faster way

        self.s_show_selected(None)
        self.s_filter_changed() # Refresh filter

    def s_filter_changed(self):
        # TODOMVC DEPRECATED
        expression = self.show_filter.text()
        casesens = self.show_filter_casesens.isChecked()

        # Determine if a show matches a filter. True -> match -> do not hide
        # Advanced search: Separate the expression into specific field terms, fail if any are not met
        if ':' in expression:
            exprs = expression.split(' ')
            expr_dict = {}
            expr_list = []
            for expr in exprs:
                if ':' in expr:
                    expr_terms = expr.split(':',1)
                    if expr_terms[0] in self.column_keys:
                        col = self.column_keys[expr_terms[0]]
                        sub_expr = expr_terms[1].replace('_', ' ').replace('+', ' ')
                        expr_dict[col] = sub_expr
                    else: # If it's not a field key, let it be a regular search term
                        expr_list.append(expr)
                else:
                    expr_list.append(expr)
            expression = ' '.join(expr_list)
            self.view.model().setFilterColumns(expr_dict)

        self.view.model().setFilterCaseSensitivity(casesens)
        self.view.model().setFilterFixedString(expression)

    def s_plus_episode(self):
        self._busy(True)
        self.worker_call('set_episode', self.r_generic, self.selected_show_id, self.show_progress.value()+1)

    def s_rem_episode(self):
        if not self.show_progress.value() <= 0:
            self._busy(True)
            self.worker_call('set_episode', self.r_generic, self.selected_show_id, self.show_progress.value()-1)

    def s_set_episode(self, showid=None, ep=None):
        self._busy(True)
        self.worker_call('set_episode', self.r_generic, showid or self.selected_show_id, ep or self.show_progress.value())

    def s_set_score(self, showid=None, score=None):
        self._busy(True)

        if score is None:
            self.worker_call('set_score', self.r_generic, self.selected_show_id, self.show_score.value())
        else:
            self.worker_call('set_score', self.r_generic, showid, score)

    def s_set_status(self, index):
        if self.selected_show_id:
            self._busy(True)
            self.worker_call('set_status', self.r_generic, self.selected_show_id, self.mediainfo['statuses'][index])

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
        if self.selected_show_id:
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
        if self.selected_show_id:
            show = self.worker.engine.get_show_info(self.selected_show_id)
            reply = QMessageBox.question(self, 'Confirmation',
                'Are you sure you want to delete %s?' % show['title'],
                QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.worker_call('delete_show', self.r_generic, show)

    def s_scan_library(self):
        self.worker_call('scan_library', self.r_library_scanned, rescan=False)

    def s_rescan_library(self):
        self.worker_call('scan_library', self.r_library_scanned, rescan=True)

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
        current_status = self.notebook.tabData(self.notebook.currentIndex())

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
        (index, column_name, visible) = (w.data(), w.text(), w.isChecked())
        MIN_WIDTH = 30  # Width to restore columns to if too small to see

        if visible:
            if column_name not in self.api_config['visible_columns']:
                self.api_config['visible_columns'].append(str(column_name))
        else:
            if column_name in self.api_config['visible_columns']:
                self.api_config['visible_columns'].remove(column_name)

        self._save_config()

        self.view.setColumnHidden(index, not visible)
        if visible and self.view.columnWidth(index) < MIN_WIDTH:
            self.view.setColumnWidth(index, MIN_WIDTH)

    ### Worker slots
    def ws_changed_status(self, classname, msgtype, msg):
        if msgtype != messenger.TYPE_DEBUG:
            self.status('{}: {}'.format(classname, msg))
        elif self.debug:
            print('[D] {}: {}'.format(classname, msg))

    def ws_changed_show(self, show, is_playing=False, episode=None, altname=None):
        if show:
            if not self.view:
                return # List not built yet; can be safely avoided

            # Update the view of the updated show
            self.view.model().sourceModel().update(show['id'], is_playing)

            if show['id'] == self.selected_show_id:
                self._select_show(show)

            if is_playing and self.config['show_tray'] and self.config['notifications']:
                if episode == (show['my_progress'] + 1):
                    delay = self.worker.engine.get_config('tracker_update_wait_s')
                    self.tray.showMessage('Trackma Tracker', "Playing %s %s. Will update in %d seconds." % (show['title'], episode, delay))

    def ws_changed_show_status(self, show, old_status=None):
        # Update the view of the new show
        self.view.model().sourceModel().update(show['id'])

        # Update counts
        self.counts[show['my_status']] += 1
        self.counts[old_status] -= 1
        self._update_counts()

        # Set notebook to the new page
        self.notebook.setCurrentIndex( self.mediainfo['statuses'].index(show['my_status']) )
        # Refresh filter
        self.s_filter_changed()

    def ws_changed_list(self, show):
        self._rebuild_view()
        self._recalculate_counts()
        self.s_filter_changed()

    def ws_changed_queue(self, queue):
        self._update_queue_counter(queue)

    def ws_tracker_state(self, status):
        self._update_tracker_info(status)

    def ws_prompt_update(self, show, episode):
        reply = QMessageBox.question(self, 'Message',
            'Do you want to update %s to %d?' % (show['title'], episode),
            QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.worker_call('set_episode', self.r_generic, show['id'], episode)

    def ws_prompt_add(self, show, episode):
        page = self.notebook.currentIndex()
        current_status = self.mediainfo['statuses'][page]

        addwindow = AddDialog(None, self.worker, current_status, default=show['title'])
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

            # Set globals
            self.api_info = self.worker.engine.api_info
            self.mediainfo = self.worker.engine.mediainfo

            # Rebuild statuses
            self._rebuild_statuses()

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
                self.tray.setIcon(QtGui.QIcon(utils.available_libs[self.account['api']][1]))
            self.api_user.setText(self.worker.engine.get_userconfig('username'))
            self.setWindowTitle("Trackma-qt %s [%s (%s)]" % (utils.VERSION, self.api_info['name'], self.api_info['mediatype']))

            # Show tracker info
            tracker_info = self.worker.engine.tracker_status()
            if tracker_info:
                self._update_tracker_info(tracker_info)

            # Build our main view and show total counts
            self._rebuild_view()
            self._recalculate_counts()

            # Recover column state
            if self.config['remember_columns'] and isinstance(self.api_config['columns_state'], str):
                state = QtCore.QByteArray(base64.b64decode(self.api_config['columns_state']))
                self.view.horizontalHeader().restoreState(state)

            self.s_show_selected(None)

            self.status('Ready.')

        self._unbusy()

    def r_list_retrieved(self, result):
        if result['success']:
            self._rebuild_view()
            self._recalculate_counts()

            self.status('Ready.')

        self._unbusy()

    def r_library_scanned(self, result):
        if result['success']:
            self._rebuild_view()

            self.status('Ready.')

        self._unbusy()

    def r_engine_unloaded(self, result):
        if result['success']:
            self.close()
            if not self.finish:
                self.s_switch_account()

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
import os

pyqt_version = 0
skip_pyqt5 = "PYQT4" in os.environ  # TODO: Make this a program argument or something

if not skip_pyqt5:
    try:
        from PyQt5 import QtGui, QtCore
        from PyQt5.QtGui import QIcon, QPalette
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
        pyqt_version = 5
    except ImportError:
        print("Couldn't import Qt5 dependencies. "
              "Make sure you installed the PyQt5 package.")
if pyqt_version is 0:
    try:
        import sip
        sip.setapi('QVariant', 2)
        from PyQt4 import QtGui, QtCore
        from PyQt4.QtGui import (
            QApplication, QMainWindow, QFormLayout,
            QGridLayout, QHBoxLayout, QVBoxLayout,
            QAbstractItemView, QHeaderView, QListWidget,
            QListWidgetItem, QTabWidget, QTableWidget,
            QTableWidgetItem, QFrame, QScrollArea,
            QStackedWidget, QWidget, QCheckBox,
            QComboBox, QDoubleSpinBox, QGroupBox,
            QLineEdit, QPushButton, QRadioButton,
            QSpinBox, QStyleOptionButton, QToolButton,
            QProgressBar, QDialog, QColorDialog,
            QDialogButtonBox, QFileDialog, QInputDialog,
            QMessageBox, QAction, QActionGroup,
            QLabel, QMenu, QStyle,
            QSystemTrayIcon, QIcon, QPalette
        )
        from PyQt4.QtGui import QStyleOptionProgressBarV2 as QStyleOptionProgressBar
        pyqt_version = 4
    except ImportError:
        print("Couldn't import Qt dependencies. "
              "Make sure you installed the PyQt4 package.")
        sys.exit(-1)

import urllib.request
import base64
from io import BytesIO

from trackma.engine import Engine
from trackma.accounts import AccountManager
from trackma import messenger
from trackma import utils

try:
    from PIL import Image
    imaging_available = True
except ImportError:
    try:
        import Image
        imaging_available = True
    except ImportError:
        print("Warning: PIL or Pillow isn't available. "
              "Preview images will be disabled.")
        imaging_available = False

try:
    import dateutil.parser
    import dateutil.tz
    import datetime
    dateutil_available = True
except ImportError:
    print("Warning: DateUtil is unavailable. "
          "Next episode countdown will be disabled.")
    dateutil_available = False


class Trackma(QMainWindow):
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
        QApplication.setWindowIcon(QIcon(utils.datadir + '/data/icon.png'))
        self.setWindowTitle('Trackma-qt')

        self.accountman = AccountManager()

        # Go directly into the application if a default account is set
        # Open the selection dialog otherwise
        default = self.accountman.get_default()
        if default:
            self.start(default)
        else:
            self.accountman_create()
            accountman_widget.show()

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
        self.worker = Engine_Worker(account)
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
            self.ep_icons[key] = QIcon(buffer)
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

        #self.setMinimumSize(740, 480)
        if self.config['remember_geometry']:
            self.resize(self.config['last_width'], self.config['last_height'])
            self.move(self.config['last_x'], self.config['last_y'])

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

        if status == self.worker.engine.mediainfo['status_start']:
            for show in showlist:
                self._update_row( widget, i, show, altnames.get(show['id']), library.get(show['id']) )
                i += 1
        else:
            for show in showlist:
                self._update_row( widget, i, show, altnames.get(show['id']) )
                i += 1

        widget.setSortingEnabled(True)
        widget.sortByColumn(1, QtCore.Qt.AscendingOrder)

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
        and 'next_ep_time' in show \
        and dateutil_available:
            next_ep_dt = dateutil.parser.parse(show['next_ep_time'])
            delta = next_ep_dt - datetime.datetime.now(dateutil.tz.tzutc())
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
            self.show_progress_bar.setMaximum(show['total'])
            # Regenerate Play Episode Menu
            self.generate_episode_menus(self.menu_play, show['total'], show['my_progress'])
        else:
            self.show_progress.setMaximum(utils.estimate_aired_episodes(show) or 10000)
            self.generate_episode_menus(self.menu_play, utils.estimate_aired_episodes(show),show['my_progress'])

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
                if imaging_available:
                    self.show_image.setText('Waiting...')
                    self.image_timer.start()
                else:
                    self.show_image.setText('Not available')

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

    def s_download_image(self):
        show = self.worker.engine.get_show_info(self.selected_show_id)
        self.show_image.setText('Downloading...')
        filename = utils.get_filename('cache', "%s_%s_%s.jpg" % (self.api_info['shortname'], self.api_info['mediatype'], show['id']))

        self.image_worker = Image_Worker(show.get('image_thumb') or show['image'], filename, (100, 140))
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
        self._busy(True)
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
        addwindow = AddDialog(None, self.worker, None, default=show_title)
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

            # Set allowed ranges (this should be reported by the engine later)
            decimal_places = 0
            if isinstance(self.mediainfo['score_step'], float):
                decimal_places = len(str(self.mediainfo['score_step']).split('.')[1])

            self.show_score.setRange(0, self.mediainfo['score_max'])
            self.show_score.setDecimals(decimal_places)
            self.show_score.setSingleStep(self.mediainfo['score_step'])

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


class DetailsDialog(QDialog):
    def __init__(self, parent, worker, show):
        QDialog.__init__(self, parent)
        self.setMinimumSize(530, 550)
        self.setWindowTitle('Details')
        self.worker = worker

        main_layout = QVBoxLayout()
        details = DetailsWidget(self, worker)

        bottom_buttons = QDialogButtonBox(QDialogButtonBox.Close)
        bottom_buttons.setCenterButtons(True)
        bottom_buttons.rejected.connect(self.close)

        main_layout.addWidget(details)
        main_layout.addWidget(bottom_buttons)

        self.setLayout(main_layout)
        details.load(show)


class DetailsWidget(QWidget):
    def __init__(self, parent, worker):
        self.worker = worker

        QWidget.__init__(self, parent)

        # Build layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.show_title = QLabel()
        show_title_font = QtGui.QFont()
        show_title_font.setBold(True)
        show_title_font.setPointSize(12)
        self.show_title.setAlignment( QtCore.Qt.AlignCenter )
        self.show_title.setFont(show_title_font)

        info_area = QWidget()
        info_layout = QGridLayout()

        self.show_image = QLabel()
        self.show_image.setAlignment( QtCore.Qt.AlignTop )
        self.show_info = QLabel()
        self.show_info.setWordWrap(True)
        self.show_info.setAlignment( QtCore.Qt.AlignTop )
        self.show_description = QLabel()
        self.show_description.setWordWrap(True)
        self.show_description.setAlignment( QtCore.Qt.AlignTop )

        info_layout.addWidget( self.show_image,        0,0,1,1 )
        info_layout.addWidget( self.show_info,         1,0,1,1 )
        info_layout.addWidget( self.show_description,  0,1,2,1 )

        info_area.setLayout(info_layout)

        scroll_area = QScrollArea()
        scroll_area.setBackgroundRole(QPalette.Light)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(info_area)

        main_layout.addWidget(self.show_title)
        main_layout.addWidget(scroll_area)

        self.setLayout(main_layout)

    def worker_call(self, function, ret_function, *args, **kwargs):
        # Run worker in a thread
        self.worker.set_function(function, ret_function, *args, **kwargs)
        self.worker.start()

    def load(self, show):
        self.show_title.setText( "<a href=\"%s\">%s</a>" % (show['url'], show['title']) )
        self.show_title.setTextFormat(QtCore.Qt.RichText)
        self.show_title.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        self.show_title.setOpenExternalLinks(True)

        # Load show info
        self.show_info.setText('Wait...')
        self.worker_call('get_show_details', self.r_details_loaded, show)
        api_info = self.worker.engine.api_info

        # Load show image
        filename = utils.get_filename('cache', "%s_%s_f_%s.jpg" % (api_info['shortname'], api_info['mediatype'], show['id']))

        if os.path.isfile(filename):
            self.s_show_image(filename)
        else:
            self.show_image.setText('Downloading...')
            self.image_worker = Image_Worker(show['image'], filename)
            self.image_worker.finished.connect(self.s_show_image)
            self.image_worker.start()

    def s_show_image(self, filename):
        self.show_image.setPixmap( QtGui.QPixmap( filename ) )

    def r_details_loaded(self, result):
        if result['success']:
            details = result['details']

            info_strings = []
            description_strings = []
            description_keys = {'Synopsis', 'English', 'Japanese', 'Synonyms'} # This might come down to personal preference
            list_keys = {'Genres'} # Anilist gives genres as a list, need a special case to fix formatting

            for line in details['extra']:
                if line[0] and line[1]:
                    if line[0] in description_keys:
                        description_strings.append( "<h3>%s</h3><p>%s</p>" % (line[0], line[1]) )
                    else:
                        if line[0] in list_keys:
                            description_strings.append( "<h3>%s</h3><p>%s</p>" % (line[0], ', '.join(line[1])) )
                        elif len("%s" % line[1]) >= 17: # Avoid short tidbits taking up too much vertical space
                            info_strings.append( "<h3>%s</h3><p>%s</p>" % (line[0], line[1]) )
                        else:
                            info_strings.append( "<p><b>%s:</b> %s</p>" % (line[0], line[1]) )

            info_string = ''.join(info_strings)
            self.show_info.setText( info_string )
            description_string = ''.join(description_strings)
            self.show_description.setText( description_string )
        else:
            self.show_info.setText( 'There was an error while getting details.' )


class AddDialog(QDialog):
    worker = None
    selected_show = None

    def __init__(self, parent, worker, current_status, default=None):
        QMainWindow.__init__(self, parent)
        self.setMinimumSize(700, 500)
        self.setWindowTitle('Search/Add from Remote')
        self.worker = worker
        self.current_status = current_status
        self.default = default
        if default:
            self.setWindowTitle('Search/Add from Remote for new show: %s' % default)

        layout = QGridLayout()

        # Create top layout
        top_layout = QHBoxLayout()
        search_lbl = QLabel('Search terms:')
        self.search_txt = QLineEdit(self)
        self.search_txt.returnPressed.connect(self.s_search)
        self.search_txt.setFocus()
        if default:
            self.search_txt.setText(default)
        self.search_btn = QPushButton('Search')
        self.search_btn.clicked.connect(self.s_search)
        top_layout.addWidget(search_lbl)
        top_layout.addWidget(self.search_txt)
        top_layout.addWidget(self.search_btn)

        # Create table
        columns = ['Title', 'Type', 'Total']
        self.table = QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setGridStyle(QtCore.Qt.NoPen)
        if pyqt_version is 5:
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        else:
            self.table.horizontalHeader().setResizeMode(0, QHeaderView.Stretch)
        self.table.currentItemChanged.connect(self.s_show_selected)
        #self.table.doubleClicked.connect(self.s_show_details)

        bottom_buttons = QDialogButtonBox(self)
        bottom_buttons.addButton("Cancel", QDialogButtonBox.RejectRole)
        self.select_btn = bottom_buttons.addButton("Add", QDialogButtonBox.AcceptRole)
        bottom_buttons.accepted.connect(self.s_add)
        bottom_buttons.rejected.connect(self.close)

        # Info box
        self.details = DetailsWidget(self, worker)

        # Finish layout
        layout.addLayout(top_layout,     0, 0, 1, 2)
        layout.addWidget(self.table,     1, 0, 1, 1)
        layout.addWidget(self.details,   1, 1, 1, 1)
        layout.addWidget(bottom_buttons, 2, 0, 1, 2)
        self.setLayout(layout)

    def worker_call(self, function, ret_function, *args, **kwargs):
        # Run worker in a thread
        self.worker.set_function(function, ret_function, *args, **kwargs)
        self.worker.start()

    def _enable_widgets(self, enable):
        self.search_btn.setEnabled(enable)
        self.table.setEnabled(enable)

    # Slots
    def s_search(self):
        self.search_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.table.clearSelection()
        self.table.setEnabled(False)

        self.worker_call('search', self.r_searched, self.search_txt.text())

    def s_show_selected(self, new, old=None):
        if not new:
            return

        index = new.row()
        self.selected_show = self.results[index]
        self.details.load(self.selected_show)
        self.select_btn.setEnabled(True)

    def s_add(self):
        if self.selected_show:
            self.worker_call('add_show', self.r_added, self.selected_show, self.current_status)

    # Worker responses
    def r_searched(self, result):
        if result['success']:
            self.search_btn.setEnabled(True)
            self.table.setEnabled(True)

            self.results = result['results']

            self.table.setRowCount(len(self.results))
            i = 0
            for res in self.results:
                self.table.setRowHeight(i, QtGui.QFontMetrics(self.table.font()).height() + 2);
                self.table.setItem(i, 0, ShowItem(res['title']))
                self.table.setItem(i, 1, ShowItem(res['type']))
                self.table.setItem(i, 2, ShowItem(str(res['total'])))

                i += 1
            if self.table.currentRow() is 0:  # Row number hasn't changed but the data probably has!
                self.s_show_selected(self.table.item(0, 0))
            self.table.setCurrentItem(self.table.item(0, 0))
        else:
            self.table.setRowCount(0)

        self.search_btn.setEnabled(True)
        self.table.setEnabled(True)

    def r_added(self, result):
        if result['success']:
            if self.default:
                self.accept()


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
        self.tracker_type_local = QRadioButton('Local')
        self.tracker_type_local.toggled.connect(self.tracker_type_change)
        self.tracker_type_plex = QRadioButton('Plex media server')
        self.tracker_type_plex.toggled.connect(self.tracker_type_change)
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
        g_media_layout.addRow(self.tracker_type_local)
        g_media_layout.addRow(self.tracker_type_plex)
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
        self.plex_obey_wait = QCheckBox()

        g_plex_layout = QGridLayout()
        g_plex_layout.addWidget(QLabel('Host and Port'),                   0, 0, 1, 1)
        g_plex_layout.addWidget(self.plex_host,                            0, 1, 1, 1)
        g_plex_layout.addWidget(self.plex_port,                            0, 2, 1, 2)
        g_plex_layout.addWidget(QLabel('Use "wait before updating" time'), 1, 0, 1, 1)
        g_plex_layout.addWidget(self.plex_obey_wait,                       1, 2, 1, 1)

        g_plex.setLayout(g_plex_layout)

        # Group: Play Next
        g_playnext = QGroupBox('Play Next')
        g_playnext.setFlat(True)
        self.player = QLineEdit()
        self.player_browse = QPushButton('Browse...')
        self.player_browse.clicked.connect(self.s_player_browse)
        self.searchdir = QLineEdit()
        self.searchdir_browse = QPushButton('Browse...')
        self.searchdir_browse.clicked.connect(self.s_searchdir_browse)
        self.library_autoscan = QCheckBox()

        g_playnext_layout = QGridLayout()
        g_playnext_layout.addWidget(QLabel('Player'),                    0, 0, 1, 1)
        g_playnext_layout.addWidget(self.player,                         0, 1, 1, 1)
        g_playnext_layout.addWidget(self.player_browse,                  0, 2, 1, 1)
        g_playnext_layout.addWidget(QLabel('Media directory'),           1, 0, 1, 1)
        g_playnext_layout.addWidget(self.searchdir,                      1, 1, 1, 1)
        g_playnext_layout.addWidget(self.searchdir_browse,               1, 2, 1, 1)
        g_playnext_layout.addWidget(QLabel('Rescan Library at startup'), 2, 0, 1, 2)
        g_playnext_layout.addWidget(self.library_autoscan,               2, 2, 1, 1)

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
        self.filter_global = QCheckBox('Update filter for all lists (slow)')
        g_lists_layout = QFormLayout()
        g_lists_layout.addRow('Filter bar position:', self.filter_bar_position)
        g_lists_layout.addRow(self.filter_global)
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
        ep_bar_styles = [(EpisodeBar.BarStyleBasic,  'Basic'),
                         (EpisodeBar.BarStyle04,     'Trackma v0.4 Dual'),
                         (EpisodeBar.BarStyleHybrid, 'Hybrid Dual')]
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

    def _load(self):
        engine = self.worker.engine
        tracker_type = engine.get_config('tracker_type')
        autoretrieve = engine.get_config('autoretrieve')
        autosend = engine.get_config('autosend')

        self.tracker_enabled.setChecked(engine.get_config('tracker_enabled'))
        self.tracker_interval.setValue(engine.get_config('tracker_interval'))
        self.tracker_process.setText(engine.get_config('tracker_process'))
        self.tracker_update_wait.setValue(engine.get_config('tracker_update_wait_s'))
        self.tracker_update_close.setChecked(engine.get_config('tracker_update_close'))
        self.tracker_update_prompt.setChecked(engine.get_config('tracker_update_prompt'))
        self.tracker_not_found_prompt.setChecked(engine.get_config('tracker_not_found_prompt'))

        self.player.setText(engine.get_config('player'))
        self.searchdir.setText(engine.get_config('searchdir'))
        self.library_autoscan.setChecked(engine.get_config('library_autoscan'))
        self.plex_host.setText(engine.get_config('plex_host'))
        self.plex_port.setText(engine.get_config('plex_port'))
        self.plex_obey_wait.setChecked(engine.get_config('plex_obey_update_wait_s'))

        if tracker_type == 'local':
            self.tracker_type_local.setChecked(True)
            self.plex_host.setEnabled(False)
            self.plex_port.setEnabled(False)
            self.plex_obey_wait.setEnabled(False)
        elif tracker_type == 'plex':
            self.tracker_type_plex.setChecked(True)
            self.tracker_process.setEnabled(False)

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
        self.filter_global.setChecked(self.config['filter_global'])

        self.ep_bar_style.setCurrentIndex(self.ep_bar_style.findData(self.config['episodebar_style']))
        self.ep_bar_text.setChecked(self.config['episodebar_text'])

        self.autoretrieve_days_n.setEnabled(self.autoretrieve_days.isChecked())
        self.autosend_minutes_n.setEnabled(self.autosend_minutes.isChecked())
        self.autosend_size_n.setEnabled(self.autosend_size.isChecked())
        self.close_to_tray.setEnabled(self.tray_icon.isChecked())
        self.start_in_tray.setEnabled(self.tray_icon.isChecked())
        self.notifications.setEnabled(self.tray_icon.isChecked())

        self.color_values = self.config['colors'].copy()

    def _save(self):
        engine = self.worker.engine

        engine.set_config('tracker_enabled',       self.tracker_enabled.isChecked())
        engine.set_config('tracker_interval',      self.tracker_interval.value())
        engine.set_config('tracker_process',       str(self.tracker_process.text()))
        engine.set_config('tracker_update_wait_s', self.tracker_update_wait.value())
        engine.set_config('tracker_update_close',  self.tracker_update_close.isChecked())
        engine.set_config('tracker_update_prompt', self.tracker_update_prompt.isChecked())
        engine.set_config('tracker_not_found_prompt', self.tracker_not_found_prompt.isChecked())

        engine.set_config('player',            self.player.text())
        engine.set_config('searchdir',         self.searchdir.text())
        engine.set_config('library_autoscan',  self.library_autoscan.isChecked())
        engine.set_config('plex_host',         self.plex_host.text())
        engine.set_config('plex_port',         self.plex_port.text())
        engine.set_config('plex_obey_update_wait_s', self.plex_obey_wait.isChecked())

        if self.tracker_type_local.isChecked():
            engine.set_config('tracker_type', 'local')
        elif self.tracker_type_plex.isChecked():
            engine.set_config('tracker_type', 'plex')

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
        self.config['filter_global'] = self.filter_global.isChecked()

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
            self.tracker_type_local.setEnabled(True)
            self.tracker_type_plex.setEnabled(True)
            if self.tracker_type_local.isChecked():
                self.tracker_process.setEnabled(True)
                self.plex_host.setEnabled(False)
                self.plex_port.setEnabled(False)
                self.plex_obey_wait.setEnabled(False)
            elif self.tracker_type_plex.isChecked():
                self.plex_host.setEnabled(True)
                self.plex_port.setEnabled(True)
                self.plex_obey_wait.setEnabled(True)
                self.tracker_process.setEnabled(False)
        else:
            self.tracker_type_local.setEnabled(False)
            self.tracker_type_plex.setEnabled(False)
            self.plex_host.setEnabled(False)
            self.plex_port.setEnabled(False)
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
        if self.ep_bar_style.itemData(index) == EpisodeBar.BarStyle04:
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

    def s_searchdir_browse(self):
        self.searchdir.setText(QFileDialog.getExistingDirectory(caption='Choose media directory'))

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


class ThemedColorPicker(QDialog):
    def __init__(self, parent=None, default=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle('Select Color')
        layout = QVBoxLayout()
        colorbox = QGridLayout()
        self.colorString = default

        self.groups = [0, 1, 2]
        self.roles = [1, 2, 3, 4, 5, 11, 12, 16]  # Only use background roles
        self.colors = []
        row = 0
        # Make colored buttons for selection
        for group in self.groups:
            col = 0
            for role in self.roles:
                self.colors.append(QPushButton())
                self.colors[-1].setStyleSheet('background-color: ' + QtGui.QColor(QPalette().color(group, role)).name())
                self.colors[-1].setFocusPolicy(QtCore.Qt.NoFocus)
                self.colors[-1].clicked.connect(self.s_select(group, role))
                colorbox.addWidget(self.colors[-1], row, col, 1, 1)
                col += 1
            row += 1
        bottombox = QDialogButtonBox()
        bottombox.addButton(QDialogButtonBox.Ok)
        bottombox.addButton(QDialogButtonBox.Cancel)
        bottombox.accepted.connect(self.accept)
        bottombox.rejected.connect(self.reject)
        layout.addLayout(colorbox)
        layout.addWidget(bottombox)
        self.setLayout(layout)

    def s_select(self, group, role):
        return lambda: self.select(group, role)

    def select(self, group, role):
        self.colorString = str(group) + ',' + str(role)

    @staticmethod
    def do(parent=None, default=None):
        dialog = ThemedColorPicker(parent, default)
        result = dialog.exec_()

        if result == QDialog.Accepted:
            return dialog.colorString
        else:
            return None


class AccountDialog(QDialog):
    selected = QtCore.pyqtSignal(int, bool)
    aborted = QtCore.pyqtSignal()

    def __init__(self, parent, accountman):
        QDialog.__init__(self, parent)

        self.accountman = accountman

        layout = QVBoxLayout()

        self.setWindowTitle('Select Account')

        # Create list
        self.table = QTableWidget()
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setGridStyle(QtCore.Qt.NoPen)
        self.table.doubleClicked.connect(self.select)

        bottom_layout = QHBoxLayout()
        self.remember_chk = QCheckBox('Remember')
        if self.accountman.get_default() is not None:
            self.remember_chk.setChecked(True)
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.cancel)
        add_btn = QPushButton('Add')
        add_btn.clicked.connect(self.add)
        self.edit_btns = QComboBox()
        self.edit_btns.blockSignals(True)
        self.edit_btns.addItem('Edit...')
        self.edit_btns.addItem('Update')
        self.edit_btns.addItem('Delete')
        self.edit_btns.addItem('Purge')
        self.edit_btns.setItemData(1, 'Change the local password/PIN for this account', QtCore.Qt.ToolTipRole)
        self.edit_btns.setItemData(2, 'Remove this account from Trackma', QtCore.Qt.ToolTipRole)
        self.edit_btns.setItemData(3, 'Clear local DB for this account', QtCore.Qt.ToolTipRole)
        self.edit_btns.setCurrentIndex(0)
        self.edit_btns.blockSignals(False)
        self.edit_btns.activated.connect(self.s_edit)
        select_btn = QPushButton('Select')
        select_btn.clicked.connect(self.select)
        bottom_layout.addWidget(self.remember_chk)
        bottom_layout.addWidget(cancel_btn)
        bottom_layout.addWidget(add_btn)
        bottom_layout.addWidget(self.edit_btns)
        bottom_layout.addWidget(select_btn)

        # Get icons
        self.icons = dict()
        for libname, lib in utils.available_libs.items():
            self.icons[libname] = QIcon(lib[1])

        # Populate list
        self.rebuild()

        # Finish layout
        layout.addWidget(self.table)
        layout.addLayout(bottom_layout)
        self.setLayout(layout)

    def add(self):
        result = AccountAddDialog.do(icons=self.icons)
        if result:
            (username, password, api) = result
            self.accountman.add_account(username, password, api)
            self.rebuild()

    def edit(self):
        self.edit_btns.blockSignals(True)
        self.edit_btns.setCurrentIndex(0)
        self.edit_btns.blockSignals(False)
        try:
            selected_account_num = self.table.selectedItems()[0].num
            acct = self.accountman.get_account(selected_account_num)
            result = AccountAddDialog.do(icons=self.icons,
                                         edit=True,
                                         username=acct['username'],
                                         password=acct['password'],
                                         api=acct['api'])
            if result:
                (username, password, api) = result
                self.accountman.edit_account(selected_account_num, username, password, api)
                self.rebuild()
        except IndexError:
            self._error("Please select an account.")

    def delete(self):
        try:
            selected_account_num = self.table.selectedItems()[0].num
            reply = QMessageBox.question(self, 'Confirmation', 'Do you want to delete the selected account?', QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.accountman.delete_account(selected_account_num)
                self.rebuild()
        except IndexError:
            self._error("Please select an account.")

    def purge(self):
        try:
            selected_account_num = self.table.selectedItems()[0].num
            reply = QMessageBox.question(self, 'Confirmation', 'Do you want to purge the selected account\'s local data?', QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.accountman.purge_account(selected_account_num)
                self.rebuild()
        except IndexError:
            self._error("Please select an account.")

    def s_edit(self, index):
        if   index is 1:
            self.edit()
        elif index is 2:
            self.delete()
        elif index is 3:
            self.purge()

    def rebuild(self):
        self.table.clear()

        columns = ['Username', 'Site']
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(len(self.accountman.accounts['accounts']))

        accounts = self.accountman.get_accounts()
        i = 0
        for k, account in accounts:
            self.table.setRowHeight(i, QtGui.QFontMetrics(self.table.font()).height() + 2)
            self.table.setItem(i, 0, AccountItem(k, account['username']))
            self.table.setItem(i, 1, AccountItem(k, account['api'], self.icons.get(account['api'])))

            i += 1

        if pyqt_version is 5:
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        else:
            self.table.horizontalHeader().setResizeMode(0, QHeaderView.Stretch)

    def select(self, checked):
        try:
            selected_account_num = self.table.selectedItems()[0].num
            self.selected.emit(selected_account_num, self.remember_chk.isChecked())
            self.close()
        except IndexError:
            self._error("Please select an account.")

    def cancel(self, checked):
        self.aborted.emit()
        self.close()

    def _error(self, msg):
        QMessageBox.critical(self, 'Error', str(msg), QMessageBox.Ok)


class AccountItem(QTableWidgetItem):
    """
    Regular item able to save account item

    """
    num = None

    def __init__(self, num, text, icon=None):
        QTableWidgetItem.__init__(self, text)
        self.num = num
        if icon:
            self.setIcon(icon)


class ShowsTableWidget(QTableWidget):
    """
    Regular table widget with context menu for show actions.

    """
    def __init__(self, parent=None):
        QTableWidget.__init__(self, parent)

    def contextMenuEvent(self, event):
        action = self.context_menu.exec_(event.globalPos())


class ShowItem(QTableWidgetItem):
    """
    Regular item able to show colors and alignment

    """

    def __init__(self, text, color=None, alignment=None):
        QTableWidgetItem.__init__(self, text)
        if alignment:
            self.setTextAlignment(alignment)
        if color:
            self.setBackground(color)


class ShowItemNum(ShowItem):
    def __init__(self, num, text, color=None):
        ShowItem.__init__(self, text, color)
        self.setTextAlignment(QtCore.Qt.AlignHCenter)
        self.num = num

    def __lt__(self, other):
        return self.num < other.num


class ShowItemDate(ShowItem):
    def __init__(self, date, color=None):
        if date:
            try:
                datestr = date.strftime("%Y-%m-%d")
            except ValueError:
                datestr = '?'
        else:
            datestr = '-'

        self.date = date

        ShowItem.__init__(self, datestr, color, QtCore.Qt.AlignHCenter)

    def __lt__(self, other):
        if self.date and other.date:
            return self.date < other.date
        else:
            return True


class FilterBar():
    """
    Constants relating to filter bar settings can live here.
    """
    # Position
    PositionHidden = 0
    PositionAboveLists = 1
    PositionBelowLists = 2


class EpisodeBar(QProgressBar):
    """
  Custom progress bar to show detailed information
  about episodes
    """
    # Enum BarStyle
    BarStyleBasic = 0   # Basic native ProgressBar appearance
    BarStyle04 = 1      # Rectangular dual bar of Trackma v0.4
    BarStyleHybrid = 2  # Native ProgressBar with v0.4 library subbar overlaid

    _subvalue = -1
    _episodes = []
    _subheight = 5
    _bar_style = BarStyle04
    _show_text = False

    def __init__(self, parent, colors):
        QProgressBar.__init__(self, parent)
        self.colors = colors

    def paintEvent(self, event):
        rect = QtCore.QRect(0,0,self.width(), self.height())

        if self._bar_style is self.BarStyleBasic:
            painter = QtGui.QPainter(self)
            prog_options = QStyleOptionProgressBar()
            prog_options.maximum = self.maximum()
            prog_options.progress = self.value()
            prog_options.rect = rect
            prog_options.text = '%d%%' % (self.value()*100/self.maximum())
            prog_options.textVisible = self._show_text
            self.style().drawControl(QStyle.CE_ProgressBar, prog_options, painter)

        elif self._bar_style is self.BarStyle04:
            painter = QtGui.QPainter(self)
            painter.setBrush(getColor(self.colors['progress_bg']))
            painter.setPen(QtCore.Qt.transparent)
            painter.drawRect(rect)
            self.paintSubValue(painter)
            if self.value() > 0:
                if self.value() >= self.maximum():
                    painter.setBrush(getColor(self.colors['progress_complete']))
                    mid = self.width()
                else:
                    painter.setBrush(getColor(self.colors['progress_fg']))
                    mid = int(self.width() / float(self.maximum()) * self.value())
                progressRect = QtCore.QRect(0, 0, mid, self.height())
                painter.drawRect(progressRect)
            self.paintEpisodes(painter)

        elif self._bar_style is self.BarStyleHybrid:
            buffer = QtGui.QImage(self.width(), self.height(), QtGui.QImage.Format_ARGB32_Premultiplied)
            painter = QtGui.QPainter(buffer)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_Source)
            painter.fillRect(rect, QtCore.Qt.transparent)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            prog_options = QStyleOptionProgressBar()
            prog_options.maximum = self.maximum()
            prog_options.progress = self.value()
            prog_options.rect = rect
            prog_options.text = '%d%%' % (self.value()*100/self.maximum())
            self.style().drawControl(QStyle.CE_ProgressBar, prog_options, painter)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceAtop)
            painter.setPen(QtCore.Qt.transparent)
            self.paintSubValue(painter)
            self.paintEpisodes(painter)
            painter = QtGui.QPainter(self)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            painter.drawImage(rect, buffer)
            if self._show_text:
                self.style().drawControl(QStyle.CE_ProgressBarLabel, prog_options, painter)

    def paintSubValue(self, painter):
        if self.subValue() > 0:
            painter.setBrush(getColor(self.colors['progress_sub_bg']))
            mid = int(self.width() / float(self.maximum()) * self.subValue())
            progressRect = QtCore.QRect(
                0,
                self.height()-self._subheight,
                mid,
                self.height()-(self.height()-self._subheight)
            )
            painter.drawRect(progressRect)

    def paintEpisodes(self, painter):
        if self.episodes():
            for episode in self.episodes():
                painter.setBrush(getColor(self.colors['progress_sub_fg']))
                if episode <= self.maximum():
                    start = int(self.width() / float(self.maximum()) * (episode - 1))
                    finish = int(self.width() / float(self.maximum()) * episode)
                    progressRect = QtCore.QRect(
                        start,
                        self.height()-self._subheight,
                        finish-start,
                        self.height()-(self.height()-self._subheight)
                    )
                    painter.drawRect(progressRect)

    def setSubValue(self, subvalue):
        if subvalue > self.maximum():
            self._subvalue = self.maximum()
        else:
            self._subvalue = subvalue

        self.update()

    def subValue(self):
        return self._subvalue

    def setEpisodes(self, episodes):
        self._episodes = episodes
        self.update()

    def episodes(self):
        return self._episodes

    def setBarStyle(self, style, show_text):
        self._bar_style = style
        self._show_text = show_text


class AccountAddDialog(QDialog):
    def __init__(self, parent, icons, edit=False, username='', password='', api=''):
        QDialog.__init__(self, parent)
        self.edit = edit

        # Build UI
        layout = QVBoxLayout()

        formlayout = QFormLayout()
        self.lbl_username = QLabel('Username:')
        self.username = QLineEdit(username)

        pin_layout = QHBoxLayout()
        self.lbl_password = QLabel('Password:')
        self.password = QLineEdit(password)
        self.api = QComboBox()
        self.api.currentIndexChanged.connect(self.s_refresh)
        self.api_auth = QLabel('Request PIN')
        self.api_auth.setTextFormat(QtCore.Qt.RichText)
        self.api_auth.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        self.api_auth.setOpenExternalLinks(True)
        pin_layout.addWidget(self.password)
        pin_layout.addWidget(self.api_auth)

        formlayout.addRow(QLabel('Site:'), self.api)
        formlayout.addRow(self.lbl_username, self.username)
        formlayout.addRow(self.lbl_password, pin_layout)

        bottombox = QDialogButtonBox()
        bottombox.addButton(QDialogButtonBox.Save)
        bottombox.addButton(QDialogButtonBox.Cancel)
        bottombox.accepted.connect(self.validate)
        bottombox.rejected.connect(self.reject)

        # Populate APIs
        for libname, lib in sorted(utils.available_libs.items()):
            self.api.addItem(icons[libname], lib[0], libname)

        if self.edit:
            self.username.setEnabled(False)
            self.api.setCurrentIndex(self.api.findData(api, QtCore.Qt.UserRole))
            self.api.setEnabled(False)

        # Finish layouts
        layout.addLayout(formlayout)
        layout.addWidget(bottombox)

        self.setLayout(layout)

    def validate(self):
        if len(self.username.text()) is 0:
            if len(self.password.text()) is 0:
                self._error('Please fill the credentials fields.')
            else:
                self._error('Please fill the username field.')
        elif len(self.password.text()) is 0:
            self._error('Please fill the password/PIN field.')
        else:
            self.accept()

    def s_refresh(self, index):
        if not self.edit:
            self.username.setText("")
            self.password.setText("")

        if pyqt_version is 5:
            apiname = self.api.itemData(index)
        else:
            apiname = str(self.api.itemData(index))
        api = utils.available_libs[apiname]
        if api[2] == utils.LOGIN_OAUTH:
            apiname = str(self.api.itemData(index))
            url = utils.available_libs[apiname][4]
            self.api_auth.setText( "<a href=\"{}\">Request PIN</a>".format(url) )
            self.api_auth.show()

            self.lbl_username.setText('Name:')
            self.lbl_password.setText('PIN:')
            self.password.setEchoMode(QLineEdit.Normal)
        else:
            self.lbl_username.setText('Username:')
            self.lbl_password.setText('Password:')
            self.password.setEchoMode(QLineEdit.Password)
            self.api_auth.hide()

    def _error(self, msg):
        QMessageBox.critical(self, 'Error', msg, QMessageBox.Ok)

    @staticmethod
    def do(parent=None, icons=None, edit=False, username='', password='', api=''):
        dialog = AccountAddDialog(parent, icons, edit, username, password, api)
        result = dialog.exec_()

        if result == QDialog.Accepted:
            currentIndex = dialog.api.currentIndex()
            return (
                    str(dialog.username.text()),
                    str(dialog.password.text()),
                    str(dialog.api.itemData(currentIndex))
                   )
        else:
            return None


class Image_Worker(QtCore.QThread):
    """
    Image thread

    Downloads an image and shrinks it if necessary.

    """
    cancelled = False
    finished = QtCore.pyqtSignal(str)

    def __init__(self, remote, local, size=None):
        self.remote = remote
        self.local = local
        self.size = size
        super(Image_Worker, self).__init__()

    def __del__(self):
        self.wait()

    def run(self):
        self.cancelled = False

        req = urllib.request.Request(self.remote)
        req.add_header("User-agent", "TrackmaImage/{}".format(utils.VERSION))
        try:
            img_file = BytesIO(urllib.request.urlopen(req).read())
            if self.size:
                im = Image.open(img_file)
                im.thumbnail((self.size[0], self.size[1]), Image.ANTIALIAS)
                im.save(self.local)
            else:
                with open(self.local, 'wb') as f:
                    f.write(img_file.read())
        except urllib.error.URLError as e:
            print("Warning: Error getting image ({})".format(e))
            return

        if self.cancelled:
            return

        self.finished.emit(self.local)

    def cancel(self):
        self.cancelled = True


class Engine_Worker(QtCore.QThread):
    """
    Worker thread

    Contains the engine and manages every process in a separate thread.

    """
    engine = None
    function = None
    finished = QtCore.pyqtSignal(dict)

    # Message handler signals
    changed_status = QtCore.pyqtSignal(str, int, str)
    raised_error = QtCore.pyqtSignal(str)
    raised_fatal = QtCore.pyqtSignal(str)

    # Event handler signals
    changed_show = QtCore.pyqtSignal(dict)
    changed_list = QtCore.pyqtSignal(dict, object)
    changed_queue = QtCore.pyqtSignal(int)
    tracker_state = QtCore.pyqtSignal(int, int)
    playing_show = QtCore.pyqtSignal(dict, bool, int)
    prompt_for_update = QtCore.pyqtSignal(dict, int)
    prompt_for_add = QtCore.pyqtSignal(str, int)

    def __init__(self, account):
        super(Engine_Worker, self).__init__()
        self.engine = Engine(account, self._messagehandler)
        self.engine.connect_signal('episode_changed', self._changed_show)
        self.engine.connect_signal('score_changed', self._changed_show)
        self.engine.connect_signal('tags_changed', self._changed_show)
        self.engine.connect_signal('status_changed', self._changed_list)
        self.engine.connect_signal('playing', self._playing_show)
        self.engine.connect_signal('show_added', self._changed_list)
        self.engine.connect_signal('show_deleted', self._changed_list)
        self.engine.connect_signal('show_synced', self._changed_show)
        self.engine.connect_signal('queue_changed', self._changed_queue)
        self.engine.connect_signal('prompt_for_update', self._prompt_for_update)
        self.engine.connect_signal('prompt_for_add', self._prompt_for_add)
        self.engine.connect_signal('tracker_state', self._tracker_state)

        self.function_list = {
            'start': self._start,
            'reload': self._reload,
            'get_list': self._get_list,
            'set_episode': self._set_episode,
            'set_score': self._set_score,
            'set_status': self._set_status,
            'set_tags': self._set_tags,
            'play_episode': self._play_episode,
            'play_random': self._play_random,
            'list_download': self._list_download,
            'list_upload': self._list_upload,
            'get_show_details': self._get_show_details,
            'search': self._search,
            'add_show': self._add_show,
            'delete_show': self._delete_show,
            'unload': self._unload,
            'scan_library': self._scan_library,
        }

    def _messagehandler(self, classname, msgtype, msg):
        self.changed_status.emit(classname, msgtype, msg)

    def _error(self, msg):
        self.raised_error.emit(str(msg))

    def _fatal(self, msg):
        self.raised_fatal.emit(str(msg))

    def _changed_show(self, show, changes=None):
        self.changed_show.emit(show)

    def _changed_list(self, show, old_status=None):
        self.changed_list.emit(show, old_status)

    def _changed_queue(self, queue):
        self.changed_queue.emit(len(queue))

    def _tracker_state(self, state, timer):
        self.tracker_state.emit(state, timer)

    def _playing_show(self, show, is_playing, episode):
        self.playing_show.emit(show, is_playing, episode)

    def _prompt_for_update(self, show, episode):
        self.prompt_for_update.emit(show, episode)

    def _prompt_for_add(self, show_title, episode):
        self.prompt_for_add.emit(show_title, episode)

    # Callable functions
    def _start(self):
        try:
            self.engine.start()
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _reload(self, account, mediatype):
        try:
            self.engine.reload(account, mediatype)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _unload(self):
        try:
            self.engine.unload()
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _scan_library(self):
        try:
            self.engine.scan_library(rescan=True)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _get_list(self):
        try:
            showlist = self.engine.get_list()
            altnames = self.engine.altnames()
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True, 'showlist': showlist, 'altnames': altnames}

    def _set_episode(self, showid, episode):
        try:
            self.engine.set_episode(showid, episode)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _set_score(self, showid, score):
        try:
            self.engine.set_score(showid, score)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _set_status(self, showid, status):
        try:
            self.engine.set_status(showid, status)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _set_tags(self, showid, tags):
        try:
            self.engine.set_tags(showid, tags)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _play_episode(self, show, episode):
        try:
            played_ep = self.engine.play_episode(show, episode)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True, 'show': show, 'played_ep': played_ep}

    def _play_random(self):
        try:
            (show, ep) = self.engine.play_random()
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True, 'played_show': show, 'played_ep': ep}

    def _list_download(self):
        try:
            self.engine.list_download()
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _list_upload(self):
        try:
            self.engine.list_upload()
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _get_show_details(self, show):
        try:
            details = self.engine.get_show_details(show)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True, 'details': details}

    def _search(self, terms):
        try:
            results = self.engine.search(terms)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True, 'results': results}

    def _add_show(self, show, status):
        try:
            results = self.engine.add_show(show, status)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _delete_show(self, show):
        try:
            results = self.engine.delete_show(show)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def set_function(self, function, ret_function, *args, **kwargs):
        self.function = self.function_list[function]

        try:
            self.finished.disconnect()
        except Exception:
            pass

        if ret_function:
            self.finished.connect(ret_function)

        self.args = args
        self.kwargs = kwargs

    def __del__(self):
        self.wait()

    def run(self):
        try:
            ret = self.function(*self.args,**self.kwargs)
            self.finished.emit(ret)
        except utils.TrackmaFatal as e:
            self._fatal(e)


def getIcon(icon_name):
    fallback = QIcon(utils.datadir + '/data/qtui/{}.png'.format(icon_name))
    return QIcon.fromTheme(icon_name, fallback)


def getColor(colorString):
    # Takes a color string in either #RRGGBB format or group,role format (using QPalette int values)
    if colorString[0] == "#":
        return QtGui.QColor(colorString)
    else:
        (group, role) = [int(i) for i in colorString.split(',')]
        if (0 <= group <= 2) and (0 <= role <= 19):
            return QtGui.QColor(QPalette().color(group, role))
        else:
            # Failsafe - return black
            return QtGui.QColor()


def main():
    debug = False

    print("Trackma-qt v{}".format(utils.VERSION))

    if '-h' in sys.argv:
        print("Usage: trackma-qt [options]")
        print()
        print('Options:')
        print(' -d  Shows debugging information')
        print(' -h  Shows this help')
        return
    if '-d' in sys.argv:
        debug = True

    app = QApplication(sys.argv)
    try:
        mainwindow = Trackma(debug)
        sys.exit(app.exec_())
    except utils.TrackmaFatal as e:
        QMessageBox.critical(None, 'Fatal Error', "{0}".format(e), QMessageBox.Ok)

if __name__ == '__main__':
    main()

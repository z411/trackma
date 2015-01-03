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
    from PyQt4 import QtGui, QtCore
except ImportError:
    print ("Couldn't import Qt dependencies. Make sure you "
           "installed the PyQt4 package.")
    sys.exit(-1)

import os
from cStringIO import StringIO
import urllib2 as urllib

import trackma.messenger as messenger
import trackma.utils as utils

from trackma.engine import Engine
from trackma.accounts import AccountManager

try:
    import Image
    imaging_available = True
except ImportError:
    try:
        from PIL import Image
        imaging_available = True
    except ImportError:
        print "Warning: PIL or Pillow isn't available. Preview images will be disabled."
        imaging_available = False

class Trackma(QtGui.QMainWindow):
    """
    Main GUI class

    """
    config = None
    tray = None
    accountman = None
    worker = None
    image_worker = None
    started = False
    selected_show_id = None
    show_lists = None
    finish = False

    def __init__(self):
        QtGui.QMainWindow.__init__(self, None)

        # Load QT specific configuration
        self.configfile = utils.get_root_filename('ui-qt.json')
        self.config = utils.parse_config(self.configfile, utils.qt_defaults)
         
        # Build UI
        QtGui.QApplication.setWindowIcon(QtGui.QIcon(utils.datadir + '/data/icon.png'))
        self.setWindowTitle('Trackma-qt')
        
        self.accountman = AccountManager()
        self.accountman_widget = AccountDialog(None, self.accountman)
        self.accountman_widget.selected.connect(self.accountman_selected)

        # Go directly into the application if a default account is set
        # Open the selection dialog otherwise
        default = self.accountman.get_default()
        if default:
            self.start(default)
        else:
            self.accountman_widget.show()

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
        self.image_timer.setInterval(1000)
        self.image_timer.setSingleShot(True)
        self.image_timer.timeout.connect(self.s_download_image)
        
        self.busy_timer = QtCore.QTimer()
        self.busy_timer.setInterval(100)
        self.busy_timer.setSingleShot(True)
        self.busy_timer.timeout.connect(self.s_busy)
        
        # Build menus
        action_play_next = QtGui.QAction(QtGui.QIcon.fromTheme('media-playback-start'), 'Play &Next', self)
        action_play_next.setStatusTip('Play the next unwatched episode.')
        action_play_next.triggered.connect(lambda: self.s_play(True))
        action_details = QtGui.QAction('Show &details...', self)
        action_details.setStatusTip('Show detailed information about the selected show.')
        action_details.triggered.connect(self.s_show_details)
        action_altname = QtGui.QAction('Change &alternate name...', self)
        action_altname.setStatusTip('Set an alternate title for the tracker.')
        action_altname.triggered.connect(self.s_altname)
        action_add = QtGui.QAction(QtGui.QIcon.fromTheme('edit-find'), 'Search/Add from Remote', self)
        action_add.triggered.connect(self.s_add)
        action_delete = QtGui.QAction(QtGui.QIcon.fromTheme('edit-delete'), '&Delete', self)
        action_delete.setStatusTip('Remove this show from your list.')
        action_delete.triggered.connect(self.s_delete)
        action_quit = QtGui.QAction(QtGui.QIcon.fromTheme('application-exit'), '&Quit', self)
        action_quit.setStatusTip('Exit Trackma.')
        action_quit.triggered.connect(self._exit)

        action_sync = QtGui.QAction('&Sync', self)
        action_sync.setStatusTip('Send changes and then retrieve remote list')
        action_sync.triggered.connect(lambda: self.s_send(True))
        action_send = QtGui.QAction('Sen&d changes', self)
        action_send.setStatusTip('Upload any changes made to the list immediately.')
        action_send.triggered.connect(self.s_send)
        action_retrieve = QtGui.QAction('&Redownload list', self)
        action_retrieve.setStatusTip('Discard any changes made to the list and re-download it.')
        action_retrieve.triggered.connect(self.s_retrieve)
        
        action_reload = QtGui.QAction('Switch &Account', self)
        action_reload.setStatusTip('Switch to a different account.')
        action_reload.triggered.connect(self.s_switch_account)
        action_settings = QtGui.QAction('&Settings...', self)
        action_settings.triggered.connect(self.s_settings)

        action_about = QtGui.QAction(QtGui.QIcon.fromTheme('help-about'), 'About...', self)
        action_about.triggered.connect(self.s_about)
        action_about_qt = QtGui.QAction('About Qt...', self)
        action_about_qt.triggered.connect(self.s_about_qt)

        menubar = self.menuBar()
        self.menu_show = menubar.addMenu('&Show')
        self.menu_show.addAction(action_play_next)
        self.menu_show.addAction(action_details)
        self.menu_show.addAction(action_altname)
        self.menu_show.addSeparator()
        self.menu_show.addAction(action_add)
        self.menu_show.addAction(action_delete)
        self.menu_show.addSeparator()
        self.menu_show.addAction(action_quit)
        menu_list = menubar.addMenu('&List')
        menu_list.addAction(action_sync)
        menu_list.addSeparator()
        menu_list.addAction(action_send)
        menu_list.addAction(action_retrieve)
        self.menu_mediatype = menubar.addMenu('&Mediatype')
        self.mediatype_actiongroup = QtGui.QActionGroup(self, exclusive=True)
        self.mediatype_actiongroup.triggered.connect(self.s_mediatype)
        menu_options = menubar.addMenu('&Options')
        menu_options.addAction(action_reload)
        menu_options.addSeparator()
        menu_options.addAction(action_settings)
        menu_help = menubar.addMenu('&Help')
        menu_help.addAction(action_about)
        menu_help.addAction(action_about_qt)

        # Build layout
        main_layout = QtGui.QVBoxLayout()
        top_hbox = QtGui.QHBoxLayout()
        main_hbox = QtGui.QHBoxLayout()
        left_box = QtGui.QFormLayout()
        
        self.show_title = QtGui.QLabel('Trackma-qt')
        show_title_font = QtGui.QFont()
        show_title_font.setBold(True)
        show_title_font.setPointSize(12)
        self.show_title.setFont(show_title_font)

        self.api_icon = QtGui.QLabel('icon')
        self.api_user = QtGui.QLabel('user')

        top_hbox.addWidget(self.show_title, 1)
        top_hbox.addWidget(self.api_icon)
        top_hbox.addWidget(self.api_user)

        self.notebook = QtGui.QTabWidget()
        self.notebook.currentChanged.connect(self.s_tab_changed)
        self.setMinimumSize(740, 480)
        
        self.show_image = QtGui.QLabel('Trackma-qt')
        self.show_image.setFixedHeight( 149 )
        self.show_image.setFixedWidth( 100 )
        self.show_image.setAlignment( QtCore.Qt.AlignCenter )
        self.show_image.setStyleSheet("border: 1px solid #777;background-color:#999;text-align:center")
        show_progress_label = QtGui.QLabel('Progress')
        self.show_progress = QtGui.QSpinBox()
        self.show_progress_bar = QtGui.QProgressBar()
        self.show_progress_btn = QtGui.QPushButton('Update')
        self.show_progress_btn.clicked.connect(self.s_set_episode)
        self.show_play_btn = QtGui.QPushButton('Play')
        self.show_play_btn.clicked.connect(lambda: self.s_play(False))
        self.show_play_next_btn = QtGui.QPushButton('Next')
        self.show_play_next_btn.clicked.connect(lambda: self.s_play(True))
        show_score_label = QtGui.QLabel('Score')
        self.show_score = QtGui.QDoubleSpinBox()
        self.show_score_btn = QtGui.QPushButton('Set')
        self.show_score_btn.clicked.connect(self.s_set_score)
        self.show_status = QtGui.QComboBox()
        self.show_status.currentIndexChanged.connect(self.s_set_status)

        left_box.addRow(self.show_image)
        left_box.addRow(self.show_progress_bar)
        left_box.addRow(show_progress_label, self.show_progress)
        left_box.addRow(self.show_progress_btn)
        left_box.addRow(self.show_play_btn)
        left_box.addRow(show_score_label, self.show_score)
        left_box.addRow(self.show_score_btn)
        left_box.addRow(self.show_status)

        main_hbox.addLayout(left_box)
        main_hbox.addWidget(self.notebook, 1)

        main_layout.addLayout(top_hbox)
        main_layout.addLayout(main_hbox)

        self.main_widget = QtGui.QWidget(self)
        self.main_widget.setLayout(main_layout)
        self.setCentralWidget(self.main_widget)
        
        # Statusbar
        self.status_text = QtGui.QLabel('Trackma-qt')
        self.queue_text = QtGui.QLabel('Unsynced items: N/A')
        self.statusBar().addWidget(self.status_text, 1)
        self.statusBar().addWidget(self.queue_text)
        
        # Tray icon
        tray_menu = QtGui.QMenu(self)
        action_hide = QtGui.QAction('Show/Hide', self)
        action_hide.triggered.connect(self.s_hide)
        tray_menu.addAction(action_hide)
        tray_menu.addAction(action_quit)
        
        self.tray = QtGui.QSystemTrayIcon(self.windowIcon())
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self.s_tray_clicked)
        self._tray()

        # Connect worker signals
        self.worker.changed_status.connect(self.status)
        self.worker.raised_error.connect(self.error)
        self.worker.raised_fatal.connect(self.fatal)
        self.worker.changed_show.connect(self.ws_changed_show)
        self.worker.changed_list.connect(self.ws_changed_list)
        self.worker.changed_queue.connect(self.ws_changed_queue)
        self.worker.playing_show.connect(self.ws_changed_show)
        
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
        print unicode(message).encode('utf-8')
    
    def error(self, msg):
        self.status('Error: {}'.format(msg))
        QtGui.QMessageBox.critical(self, 'Error', msg, QtGui.QMessageBox.Ok)

    def fatal(self, msg):
        QtGui.QMessageBox.critical(self, 'Fatal Error', "Fatal Error! Reason:\n\n{0}".format(msg), QtGui.QMessageBox.Ok)
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
        self.finish = True
        self.worker_call('unload', self.r_engine_unloaded)

    def _enable_widgets(self, enable):
        self.notebook.setEnabled(enable)
        self.menuBar().setEnabled(enable)

        if self.selected_show_id:
            self.show_progress_btn.setEnabled(enable)
            self.show_score_btn.setEnabled(enable)
            self.show_play_btn.setEnabled(enable)
            self.show_play_next_btn.setEnabled(enable)
            self.show_status.setEnabled(enable)
    
    def _update_queue_counter(self, queue):
        self.queue_text.setText("Unsynced items: %d" % queue)
    
    def _tray(self):
        if self.tray.isVisible() and not self.config['show_tray']:
            self.tray.hide()
        elif not self.tray.isVisible() and self.config['show_tray']:
            self.tray.show()

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
    
    def _rebuild_lists(self, showlist, altnames):
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
            self._rebuild_list(status, filtered_list[status], altnames)


    def _rebuild_list(self, status, showlist=None, altnames=None):
        if not showlist:
            showlist = self.worker.engine.filter_list(status)
        if not altnames:
            altnames = self.worker.engine.altnames()

        widget = self.show_lists[status]
        columns = ['ID', 'Title', 'Progress', 'Score', 'Percent', 'Date']
        widget.clear()
        widget.setSortingEnabled(False)
        widget.setRowCount(len(showlist))
        widget.setColumnCount(len(columns))
        widget.setHorizontalHeaderLabels(columns)
        widget.setColumnHidden(0, True)
        widget.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Stretch)
        widget.horizontalHeader().resizeSection(2, 70)
        widget.horizontalHeader().resizeSection(3, 55)
        widget.horizontalHeader().resizeSection(4, 100)

        i = 0
        for show in showlist:
            self._update_row( widget, i, show, altnames.get(show['id']) )
            i += 1
        
        widget.setSortingEnabled(True)
        widget.sortByColumn(1, QtCore.Qt.AscendingOrder)
        
        # Update tab name with total
        tab_index = self.statuses_nums.index(status)
        tab_name = "%s (%d)" % (self.statuses_names[status], i)
        self.notebook.setTabText(tab_index, tab_name)

    def _update_row(self, widget, row, show, altname, is_playing=False):
        if is_playing:
            color = QtGui.QColor(150, 150, 250)
        else:
            color = self._get_color(show)
        
        title_str = show['title']
        if altname:
            title_str += " [%s]" % altname
        progress_str = "%d / %d" % (show['my_progress'], show['total'])
        percent_widget = QtGui.QProgressBar()
        percent_widget.setRange(0, 100)
        if show['total'] > 0:
            percent_widget.setValue( 100L * show['my_progress'] / show['total'] )

        widget.setRowHeight(row, QtGui.QFontMetrics(widget.font()).height() + 2);
        widget.setItem(row, 0, ShowItem( str(show['id']), color ))
        widget.setItem(row, 1, ShowItem( title_str, color ))
        widget.setItem(row, 2, ShowItemNum( show['my_progress'], progress_str, color ))
        widget.setItem(row, 3, ShowItemNum( show['my_score'], str(show['my_score']), color ))
        widget.setCellWidget(row, 4, percent_widget )
        widget.setItem(row, 5, ShowItemDate( show['start_date'], color ))

    def _get_color(self, show):
        if show.get('queued'):
            return QtGui.QColor(210, 250, 210)
        elif show.get('neweps'):
            return QtGui.QColor(250, 250, 130)
        elif show['status'] == 1:
            return QtGui.QColor(210, 250, 250)
        elif show['status'] == 3:
            return QtGui.QColor(250, 250, 210)
        else:
            return None
    
    def _get_row_from_showid(self, widget, showid):
        # identify the row this show is in the table
        for row in xrange(0, widget.rowCount()):
            if widget.item(row, 0).text() == str(showid):
                return row

        return None

    ### Slots
    def s_hide(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
    
    def s_tray_clicked(self, reason):
        if reason == QtGui.QSystemTrayIcon.Trigger:
            self.s_hide()

    def s_busy(self):
        self._enable_widgets(False)
        
    def s_show_selected(self, new, old=None):
        if not new:
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
            self.show_play_btn.setEnabled(False)
            self.show_play_next_btn.setEnabled(False)
            return
        
        index = new.row()
        selected_id = self.notebook.currentWidget().item( index, 0 ).text()

        # Attempt to convert to int if possible
        try:
            selected_id = int(selected_id)
        except ValueError:
            selected_id = str(selected_id)

        show = self.worker.engine.get_show_info(selected_id)
        
        # Block signals
        self.show_status.blockSignals(True)

        # Set proper ranges
        if show['total']:
            self.show_progress.setRange(0, show['total'])
        else:
            self.show_progress.setRange(0, 5000)

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
        self.show_play_btn.setEnabled(True)
        self.show_play_next_btn.setEnabled(True)
        self.show_status.setEnabled(True)
 
        # Download image or use cache
        if show.get('image'):
            if self.image_worker is not None:
                self.image_worker.cancel()

            utils.make_dir('cache')
            filename = utils.get_filename('cache', "%s.jpg" % show['id'])

            if os.path.isfile(filename):
                self.s_show_image(filename)
            else:
                if imaging_available:
                    self.show_image.setText('Waiting...')
                    self.image_timer.start()
                else:
                    self.show_image.setText('Not available')
               
        if show['total'] > 0:
            self.show_progress_bar.setValue( 100L * show['my_progress'] / show['total'] )
        else:
            self.show_progress_bar.setValue( 0 )

        # Make it global
        self.selected_show_id = selected_id

        # Unblock signals
        self.show_status.blockSignals(False)

    def s_download_image(self):
        show = self.worker.engine.get_show_info(self.selected_show_id)
        self.show_image.setText('Downloading...')
        filename = utils.get_filename('cache', "%s.jpg" % show['id'])
    
        self.image_worker = Image_Worker(show['image'], filename, (100, 140))
        self.image_worker.finished.connect(self.s_show_image)
        self.image_worker.start()
    
    def s_tab_changed(self):
        item = self.notebook.currentWidget().currentItem()
        if item:
            self.s_show_selected(item)

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
    
    def s_play(self, play_next):
        if self.selected_show_id:
            show = self.worker.engine.get_show_info(self.selected_show_id)

            episode = 0 # Engine plays next unwatched episode
            if not play_next:
                episode = self.show_progress.value()

            self._busy(False)
            self.worker_call('play_episode', self.r_played, show, episode)

    def s_delete(self):
        show = self.worker.engine.get_show_info(self.selected_show_id)
        reply = QtGui.QMessageBox.question(self, 'Confirmation',
            'Are you sure you want to delete %s?' % show['title'],
            QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
        
        if reply == QtGui.QMessageBox.Yes:
            self.worker_call('delete_show', self.r_generic, show)

    def s_altname(self):
        show = self.worker.engine.get_show_info(self.selected_show_id)
        current_altname = self.worker.engine.altname(self.selected_show_id)

        new_altname, ok = QtGui.QInputDialog.getText(self, 'Alternative title',
            'Set the new alternative title for %s (blank to remove):' % show['title'],
            text=current_altname)

        if ok:
            self.worker.engine.altname(self.selected_show_id, str(new_altname))
            self.ws_changed_show(show, altname=new_altname)

    def s_retrieve(self):
        queue = self.worker.engine.get_queue()

        if queue:
            reply = QtGui.QMessageBox.question(self, 'Confirmation',
                'There are %d unsynced changes. Do you want to send them first? (Choosing No will discard them!)' % len(queue),
                QtGui.QMessageBox.Yes, QtGui.QMessageBox.No, QtGui.QMessageBox.Cancel)
            
            if reply == QtGui.QMessageBox.Yes:
                self.s_send(True)
            elif reply == QtGui.QMessageBox.No:
                self._busy(True)
                self.worker.engine.undoall()
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
        self.addwindow = AddDialog(None, self.worker)
        self.addwindow.setModal(True)
        self.addwindow.show()
    
    def s_mediatype(self, action):
        index = action.data().toInt()[0]
        mediatype = self.api_info['supported_mediatypes'][index]
        self.reload(None, mediatype)
    
    def s_settings(self):
        dialog = SettingsDialog(None, self.worker, self.config, self.configfile)
        dialog.saved.connect(self._tray)
        dialog.exec_()
                    
    def s_about(self):
        QtGui.QMessageBox.about(self, 'About Trackma-qt %s' % utils.VERSION,
            '<p><b>About Trackma-qt %s</b></p><p>Trackma is an open source client for media tracking websites.</p>'
            '<p>This program is licensed under the GPLv3, for more information read COPYING file.</p>'
            '<p>Copyright (C) z411 - Icon by shuuichi</p>'
            '<p><a href="http://github.com/z411/trackma">http://github.com/z411/trackma</a></p>' % utils.VERSION)

    def s_about_qt(self):
        QtGui.QMessageBox.aboutQt(self, 'About Qt')
        

    ### Worker slots
    def ws_changed_show(self, show, is_playing=False, episode=None, altname=None):
        if show:
            if not self.show_lists:
                return # Lists not built yet; can be safely avoided

            widget = self.show_lists[show['my_status']]
            row = self._get_row_from_showid(widget, show['id'])
            
            if row is None:
                return # Row not in list yet; can be safely avoided
            
            widget.setSortingEnabled(False)
            self._update_row(widget, row, show, altname, is_playing)
            widget.setSortingEnabled(True)

            if is_playing and self.config['show_tray'] and self.config['notifications']:
                if episode == (show['my_progress'] + 1):
                    delay = self.worker.engine.get_config('tracker_update_wait')
                    self.tray.showMessage('Trackma Tracker', "Playing %s %s. Will update in %d minutes." % (show['title'], episode, delay))
        
    def ws_changed_list(self, show, old_status=None):
        # Rebuild both new and old (if any) lists
        self._rebuild_list(show['my_status'])
        if old_status:
            self._rebuild_list(old_status)
        
        # Set notebook to the new page
        self.notebook.setCurrentIndex( self.statuses_nums.index(show['my_status']) )
    
    def ws_changed_queue(self, queue):
        self._update_queue_counter(queue)

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
            if isinstance( self.mediainfo['score_step'], float ):
                decimal_places = len(str(self.mediainfo['score_step']).split('.')[1])

            self.show_score.setRange(0, self.mediainfo['score_max'])
            self.show_score.setDecimals(decimal_places)
            self.show_score.setSingleStep(self.mediainfo['score_step'])
            
            # Build notebook
            for status in self.statuses_nums:
                name = self.statuses_names[status]

                self.show_lists[status] = QtGui.QTableWidget()
                self.show_lists[status].setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
                #self.show_lists[status].setFocusPolicy(QtCore.Qt.NoFocus)
                self.show_lists[status].setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
                self.show_lists[status].setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
                self.show_lists[status].horizontalHeader().setHighlightSections(False)
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
                action = QtGui.QAction(mediatype, self, checkable=True)
                if mediatype == self.api_info['mediatype']:
                    action.setChecked(True)
                else:
                    action.setData(n)
                self.mediatype_actiongroup.addAction(action)
                self.menu_mediatype.addAction(action)
            
            # Show API info
            self.api_icon.setPixmap( QtGui.QPixmap( utils.available_libs[self.account['api']][1] ) )
            self.api_user.setText( self.account['username'] )
            self.setWindowTitle( "Trackma-qt %s [%s (%s)]" % (utils.VERSION, self.api_info['name'], self.api_info['mediatype']) )

            # Rebuild lists
            self._rebuild_lists(showlist, altnames)
            
            self.s_show_selected(None)
            self._update_queue_counter( len( self.worker.engine.get_queue() ) )
            
            self.status('Ready.')
            
        self._unbusy()
    
    def r_list_retrieved(self, result):
        if result['success']:
            showlist = self.worker.engine.get_list()
            altnames = self.worker.engine.altnames()
            self._rebuild_lists(showlist, altnames)
            
            self.status('Ready.')
            
        self._unbusy()
        
    def r_engine_unloaded(self, result):
        if result['success']:
            self.close()
            if not self.finish:
                self.s_switch_account()

    def r_played(self, result):
        self._unbusy()
        self.status('Ready.')

        if result['success']:
            show = result['show']
            played_ep = result['played_ep']
            
            if played_ep == (show['my_progress'] + 1):
                reply = QtGui.QMessageBox.question(self, 'Message',
                    'Do you want to update the show to %d?' % result['played_ep'],
                    QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

                if reply == QtGui.QMessageBox.Yes:
                    self.worker_call('set_episode', self.r_generic, show['id'], played_ep)


class DetailsDialog(QtGui.QDialog):
    def __init__(self, parent, worker, show):
        QtGui.QDialog.__init__(self, parent)
        self.setMinimumSize(530, 550)
        self.setWindowTitle('Details')
        self.worker = worker

        main_layout = QtGui.QVBoxLayout()
        details = DetailsWidget(self, worker)
        
        bottom_buttons = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Close)
        bottom_buttons.setCenterButtons(True)
        bottom_buttons.rejected.connect(self.close)

        main_layout.addWidget(details)
        main_layout.addWidget(bottom_buttons)

        self.setLayout(main_layout)
        details.load(show)
        
class DetailsWidget(QtGui.QWidget):
    def __init__(self, parent, worker):
        self.worker = worker

        QtGui.QWidget.__init__(self, parent)

        # Build layout
        main_layout = QtGui.QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.show_title = QtGui.QLabel()
        show_title_font = QtGui.QFont()
        show_title_font.setBold(True)
        show_title_font.setPointSize(12)
        self.show_title.setAlignment( QtCore.Qt.AlignCenter )
        self.show_title.setFont(show_title_font)
        
        info_area = QtGui.QWidget()
        info_layout = QtGui.QHBoxLayout()
        
        self.show_image = QtGui.QLabel()
        self.show_image.setAlignment( QtCore.Qt.AlignTop )
        self.show_info = QtGui.QLabel()
        self.show_info.setWordWrap(True)
        self.show_info.setAlignment( QtCore.Qt.AlignTop )
        
        info_layout.addWidget( self.show_image )
        info_layout.addWidget( self.show_info, 1 )
        
        info_area.setLayout(info_layout)
        
        scroll_area = QtGui.QScrollArea()
        scroll_area.setBackgroundRole(QtGui.QPalette.Light)
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
        
        # Load show image
        filename = utils.get_filename('cache', "f_%s.jpg" % show['id'])
        
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
            for line in details['extra']:
                if line[0] and line[1]:
                    info_strings.append( "<h3>%s</h3><p>%s</p>" % (line[0], line[1]) )
        
            info_string = ''.join(info_strings)
            self.show_info.setText( info_string )
        else:
            self.show_info.setText( 'There was an error while getting details.' )

class AddDialog(QtGui.QDialog):
    worker = None
    selected_show = None

    def __init__(self, parent, worker):
        QtGui.QMainWindow.__init__(self, parent)
        self.setMinimumSize(700, 500)
        self.setWindowTitle('Search/Add from Remote')
        self.worker = worker
    
        layout = QtGui.QGridLayout()
        
        # Create top layout
        top_layout = QtGui.QHBoxLayout()
        search_lbl = QtGui.QLabel('Search terms:')
        self.search_txt = QtGui.QLineEdit(self)
        self.search_txt.returnPressed.connect(self.s_search)
        self.search_txt.setFocus()
        self.search_btn = QtGui.QPushButton('Search')
        self.search_btn.clicked.connect(self.s_search)
        top_layout.addWidget(search_lbl)
        top_layout.addWidget(self.search_txt)
        top_layout.addWidget(self.search_btn)
        
        # Create table
        columns = ['Title', 'Type', 'Total']
        self.table = QtGui.QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setGridStyle(QtCore.Qt.NoPen)
        self.table.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.table.currentItemChanged.connect(self.s_show_selected)
        #self.table.doubleClicked.connect(self.s_show_details)
        
        bottom_buttons = QtGui.QDialogButtonBox(self)
        bottom_buttons.addButton("Cancel", QtGui.QDialogButtonBox.RejectRole)
        self.select_btn = bottom_buttons.addButton("Add", QtGui.QDialogButtonBox.AcceptRole)
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
            self.worker_call('add_show', self.r_added, self.selected_show)
    
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
        else:
            self.table.setRowCount(0)

        self.search_btn.setEnabled(True)
        self.table.setEnabled(True)
    
    def r_added(self, result):
        if result['success']:
            pass
        

class SettingsDialog(QtGui.QDialog):
    worker = None
    config = None
    configfile = None

    saved = QtCore.pyqtSignal()
    
    def __init__(self, parent, worker, config, configfile):
        QtGui.QDialog.__init__(self, parent)
        
        self.worker = worker
        self.config = config
        self.configfile = configfile
        self.setStyleSheet("QGroupBox { font-weight: bold; } ")
        self.setWindowTitle('Settings')
        layout = QtGui.QGridLayout()
        
        # Categories
        self.category_list = QtGui.QListWidget()
        category_media = QtGui.QListWidgetItem(QtGui.QIcon.fromTheme('media-playback-start'), 'Media', self.category_list)
        category_sync = QtGui.QListWidgetItem(QtGui.QIcon.fromTheme('view-refresh'), 'Sync', self.category_list)
        category_ui = QtGui.QListWidgetItem(QtGui.QIcon.fromTheme('window-new'), 'User Interface', self.category_list)
        self.category_list.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.category_list.setCurrentRow(0)
        self.category_list.setMaximumWidth(self.category_list.sizeHintForColumn(0) + 15)
        self.category_list.setFocus()
        self.category_list.currentItemChanged.connect(self.s_switch_page)
        
        # Media tab
        page_media = QtGui.QWidget()
        page_media_layout = QtGui.QVBoxLayout()
        page_media_layout.setAlignment(QtCore.Qt.AlignTop)
        
        # Group: Media settings
        g_media = QtGui.QGroupBox('Media settings')
        g_media.setFlat(True)
        g_media_layout = QtGui.QFormLayout()
        self.tracker_enabled = QtGui.QCheckBox()
        self.tracker_interval = QtGui.QSpinBox()
        self.tracker_interval.setRange(5, 1000)
        self.tracker_interval.setMaximumWidth(60)
        self.tracker_process = QtGui.QLineEdit()
        self.tracker_update_wait = QtGui.QSpinBox()
        self.tracker_update_wait.setRange(0, 1000)
        self.tracker_update_wait.setMaximumWidth(60)
        g_media_layout.addRow( 'Enable tracker', self.tracker_enabled )
        g_media_layout.addRow( 'Tracker interval (seconds)', self.tracker_interval )
        g_media_layout.addRow( 'Process name (regex)', self.tracker_process )
        g_media_layout.addRow( 'Wait before updating (minutes)', self.tracker_update_wait )

        g_media.setLayout(g_media_layout)

        # Group: Play Next
        g_playnext = QtGui.QGroupBox('Play Next')
        g_playnext.setFlat(True)
        self.player = QtGui.QLineEdit()
        self.player_browse = QtGui.QPushButton('Browse...')
        self.player_browse.clicked.connect(self.s_player_browse)
        self.searchdir = QtGui.QLineEdit()
        self.searchdir_browse = QtGui.QPushButton('Browse...')
        self.searchdir_browse.clicked.connect(self.s_searchdir_browse)

        g_playnext_layout = QtGui.QGridLayout()
        g_playnext_layout.addWidget( QtGui.QLabel('Player'),            0, 0, 1, 1)
        g_playnext_layout.addWidget( self.player,                       0, 1, 1, 1)
        g_playnext_layout.addWidget( self.player_browse,                0, 2, 1, 1)
        g_playnext_layout.addWidget( QtGui.QLabel('Media directory'),   1, 0, 1, 1)
        g_playnext_layout.addWidget( self.searchdir,                    1, 1, 1, 1)
        g_playnext_layout.addWidget( self.searchdir_browse,             1, 2, 1, 1)

        g_playnext.setLayout(g_playnext_layout)
       
        # Media form
        page_media_layout.addWidget(g_media)
        page_media_layout.addWidget(g_playnext)
        page_media.setLayout(page_media_layout)
        
        # Sync tab
        page_sync = QtGui.QWidget()
        page_sync_layout = QtGui.QVBoxLayout()
        page_sync_layout.setAlignment(QtCore.Qt.AlignTop)
        
        # Group: Autoretrieve
        g_autoretrieve = QtGui.QGroupBox('Autoretrieve')
        g_autoretrieve.setFlat(True)
        self.autoretrieve_off = QtGui.QRadioButton('Disabled')
        self.autoretrieve_always = QtGui.QRadioButton('Always at start')
        self.autoretrieve_days = QtGui.QRadioButton('After n days')
        self.autoretrieve_days.toggled.connect(self.s_autoretrieve_days)
        self.autoretrieve_days_n = QtGui.QSpinBox()
        self.autoretrieve_days_n.setRange(1, 100)
        g_autoretrieve_layout = QtGui.QGridLayout()
        g_autoretrieve_layout.setColumnStretch(0, 1)
        g_autoretrieve_layout.addWidget(self.autoretrieve_off,      0, 0, 1, 1)
        g_autoretrieve_layout.addWidget(self.autoretrieve_always,   1, 0, 1, 1)
        g_autoretrieve_layout.addWidget(self.autoretrieve_days,     2, 0, 1, 1)
        g_autoretrieve_layout.addWidget(self.autoretrieve_days_n,   2, 1, 1, 1)
        g_autoretrieve.setLayout(g_autoretrieve_layout)

        # Group: Autosend
        g_autosend = QtGui.QGroupBox('Autosend')
        g_autosend.setFlat(True)
        self.autosend_off = QtGui.QRadioButton('Disabled')
        self.autosend_always = QtGui.QRadioButton('Immediately after every change')
        self.autosend_hours = QtGui.QRadioButton('After n hours')
        self.autosend_hours.toggled.connect(self.s_autosend_hours)
        self.autosend_hours_n = QtGui.QSpinBox()
        self.autosend_hours_n.setRange(1, 1000)
        self.autosend_size = QtGui.QRadioButton('After the queue reaches n items')
        self.autosend_size.toggled.connect(self.s_autosend_size)
        self.autosend_size_n = QtGui.QSpinBox()
        self.autosend_size_n.setRange(2, 20)
        self.autosend_at_exit = QtGui.QCheckBox('At exit')
        g_autosend_layout = QtGui.QGridLayout()
        g_autosend_layout.setColumnStretch(0, 1)
        g_autosend_layout.addWidget(self.autosend_off,      0, 0, 1, 1)
        g_autosend_layout.addWidget(self.autosend_always,   1, 0, 1, 1)
        g_autosend_layout.addWidget(self.autosend_hours,    2, 0, 1, 1)
        g_autosend_layout.addWidget(self.autosend_hours_n,  2, 1, 1, 1)
        g_autosend_layout.addWidget(self.autosend_size,     3, 0, 1, 1)
        g_autosend_layout.addWidget(self.autosend_size_n,   3, 1, 1, 1)
        g_autosend_layout.addWidget(self.autosend_at_exit,  4, 0, 1, 1)
        g_autosend.setLayout(g_autosend_layout)

        # Group: Extra
        g_extra = QtGui.QGroupBox('Additional options')
        g_extra.setFlat(True)
        self.auto_status_change = QtGui.QCheckBox('Change status automatically')
        self.auto_status_change.toggled.connect(self.s_auto_status_change)
        self.auto_status_change_if_scored = QtGui.QCheckBox('Change status automatically only if scored')
        self.auto_date_change = QtGui.QCheckBox('Change start and finish dates automatically')
        g_extra_layout = QtGui.QVBoxLayout()
        g_extra_layout.addWidget(self.auto_status_change)
        g_extra_layout.addWidget(self.auto_status_change_if_scored)
        g_extra_layout.addWidget(self.auto_date_change)
        g_extra.setLayout(g_extra_layout)
        
        # Sync layout
        page_sync_layout.addWidget( g_autoretrieve )
        page_sync_layout.addWidget( g_autosend )
        page_sync_layout.addWidget( g_extra )
        page_sync.setLayout(page_sync_layout)
        
        # UI tab
        page_ui = QtGui.QWidget()
        page_ui_layout = QtGui.QFormLayout()
        page_ui_layout.setAlignment(QtCore.Qt.AlignTop)
        
        # Group: Icon
        g_icon = QtGui.QGroupBox('Notification Icon')
        g_icon.setFlat(True)
        self.tray_icon = QtGui.QCheckBox('Show tray icon')
        self.tray_icon.toggled.connect(self.s_tray_icon)
        self.close_to_tray = QtGui.QCheckBox('Close to tray')
        self.start_in_tray = QtGui.QCheckBox('Start minimized to tray')
        self.notifications = QtGui.QCheckBox('Show notification when tracker detects new media')
        g_icon_layout = QtGui.QVBoxLayout()
        g_icon_layout.addWidget(self.tray_icon)
        g_icon_layout.addWidget(self.close_to_tray)
        g_icon_layout.addWidget(self.start_in_tray)
        g_icon_layout.addWidget(self.notifications)
        g_icon.setLayout(g_icon_layout)

        # UI layout
        page_ui_layout.addWidget(g_icon)
        page_ui.setLayout(page_ui_layout)
        
        # Content
        self.contents = QtGui.QStackedWidget()
        self.contents.addWidget(page_media)
        self.contents.addWidget(page_sync)
        self.contents.addWidget(page_ui)
        self.contents.layout().setMargin(0)
        
        # Bottom buttons
        bottombox = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok|QtGui.QDialogButtonBox.Apply|QtGui.QDialogButtonBox.Cancel)
        bottombox.accepted.connect(self.s_save)
        bottombox.button(QtGui.QDialogButtonBox.Apply).clicked.connect(self._save)
        bottombox.rejected.connect(self.reject)
        
        # Main layout finish
        layout.addWidget(self.category_list,  0, 0, 1, 1)
        layout.addWidget(self.contents,       0, 1, 1, 1)
        layout.addWidget(bottombox,           1, 0, 1, 2)
        layout.setColumnStretch(1, 1)
        
        self._load()

        self.setLayout(layout)
    
    def _load(self):
        engine = self.worker.engine
        autoretrieve = engine.get_config('autoretrieve')
        autosend = engine.get_config('autosend')

        self.tracker_enabled.setChecked(engine.get_config('tracker_enabled'))
        self.tracker_interval.setValue(engine.get_config('tracker_interval'))
        self.tracker_process.setText(engine.get_config('tracker_process'))
        self.tracker_update_wait.setValue(engine.get_config('tracker_update_wait'))

        self.player.setText(engine.get_config('player'))
        self.searchdir.setText(engine.get_config('searchdir'))

        if autoretrieve == 'always':
            self.autoretrieve_always.setChecked(True)
        elif autoretrieve == 'days':
            self.autoretrieve_days.setChecked(True)
        else:
            self.autoretrieve_off.setChecked(True)

        self.autoretrieve_days_n.setValue(engine.get_config('autoretrieve_days'))

        if autosend == 'always':
            self.autosend_always.setChecked(True)
        elif autosend == 'hours':
            self.autosend_hours.setChecked(True)
        elif autosend == 'size':
            self.autosend_size.setChecked(True)
        else:
            self.autosend_off.setChecked(True)
        
        self.autosend_hours_n.setValue(engine.get_config('autosend_hours'))
        self.autosend_size_n.setValue(engine.get_config('autosend_size'))

        self.autosend_at_exit.setChecked(engine.get_config('autosend_at_exit'))
        self.auto_status_change.setChecked(engine.get_config('auto_status_change'))
        self.auto_status_change_if_scored.setChecked(engine.get_config('auto_status_change_if_scored'))
        self.auto_date_change.setChecked(engine.get_config('auto_date_change'))

        self.tray_icon.setChecked(self.config['show_tray'])
        self.close_to_tray.setChecked(self.config['close_to_tray'])
        self.start_in_tray.setChecked(self.config['start_in_tray'])
        self.notifications.setChecked(self.config['notifications'])

        self.autoretrieve_days_n.setEnabled(self.autoretrieve_days.isChecked())
        self.autosend_hours_n.setEnabled(self.autosend_hours.isChecked())
        self.autosend_size_n.setEnabled(self.autosend_size.isChecked())
        self.close_to_tray.setEnabled(self.tray_icon.isChecked())
        self.start_in_tray.setEnabled(self.tray_icon.isChecked())
        self.notifications.setEnabled(self.tray_icon.isChecked())

    def _save(self):
        engine = self.worker.engine

        engine.set_config('tracker_enabled',     self.tracker_enabled.isChecked())
        engine.set_config('tracker_interval',    self.tracker_interval.value())
        engine.set_config('tracker_process',     str(self.tracker_process.text()))
        engine.set_config('tracker_update_wait', self.tracker_update_wait.value())

        engine.set_config('player',     unicode(self.player.text()))
        engine.set_config('searchdir',  unicode(self.searchdir.text()))

        if self.autoretrieve_always.isChecked():
            engine.set_config('autoretrieve', 'always')
        elif self.autoretrieve_days.isChecked():
            engine.set_config('autoretrieve', 'days')
        else:
            engine.set_config('autoretrieve', 'off')

        engine.set_config('autoretrieve_days',   self.autoretrieve_days_n.value())

        if self.autosend_always.isChecked():
            engine.set_config('autosend', 'always')
        elif self.autosend_hours.isChecked():
            engine.set_config('autosend', 'hours')
        elif self.autosend_size.isChecked():
            engine.set_config('autosend', 'size')
        else:
            engine.set_config('autosend', 'off')
        
        engine.set_config('autosend_hours',   self.autosend_hours_n.value())
        engine.set_config('autosend_size',   self.autosend_size_n.value())
        
        engine.set_config('autosend_at_exit',   self.autosend_at_exit.isChecked())
        engine.set_config('auto_status_change', self.auto_status_change.isChecked())
        engine.set_config('auto_status_change_if_scored', self.auto_status_change_if_scored.isChecked())
        engine.set_config('auto_date_change',   self.auto_date_change.isChecked())

        engine.save_config()

        self.config['show_tray'] = self.tray_icon.isChecked()
        self.config['close_to_tray'] = self.close_to_tray.isChecked()
        self.config['start_in_tray'] = self.start_in_tray.isChecked()
        self.config['notifications'] = self.notifications.isChecked()

        utils.save_config(self.config, self.configfile)

        self.saved.emit()

    def s_save(self):
        self._save()
        self.accept()
    
    def s_autoretrieve_days(self, checked):
        self.autoretrieve_days_n.setEnabled(checked)

    def s_autosend_hours(self, checked):
        self.autosend_hours_n.setEnabled(checked)

    def s_autosend_size(self, checked):
        self.autosend_size_n.setEnabled(checked)

    def s_tray_icon(self, checked):
        self.close_to_tray.setEnabled(checked)
        self.start_in_tray.setEnabled(checked)
        self.notifications.setEnabled(checked)

    def s_auto_status_change(self, checked):
        self.auto_status_change_if_scored.setEnabled(checked)

    def s_player_browse(self):
        self.player.setText( QtGui.QFileDialog.getOpenFileName(caption='Choose player executable') )

    def s_searchdir_browse(self):
        self.searchdir.setText( QtGui.QFileDialog.getExistingDirectory(caption='Choose media directory') )

    def s_switch_page(self, new, old):
        if not new:
            new = old
        
        self.contents.setCurrentIndex( self.category_list.row( new ) )
        
class AccountDialog(QtGui.QDialog):
    selected = QtCore.pyqtSignal(int, bool)
    aborted = QtCore.pyqtSignal()

    def __init__(self, parent, accountman):
        QtGui.QDialog.__init__(self, parent)

        self.accountman = accountman
        
        layout = QtGui.QVBoxLayout()
        
        self.setWindowTitle('Select Account')
        
        # Create list
        self.table = QtGui.QTableWidget()
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setGridStyle(QtCore.Qt.NoPen)
        self.table.doubleClicked.connect(self.select)
        
        bottom_layout = QtGui.QHBoxLayout()
        self.remember_chk = QtGui.QCheckBox('Remember')
        if self.accountman.get_default() is not None:
            self.remember_chk.setChecked(True)
        cancel_btn = QtGui.QPushButton('Cancel')
        cancel_btn.clicked.connect(self.cancel)
        add_btn = QtGui.QPushButton('Add')
        add_btn.clicked.connect(self.add)
        delete_btn = QtGui.QPushButton('Delete')
        delete_btn.clicked.connect(self.delete)
        select_btn = QtGui.QPushButton('Select')
        select_btn.clicked.connect(self.select)
        bottom_layout.addWidget(self.remember_chk) #, 1, QtCore.Qt.AlignRight)
        bottom_layout.addWidget(cancel_btn)
        bottom_layout.addWidget(add_btn)
        bottom_layout.addWidget(delete_btn)
        bottom_layout.addWidget(select_btn)
        
        # Get icons
        self.icons = dict()
        for libname, lib in utils.available_libs.iteritems():
            self.icons[libname] = QtGui.QIcon(lib[1])
            
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
    
    def delete(self):
        try:
            selected_account_num = self.table.selectedItems()[0].num
            reply = QtGui.QMessageBox.question(self, 'Confirmation', 'Do you want to delete the selected account?', QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

            if reply == QtGui.QMessageBox.Yes:
                self.accountman.delete_account(selected_account_num)
                self.rebuild()
        except IndexError:
            self._error("Please select an account.")
        
    def rebuild(self):
        self.table.clear()

        columns = ['Username', 'Site']
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(len(self.accountman.accounts['accounts']))
        
        accounts = self.accountman.get_accounts()
        i = 0
        for k, account in accounts:
            self.table.setRowHeight(i, QtGui.QFontMetrics(self.table.font()).height() + 2);
            self.table.setItem(i, 0, AccountItem(k, account['username']))
            self.table.setItem(i, 1, AccountItem(k, account['api'], self.icons[account['api']]))

            i += 1
        
        self.table.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        
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
        QtGui.QMessageBox.critical(self, 'Error', msg, QtGui.QMessageBox.Ok)

class AccountItem(QtGui.QTableWidgetItem):
    """
    Regular item able to save account item

    """
    num = None

    def __init__(self, num, text, icon=None):
        QtGui.QTableWidgetItem.__init__(self, text)
        self.num = num
        if icon:
            self.setIcon( icon )

class ShowItem(QtGui.QTableWidgetItem):
    """
    Regular item able to show colors and alignment
    
    """
    
    def __init__(self, text, color=None):
        QtGui.QTableWidgetItem.__init__(self, text)
        #if alignment:
        #    self.setTextAlignment( alignment )
        if color:
            self.setBackgroundColor( color )

class ShowItemNum(ShowItem):
    def __init__(self, num, text, color=None):
        ShowItem.__init__(self, text, color) 
        self.num = num
        
    def __lt__(self, other):
        return self.num < other.num

class ShowItemDate(ShowItem):
    def __init__(self, date, color=None):
        if date:
            datestr = date.strftime("%Y-%m-%d")
        else:
            datestr = '-'

        self.date = date

        ShowItem.__init__(self, datestr, color)

    def __lt__(self, other):
        if self.date and other.date:
            return self.date < other.date
        else:
            return True

class AccountAddDialog(QtGui.QDialog):
    def __init__(self, parent, icons):
        QtGui.QDialog.__init__(self, parent)
        
        # Build UI
        layout = QtGui.QVBoxLayout()
        
        formlayout = QtGui.QFormLayout()
        self.username = QtGui.QLineEdit()
        self.password = QtGui.QLineEdit()
        self.password.setEchoMode(QtGui.QLineEdit.Password)
        self.api = QtGui.QComboBox()
        
        formlayout.addRow( QtGui.QLabel('Username:'), self.username )
        formlayout.addRow( QtGui.QLabel('Password:'), self.password )
        formlayout.addRow( QtGui.QLabel('Site:'), self.api )
        
        bottombox = QtGui.QDialogButtonBox()
        bottombox.addButton(QtGui.QDialogButtonBox.Save)
        bottombox.addButton(QtGui.QDialogButtonBox.Cancel)
        bottombox.accepted.connect(self.validate)
        bottombox.rejected.connect(self.reject)
        
        # Populate APIs
        for libname, lib in utils.available_libs.iteritems():
            self.api.addItem(icons[libname], lib[0], libname)
        
        # Finish layouts
        layout.addLayout(formlayout)
        layout.addWidget(bottombox)
        
        self.setLayout(layout)
    
    def validate(self):
        if len(self.username.text()) > 0 and len(self.password.text()) > 0:
            self.accept()
        else:
            self._error('Please fill all the fields.')
        
    def _error(self, msg):
        QtGui.QMessageBox.critical(self, 'Error', msg, QtGui.QMessageBox.Ok)
        
    @staticmethod
    def do(parent=None, icons=None):
        dialog = AccountAddDialog(parent, icons)
        result = dialog.exec_()
        
        if result == QtGui.QDialog.Accepted:
            currentIndex = dialog.api.currentIndex()
            return (
                    str( dialog.username.text() ),
                    str( dialog.password.text() ),
                    str( dialog.api.itemData(currentIndex).toString() )
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

        img_file = StringIO(urllib.urlopen(self.remote).read())
        if self.size:
            im = Image.open(img_file)
            im.thumbnail((self.size[0], self.size[1]), Image.ANTIALIAS)
            im.save(self.local)
        else:
            with open(self.local, 'wb') as f:
                f.write(img_file.read())

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
    changed_status = QtCore.pyqtSignal(str)
    raised_error = QtCore.pyqtSignal(str)
    raised_fatal = QtCore.pyqtSignal(str)

    # Event handler signals
    changed_show = QtCore.pyqtSignal(dict)
    changed_list = QtCore.pyqtSignal(dict, object)
    changed_queue = QtCore.pyqtSignal(int)
    playing_show = QtCore.pyqtSignal(dict, bool, int)

    def __init__(self, account):
        super(Engine_Worker, self).__init__()
        self.engine = Engine(account, self._messagehandler)
        self.engine.connect_signal('episode_changed', self._changed_show)
        self.engine.connect_signal('score_changed', self._changed_show)
        self.engine.connect_signal('status_changed', self._changed_list)
        self.engine.connect_signal('playing', self._playing_show)
        self.engine.connect_signal('show_added', self._changed_list)
        self.engine.connect_signal('show_deleted', self._changed_list)
        self.engine.connect_signal('show_synced', self._changed_show)
        self.engine.connect_signal('queue_changed', self._changed_queue)

        self.function_list = {
            'start': self._start,
            'reload': self._reload,
            'get_list': self._get_list,
            'set_episode': self._set_episode,
            'set_score': self._set_score,
            'set_status': self._set_status,
            'play_episode': self._play_episode,
            'list_download': self._list_download,
            'list_upload': self._list_upload,
            'get_show_details': self._get_show_details,
            'search': self._search,
            'add_show': self._add_show,
            'delete_show': self._delete_show,
            'unload': self._unload,
        }

    def _messagehandler(self, classname, msgtype, msg):
        self.changed_status.emit("%s: %s" % (classname, msg))

    def _error(self, msg):
        self.raised_error.emit(msg)

    def _fatal(self, msg):
        self.raised_fatal.emit(msg)

    def _changed_show(self, show):
        self.changed_show.emit(show)

    def _changed_list(self, show, old_status=None):
        self.changed_list.emit(show, old_status)
    
    def _changed_queue(self, queue):
        self.changed_queue.emit(queue)
    
    def _playing_show(self, show, is_playing, episode):
        self.playing_show.emit(show, is_playing, episode)
    
    # Callable functions
    def _start(self):
        try:
            self.engine.start()
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}
        
        return {'success': True}
 
    def _reload(self, account, mediatype):
        try:
            self.engine.reload(account, mediatype)
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}
        
        return {'success': True}
    
    def _unload(self):
        try:
            self.engine.unload()
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}

    def _get_list(self):
        try:
            showlist = self.engine.get_list()
            altnames = self.engine.altnames()
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True, 'showlist': showlist, 'altnames': altnames}

    def _set_episode(self, showid, episode):
        try:
            self.engine.set_episode(showid, episode)
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}

    def _set_score(self, showid, score):
        try:
            self.engine.set_score(showid, score)
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}

    def _set_status(self, showid, status):
        try:
            self.engine.set_status(showid, status)
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}
       
    def _play_episode(self, show, episode):
        try:
            played_ep = self.engine.play_episode(show, episode)
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True, 'show': show, 'played_ep': played_ep}

    def _list_download(self):
        try:
            self.engine.list_download()
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}
    
    def _list_upload(self):
        try:
            self.engine.list_upload()
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}
    
    def _get_show_details(self, show):
        try:
            details = self.engine.get_show_details(show)
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True, 'details': details}

    def _search(self, terms):
        try:
            results = self.engine.search(terms)
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True, 'results': results}
    
    def _add_show(self, show):
        try:
            results = self.engine.add_show(show)
        except utils.TrackmaError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}

    def _delete_show(self, show):
        try:
            results = self.engine.delete_show(show)
        except utils.TrackmaError, e:
            self._error(e.message)
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
        except utils.TrackmaFatal, e:
            self._fatal(e.message)

def main():
    app = QtGui.QApplication(sys.argv)
    mainwindow = Trackma()
    sys.exit(app.exec_())

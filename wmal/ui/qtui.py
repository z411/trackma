# This file is part of wMAL.
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
import sys
from PyQt4 import QtGui, QtCore
from cStringIO import StringIO
import urllib2 as urllib

import wmal.messenger as messenger
import wmal.utils as utils

from wmal.engine import Engine
from wmal.accounts import AccountManager

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

class wmal(QtGui.QMainWindow):
    """
    Main GUI class

    """
    accountman = None
    worker = None
    image_worker = None
    started = False
    selected_show_id = None

    def __init__(self):
        QtGui.QMainWindow.__init__(self, None)
        
        # Build UI
        QtGui.QApplication.setWindowIcon(QtGui.QIcon(utils.datadir + '/data/wmal_icon.png'))
        self.setWindowTitle('wMAL-qt v0.2')
        
        self.accountman = AccountManager()
        self.accountman_widget = AccountWidget(None, self.accountman)
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
        action_details = QtGui.QAction('Show &details...', self)
        action_details.setStatusTip('Show detailed information about the selected show.')
        action_details.triggered.connect(self.s_show_details)
        action_send = QtGui.QAction('&Send changes', self)
        action_send.setStatusTip('Upload any changes made to the list immediately.')
        action_send.triggered.connect(self.s_send)
        action_quit = QtGui.QAction('&Quit', self)
        action_quit.setStatusTip('Exit wMAL.')
        action_quit.triggered.connect(self.close)

        action_reload = QtGui.QAction('Switch &Account', self)
        action_reload.setStatusTip('Switch to a different account.')
        action_reload.triggered.connect(self.s_switch_account)
        action_retrieve = QtGui.QAction('&Redownload list', self)
        action_retrieve.setStatusTip('Discard any changes made to the list and re-download it.')
        action_retrieve.triggered.connect(self.s_retrieve)

        action_about = QtGui.QAction('About...', self)
        action_about.triggered.connect(self.s_about)
        action_about_qt = QtGui.QAction('About Qt...', self)
        action_about_qt.triggered.connect(self.s_about_qt)

        menubar = self.menuBar()
        menu_show = menubar.addMenu('&Show')
        menu_show.addAction(action_details)
        menu_show.addAction(action_send)
        menu_show.addAction(action_quit)
        menu_options = menubar.addMenu('&Options')
        menu_options.addAction(action_reload)
        menu_options.addAction(action_retrieve)
        menu_help = menubar.addMenu('&Help')
        menu_help.addAction(action_about)
        menu_help.addAction(action_about_qt)

        # Build layout
        main_layout = QtGui.QVBoxLayout()
        main_hbox = QtGui.QHBoxLayout()
        left_box = QtGui.QFormLayout()
        
        self.show_title = QtGui.QLabel('wMAL-qt')
        show_title_font = QtGui.QFont()
        show_title_font.setBold(True)
        show_title_font.setPointSize(12)
        self.show_title.setFont(show_title_font)

        self.notebook = QtGui.QTabWidget()
        self.notebook.currentChanged.connect(self.s_tab_changed)
        self.setMinimumSize(680, 450)
        
        self.show_image = QtGui.QLabel('wMAL-qt')
        self.show_image.setFixedHeight( 149 )
        self.show_image.setFixedWidth( 100 )
        self.show_image.setAlignment( QtCore.Qt.AlignCenter )
        self.show_image.setStyleSheet("border: 1px solid #777;background-color:#999;text-align:center")
        show_progress_label = QtGui.QLabel('Progress')
        self.show_progress = QtGui.QSpinBox()
        self.show_progress_bar = QtGui.QProgressBar()
        self.show_progress_btn = QtGui.QPushButton('Update')
        self.show_progress_btn.clicked.connect(self.s_set_episode)
        show_score_label = QtGui.QLabel('Score')
        self.show_score = QtGui.QSpinBox()
        self.show_score_btn = QtGui.QPushButton('Set')
        self.show_score_btn.clicked.connect(self.s_set_score)
        self.show_status = QtGui.QComboBox()
        self.show_status.currentIndexChanged.connect(self.s_set_status)

        left_box.addRow(self.show_image)
        left_box.addRow(self.show_progress_bar) # , 1, QtCore.Qt.AlignTop)
        left_box.addRow(show_progress_label, self.show_progress)
        left_box.addRow(self.show_progress_btn)
        left_box.addRow(show_score_label, self.show_score)
        left_box.addRow(self.show_score_btn)
        left_box.addRow(self.show_status)

        main_hbox.addLayout(left_box)
        main_hbox.addWidget(self.notebook, 1)

        main_layout.addWidget(self.show_title)
        main_layout.addLayout(main_hbox)

        self.main_widget = QtGui.QWidget(self)
        self.main_widget.setLayout(main_layout)
        self.setCentralWidget(self.main_widget)
 
        # Connect worker signals
        self.worker.changed_status.connect(self.status)
        self.worker.changed_show.connect(self.ws_changed_show)
        self.worker.changed_list.connect(self.ws_changed_list)
        self.worker.playing_show.connect(self.ws_changed_show)
        
        # Show main window
        self.show()
        
        # Start loading engine
        self.started = True
        self._busy(False)
        self.worker_call('start', self.r_engine_loaded)

    def reload(self, account=None, mediatype=None):
        self._busy(False)
        self.worker_call('reload', self.r_engine_loaded, account, mediatype)
        
    def closeEvent(self, event):
        if not self.started or not self.worker.engine.loaded:
            event.accept()
        else:
            self._busy()
            self.worker_call('unload', self.r_engine_unloaded)
            event.ignore()

    def status(self, string):
        self.statusBar().showMessage(string)
        print string

    def worker_call(self, function, ret_function, *args, **kwargs):
        # Run worker in a thread
        self.worker.set_function(function, ret_function, *args, **kwargs)
        self.worker.start()
    
    ### GUI Functions
    def _enable_widgets(self, enable):
        self.notebook.setEnabled(enable)
        self.show_progress_btn.setEnabled(enable)
        self.show_score_btn.setEnabled(enable)
    
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
    
    def _rebuild_lists(self, showlist):
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
            self._rebuild_list(status, filtered_list[status])


    def _rebuild_list(self, status, showlist=None):
        if not showlist:
            showlist = self.worker.engine.filter_list(status)

        widget = self.show_lists[status]
        columns = ['Title', 'Progress', 'Score', 'Percent', 'ID']
        widget.clear()
        widget.setRowCount(len(showlist))
        widget.setColumnCount(len(columns))
        widget.setHorizontalHeaderLabels(columns)
        widget.setColumnHidden(4, True)
        widget.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.Stretch)
        widget.horizontalHeader().resizeSection(1, 70)
        widget.horizontalHeader().resizeSection(2, 55)
        widget.horizontalHeader().resizeSection(3, 100)

        i = 0
        for show in showlist:
            self._update_row(widget, i, show)
            i += 1

        widget.model().sort(0)
        
        # Update tab name with total
        tab_index = self.statuses_nums.index(status)
        tab_name = "%s (%d)" % (self.statuses_names[status], i)
        self.notebook.setTabText(tab_index, tab_name)

    def _update_row(self, widget, row, show, is_playing=False):
        if is_playing:
            color = QtGui.QColor(150, 150, 250)
        else:
            color = self._get_color(show)
        progress_str = "%d / %d" % (show['my_progress'], show['total'])
        progress_widget = QtGui.QProgressBar()
        progress_widget.setMinimum(0)
        progress_widget.setMaximum(100)
        if show['total'] > 0:
            progress_widget.setValue( 100L * show['my_progress'] / show['total'] )

        widget.setRowHeight(row, QtGui.QFontMetrics(widget.font()).height() + 2);
        widget.setItem(row, 0, ShowItem( show['title'], color ))
        widget.setItem(row, 1, ShowItem( progress_str, color ))
        widget.setItem(row, 2, ShowItem( str(show['my_score']), color ))
        widget.setCellWidget(row, 3, progress_widget )
        widget.setItem(row, 4, ShowItem( str(show['id']), color ))

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
            if widget.item(row, 4).text() == str(showid):
                return row

        print "Warning: Show not found in list for some reason"
        return 0

    ### Slots
    def s_busy(self):
        self._enable_widgets(False)
        
    def s_show_selected(self, new, old=None):
        if not new:
            return # Nothing to select
        
        index = new.row()
        selected_id = self.notebook.currentWidget().item( index, 4 ).text()

        # Attempt to convert to int if possible
        try:
            selected_id = int(selected_id)
        except:
            pass

        show = self.worker.engine.get_show_info(selected_id)
        
        # Block signals
        self.show_status.blockSignals(True)

        # Update information
        self.show_title.setText(show['title'])
        self.show_progress.setValue(show['my_progress'])
        self.show_status.setCurrentIndex(self.statuses_nums.index(show['my_status']))
        self.show_score.setValue(show['my_score'])
       
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
    
    def s_retrieve(self):
        self._busy(False)
        self.worker_call('list_download', self.r_list_retrieved)
    
    def s_send(self):
        self._busy(True)
        self.worker_call('list_upload', self.r_list_retrieved)

    def s_switch_account(self):
        self.accountman_widget.setModal(True)
        self.accountman_widget.show()

    def s_show_image(self, filename):
        self.show_image.setPixmap( QtGui.QPixmap( filename ) )
    
    def s_show_details(self):
        show = self.worker.engine.get_show_info(self.selected_show_id)
        
        self.detailswindow = DetailsDialog(None, self.worker)
        self.detailswindow.setModal(True)
        self.detailswindow.load(show)
        self.detailswindow.show()

    def s_about(self):
        QtGui.QMessageBox.about(self, 'About wMAL-qt',
            '<p><b>About wMAL-qt</b></p><p>wMAL is an open source client for media tracking websites.</p>'
            '<p>This program is licensed under the GPLv3, for more information read COPYING file.</p>'
            '<p>Copyright (C) z411 - Icon by shuuichi</p>'
            '<p><a href="http://github.com/z411/wmal-python">http://github.com/z411/wmal-python</a></p>')

    def s_about_qt(self):
        QtGui.QMessageBox.aboutQt(self, 'About Qt')
        

    ### Worker slots
    def ws_changed_show(self, show, is_playing=False):
        widget = self.show_lists[show['my_status']]
        row = self._get_row_from_showid(widget, show['id'])
        self._update_row(widget, row, show, is_playing)
        
    def ws_changed_list(self, show, old_status=None):
        # Rebuild both new and old (if any) lists
        self._rebuild_list(show['my_status'])
        if old_status:
            self._rebuild_list(old_status)
        
        # Set notebook to the new page
        self.notebook.setCurrentIndex( self.statuses_nums.index(show['my_status']) )

    ### Responses from the engine thread
    def r_generic(self):
        self._unbusy()
    
    def r_generic_ready(self):
        self._unbusy()
        self.status('Ready.')
        
    def r_engine_loaded(self, result):
        if result['success']:
            showlist = self.worker.engine.get_list()
            
            self.notebook.blockSignals(True)
            self.show_status.blockSignals(True)

            self.notebook.clear()
            self.show_status.clear()
            self.show_lists = dict()

            self.statuses_nums = self.worker.engine.mediainfo['statuses']
            self.statuses_names = self.worker.engine.mediainfo['statuses_dict']
            self.has_progress = self.worker.engine.mediainfo['has_progress']
            
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
                
                self.notebook.addTab(self.show_lists[status], name)
                self.show_status.addItem(name)

            self.show_status.blockSignals(False)
            self.notebook.blockSignals(False)

            self._rebuild_lists(showlist)
            
            if not self.has_progress:
                self.show_progress_btn.setEnabled(False)
            
            self.status('Ready.')
            
        self._unbusy()
    
    def r_list_retrieved(self, result):
        if result['success']:
            showlist = self.worker.engine.get_list()
            self._rebuild_lists(showlist)
            
            self.status('Ready.')
            
        self._unbusy()
        
    def r_engine_unloaded(self, result):
        if result['success']:
            self.close()


class DetailsDialog(QtGui.QDialog):
    worker = None

    def __init__(self, parent, worker):
        QtGui.QMainWindow.__init__(self, parent)
        self.setMinimumSize(530, 550)
        self.setWindowTitle('Details')
        self.worker = worker
    
        # Build layout
        main_layout = QtGui.QVBoxLayout()
        
        self.show_title = QtGui.QLabel()
        show_title_font = QtGui.QFont()
        show_title_font.setBold(True)
        show_title_font.setPointSize(12)
        self.show_title.setAlignment( QtCore.Qt.AlignCenter )
        self.show_title.setFont(show_title_font)
        
        info_area = QtGui.QWidget()
        info_layout = QtGui.QHBoxLayout()
        
        self.show_image = QtGui.QLabel('Downloading...')
        self.show_image.setAlignment( QtCore.Qt.AlignTop )
        self.show_info = QtGui.QLabel('Wait...')
        self.show_info.setWordWrap(True)
        self.show_info.setAlignment( QtCore.Qt.AlignTop )
        
        info_layout.addWidget( self.show_image )
        info_layout.addWidget( self.show_info, 1 )
        
        info_area.setLayout(info_layout)
        
        scroll_area = QtGui.QScrollArea()
        scroll_area.setBackgroundRole(QtGui.QPalette.Dark)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(info_area)
        
        done_button = QtGui.QPushButton('Done')
        done_button.clicked.connect(self.close)

        main_layout.addWidget(self.show_title)
        main_layout.addWidget(scroll_area)
        main_layout.addWidget(done_button)

        self.setLayout(main_layout)
    
    def worker_call(self, function, ret_function, *args, **kwargs):
        # Run worker in a thread
        self.worker.set_function(function, ret_function, *args, **kwargs)
        self.worker.start()
        
    def load(self, show):
        self.show_title.setText( "<a href=\"%s\">%s</a>" % (show['url'], show['title']) )
        
        # Load show info
        self.worker_call('get_show_details', self.r_details_loaded, show)
        
        # Load show image
        filename = utils.get_filename('cache', "f_%s.jpg" % show['id'])
        
        if os.path.isfile(filename):
            self.s_show_image(filename)
        else:
            self.image_worker = Image_Worker(show['image'], filename)
            self.image_worker.finished.connect(self.s_show_image)
            self.image_worker.start()
    
    def s_show_image(self, filename):
        self.show_image.setPixmap( QtGui.QPixmap( filename ) )
    
    def r_details_loaded(self, result):
        details = result['details']
        
        info_string = ""
        for line in details['extra']:
            if line[0] and line[1]:
                info_string += "<h3>%s</h3><p>%s</p>" % (line[0], line[1])
                
        self.show_info.setText( info_string )
        
class AccountWidget(QtGui.QDialog):
    selected = QtCore.pyqtSignal(int, bool)
    aborted = QtCore.pyqtSignal()

    def __init__(self, parent, accountman):
        QtGui.QDialog.__init__(self, parent)

        self.accountman = accountman
        
        layout = QtGui.QVBoxLayout()
        
        self.setWindowTitle('Select Account')
        
        # Create list
        columns = ['Username', 'Site']
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

        # Populate
        accounts = self.accountman.get_accounts()
        icons = dict()
        for libname, lib in utils.available_libs.iteritems():
            icons[libname] = QtGui.QIcon(lib[1])

        self.table.setRowCount(len(self.accountman.accounts['accounts']))
        i = 0
        for k, account in accounts:
            self.table.setItem(i, 0, AccountItem(k, account['username']))
            self.table.setItem(i, 1, AccountItem(k, account['api'], icons[account['api']]))

            i += 1
        
        bottom_layout = QtGui.QHBoxLayout()
        self.remember_chk = QtGui.QCheckBox('Remember')
        if self.accountman.get_default() is not None:
            self.remember_chk.setChecked(True)
        cancel_btn = QtGui.QPushButton('Cancel')
        cancel_btn.clicked.connect(self.cancel)
        select_btn = QtGui.QPushButton('Select')
        select_btn.clicked.connect(self.select)
        bottom_layout.addWidget(self.remember_chk) #, 1, QtCore.Qt.AlignRight)
        bottom_layout.addWidget(cancel_btn)
        bottom_layout.addWidget(select_btn)

        # Finish layout
        layout.addWidget(self.table)
        layout.addLayout(bottom_layout)
        self.setLayout(layout)

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

    # Event handler signals
    changed_show = QtCore.pyqtSignal(dict)
    changed_list = QtCore.pyqtSignal(dict, object)
    playing_show = QtCore.pyqtSignal(dict, bool)

    def __init__(self, account):
        super(Engine_Worker, self).__init__()
        self.engine = Engine(account, self._messagehandler)
        self.engine.connect_signal('episode_changed', self._changed_show)
        self.engine.connect_signal('score_changed', self._changed_show)
        self.engine.connect_signal('status_changed', self._changed_list)
        self.engine.connect_signal('playing', self._playing_show)
        self.engine.connect_signal('show_added', self._changed_list)
        self.engine.connect_signal('show_deleted', self._changed_list)

        self.function_list = {
            'start': self._start,
            'reload': self._reload,
            'get_list': self._get_list,
            'set_episode': self._set_episode,
            'set_score': self._set_score,
            'set_status': self._set_status,
            'list_download': self._list_download,
            'list_upload': self._list_upload,
            'get_show_details': self._get_show_details,
            'unload': self._unload,
        }

    def _messagehandler(self, classname, msgtype, msg):
        self.changed_status.emit("%s: %s" % (classname, msg))

    def _error(self, msg):
        self.raised_error.emit(msg)

    def _changed_show(self, show):
        self.changed_show.emit(show)

    def _changed_list(self, show, old_status=None):
        self.changed_list.emit(show, old_status)

    def _playing_show(self, show, is_playing):
        self.playing_show.emit(show, is_playing)
    
    # Callable functions
    def _start(self):
        try:
            self.engine.start()
        except utils.wmalError, e:
            self._error(e.message)
            return {'success': False}
        
        return {'success': True}
 
    def _reload(self, account, mediatype):
        try:
            self.engine.reload(account, mediatype)
        except utils.wmalError, e:
            self._error(e.message)
            return {'success': False}
        
        return {'success': True}
    
    def _unload(self):
        try:
            self.engine.unload()
        except utils.wmalError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}

    def _get_list(self):
        try:
            showlist = self.engine.get_list()
        except utils.wmalError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True, 'showlist': showlist}

    def _set_episode(self, showid, episode):
        try:
            self.engine.set_episode(showid, episode)
        except utils.wmalError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}

    def _set_score(self, showid, score):
        try:
            self.engine.set_score(showid, score)
        except utils.wmalError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}

    def _set_status(self, showid, status):
        try:
            self.engine.set_status(showid, status)
        except utils.wmalError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}
       
    def _list_download(self):
        try:
            self.engine.list_download()
        except utils.wmalError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}
    
    def _list_upload(self):
        try:
            self.engine.list_upload()
        except utils.wmalError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True}
    
    def _get_show_details(self, show):
        try:
            details = self.engine.get_show_details(show)
        except utils.wmalError, e:
            self._error(e.message)
            return {'success': False}

        return {'success': True, 'details': details}

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
        ret = self.function(*self.args,**self.kwargs)
        self.finished.emit(ret)


def main():
    app = QtGui.QApplication(sys.argv)
    mainwindow = wmal()
    sys.exit(app.exec_())

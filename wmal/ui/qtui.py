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
        self.accountman = AccountManager()
        self.accountman_widget = AccountWidget(None, self.accountman)
        self.accountman_widget.selected.connect(self.accountman_selected)
        
        # Build UI
        self.setWindowTitle('wMAL-qt v0.2')
        self.setWindowIcon(QtGui.QIcon(utils.datadir + '/data/wmal_icon.png'))

        # Go directly into the application if a default account is set
        # Open the selection dialog otherwise
        default = self.accountman.get_default()
        if default:
            self.show()
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
            self.show()
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
        
        # Build menus
        action_quit = QtGui.QAction('&Quit', self)
        action_quit.triggered.connect(self.close)

        action_reload = QtGui.QAction('Switch &Account', self)
        action_reload.triggered.connect(self.s_switch_account)

        action_about = QtGui.QAction('About...', self)
        action_about.triggered.connect(self.s_about)
        action_about_qt = QtGui.QAction('About Qt...', self)
        action_about_qt.triggered.connect(self.s_about_qt)

        menubar = self.menuBar()
        menu_show = menubar.addMenu('&Show')
        menu_show.addAction(action_quit)
        menu_options = menubar.addMenu('&Options')
        menu_options.addAction(action_reload)
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
        
        self.show_image = QtGui.QLabel()
        self.show_image.setFixedHeight( 149 )
        self.show_image.setFixedWidth( 100 )
        show_progress_label = QtGui.QLabel('Progress')
        self.show_progress = QtGui.QSpinBox()
        self.show_progress_bar = QtGui.QProgressBar()
        show_progress_btn = QtGui.QPushButton('Update')
        show_progress_btn.clicked.connect(self.s_set_episode)
        show_score_label = QtGui.QLabel('Score')
        self.show_score = QtGui.QSpinBox()
        show_score_btn = QtGui.QPushButton('Set')
        show_score_btn.clicked.connect(self.s_set_score)
        self.show_status = QtGui.QComboBox()
        self.show_status.currentIndexChanged.connect(self.s_set_status)

        left_box.addRow(self.show_image)
        left_box.addRow(self.show_progress_bar) # , 1, QtCore.Qt.AlignTop)
        left_box.addRow(show_progress_label, self.show_progress)
        left_box.addRow(show_progress_btn)
        left_box.addRow(show_score_label, self.show_score)
        left_box.addRow(show_score_btn)
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
        
        # Start loading engine
        self.started = True
        self.worker.set_function('start', self.r_engine_loaded)
        self.worker.start()

    def reload(self, account=None, mediatype=None):
        self.worker.set_function('reload', self.r_engine_loaded, account, mediatype)
        self.worker.start()
        
    def closeEvent(self, event):
        if not self.started or not self.worker.engine.loaded:
            event.accept()
        else:
            self.worker.set_function('unload', self.r_engine_unloaded)
            self.worker.start()
            event.ignore()

    def status(self, string):
        self.statusBar().showMessage(string)
        print string
    
    ### GUI Functions
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

        self.status('Ready.')

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

    def _update_row(self, widget, row, show):
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
        if show['status'] == 1:
            return QtGui.QColor(216, 255, 255)
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
    def s_show_selected(self, new, old=None):
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
                self.show_image.setText('Waiting...')
                self.image_timer.start()
               
        if show['total'] > 0:
            self.show_progress_bar.setValue( 100L * show['my_progress'] / show['total'] )
        else:
            self.show_progress_bar.setValue( 0 )

        # Make it global
        self.selected_show_id = selected_id

        # Unblock signals
        self.show_status.blockSignals(False)

    def s_download_image(self):
        if imaging_available:
            show = self.worker.engine.get_show_info(self.selected_show_id)
            self.show_image.setText('Downloading...')
            filename = utils.get_filename('cache', "%s.jpg" % show['id'])
        
            self.image_worker = Image_Worker(show['image'], filename, (100, 140))
            self.image_worker.finished.connect(self.s_show_image)
            self.image_worker.start()
        else:
            self.show_image.setText('Not available')
    
    def s_tab_changed(self):
        item = self.notebook.currentWidget().currentItem()
        if item:
            self.s_show_selected(item)

    def s_set_episode(self):
        self.worker.set_function('set_episode', None, self.selected_show_id, self.show_progress.value())
        self.worker.start()

    def s_set_score(self):
        self.worker.set_function('set_score', None, self.selected_show_id, self.show_score.value())
        self.worker.start()

    def s_set_status(self, index):
        if self.selected_show_id:
            self.worker.set_function('set_status', None, self.selected_show_id, self.statuses_nums[index])
            self.worker.start()

    def s_switch_account(self):
        self.accountman_widget.show()

    def s_show_image(self, filename):
        self.show_image.setPixmap( QtGui.QPixmap( filename ) )

    def s_about(self):
        QtGui.QMessageBox.about(self, 'About wMAL-qt',
            '<p><b>About wMAL-qt</b></p><p>wMAL is an open source client for media tracking websites.</p>'
            '<p>This program is licensed under the GPLv3, for more information read COPYING file.</p>'
            '<p>Copyright (C) z411 - Icon by shuuichi</p>'
            '<p><a href="http://github.com/z411/wmal-python">http://github.com/z411/wmal-python</a></p>')

    def s_about_qt(self):
        QtGui.QMessageBox.aboutQt(self, 'About Qt')

    ### Worker slots
    def ws_changed_show(self, show):
        widget = self.show_lists[show['my_status']]
        row = self._get_row_from_showid(widget, show['id'])
        self._update_row(widget, row, show)
        
    def ws_changed_list(self, show, old_status=None):
        # Rebuild both new and old (if any) lists
        self._rebuild_list(show['my_status'])
        if old_status:
            self._rebuild_list(old_status)
        
        # Set notebook to the new page
        self.notebook.setCurrentIndex( self.statuses_nums.index(show['my_status']) )

    ### Responses from the engine thread
    def r_engine_loaded(self, result):
        if result['success']:
            self.worker.set_function('get_list', self.r_build_lists)
            self.worker.start()

    def r_build_lists(self, result):
        if result['success']:
            self.notebook.blockSignals(True)
            self.show_status.blockSignals(True)

            self.notebook.clear()
            self.show_status.clear()
            self.show_lists = dict()

            self.statuses_nums = self.worker.engine.mediainfo['statuses']
            self.statuses_names = self.worker.engine.mediainfo['statuses_dict']
            
            for status in self.statuses_nums:
                name = self.statuses_names[status]

                self.show_lists[status] = QtGui.QTableWidget()
                self.show_lists[status].setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
                #self.show_lists[status].setFocusPolicy(QtCore.Qt.NoFocus)
                self.show_lists[status].setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
                self.show_lists[status].setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
                self.show_lists[status].horizontalHeader().setHighlightSections(False)
                self.show_lists[status].verticalHeader().hide()
                self.show_lists[status].currentItemChanged.connect(self.s_show_selected)
                
                self.notebook.addTab(self.show_lists[status], name)
                self.show_status.addItem(name)

            self.show_status.blockSignals(False)
            self.notebook.blockSignals(False)

            self._rebuild_lists(result['showlist'])

    def r_engine_unloaded(self, result):
        if result['success']:
            self.close()


class AccountWidget(QtGui.QDialog):
    selected = QtCore.pyqtSignal(int, bool)
    aborted = QtCore.pyqtSignal()

    def __init__(self, parent, accountman):
        QtGui.QDialog.__init__(self, parent)

        self.accountman = accountman
        
        layout = QtGui.QVBoxLayout()
        
        # Create list
        columns = ['Username', 'Site']
        self.table = QtGui.QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()

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

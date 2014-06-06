import sys
from PyQt4 import QtGui, QtCore

import wmal.messenger as messenger
import wmal.utils as utils

from wmal.engine import Engine
from wmal.accounts import AccountManager

class wmal(QtGui.QMainWindow):
    """
    Main GUI class

    """
    accountman = None
    worker = None
    started = False

    def __init__(self):
        QtGui.QMainWindow.__init__(self, None)
        self.accountman = AccountManager()
        self.accountman_widget = AccountWidget(None, self.accountman)
        self.accountman_widget.selected.connect(self.accountman_selected)
        
        # Build UI
        self.setWindowTitle('wMAL-qt v0.2')
        self.accountman_widget.show()
        self.setWindowIcon(QtGui.QIcon(utils.datadir + '/data/wmal_icon.png'))

    def accountman_selected(self, account_num):
        account = self.accountman.get_account(account_num)

        if self.started:
            self.reload(account)
        else:
            self.show()
            self.start(account)

    def start(self, account):
        """
        Start engine and everything

        """
        self.worker = Engine_Worker(account)
        
        # Build menus
        action_reload = QtGui.QAction('Switch &Account', self)
        action_reload.triggered.connect(self.s_switch_account)

        action_about = QtGui.QAction('About...', self)
        action_about.triggered.connect(self.s_about)
        action_about_qt = QtGui.QAction('About Qt...', self)
        action_about_qt.triggered.connect(self.s_about_qt)

        menubar = self.menuBar()
        menu_options = menubar.addMenu('&Options')
        menu_options.addAction(action_reload)
        menu_help = menubar.addMenu('&Help')
        menu_help.addAction(action_about)
        menu_help.addAction(action_about_qt)

        # Build layout
        main_layout = QtGui.QVBoxLayout()
        
        self.show_title = QtGui.QLabel('Show title')
        show_title_font = QtGui.QFont()
        show_title_font.setBold(True)
        show_title_font.setPointSize(12)
        self.show_title.setFont(show_title_font)

        self.notebook = QtGui.QTabWidget()
        self.setMinimumSize(680, 450)
        
        main_layout.addWidget(self.show_title)
        main_layout.addWidget(self.notebook)

        self.main_widget = QtGui.QWidget(self)
        self.main_widget.setLayout(main_layout)
        self.setCentralWidget(self.main_widget)
 
        # Connect worker signals
        self.worker.changed_status.connect(self.status)
        
        # Prepare globals
        
        # Start loading engine
        self.started = True
        self.worker.set_function('start', self.r_engine_loaded)
        self.worker.start()

    def reload(self, account=None, mediatype=None):
        # TODO reload
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

    def _rebuild_list(self, status, showlist):
        columns = ['Title', 'Progress', 'Score', 'Percent', 'ID']
        self.show_lists[status].clear()
        self.show_lists[status].setRowCount(len(showlist))
        self.show_lists[status].setColumnCount(len(columns))
        self.show_lists[status].setHorizontalHeaderLabels(columns)
        self.show_lists[status].setColumnHidden(4, True)
        self.show_lists[status].horizontalHeader().resizeSection(0, 300)
        self.show_lists[status].horizontalHeader().resizeSection(1, 70)
        self.show_lists[status].horizontalHeader().resizeSection(2, 55)
        self.show_lists[status].horizontalHeader().resizeSection(3, 100)

        i = 0
        for show in showlist:
            progress_str = "%d/%d" % (show['my_progress'], show['total'])
            progress_widget = QtGui.QProgressBar()
            progress_widget.setMinimum(0)
            progress_widget.setMaximum(100)
            if show['total'] > 0:
                progress_widget.setValue( 100L * show['my_progress'] / show['total'] )

            self.show_lists[status].setItem(i, 0, QtGui.QTableWidgetItem(show['title']))
            self.show_lists[status].setItem(i, 1, QtGui.QTableWidgetItem(progress_str))
            self.show_lists[status].setItem(i, 2, QtGui.QTableWidgetItem(str(show['my_score']) ))
            self.show_lists[status].setCellWidget(i, 3, progress_widget )
            self.show_lists[status].setItem(i, 4, QtGui.QTableWidgetItem(str(show['id'])))

            i += 1

    ### Slots
    def s_show_selected(self, new, old):
        index = new.row()
        selected_id = self.notebook.currentWidget().item( index, 4 ).text()

        # Attempt to convert to int if possible
        try:
            selected_id = int(selected_id)
        except:
            pass

        show = self.worker.engine.get_show_info(selected_id)
        
        # Update information
        self.show_title.setText(show['title'])

        # Make it global
        self.selected_show = show

    def s_switch_account(self):
        self.accountman_widget.show()

    def s_about(self):
        QtGui.QMessageBox.about(self, 'About wMAL-qt',
            '<p><b>About wMAL-qt</b></p><p>wMAL is an open source client for media tracking websites.</p>'
            '<p>This program is licensed under the GPLv3, for more information read COPYING file.</p>'
            '<p>Copyright (C) z411 - Icon by shuuichi</p>'
            '<p><a href="http://github.com/z411/wmal-python">http://github.com/z411/wmal-python</a></p>')

    def s_about_qt(self):
        QtGui.QMessageBox.aboutQt(self, 'About Qt')

    ### Returning functions 
    def r_engine_loaded(self, result):
        if result['success']:
            self.worker.set_function('get_list', self.r_build_lists)
            self.worker.start()

    def r_build_lists(self, result):
        if result['success']:
            self.notebook.clear()
            self.show_lists = dict()

            statuses_nums = self.worker.engine.mediainfo['statuses']
            statuses_names = self.worker.engine.mediainfo['statuses_dict']
            
            for status in statuses_nums:
                name = statuses_names[status]

                self.show_lists[status] = QtGui.QTableWidget()
                self.show_lists[status].setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
                self.show_lists[status].setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
                self.show_lists[status].setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
                self.show_lists[status].verticalHeader().hide()
                self.show_lists[status].currentItemChanged.connect(self.s_show_selected)
                
                self.notebook.addTab(self.show_lists[status], name)

            self._rebuild_lists(result['showlist'])

    def r_engine_unloaded(self, result):
        if result['success']:
            self.close()


class AccountWidget(QtGui.QDialog):
    selected = QtCore.pyqtSignal(int)
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
        cancel_btn = QtGui.QPushButton('Cancel')
        cancel_btn.clicked.connect(self.cancel)
        select_btn = QtGui.QPushButton('Select')
        select_btn.clicked.connect(self.select)
        bottom_layout.addWidget(cancel_btn)
        bottom_layout.addWidget(select_btn)

        # Finish layout
        layout.addWidget(self.table)
        layout.addLayout(bottom_layout)
        self.setLayout(layout)

    def select(self, checked):
        try:
            selected_account_num = self.table.selectedItems()[0].num
            self.selected.emit(selected_account_num)
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
    
    def __init__(self, text, alignment=None, color=None):
        QtGui.QTableWidgetItem.__init__(self, text)
        if alignment:
            self.setTextAlignment( alignment )
        if color:
            self.setBackgroundColor( color )


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
    engine_changed_show = QtCore.pyqtSignal(dict)

    def __init__(self, account):
        super(Engine_Worker, self).__init__()
        self.engine = Engine(account, self._messagehandler)
        self.engine.connect_signal('episode_changed', self._changed_show)

        self.function_list = {
            'start': self._start,
            'reload': self._reload,
            'get_list': self._get_list,
            'unload': self._unload,
        }

    def _messagehandler(self, classname, msgtype, msg):
        self.changed_status.emit(msg)

    def _error(self, msg):
        self.raised_error.emit(msg)

    def _changed_show(self, show):
        self.engine_changed_show.emit(show)
    
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

    def set_function(self, function, ret_function, *args, **kwargs):
        self.function = self.function_list[function]
        try:
            self.finished.disconnect()
        except Exception:
            pass
        self.finished.connect(ret_function)
        self.args = args
        self.kwargs = kwargs

    def __del__(self):
        self.wait()

    def run(self):
        print "Running"
        ret = self.function(*self.args,**self.kwargs)
        self.finished.emit(ret)


def main():
    app = QtGui.QApplication(sys.argv)
    mainwindow = wmal()
    #mainwindow.start()
    sys.exit(app.exec_())

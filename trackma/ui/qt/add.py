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

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QTableView, QListView, QAbstractItemView, QHeaderView,
    QDialogButtonBox)

from trackma.ui.qt.models import AddTableModel, AddListModel
from trackma.ui.qt.delegates import AddListDelegate
from trackma.ui.qt.widgets import DetailsWidget

class AddDialog(QDialog):
    worker = None
    selected_show = None
    results = []

    def __init__(self, parent, worker, current_status, default=None):
        QDialog.__init__(self, parent)
        self.resize(950, 700)
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
        #self.model = AddTableModel()
        #self.table = QTableView()
        
        self.model = AddListModel(api_info=self.worker.engine.api_info)
        self.table = QListView()
        self.table.setItemDelegate(AddListDelegate())
        self.table.setFlow(QListView.LeftToRight)
        self.table.setWrapping(True)

        self.table.setModel(self.model)
        #self.table.setSortingEnabled(True)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        #self.table.setGridStyle(QtCore.Qt.NoPen)
        
        self.model.setResults([{'id': 1, 'title': 'Hola', 'image': 'https://omaera.org/icon.png'}])
        
        #if pyqt_version is 5:
        #    self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        #else:
        #    self.table.horizontalHeader().setResizeMode(0, QHeaderView.Stretch)
            
        #self.table.currentItemChanged.connect(self.s_show_selected)

        """columns = ['Title', 'Type', 'Total']
        self.table = QTableWidget()
        self.table.horizontalHeader().sortIndicatorChanged.connect(self.sort_results)
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setHighlightSections(False)
        """

        bottom_buttons = QDialogButtonBox(self)
        bottom_buttons.addButton("Cancel", QDialogButtonBox.RejectRole)
        self.select_btn = bottom_buttons.addButton("Add", QDialogButtonBox.AcceptRole)
        bottom_buttons.accepted.connect(self.s_add)
        bottom_buttons.rejected.connect(self.close)

        # Info box
        self.details = DetailsWidget(self, worker)

        # Finish layout
        layout.addLayout(top_layout,     0, 0, 1, 2)
        layout.addWidget(self.table,     1, 0, 1, 2)
        #layout.addWidget(self.details,   1, 1, 1, 1)
        layout.addWidget(bottom_buttons, 2, 0, 1, 2)
        self.setLayout(layout)

    def worker_call(self, function, ret_function, *args, **kwargs):
        # Run worker in a thread
        self.worker.set_function(function, ret_function, *args, **kwargs)
        self.worker.start()

    def _enable_widgets(self, enable):
        self.search_btn.setEnabled(enable)
        self.table.setEnabled(enable)

    def sort_results(self, index, order):
        if not self.results:
            return
        rev = bool(order)
        if index == 0:
            self.results.sort(key=lambda s: s['title'], reverse=rev)
        elif index == 1:
            self.results.sort(key=lambda s: s['type'], reverse=rev)
        else:
            self.results.sort(key=lambda s: str(s['total']), reverse=rev)

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
            self.model.setResults(result['results'])
            
            """self.table.setRowCount(len(self.results))
            i = 0
            for res in self.results:
                self.table.setRowHeight(i, QtGui.QFontMetrics(self.table.font()).height() + 2);
                self.table.setItem(i, 0, ShowItem(res['title']))
                self.table.setItem(i, 1, ShowItem(res['type']))
                self.table.setItem(i, 2, ShowItem(str(res['total'])))

                i += 1
            if self.table.currentRow() is 0:  # Row number hasn't changed but the data probably has!
                self.s_show_selected(self.table.item(0, 0))
            self.table.setCurrentItem(self.table.item(0, 0))"""
        else:
            self.model.setResults(None)
            #self.table.setRowCount(0)

        self.search_btn.setEnabled(True)
        self.table.setEnabled(True)

    def r_added(self, result):
        if result['success']:
            if self.default:
                self.accept()

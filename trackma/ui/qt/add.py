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

from datetime import date

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableView, QAbstractItemView, QHeaderView, QSpinBox,
    QDialogButtonBox, QStackedWidget, QComboBox, QRadioButton, QSplitter)

from trackma.ui.qt.details import DetailsDialog
from trackma.ui.qt.widgets import AddTableDetailsView, AddCardView

from trackma import utils

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
        
        # Get available search methods and default to keyword search if not reported by the API
        search_methods = self.worker.engine.mediainfo.get('search_methods', [utils.SEARCH_METHOD_KW])

        layout = QVBoxLayout()

        # Create top layout
        top_layout = QHBoxLayout()

        if utils.SEARCH_METHOD_KW in search_methods:
            self.search_rad = QRadioButton('By keyword:')
            self.search_rad.setChecked(True)
            self.search_txt = QLineEdit()
            self.search_txt.returnPressed.connect(self.s_search)
            if default:
                self.search_txt.setText(default)
            self.search_btn = QPushButton('Search')
            self.search_btn.clicked.connect(self.s_search)
            top_layout.addWidget(self.search_rad)
            top_layout.addWidget(self.search_txt)
        else:
            top_layout.setAlignment(QtCore.Qt.AlignRight)

        top_layout.addWidget(self.search_btn)
        
        # Create filter line
        filters_layout = QHBoxLayout()
        
        if utils.SEARCH_METHOD_SEASON in search_methods:
            self.season_rad = QRadioButton('By season:')
            self.season_combo = QComboBox()
            self.season_combo.addItem('Winter', utils.SEASON_WINTER)
            self.season_combo.addItem('Spring', utils.SEASON_SPRING)
            self.season_combo.addItem('Summer', utils.SEASON_SUMMER)
            self.season_combo.addItem('Fall', utils.SEASON_FALL)
        
            self.season_year = QSpinBox()

            today = date.today()
            current_season = (today.month - 1) / 3

            self.season_year.setRange(1900, today.year)
            self.season_year.setValue(today.year)
            self.season_combo.setCurrentIndex(current_season)

            filters_layout.addWidget(self.season_rad)
            filters_layout.addWidget(self.season_combo)
            filters_layout.addWidget(self.season_year)
        
            filters_layout.setAlignment(QtCore.Qt.AlignLeft)
            filters_layout.addWidget(QSplitter())
        else:
            filters_layout.setAlignment(QtCore.Qt.AlignRight)
        
        view_combo = QComboBox()
        view_combo.addItem('Table view')
        view_combo.addItem('Card view')
        view_combo.currentIndexChanged.connect(self.s_change_view)
        
        filters_layout.addWidget(view_combo)

        # Create central content
        self.contents = QStackedWidget()
        
        # Set up views
        tableview = AddTableDetailsView(None, self.worker)
        tableview.changed.connect(self.s_selected)
        self.contents.addWidget(tableview)
        
        cardview = AddCardView(api_info=self.worker.engine.api_info)
        cardview.changed.connect(self.s_selected)
        cardview.activated.connect(self.s_show_details)
        self.contents.addWidget(cardview)
        
        # Use for testing
        #self.set_results([{'id': 1, 'title': 'Hola', 'image': 'https://omaera.org/icon.png'}])

        bottom_buttons = QDialogButtonBox()
        bottom_buttons.addButton("Cancel", QDialogButtonBox.RejectRole)
        self.add_btn = bottom_buttons.addButton("Add", QDialogButtonBox.AcceptRole)
        self.add_btn.setEnabled(False)
        bottom_buttons.accepted.connect(self.s_add)
        bottom_buttons.rejected.connect(self.close)

        # Finish layout
        layout.addLayout(top_layout)
        layout.addLayout(filters_layout)
        layout.addWidget(self.contents)
        layout.addWidget(bottom_buttons)
        self.setLayout(layout)

        if utils.SEARCH_METHOD_SEASON in search_methods:
            self.search_txt.setFocus()

    def worker_call(self, function, ret_function, *args, **kwargs):
        # Run worker in a thread
        self.worker.set_function(function, ret_function, *args, **kwargs)
        self.worker.start()

    def _enable_widgets(self, enable):
        self.search_btn.setEnabled(enable)
        self.contents.currentWidget().setEnabled(enable)

    def set_results(self, results):
        self.results = results
        self.contents.currentWidget().setResults(self.results)

    # Slots
    def s_show_details(self):
        detailswindow = DetailsDialog(self, self.worker, self.selected_show)
        detailswindow.setModal(True)
        detailswindow.show()

    def s_change_view(self, item):
        self.contents.currentWidget().getModel().setResults(None)
        self.contents.setCurrentIndex(item)
        self.contents.currentWidget().getModel().setResults(self.results)
        
    def s_search(self):
        if self.search_rad.isChecked():
            criteria = self.search_txt.text().strip()
            if not criteria:
                return
            method = utils.SEARCH_METHOD_KW
        elif self.season_rad.isChecked():
            criteria = (self.season_combo.itemData(self.season_combo.currentIndex()), self.season_year.value())
            method = utils.SEARCH_METHOD_SEASON
        
        self.contents.currentWidget().clearSelection()
        self.selected_show = None
        
        self._enable_widgets(False)
        self.add_btn.setEnabled(False)
        
        self.worker_call('search', self.r_searched, criteria, method)
    
    def s_selected(self, show):
        self.selected_show = show
        self.add_btn.setEnabled(True)
        
    def s_add(self):
        if self.selected_show:
            self.worker_call('add_show', self.r_added, self.selected_show, self.current_status)

    # Worker responses
    def r_searched(self, result):
        self._enable_widgets(True)
        
        if result['success']:
            self.set_results(result['result'])
            
            """
            if self.table.currentRow() is 0:  # Row number hasn't changed but the data probably has!
                self.s_show_selected(self.table.item(0, 0))
            self.table.setCurrentItem(self.table.item(0, 0))"""
        else:
            self.set_results(None)

    def r_added(self, result):
        if result['success']:
            if self.default:
                self.accept()

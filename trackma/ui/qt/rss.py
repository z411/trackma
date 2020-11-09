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

from trackma.ui.qt.models import RSSTableModel
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableView,
    QDialogButtonBox)

class RSSDialog(QDialog):
    def __init__(self, parent, worker):
        QDialog.__init__(self, parent)
        self.resize(800, 700)
        self.setWindowTitle('RSS Feed')
        self.worker = worker
        self.results = None
        
        layout = QVBoxLayout()
        top_layout = QHBoxLayout()

        search_lbl = QLabel('Search RSS:')
        self.search_txt = QLineEdit()
        self.search_txt.setClearButtonEnabled(True)
        self.search_txt.setText(self.worker.engine.get_config('rss_url'))
        self.search_txt.returnPressed.connect(self.s_search)
        self.search_btn = QPushButton('Search')
        self.search_btn.clicked.connect(self.s_search)
        top_layout.addWidget(search_lbl)
        top_layout.addWidget(self.search_txt)
        top_layout.addWidget(self.search_btn)
        
        self.view = QTableView(self)
        self.view.setModel(RSSTableModel())
        
        bottom_buttons = QDialogButtonBox()
        bottom_buttons.addButton("Cancel", QDialogButtonBox.RejectRole)
        self.download_btn = bottom_buttons.addButton(
            "Download", QDialogButtonBox.AcceptRole)
        self.download_btn.setEnabled(False)
        #bottom_buttons.accepted.connect(self.s_download)
        bottom_buttons.rejected.connect(self.close)

        layout.addLayout(top_layout)
        layout.addWidget(self.view)
        layout.addWidget(bottom_buttons)
        self.setLayout(layout)
        self.search_txt.setFocus()
    
    def _enable_widgets(self, enable):
        self.search_btn.setEnabled(enable)
        self.view.setEnabled(enable)

    def worker_call(self, function, ret_function, *args, **kwargs):
        # Run worker in a thread
        self.worker.set_function(function, ret_function, *args, **kwargs)
        self.worker.start()

    def set_results(self, results):
        self.results = results
        self.view.model().setResults(self.results)
        
    def s_search(self):
        self._enable_widgets(False)
        self.worker_call('rss_list', self.r_rss_done, self.search_txt.text())
    
    def r_rss_done(self, result):
        self._enable_widgets(True)
        
        if result['success']:
            self.set_results(result['result'])
        else:
            self.set_results(None)

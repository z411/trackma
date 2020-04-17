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

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox

from trackma.ui.qt.widgets import DetailsWidget

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

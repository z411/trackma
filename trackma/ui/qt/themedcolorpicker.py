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

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QPushButton, QDialogButtonBox)

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
                self.colors[-1].setStyleSheet('background-color: ' + QtGui.QColor(QtGui.QPalette().color(group, role)).name())
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

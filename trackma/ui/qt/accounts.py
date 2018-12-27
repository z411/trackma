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
    QDialog, QTableWidgetItem, QVBoxLayout, QHBoxLayout, QTableWidget,
    QAbstractItemView, QCheckBox, QPushButton, QComboBox, QHeaderView,
    QMessageBox, QFormLayout, QLabel, QLineEdit, QDialogButtonBox)
    
from trackma import utils

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
        select_btn.setDefault(True)
        bottom_layout.addWidget(self.remember_chk)
        bottom_layout.addWidget(cancel_btn)
        bottom_layout.addWidget(add_btn)
        bottom_layout.addWidget(self.edit_btns)
        bottom_layout.addWidget(select_btn)

        # Get icons
        self.icons = dict()
        for libname, lib in utils.available_libs.items():
            self.icons[libname] = QtGui.QIcon(lib[1])

        # Populate list
        self.update()
        self.rebuild()

        # Finish layout
        layout.addWidget(self.table)
        layout.addLayout(bottom_layout)
        self.setLayout(layout)

    def update(self):
        self.remember_chk.setChecked(self.accountman.get_default() is not None)

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

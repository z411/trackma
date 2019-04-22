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


import os
import webbrowser
import gi
gi.require_version('Gtk', '3.0')
from enum import Enum
from gi.repository import Gtk, GdkPixbuf, GObject
from trackma.ui.gtk import gtk_dir
from trackma.ui.gtk.gi_composites import GtkTemplate
from trackma import utils


class AccountsView(Enum):
    LIST = 1
    NEW = 2
    EDIT = 3


@GtkTemplate(ui=os.path.join(gtk_dir, 'data/accountswindow.ui'))
class AccountsWindow(Gtk.Dialog):

    __gtype_name__ = 'AccountsWindow'

    __gsignals__ = {
        'account-cancel': (GObject.SIGNAL_RUN_FIRST, None,
                           ()),
        'account-open': (GObject.SIGNAL_RUN_FIRST, None,
                         (int, bool))
    }

    header_bar = GtkTemplate.Child()
    internal_box = GtkTemplate.Child()
    accounts_frame = GtkTemplate.Child()
    accounts_listbox = GtkTemplate.Child()
    revealer_action_bar = GtkTemplate.Child()
    btn_cancel = GtkTemplate.Child()
    btn_add = GtkTemplate.Child()
    btn_new_confirm = GtkTemplate.Child()
    btn_new_cancel = GtkTemplate.Child()
    btn_edit_confirm = GtkTemplate.Child()
    remember_switch = GtkTemplate.Child()
    accounts_stack = GtkTemplate.Child()
    accounts_combo = GtkTemplate.Child()
    password_label = GtkTemplate.Child()
    password_entry = GtkTemplate.Child()
    username_label = GtkTemplate.Child()
    username_entry = GtkTemplate.Child()
    btn_pin_request = GtkTemplate.Child()

    def __init__(self, manager, **kwargs):
        Gtk.Window.__init__(self, **kwargs)
        self.init_template()

        self.accounts = []
        self.pixbufs = {}
        self.treeiters = {}
        self.current = AccountsView.LIST
        self.manager = manager

        self._remove_border()
        self._add_separators()
        self._refresh_remember()
        self._refresh_pixbufs()
        self._refresh_list()
        self._populate_combobox()

        self.show()

    def _remove_border(self):
        self.internal_box.set_border_width(0)

    def _add_separators(self):
        self.accounts_listbox.set_header_func(self._accounts_listbox_header_func, None)

    def _accounts_listbox_header_func(self, row, before, user_data):
        if before is None:
            row.set_header(None)
            return

        current = row.get_header()
        if current is None:
            current = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            current.show()
            row.set_header(current)

    def _refresh_remember(self):
        remember = self.manager.get_default() is not None
        self.remember_switch.set_active(remember)

    def _refresh_pixbufs(self):
        self.pixbufs = {}
        for (libname, lib) in utils.available_libs.items():
            self.pixbufs[libname] = GdkPixbuf.Pixbuf.new_from_file(lib[1])

    def _refresh_list(self):
        for account in self.accounts:
            account.destroy()

        self.accounts = []

        for k, account in self.manager.get_accounts():
            libname = account['api']
            try:
                api = utils.available_libs[libname]
                account = AccountRow({
                    'number': k,
                    'username': account['username'],
                    'libname': libname,
                    'libname_desc': api[0],
                    'logo': self.pixbufs[libname],
                    'active': True
                })

            except KeyError:
                # Invalid API
                account = AccountRow({
                    'number': k,
                    'username': account['username'],
                    'libname': None,
                    'libname_desc': 'N/A',
                    'logo': None,
                    'active': False
                })

            self.accounts_listbox.add(account)
            self.accounts.append(account)

        if not self.accounts:
            self.accounts_frame.hide()
        else:
            self.accounts_frame.show()

    @GtkTemplate.Callback
    def _on_dialog_close(self, dialog):
        self.emit('account-cancel')
        self.destroy()

    @GtkTemplate.Callback
    def _on_btn_cancel_clicked(self, btn):
        self.emit('account-cancel')
        self.destroy()

    @GtkTemplate.Callback
    def _on_row_selected(self, list_box, row):
        reveal = row is not None
        self.revealer_action_bar.set_reveal_child(reveal)

    @GtkTemplate.Callback
    def _on_row_activated(self, list_box, row):
        acc_num = row.get_account_id()
        remember = self.remember_switch.get_active()
        self.emit('account-open', acc_num, remember)
        self.destroy()

    @GtkTemplate.Callback
    def _on_btn_edit_clicked(self, btn):
        self._show_edit()

    @GtkTemplate.Callback
    def _on_btn_open_clicked(self, btn):
        acc_num = self.accounts_listbox.get_selected_row().get_account_id()
        remember = self.remember_switch.get_active()
        self.emit('account-open', acc_num, remember)
        self.destroy()

    @GtkTemplate.Callback
    def _on_btn_delete_clicked(self, btn):
        row = self.accounts_listbox.get_selected_row()
        self.manager.delete_account(row.get_account_id())
        row.destroy()

    @GtkTemplate.Callback
    def _on_btn_add_clicked(self, btn):
        self._show_add_new()

    @GtkTemplate.Callback
    def _on_btn_new_cancel_clicked(self, btn):
        self._show_accounts_list()

    @GtkTemplate.Callback
    def _on_btn_new_confirm_clicked(self, btn):
        self._add_account()
        self._refresh_list()
        self._show_accounts_list()

    @GtkTemplate.Callback
    def _on_btn_edit_confirm_clicked(self, btn):
        self._edit_account()
        self._refresh_list()
        self._show_accounts_list()

    def _show_edit(self):
        row = self.accounts_listbox.get_selected_row()
        self.account_edit = self.manager.get_account(row.get_account_id())
        self.account_edit['account_id'] = row.get_account_id()

        self.header_bar.set_title("Edit account")
        self._clear_new_account()

        if utils.available_libs[self.account_edit['api']][2] == utils.LOGIN_OAUTH:
            self._show_oauth_account()
        else:
            self._show_password_account()

        self.accounts_combo.set_active_iter(self.treeiters[row.get_libname()])
        self.username_entry.set_text(self.account_edit['username'])
        self.password_entry.set_text(self.account_edit['password'])

        self.accounts_combo.set_sensitive(False)
        self.username_entry.set_sensitive(False)

        self.btn_new_confirm.hide()
        self.btn_new_cancel.show()
        self.btn_edit_confirm.show()
        self.btn_add.hide()
        self.btn_cancel.hide()

        self.current = AccountsView.EDIT
        self.accounts_stack.set_visible_child_full('new_account', Gtk.StackTransitionType.SLIDE_LEFT)

    def _show_add_new(self):
        self.header_bar.set_title("Add account")
        self._clear_new_account()
        self.btn_new_confirm.show()
        self.btn_new_cancel.show()
        self.btn_add.hide()
        self.btn_cancel.hide()
        self.accounts_combo.set_sensitive(True)
        self.username_entry.set_sensitive(True)

        self.current = AccountsView.NEW
        self.accounts_stack.set_visible_child_full('new_account', Gtk.StackTransitionType.SLIDE_LEFT)

    def _show_accounts_list(self):
        self.header_bar.set_title("Accounts")
        self.btn_new_confirm.hide()
        self.btn_new_cancel.hide()
        self.btn_edit_confirm.hide()
        self.btn_add.show()
        self.btn_cancel.show()

        self.current = AccountsView.LIST
        self.accounts_stack.set_visible_child_full('accounts', Gtk.StackTransitionType.SLIDE_RIGHT)

    def _populate_combobox(self):
        model_api = Gtk.ListStore(str, str, GdkPixbuf.Pixbuf)

        for (libname, lib) in sorted(utils.available_libs.items()):
            self.treeiters[libname] = model_api.append([libname, lib[0], self.pixbufs[libname]])

        self.accounts_combo.set_model(model_api)

    @GtkTemplate.Callback
    def _on_accounts_combo_changed(self, combo):
        self.username_entry.set_text("")
        self.password_entry.set_text("")
        api = self._get_combo_active_api_name()

        if not api or utils.available_libs[api][2] == utils.LOGIN_OAUTH:
            self._show_oauth_account()
        else:
            self._show_password_account()

    @GtkTemplate.Callback
    def _on_btn_pin_request_clicked(self, btn):
        api = self._get_combo_active_api_name()
        url = utils.available_libs[api][4]

        webbrowser.open(url, 2, True)

    def _clear_new_account(self):
        self.accounts_combo.set_active_id(None)
        self.username_entry.set_text("")
        self.password_entry.set_text("")

    def _show_oauth_account(self):
        self.username_label.set_text("Name")
        self.password_label.set_text("PIN")
        self.password_entry.set_visibility(True)
        self.btn_pin_request.show()

    def _show_password_account(self):
        self.username_label.set_text("Username")
        self.password_label.set_text("Password")
        self.password_entry.set_visibility(False)
        self.btn_pin_request.hide()

    def _get_combo_active_api_name(self):
        apiiter = self.accounts_combo.get_active_iter()

        if not apiiter:
            return None

        return self.accounts_combo.get_model().get(apiiter, 0)[0]

    @GtkTemplate.Callback
    def _on_username_entry_changed(self, entry):
        if self.current == AccountsView.NEW:
            self._refresh_btn_new_confirm()
        elif self.current == AccountsView.EDIT:
            self._refresh_btn_edit_confirm()

    @GtkTemplate.Callback
    def _on_password_entry_changed(self, entry):
        if self.current == AccountsView.NEW:
            self._refresh_btn_new_confirm()
        elif self.current == AccountsView.EDIT:
            self._refresh_btn_edit_confirm()

    def _refresh_btn_new_confirm(self):
        sensitive = (self._get_combo_active_api_name() and
                     self.username_entry.get_text().strip() and
                     self.password_entry.get_text())

        self.btn_new_confirm.set_sensitive(sensitive)

    def _refresh_btn_edit_confirm(self):
        sensitive = (self.password_entry.get_text() and
                     not self.account_edit['password'] == self.password_entry.get_text())
        self.btn_edit_confirm.set_sensitive(sensitive)

    def _add_account(self):
        username =  self.username_entry.get_text().strip()
        password = self.password_entry.get_text()
        api = self._get_combo_active_api_name()

        self.manager.add_account(username, password, api)

    def _edit_account(self):
        num = self.account_edit['account_id']
        username =  self.account_edit['username']
        password = self.password_entry.get_text()
        api = self.account_edit['api']

        self.manager.edit_account(num, username, password, api)


@GtkTemplate(ui=os.path.join(gtk_dir, 'data/accountrow.ui'))
class AccountRow(Gtk.ListBoxRow):
    __gtype_name__ = 'AccountRow'

    account_logo = GtkTemplate.Child()
    account_username = GtkTemplate.Child()
    account_api = GtkTemplate.Child()

    def __init__(self, account):
        Gtk.ListBoxRow.__init__(self)
        self.init_template()
        self.account = account

        if account['active']:
            self.account_username.set_text(account['username'])
            self.account_api.set_text(account['libname_desc'])
            self.account_logo.set_from_pixbuf(account['logo'])

    def get_account_id(self):
        return self.account['number']

    def get_libname(self):
        return self.account['libname']


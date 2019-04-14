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


import webbrowser
import gi


gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf
from trackma import utils


class AccountsWindow(Gtk.Window):
    default = None

    def __init__(self, manager, switch=False):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)
        self.use_button = Gtk.Button('Switch')
        self.use_button.set_sensitive(False)

        self.manager = manager
        self.switch = switch

        self.pixbufs = None
        self.accountlist = None
        self.store = None
        self.remember = None
        self.delete_button = None
        self.add_win = None

    def create(self):
        self.pixbufs = {}
        for (libname, lib) in utils.available_libs.items():
            self.pixbufs[libname] = GdkPixbuf.Pixbuf.new_from_file(lib[1])

        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Select Account')
        self.set_border_width(10)
        self.connect('delete-event', self.on_delete)

        vbox = Gtk.VBox(False, 10)

        # Treeview
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_size_request(400, 200)

        self.accountlist = Gtk.TreeView()

        col_user = Gtk.TreeViewColumn('Username')
        col_user.set_expand(True)
        self.accountlist.append_column(col_user)
        col_site = Gtk.TreeViewColumn('Site')
        self.accountlist.append_column(col_site)

        renderer_user = Gtk.CellRendererText()
        col_user.pack_start(renderer_user, False)
        col_user.add_attribute(renderer_user, 'text', 1)
        renderer_icon = Gtk.CellRendererPixbuf()
        col_site.pack_start(renderer_icon, False)
        col_site.add_attribute(renderer_icon, 'pixbuf', 3)
        renderer_site = Gtk.CellRendererText()
        col_site.pack_start(renderer_site, False)
        col_site.add_attribute(renderer_site, 'text', 2)

        self.store = Gtk.ListStore(int, str, str, GdkPixbuf.Pixbuf, bool)
        self.accountlist.set_model(self.store)

        self.accountlist.get_selection().connect("changed", self.on_account_changed)
        self.accountlist.connect("row-activated", self.on_row_activated)

        # Bottom buttons
        alignment = Gtk.Alignment(xalign=1.0, xscale=0)
        bottombar = Gtk.HBox(False, 5)

        self.remember = Gtk.CheckButton('Remember')
        if self.manager.get_default() is not None:
            self.remember.set_active(True)
        add_button = Gtk.Button('Add')
        add_button.set_image(Gtk.Image.new_from_icon_name(Gtk.STOCK_APPLY, Gtk.IconSize.BUTTON))
        add_button.connect("clicked", self._do_add)
        self.delete_button = Gtk.Button('Delete')
        self.delete_button.set_sensitive(False)
        self.delete_button.connect("clicked", self.__do_delete)
        self.delete_button.set_image(Gtk.Image.new_from_icon_name(Gtk.STOCK_DELETE, Gtk.IconSize.BUTTON))
        close_button = Gtk.Button('Close')
        close_button.set_image(Gtk.Image.new_from_icon_name(Gtk.STOCK_CLOSE, Gtk.IconSize.BUTTON))
        close_button.connect("clicked", self.__do_close)

        bottombar.pack_start(self.remember, False, False, 0)
        bottombar.pack_start(self.use_button, False, False, 0)
        bottombar.pack_start(add_button, False, False, 0)
        bottombar.pack_start(self.delete_button, False, False, 0)
        bottombar.pack_start(close_button, False, False, 0)
        alignment.add(bottombar)

        sw.add(self.accountlist)

        vbox.pack_start(sw, True, True, 0)
        vbox.pack_start(alignment, False, False, 0)
        self.add(vbox)

        self._refresh_list()
        self.show_all()

    def _refresh_list(self):
        self.store.clear()
        for k, account in self.manager.get_accounts():
            libname = account['api']
            try:
                api = utils.available_libs[libname]
                self.store.append([k, account['username'], api[0], self.pixbufs[libname], True])
            except KeyError:
                # Invalid API
                self.store.append([k, account['username'], 'N/A', None, False])


    def is_remember(self):
        # Return the state of the checkbutton if there's no default account
        if self.default is None:
            return self.remember.get_active()

        return True

    def get_selected(self):
        selection = self.accountlist.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)
        return selection.get_selected()

    def get_selected_id(self):
        if self.default is not None:
            return self.default

        tree_model, tree_iter = self.get_selected()
        return tree_model.get_value(tree_iter, 0)

    def on_account_changed(self, widget):
        tree_model, tree_iter = self.get_selected()
        if tree_iter:
            is_selectable = tree_model.get_value(tree_iter, 4)
        else:
            is_selectable = False

        self.use_button.set_sensitive(is_selectable)
        self.delete_button.set_sensitive(True)

    def on_row_activated(self, treeview, tree_iter, path):
        self.use_button.emit("clicked")

    def _do_add(self, widget):
        """Create Add Account window"""
        self.add_win = AccountAddWindow(self.pixbufs)
        self.add_win.add_button.connect("clicked", self.add_account)

    def add_account(self, widget):
        """Closes Add Account window and tells the manager to add
        the account to the database"""
        username =  self.add_win.txt_user.get_text().strip()
        password = self.add_win.txt_passwd.get_text()
        apiiter = self.add_win.cmb_api.get_active_iter()

        if not username:
            self.error('Please enter a username.')
            return
        if not password:
            self.error('Please enter a password.')
            return
        if not apiiter:
            self.error('Please select a website.')
            return

        api = self.add_win.model_api.get(apiiter, 0)[0]
        self.add_win.destroy()

        self.manager.add_account(username, password, api)
        self._refresh_list()

    def __do_delete(self, widget):
        selectedid = self.get_selected_id()
        self.manager.delete_account(selectedid)

        self._refresh_list()

    def error(self, msg):
        md = Gtk.MessageDialog(None,
                               Gtk.DialogFlags.DESTROY_WITH_PARENT,
                               Gtk.MessageType.ERROR,
                               Gtk.ButtonsType.CLOSE, str(msg))
        md.run()
        md.destroy()

    def modal_close(self, widget, response_id):
        widget.destroy()

    def __do_close(self, widget):
        self.destroy()
        if not self.switch:
            Gtk.main_quit()

    def on_delete(self, widget, data):
        self.__do_close(None)
        return False


class AccountAddWindow(Gtk.Window):
    def __init__(self, pixbufs):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)

        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title('Create Account')
        self.set_border_width(10)

        # Labels
        self.lbl_user = Gtk.Label('Username')
        self.lbl_user.set_size_request(70, -1)
        self.lbl_passwd = Gtk.Label('Password')
        self.lbl_passwd.set_size_request(70, -1)
        lbl_api = Gtk.Label('Website')
        lbl_api.set_size_request(70, -1)

        # Entries
        self.txt_user = Gtk.Entry()
        self.txt_user.set_max_length(128)
        self.txt_user.set_activates_default(True)
        self.txt_passwd = Gtk.Entry()
        self.txt_passwd.set_visibility(False)
        self.txt_passwd.set_activates_default(True)

        # Combobox
        self.model_api = Gtk.ListStore(str, str, GdkPixbuf.Pixbuf)

        for (libname, lib) in sorted(utils.available_libs.items()):
            self.model_api.append([libname, lib[0], pixbufs[libname]])

        self.cmb_api = Gtk.ComboBox.new_with_model(self.model_api)
        cell_icon = Gtk.CellRendererPixbuf()
        cell_name = Gtk.CellRendererText()
        self.cmb_api.pack_start(cell_icon, False)
        self.cmb_api.pack_start(cell_name, True)
        self.cmb_api.add_attribute(cell_icon, 'pixbuf', 2)
        self.cmb_api.add_attribute(cell_name, 'text', 1)
        self.cmb_api.connect("changed", self._refresh)

        # Buttons
        self.btn_auth = Gtk.Button("Request PIN")
        self.btn_auth.connect("clicked", self.__do_auth)

        alignment = Gtk.Alignment(xalign=0.5, xscale=0)
        bottombar = Gtk.HBox(False, 5)
        self.add_button = Gtk.Button(stock=Gtk.STOCK_APPLY)
        self.add_button.set_can_default(True)
        self.add_button.grab_default()
        close_button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        close_button.connect("clicked", self.__do_close)
        bottombar.pack_start(self.add_button, False, False, 0)
        bottombar.pack_start(close_button, False, False, 0)
        alignment.add(bottombar)

        # HBoxes
        line1 = Gtk.HBox(False, 5)
        line1.pack_start(self.lbl_user, False, False, 0)
        line1.pack_start(self.txt_user, True, True, 0)

        line2 = Gtk.HBox(False, 5)
        line2.pack_start(self.lbl_passwd, False, False, 0)
        line2.pack_start(self.txt_passwd, True, True, 0)
        line2.pack_start(self.btn_auth, False, False, 0)

        line3 = Gtk.HBox(False, 5)
        line3.pack_start(lbl_api, False, False, 0)
        line3.pack_start(self.cmb_api, True, True, 0)

        # Join HBoxes
        vbox = Gtk.VBox(False, 10)
        vbox.pack_start(line3, False, False, 0)
        vbox.pack_start(line1, False, False, 0)
        vbox.pack_start(line2, False, False, 0)
        vbox.pack_start(alignment, False, False, 0)

        self.add(vbox)
        self.show_all()
        self.btn_auth.hide()

    def _refresh(self, widget):
        self.txt_user.set_text("")
        self.txt_passwd.set_text("")

        apiiter = self.cmb_api.get_active_iter()
        api = self.model_api.get(apiiter, 0)[0]
        if utils.available_libs[api][2] == utils.LOGIN_OAUTH:
            self.lbl_user.set_text("Name")
            self.lbl_passwd.set_text("PIN")
            self.txt_passwd.set_visibility(True)
            self.btn_auth.show()
        else:
            self.lbl_user.set_text("Username")
            self.lbl_passwd.set_text("Password")
            self.txt_passwd.set_visibility(False)
            self.btn_auth.hide()

    def __do_auth(self, widget):
        apiiter = self.cmb_api.get_active_iter()
        api = self.model_api.get(apiiter, 0)[0]
        url = utils.available_libs[api][4]

        webbrowser.open(url, 2, True)

    def __do_close(self, widget):
        self.destroy()


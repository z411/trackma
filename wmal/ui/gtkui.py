# wMAL-gtk v0.2
# Lightweight GTK based script for using data from MyAnimeList.
# Copyright (C) 2012  z411
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

VERSION = 'v0.2'

import gobject
import pygtk
pygtk.require('2.0')
import gtk
gtk.gdk.threads_init() # We'll use threads

import os
import time
import threading
import urllib2 as urllib
from cStringIO import StringIO

try:
    import image
    imaging_available = True
except ImportError:
    print "Warning: PIL library isn't available. Preview images will be disabled."
    imaging_available = False

import wmal.messenger as messenger
import wmal.utils as utils

from wmal.engine import Engine
from wmal.accounts import AccountManager
    
class wmal_gtk(object):
    engine = None
    config = None
    show_lists = dict()
    image_thread = None
    close_thread = None
    can_close = False
    hidden = False
    
    def main(self):
        """Start the Account Selector"""
        self.configfile = utils.get_root_filename('wmal-gtk.json')
        self.config = utils.parse_config(self.configfile, utils.gtk_defaults)
        
        manager = AccountManager()
        
        # Use the remembered account if there's one
        if manager.get_default():
            self.start(manager.get_default())
        else:
            self.accountsel = AccountSelect(manager)
            self.accountsel.use_button.connect("clicked", self.use_account)
            self.accountsel.create()
        
        gtk.main()
    
    def do_switch_account(self, widget):
        manager = AccountManager()
        self.accountsel = AccountSelect(manager = AccountManager(), switch=True)
        self.accountsel.use_button.connect("clicked", self.use_account)
        self.accountsel.create()
        
    def use_account(self, widget):
        """Start the main application with the following account"""
        accountid = self.accountsel.get_selected_id()
        account = self.accountsel.manager.get_account(accountid)
        # If remember box is checked, set as default account
        if self.accountsel.is_remember():
            self.accountsel.manager.set_default(accountid)
        else:
            self.accountsel.manager.set_default(None)
        
        self.accountsel.destroy()
        
        # Reload the engine if already started,
        # start it otherwise
        if self.engine:
            self.do_reload(None, account, None)
        else:
            self.start(account)
        
    def start(self, account):
        """Create the main window"""
        # Create engine
        self.account = account
        self.engine = Engine(account)
        
        self.main = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.main.set_position(gtk.WIN_POS_CENTER)
        self.main.connect('delete_event', self.delete_event)
        self.main.connect('destroy', self.on_destroy)
        self.main.set_title('wMAL-gtk ' + VERSION)
        gtk.window_set_default_icon_from_file(utils.datadir + '/data/wmal_icon.png')
        
        # Menus
        mb_list = gtk.Menu()
        mb_play = gtk.ImageMenuItem(gtk.STOCK_MEDIA_PLAY)
        mb_delete = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        mb_delete.connect("activate", self.do_delete)
        mb_exit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        mb_exit.connect("activate", self.do_quit, None)
        gtk.stock_add([(gtk.STOCK_ADD, "Add/Search Shows", 0, 0, "")])
        mb_addsearch = gtk.ImageMenuItem(gtk.STOCK_ADD)
        mb_addsearch.connect("activate", self.do_addsearch)
        gtk.stock_add([(gtk.STOCK_REFRESH, "Retrieve list", 0, 0, "")])
        mb_send = gtk.MenuItem('Send changes')
        mb_send.connect("activate", self.do_send)
        
        mb_list.append(mb_play)
        mb_list.append(mb_delete)
        mb_list.append(gtk.SeparatorMenuItem())
        mb_list.append(mb_addsearch)
        mb_list.append(mb_send)
        mb_list.append(gtk.SeparatorMenuItem())
        mb_list.append(mb_exit)
        
        mb_account = gtk.Menu()
        mb_retrieve = gtk.ImageMenuItem(gtk.STOCK_REFRESH)
        mb_retrieve.connect("activate", self.do_retrieve)
        mb_switch_account = gtk.MenuItem('Switch Account...')
        mb_switch_account.connect("activate", self.do_switch_account)
        mb_settings = gtk.MenuItem('Global Settings...')
        mb_settings.connect("activate", self.do_settings)
        
        mb_account.append(mb_switch_account)
        mb_account.append(mb_retrieve)
        mb_account.append(gtk.SeparatorMenuItem())
        mb_account.append(mb_settings)
        
        self.mb_mediatype_menu = gtk.Menu()
        
        mb_options = gtk.Menu()
        mb_about = gtk.ImageMenuItem(gtk.STOCK_ABOUT)
        mb_about.connect("activate", self.on_about)
        mb_options.append(mb_about)
        
        # Root menubar
        root_menu1 = gtk.MenuItem("Show")
        root_menu1.set_submenu(mb_list)
        root_account = gtk.MenuItem("Options")
        root_account.set_submenu(mb_account)
        mb_mediatype = gtk.MenuItem("Mediatype")
        mb_mediatype.set_submenu(self.mb_mediatype_menu)
        root_menu2 = gtk.MenuItem("Help")
        root_menu2.set_submenu(mb_options)
        
        mb = gtk.MenuBar()
        mb.append(root_menu1)
        mb.append(root_account)
        mb.append(mb_mediatype)
        mb.append(root_menu2)
        
        # Create vertical box
        vbox = gtk.VBox(False, 0)
        self.main.add(vbox)
        
        vbox.pack_start(mb, False, False, 0)
        
        self.top_hbox = gtk.HBox(False, 10)
        self.top_hbox.set_border_width(5)

        self.show_image = ImageView()

        self.top_hbox.pack_start(self.show_image, False, False, 0)
        
        # Right box
        top_right_box = gtk.VBox(False, 0)
        
        # Line 1: Title
        line1 = gtk.HBox(False, 5)
        self.show_title = gtk.Label()
        self.show_title.set_use_markup(True)
        self.show_title.set_alignment(0, 0.5)

        line1.pack_start(self.show_title, True, True, 0)
        
        # API info
        api_hbox = gtk.HBox(False, 5)
        self.api_icon = gtk.Image()
        self.api_user = gtk.Label()
        api_hbox.pack_start(self.api_icon)
        api_hbox.pack_start(self.api_user)
        
        alignment1 = gtk.Alignment(xalign=1, yalign=0)
        alignment1.add(api_hbox)
        line1.pack_start(alignment1, False, False, 0)
        
        top_right_box.pack_start(line1, True, True, 0)
        
        # Line 2: Episode
        line2 = gtk.HBox(False, 5)
        line2_t = gtk.Label('  Progress')
        line2_t.set_size_request(70, -1)
        line2_t.set_alignment(0, 0.5)
        line2.pack_start(line2_t, False, False, 0)
        self.show_ep_num = gtk.SpinButton()
        self.show_ep_num.set_sensitive(False)
        #self.show_ep_num.connect("value_changed", self.do_update)
        line2.pack_start(self.show_ep_num, False, False, 0)
        
        # Buttons
        top_buttons = gtk.HBox(False, 5)
        
        self.update_button = gtk.Button('Update')
        self.update_button.connect("clicked", self.do_update)
        self.update_button.set_sensitive(False)
        line2.pack_start(self.update_button, False, False, 0)
        
        self.play_button = gtk.Button('Play')
        self.play_button.connect("clicked", self.do_play, False)
        self.play_button.set_sensitive(False)
        line2.pack_start(self.play_button, False, False, 0)
        
        self.play_next_button = gtk.Button('Play Next')
        self.play_next_button.connect("clicked", self.do_play, True)
        self.play_next_button.set_sensitive(False)
        line2.pack_start(self.play_next_button, False, False, 0)
        
        top_right_box.pack_start(line2, True, False, 0)
        
        # Disable play button if it's not supported by the mediatype
        if not self.engine.mediainfo['can_play']:
            self.play_button.set_sensitive(False)
            self.play_next_button.set_sensitive(False)
        
        # Line 3: Score
        line3 = gtk.HBox(False, 5)
        line3_t = gtk.Label('  Score')
        line3_t.set_size_request(70, -1)
        line3_t.set_alignment(0, 0.5)
        line3.pack_start(line3_t, False, False, 0)
        self.show_score = gtk.SpinButton()
        self.show_score.set_adjustment(gtk.Adjustment(upper=10, step_incr=1))
        self.show_score.set_sensitive(False)
        line3.pack_start(self.show_score, False, False, 0)
        
        self.scoreset_button = gtk.Button('Set')
        self.scoreset_button.connect("clicked", self.do_score)
        self.scoreset_button.set_sensitive(False)
        line3.pack_start(self.scoreset_button, False, False, 0)
        
        top_right_box.pack_start(line3, True, False, 0)
        
        # Line 4: Status
        line4 = gtk.HBox(False, 5)
        line4_t = gtk.Label('  Status')
        line4_t.set_size_request(70, -1)
        line4_t.set_alignment(0, 0.5)
        line4.pack_start(line4_t, False, False, 0)
        
        self.statusmodel = gtk.ListStore(int, str)
            
        self.statusbox = gtk.ComboBox(self.statusmodel)
        cell = gtk.CellRendererText()
        self.statusbox.pack_start(cell, True)
        self.statusbox.add_attribute(cell, 'text', 1)
        self.statusbox_handler = self.statusbox.connect("changed", self.do_status)
        self.statusbox.set_sensitive(False)
        
        alignment = gtk.Alignment(xalign=0, yalign=0.5)
        alignment.add(self.statusbox)
        
        line4.pack_start(alignment, True, True, 0)
        
        top_right_box.pack_start(line4, True, False, 0)

        self.top_hbox.pack_start(top_right_box, True, True, 0)
        vbox.pack_start(self.top_hbox, False, False, 0)
        
        # Notebook for lists
        self.notebook = gtk.Notebook()
        self.notebook.set_tab_pos(gtk.POS_TOP)
        self.notebook.set_scrollable(True)
        self.notebook.set_border_width(3)
        
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_size_request(550, 300)
        sw.set_border_width(5)
        self.notebook.append_page(sw, gtk.Label("Status"))
        
        vbox.pack_start(self.notebook, True, True, 0)

        self.statusbar = gtk.Statusbar()
        self.statusbar.push(0, 'wMAL-gtk ' + VERSION)
        vbox.pack_start(self.statusbar, False, False, 0)
        
        # Status icon
        self.statusicon = gtk.StatusIcon()
        self.statusicon.set_from_file(utils.datadir + '/data/wmal_icon.png')
        self.statusicon.set_tooltip('wMAL-gtk ' + VERSION)
        self.statusicon.connect('activate', self.status_event)
        self.statusicon.connect('popup-menu', self.status_menu_event)
        if self.config['show_tray']:
            self.statusicon.set_visible(True)
        else:
            self.statusicon.set_visible(False)
        
        # Engine configuration
        self.engine.set_message_handler(self.message_handler)
        self.engine.connect_signal('episode_changed', self.changed_show)
        self.engine.connect_signal('score_changed', self.changed_show)
        self.engine.connect_signal('status_changed', self.changed_show_status)
        self.engine.connect_signal('playing', self.changed_show)
        self.engine.connect_signal('show_added', self.changed_show_status)
        self.engine.connect_signal('show_deleted', self.changed_show_status)
        
        self.selected_show = 0
        
        if not imaging_available:
            self.show_image.pholder_show("PIL library\nnot available")

        self.allow_buttons(False)
        self.main.show_all()
        self.start_engine()
    
    def _clear_gui(self):
        self.show_title.set_text('<span size="14000"><b>wMAL</b></span>')
        self.show_title.set_use_markup(True)
        
        current_api = utils.available_libs[self.account['api']]
        api_iconfile = current_api[1]
        
        self.api_icon.set_from_file(api_iconfile)
        self.api_user.set_text(self.account['username'])
        
    def _create_lists(self):
        statuses_nums = self.engine.mediainfo['statuses']
        statuses_names = self.engine.mediainfo['statuses_dict']
        
        # Statusbox
        self.statusmodel.clear()
        for status in statuses_nums:
            self.statusmodel.append([status, statuses_names[status]])
        self.statusbox.set_model(self.statusmodel)
        self.statusbox.show_all()
        
        # Clear notebook
        for i in xrange(self.notebook.get_n_pages()):
            self.notebook.remove_page(-1)
        
        # Insert pages
        for status in statuses_nums:
            name = statuses_names[status]
            
            sw = gtk.ScrolledWindow()
            sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            sw.set_size_request(550, 300)
            sw.set_border_width(5)
        
            self.show_lists[status] = ShowView(status, self.engine.mediainfo['has_progress'])
            self.show_lists[status].get_selection().connect("changed", self.select_show);
            self.show_lists[status].pagenumber = self.notebook.get_n_pages()
            sw.add(self.show_lists[status])
            
            self.notebook.append_page(sw, gtk.Label(name))
            self.notebook.show_all()
    
    def on_destroy(self, widget):
        gtk.main_quit()
    
    def status_event(self, widget):
        # Called when the tray icon is left-clicked
        if self.hidden:
            self.main.show()
            self.hidden = False
        else:
            self.main.hide()
            self.hidden = True
    
    def status_menu_event(self, icon, button, time):
        # Called when the tray icon is right-clicked
        menu = gtk.Menu()
        mb_show = gtk.MenuItem("Show/Hide")
        mb_about = gtk.ImageMenuItem(gtk.STOCK_ABOUT)
        mb_quit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        
        mb_show.connect("activate", self.status_event)
        mb_about.connect("activate", self.on_about)
        mb_quit.connect("activate", self.do_quit)
        
        menu.append(mb_show)
        menu.append(mb_about)
        menu.append(gtk.SeparatorMenuItem())
        menu.append(mb_quit)
        menu.show_all()
        
        menu.popup(None, None, gtk.status_icon_position_menu, button, time, self.statusicon)
        
    def delete_event(self, widget, event, data=None):
        if self.statusicon.get_visible() and self.config['close_to_tray']:
            self.hidden = True
            self.main.hide()
        else:
            self.do_quit()
        return True
    
    def do_quit(self, widget=None, event=None, data=None):
        if self.close_thread is None:
            self.close_thread = threading.Thread(target=self.task_unload).start()
        
    def do_addsearch(self, widget):
        win = ShowSearch(self.engine)
        win.show_all()
    
    def do_settings(self, widget):
        win = Settings(self.engine, self.config, self.configfile)
        win.show_all()
        
    def do_reload(self, widget, account, mediatype):
        threading.Thread(target=self.task_reload, args=[account, mediatype]).start()
        
    def do_play(self, widget, playnext):
        threading.Thread(target=self.task_play, args=(playnext,)).start()
    
    def do_delete(self, widget):
        try:
            show = self.engine.get_show_info(self.selected_show)
            self.engine.delete_show(show)
        except utils.wmalError, e:
            self.error(e.message)
        
    def do_update(self, widget):
        ep = self.show_ep_num.get_value_as_int()
        try:
            show = self.engine.set_episode(self.selected_show, ep)
        except utils.wmalError, e:
            self.error(e.message)
    
    def do_score(self, widget):
        score = self.show_score.get_value_as_int()
        try:
            show = self.engine.set_score(self.selected_show, score)
        except utils.wmalError, e:
            self.error(e.message)
            
    def do_status(self, widget):
        statusiter = self.statusbox.get_active_iter()
        status = self.statusmodel.get(statusiter, 0)[0]
        
        try:
            show = self.engine.set_status(self.selected_show, status)
        except utils.wmalError, e:
            self.error(e.message)
    
    def do_update_next(self, show, played_ep):
        # Thread safe
        gobject.idle_add(self.task_update_next, show, played_ep)
    
    def changed_show(self, show):
        status = show['my_status']
        self.show_lists[status].update(show)
   
    def changed_show_status(self, show):
        # Rebuild lists
        self.build_list()
        
        status = show['my_status']
        self.show_lists[status].update(show)
        
        pagenumber = self.show_lists[status].pagenumber
        self.notebook.set_current_page(pagenumber)
        
        self.show_lists[status].select(show)
            
    def task_update_next(self, show, played_ep):
        dialog = gtk.MessageDialog(self.main,
                    gtk.DIALOG_MODAL,
                    gtk.MESSAGE_QUESTION,
                    gtk.BUTTONS_YES_NO,
                    "Should I update %s to episode %d?" % (show['title'], played_ep))
        dialog.show_all()
        dialog.connect("response", self.task_update_next_response, show, played_ep)
    
    def task_update_next_response(self, widget, response, show, played_ep):
        widget.destroy()
        # Update show to the played episode
        if response == gtk.RESPONSE_YES:
            try:
                show = self.engine.set_episode(show['id'], played_ep)
                status = show['my_status']
                self.show_lists[status].update(show)
            except utils.wmalError, e:
                self.error(e.message)
    
    def task_play(self, playnext):
        self.allow_buttons(False)
        
        show = self.engine.get_show_info(self.selected_show)
        
        try:
            if playnext:
                played_ep = self.engine.play_episode(show)
            else:
                ep = self.show_ep_num.get_value_as_int()
                played_ep = self.engine.play_episode(show, ep)
            
            # Ask if we should update to the next episode
            if played_ep == (show['my_progress'] + 1):
                self.do_update_next(show, played_ep)
        except utils.wmalError, e:
            self.error(e.message)
            print e.message
        
        self.status("Ready.")
        self.allow_buttons(True)
    
    def task_unload(self):
        self.allow_buttons(False)
        self.engine.unload()
        self.can_close = True
        
        gtk.threads_enter()
        self.main.destroy()
        gtk.threads_leave()
        
    def do_retrieve(self, widget):
        threading.Thread(target=self.task_sync, args=(False,)).start()
    
    def do_send(self, widget):
        threading.Thread(target=self.task_sync, args=(True,)).start()
    
    def task_sync(self, send):
        self.allow_buttons(False)
        
        if send:
            self.engine.list_upload()
        else:
            self.engine.list_download()
        
        gtk.threads_enter()
        self.build_list()
        gtk.threads_leave()
        
        self.status("Ready.")
        self.allow_buttons(True)
    
        
    def start_engine(self):
        threading.Thread(target=self.task_start_engine).start()
    
    def task_start_engine(self):
        if not self.engine.loaded:
            self.engine.start()
        
        gtk.threads_enter()
        self.statusbox.handler_block(self.statusbox_handler)
        self._clear_gui()
        self._create_lists()
        self.build_list()
        self.main.set_title('wMAL-gtk %s [%s (%s)]' % (VERSION, self.engine.api_info['name'], self.engine.api_info['mediatype']))
        
        # Clear and build API and mediatypes menus
        for i in self.mb_mediatype_menu.get_children():
            self.mb_mediatype_menu.remove(i)
        
        for mediatype in self.engine.api_info['supported_mediatypes']:
            item = gtk.RadioMenuItem(None, mediatype)
            if mediatype == self.engine.api_info['mediatype']:
                item.set_active(True)
            item.connect("activate", self.do_reload, None, mediatype)
            self.mb_mediatype_menu.append(item)
            item.show()
            
        self.statusbox.handler_unblock(self.statusbox_handler)
        gtk.threads_leave()
        
        self.status("Ready.")
        self.allow_buttons(True)
    
    def task_reload(self, account, mediatype):
        try:
            self.engine.reload(account, mediatype)
        except utils.wmalError, e:
            self.error(e.message)
        
        if account:
            self.account = account
        
        # Refresh the GUI
        self.task_start_engine()
        
    def select_show(self, widget):
        (tree_model, tree_iter) = widget.get_selected()
        if not tree_iter:
            self.allow_buttons_push(False, lists_too=False)
            return
        
        self.selected_show = int(tree_model.get(tree_iter, 0)[0])
        self.allow_buttons_push(True, lists_too=False)
        
        show = self.engine.get_show_info(self.selected_show)
        
        # Block handlers
        self.statusbox.handler_block(self.statusbox_handler)
        
        if self.image_thread is not None:
            self.image_thread.cancel()
        
        self.show_title.set_text('<span size="14000"><b>{0}</b></span>'.format(show['title']))
        self.show_title.set_use_markup(True)
        
        # Episode selector
        if show['total']:
            adjustment = gtk.Adjustment(upper=show['total'], step_incr=1)
        else:
            adjustment = gtk.Adjustment(upper=1000, step_incr=1)
        
        self.show_ep_num.set_adjustment(adjustment)
        self.show_ep_num.set_value(show['my_progress'])
        
        # Status selector
        for i in self.statusmodel:
            if i[0] == show['my_status']:
                self.statusbox.set_active_iter(i.iter)
                break
        
        # Score selector
        self.show_score.set_value(show['my_score'])
        
        # Image
        if show.get('image'):
            utils.make_dir('cache')
            filename = utils.get_filename('cache', "%d.jpg" % (show['id']))
            
            if os.path.isfile(filename):
                self.show_image.image_show(filename)
            else:
                if imaging_available:
                    self.show_image.pholder_show('Loading...')
                    self.image_thread = ImageTask(self.show_image, show['image'], filename)
                    self.image_thread.start()
                else:
                    self.show_image.pholder_show("PIL library\nnot available")
        
        # Unblock handlers
        self.statusbox.handler_unblock(self.statusbox_handler)
           
    def build_list(self):
        for widget in self.show_lists.itervalues():
            widget.append_start()
            for show in self.engine.filter_list(widget.status_filter):
                widget.append(show)
            widget.append_finish()
        
    def on_about(self, widget):
        about = gtk.AboutDialog()
        about.set_program_name("wMAL-gtk")
        about.set_version(VERSION)
        about.set_comments("wMAL is an open source client for media tracking websites.")
        about.set_website("http://github.com/z411/wmal-python")
        about.set_copyright("(c) z411 - Icon by shuuichi")
        about.run()
        about.destroy()
        
    def message_handler(self, classname, msgtype, msg):
        # Thread safe
        print "%s: %s" % (classname, msg)
        if msgtype != messenger.TYPE_DEBUG:
            gobject.idle_add(self.status_push, "%s: %s" % (classname, msg))
    
    def error(self, msg):
        # Thread safe
        gobject.idle_add(self.error_push, msg)
        
    def error_push(self, msg):
        dialog = gtk.MessageDialog(self.main, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, msg)
        dialog.show_all()
        dialog.connect("response", self.modal_close)
    
    def modal_close(self, widget, response_id):
        widget.destroy()
        
    def status(self, msg):
        # Thread safe
        gobject.idle_add(self.status_push, msg)
    
    def status_push(self, msg):
        self.statusbar.push(0, msg)
    
    def allow_buttons(self, boolean):
        # Thread safe
        gobject.idle_add(self.allow_buttons_push, boolean)
        
    def allow_buttons_push(self, boolean, lists_too=True):
        if lists_too:
            for widget in self.show_lists.itervalues():
                widget.set_sensitive(boolean)
                
        if self.selected_show or not boolean:
            if self.engine.mediainfo['can_play']:
                self.play_button.set_sensitive(boolean)
                self.play_next_button.set_sensitive(boolean)
            
            if self.engine.mediainfo['can_update']:
                self.update_button.set_sensitive(boolean)
                self.show_ep_num.set_sensitive(boolean)
            
            self.scoreset_button.set_sensitive(boolean)
            self.show_score.set_sensitive(boolean)
            self.statusbox.set_sensitive(boolean)
        

class ImageTask(threading.Thread):
    cancelled = False
    
    def __init__(self, show_image, remote, local):
        self.show_image = show_image
        self.remote = remote
        self.local = local
        threading.Thread.__init__(self)
    
    def run(self):
        print "start"
        self.cancelled = False
        
        time.sleep(1)
        
        if self.cancelled:
            return
        
        # If there's a better solution for this please tell me/implement it.
        img_file = StringIO(urllib.urlopen(self.remote).read())
        im = Image.open(img_file)
        im.thumbnail((100, 149), Image.ANTIALIAS)
        im.save(self.local)
        
        if self.cancelled:
            return
        
        gtk.threads_enter()
        self.show_image.image_show(self.local)
        gtk.threads_leave()
        print "done"
        
    def cancel(self):
        self.cancelled = True
    
class ImageView(gtk.HBox):
    def __init__(self):
        gtk.HBox.__init__(self)

        self.showing_pholder = False

        self.w_image = gtk.Image()
        self.w_image.set_size_request(100, 149)

        self.w_pholder = gtk.Label()
        self.w_pholder.set_size_request(100, 140)

        self.pack_start(self.w_image, False, False, 0)

    def image_show(self, filename):
        if self.showing_pholder:
            self.remove(self.w_pholder)
            self.pack_start(self.w_image, False, False, 0)
            self.w_image.show()
            self.showing_pholder = False

        self.w_image.set_from_file(filename)

    def pholder_show(self, msg):
        if not self.showing_pholder:
            self.pack_end(self.w_pholder, False, False, 0)
            self.remove(self.w_image)
            self.w_pholder.show()
            self.showing_pholder = True

        self.w_pholder.set_text(msg)

class ShowView(gtk.TreeView):
    def __init__(self, status, has_progress=True):
        gtk.TreeView.__init__(self)
        
        self.has_progress = has_progress
        self.status_filter = status
        
        self.set_enable_search(True)
        self.set_search_column(1)
        
        self.cols = dict()
        i = 0
        if has_progress:
            columns = ('ID', 'Title', 'Progress', 'Score', 'Percent')
        else:
            columns = ('ID', 'Title', 'Score')

        for name in columns:
            self.cols[name] = gtk.TreeViewColumn(name)
            self.cols[name].set_sort_column_id(i)
            self.append_column(self.cols[name])
            i += 1
        
        renderer_id = gtk.CellRendererText()
        self.cols['ID'].pack_start(renderer_id, False)
        self.cols['ID'].set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        self.cols['ID'].set_expand(False)
        self.cols['ID'].add_attribute(renderer_id, 'text', 0)
        
        renderer_title = gtk.CellRendererText()
        self.cols['Title'].pack_start(renderer_title, False)
        self.cols['Title'].set_resizable(True)
        self.cols['Title'].set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.cols['Title'].set_expand(True)
        self.cols['Title'].add_attribute(renderer_title, 'text', 1)
        self.cols['Title'].add_attribute(renderer_title, 'foreground', 5)
        
        if has_progress:
            renderer_progress = gtk.CellRendererText()
            self.cols['Progress'].pack_start(renderer_progress, False)
            self.cols['Progress'].add_attribute(renderer_progress, 'text', 2)
            self.cols['Progress'].set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
            self.cols['Progress'].set_expand(False)
                
            renderer_percent = gtk.CellRendererProgress()
            self.cols['Percent'].pack_start(renderer_percent, False)
            self.cols['Percent'].add_attribute(renderer_percent, 'value', 4)
            renderer_percent.set_fixed_size(100, -1)
        
        renderer_score = gtk.CellRendererText()
        self.cols['Score'].pack_start(renderer_score, False)
        self.cols['Score'].add_attribute(renderer_score, 'text', 3)
        self.cols['Score'].set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        self.cols['Score'].set_expand(False)
 
        # ID, Title, Episodes, Score, Progress, Color
        self.store = gtk.ListStore(str, str, str, str, int, str)
        self.set_model(self.store)
    
    def _get_color(self, show):
        if show.get('playing'):
            return '#6C2DC7'
        elif show.get('queued'):
            return '#54C571'
        elif show.get('neweps'):
            return '#FBB917'
        elif show['status'] == 1:
            return '#0099cc'
        elif show['status'] == 3:
            return '#999900'
        else:
            return 'black'

    def append_start(self):
        self.freeze_child_notify()
        self.store.clear()
        
    def append(self, show):
        if self.has_progress:
            if show['total'] and show['my_progress'] <= show['total']:
                progress = (float(show['my_progress']) / show['total']) * 100
            else:
                progress = 0
            episodes_str = "%d / %d" % (show['my_progress'], show['total'])
        else:
            episodes_str = ''
            progress = 0
                
        row = [show['id'], show['title'], episodes_str, show['my_score'], progress, self._get_color(show)]
        self.store.append(row)
        
    def append_finish(self):
        self.thaw_child_notify()
        self.store.set_sort_column_id(1, gtk.SORT_ASCENDING)
        
    def get_showid(self):
        selection = self.get_selection()
        if selection is not None:
            selection.set_mode(gtk.SELECTION_SINGLE)
            (tree_model, tree_iter) = selection.get_selected()
            return tree_model.get(tree_iter, 0)[0]
    
    def update(self, show):
        for row in self.store:
            if int(row[0]) == show['id']:
                if self.has_progress:
                    if show['total']:
                        progress = (float(show['my_progress']) / show['total']) * 100
                    else:
                        progress = 0
                    episodes_str = "%d / %d" % (show['my_progress'], show['total'])                    
                    row[2] = episodes_str
                    row[4] = progress
                
                row[3] = show['my_score']
                row[5] = self._get_color(show)
                return
        
        #print "Warning: Show ID not found in ShowView (%d)" % show['id']
    
    def select(self, show):
        """Select specified row"""
        for row in self.store:
            if int(row[0]) == show['id']:
                selection = self.get_selection()
                selection.select_iter(row.iter)
                break

class AccountSelect(gtk.Window):
    default = None
    
    def __init__(self, manager, switch=False):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.use_button = gtk.Button('Switch')
        self.use_button.set_sensitive(False)
        
        self.manager = manager
        self.switch = switch
        
    def create(self):
        self.pixbufs = {}
        for (libname, lib) in utils.available_libs.iteritems():
            self.pixbufs[libname] = gtk.gdk.pixbuf_new_from_file(lib[1])
        
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_title('Select Account')
        self.set_border_width(10)
        self.connect('delete-event', self.on_delete)
        
        vbox = gtk.VBox(False, 10)
        
        # Treeview
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_size_request(400, 200)
        
        self.accountlist = gtk.TreeView()
        
        col_user = gtk.TreeViewColumn('Username')
        col_user.set_expand(True)
        self.accountlist.append_column(col_user)
        col_site = gtk.TreeViewColumn('Site')
        self.accountlist.append_column(col_site)
        
        renderer_user = gtk.CellRendererText()
        col_user.pack_start(renderer_user, False)
        col_user.add_attribute(renderer_user, 'text', 1)
        renderer_icon = gtk.CellRendererPixbuf()
        col_site.pack_start(renderer_icon, False)
        col_site.add_attribute(renderer_icon, 'pixbuf', 3)
        renderer_site = gtk.CellRendererText()
        col_site.pack_start(renderer_site, False)
        col_site.add_attribute(renderer_site, 'text', 2)
        
        self.store = gtk.ListStore(int, str, str, gtk.gdk.Pixbuf)
        self.accountlist.set_model(self.store)
        
        self.accountlist.get_selection().connect("changed", self.on_account_changed)
        self.accountlist.connect("row-activated", self.on_row_activated)
        
        # Bottom buttons
        alignment = gtk.Alignment(xalign=1.0)
        bottombar = gtk.HBox(False, 5)
        
        self.remember = gtk.CheckButton('Remember')
        if self.manager.get_default() is not None:
            self.remember.set_active(True)
        gtk.stock_add([(gtk.STOCK_APPLY, "Add", 0, 0, "")])
        add_button = gtk.Button(stock=gtk.STOCK_APPLY)
        add_button.connect("clicked", self.do_add)
        self.delete_button = gtk.Button(stock=gtk.STOCK_DELETE)
        self.delete_button.set_sensitive(False)
        self.delete_button.connect("clicked", self.do_delete)
        close_button = gtk.Button(stock=gtk.STOCK_CLOSE)
        close_button.connect("clicked", self.do_close)
        
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
        i = 0
        for account in self.manager.get_accounts():
            libname = account['api']
            api = utils.available_libs[libname]
            
            self.store.append([i, account['username'], api[0], self.pixbufs[libname]])
            i += 1
    
    def is_remember(self):
        # Return the state of the checkbutton if there's no default account
        if self.default is None:
            return self.remember.get_active()
        else:
            return True
        
    def get_selected_id(self):
        if self.default is not None:
            return self.default
        else:
            selection = self.accountlist.get_selection()
            selection.set_mode(gtk.SELECTION_SINGLE)
            tree_model, tree_iter = selection.get_selected()
            return tree_model.get_value(tree_iter, 0)
    
    def on_account_changed(self, widget):
        self.use_button.set_sensitive(True)
        self.delete_button.set_sensitive(True)
    
    def on_row_activated(self, treeview, iter, path):
        self.use_button.emit("clicked")
        
    def do_add(self, widget):
        """Create Add Account window"""
        self.add_win = AccountSelectAdd(self.pixbufs)
        self.add_win.add_button.connect("clicked", self.add_account)
        self.add_win.show_all()
        
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
    
    def do_delete(self, widget):
        selectedid = self.get_selected_id()
        dele = self.manager.delete_account(selectedid)
        
        self._refresh_list()
    
    def error(self, msg):
        md = gtk.MessageDialog(None, 
            gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, 
            gtk.BUTTONS_CLOSE, msg)
        md.run()
        md.destroy()
    
    def modal_close(self, widget, response_id):
        widget.destroy()
        
    def do_close(self, widget):
        self.destroy()
        if not self.switch:
            gtk.main_quit()
        
    def on_delete(self, widget, data):
        self.do_close(None)
        return False

class Settings(gtk.Window):
    def __init__(self, engine, config, configfile):
        self.engine = engine
        
        self.config = config
        self.configfile = configfile
        
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_title('Global Settings')
        self.set_border_width(10)
        
        ### Play Next ###
        lbl_player = gtk.Label('Media Player')
        lbl_player.set_size_request(120, -1)
        self.txt_player = gtk.Entry(4096)
        playerbrowse_button = gtk.Button('Browse...')
        playerbrowse_button.connect("clicked", self.do_browse, 'Select player', self.txt_player)

        header0 = gtk.Label()
        header0.set_text('<span size="10000"><b>Play Next</b></span>')
        header0.set_use_markup(True)

        line0 = gtk.HBox(False, 5)
        line0.pack_start(lbl_player, False, False, 0)
        line0.pack_start(self.txt_player, False, False, 0)
        line0.pack_start(playerbrowse_button, False, False, 0)
        
        ### Tracker ###

        # Labels
        lbl_process = gtk.Label('Process Name')
        lbl_process.set_size_request(120, -1)
        lbl_searchdir = gtk.Label('Search Directory')
        lbl_searchdir.set_size_request(120, -1)
        lbl_tracker_enabled = gtk.Label('Enable Tracker')
        lbl_tracker_enabled.set_size_request(120, -1)
        
        # Entries
        self.txt_process = gtk.Entry(4096)
        self.txt_searchdir = gtk.Entry(4096)
        browse_button = gtk.Button('Browse...')
        browse_button.connect("clicked", self.do_browse, 'Select search directory', self.txt_searchdir, True)
        self.chk_tracker_enabled = gtk.CheckButton()
        
        # Buttons
        alignment = gtk.Alignment(xalign=0.5)
        bottombar = gtk.HBox(False, 5)
        self.apply_button = gtk.Button(stock=gtk.STOCK_APPLY)
        self.apply_button.connect("clicked", self.do_apply)
        close_button = gtk.Button(stock=gtk.STOCK_CANCEL)
        close_button.connect("clicked", self.do_close)
        bottombar.pack_start(self.apply_button, False, False, 0)
        bottombar.pack_start(close_button, False, False, 0)
        alignment.add(bottombar)
        
        # HBoxes
        header1 = gtk.Label()
        header1.set_text('<span size="10000"><b>Tracker Options</b></span>')
        header1.set_use_markup(True)
        
        line1 = gtk.HBox(False, 5)
        line1.pack_start(lbl_process, False, False, 0)
        line1.pack_start(self.txt_process, True, True, 0)
        
        line2 = gtk.HBox(False, 5)
        line2.pack_start(lbl_searchdir, False, False, 0)
        line2.pack_start(self.txt_searchdir, True, True, 0)
        line2.pack_start(browse_button, False, False, 0)
        
        line3 = gtk.HBox(False, 5)
        line3.pack_start(lbl_tracker_enabled, False, False, 0)
        line3.pack_start(self.chk_tracker_enabled, False, False, 0)
        
        ### Auto-retrieve ###
        header2 = gtk.Label()
        header2.set_text('<span size="10000"><b>Auto-retrieve</b></span>')
        header2.set_use_markup(True)
        
        # Radio buttons
        self.rbtn_autoret_off = gtk.RadioButton(None, 'Disabled')
        self.rbtn_autoret_always = gtk.RadioButton(self.rbtn_autoret_off, 'Always at start')
        
        self.rbtn_autoret_days = gtk.RadioButton(self.rbtn_autoret_off, 'After')
        self.spin_autoret_days = gtk.SpinButton(gtk.Adjustment(value=3, lower=1, upper=100, step_incr=1, page_incr=10))
        self.spin_autoret_days.set_sensitive(False)
        self.rbtn_autoret_days.connect("toggled", self.radio_toggled, self.spin_autoret_days)
        lbl_autoret_days = gtk.Label('days')
        line_autoret_days = gtk.HBox(False, 5)
        line_autoret_days.pack_start(self.rbtn_autoret_days, False, False, 0)
        line_autoret_days.pack_start(self.spin_autoret_days, False, False, 0)
        line_autoret_days.pack_start(lbl_autoret_days, False, False, 0)
        
        line4 = gtk.VBox(False, 5)
        line4.pack_start(self.rbtn_autoret_off, False, False, 0)
        line4.pack_start(self.rbtn_autoret_always, False, False, 0)
        line4.pack_start(line_autoret_days, False, False, 0)
        
        ### Auto-send ###
        header3 = gtk.Label()
        header3.set_text('<span size="10000"><b>Auto-send</b></span>')
        header3.set_use_markup(True)
        
        # Radio buttons
        self.rbtn_autosend_off = gtk.RadioButton(None, 'Disabled')
        self.rbtn_autosend_always = gtk.RadioButton(self.rbtn_autosend_off, 'After every change')
        self.rbtn_autosend_at_exit = gtk.CheckButton('Auto-send at exit')
        
        self.rbtn_autosend_hours = gtk.RadioButton(self.rbtn_autosend_off, 'After')
        self.spin_autosend_hours = gtk.SpinButton(gtk.Adjustment(value=5, lower=1, upper=1000, step_incr=1, page_incr=10))
        self.spin_autosend_hours.set_sensitive(False)
        self.rbtn_autosend_hours.connect("toggled", self.radio_toggled, self.spin_autosend_hours)
        lbl_autosend_hours = gtk.Label('hours')
        line_autosend_hours = gtk.HBox(False, 5)
        line_autosend_hours.pack_start(self.rbtn_autosend_hours, False, False, 0)
        line_autosend_hours.pack_start(self.spin_autosend_hours, False, False, 0)
        line_autosend_hours.pack_start(lbl_autosend_hours, False, False, 0)
        
        self.rbtn_autosend_size = gtk.RadioButton(self.rbtn_autosend_off, 'After the queue is larger than')
        self.spin_autosend_size = gtk.SpinButton(gtk.Adjustment(value=5, lower=1, upper=1000, step_incr=1, page_incr=10))
        self.spin_autosend_size.set_sensitive(False)
        self.rbtn_autosend_size.connect("toggled", self.radio_toggled, self.spin_autosend_size)
        lbl_autosend_size = gtk.Label('entries')
        line_autosend_size = gtk.HBox(False, 5)
        line_autosend_size.pack_start(self.rbtn_autosend_size, False, False, 0)
        line_autosend_size.pack_start(self.spin_autosend_size, False, False, 0)
        line_autosend_size.pack_start(lbl_autosend_size, False, False, 0)
        
        line5 = gtk.VBox(False, 5)
        line5.pack_start(self.rbtn_autosend_off, False, False, 0)
        line5.pack_start(self.rbtn_autosend_always, False, False, 0)
        line5.pack_start(line_autosend_hours, False, False, 0)
        line5.pack_start(line_autosend_size, False, False, 0)
        line5.pack_start(self.rbtn_autosend_at_exit, False, False, 0)
        
        
        ### GTK Interface ###
        header4 = gtk.Label()
        header4.set_text('<span size="10000"><b>GTK Interface</b></span>')
        header4.set_use_markup(True)
        
        self.chk_show_tray = gtk.CheckButton('Show Tray Icon')
        self.chk_close_to_tray = gtk.CheckButton('Close to Tray')
        self.chk_close_to_tray.set_sensitive(False)
        self.chk_show_tray.connect("toggled", self.radio_toggled, self.chk_close_to_tray)
        line6 = gtk.VBox(False, 5)
        line6.pack_start(self.chk_show_tray, False, False, 0)
        line6.pack_start(self.chk_close_to_tray, False, False, 0)
        
        # Join HBoxes
        vbox = gtk.VBox(False, 10)
        vbox.pack_start(header0, False, False, 0)
        vbox.pack_start(line0, False, False, 0)
        vbox.pack_start(header1, False, False, 0)
        vbox.pack_start(line3, False, False, 0)
        vbox.pack_start(line1, False, False, 0)
        vbox.pack_start(line2, False, False, 0)
        vbox.pack_start(header2, False, False, 0)
        vbox.pack_start(line4, False, False, 0)
        vbox.pack_start(header3, False, False, 0)
        vbox.pack_start(line5, False, False, 0)
        vbox.pack_start(header4, False, False, 0)
        vbox.pack_start(line6, False, False, 0)
        vbox.pack_start(alignment, False, False, 0)
        
        self.add(vbox)
        self.load_config()
        
    def load_config(self):
        """Engine Configuration"""
        self.txt_player.set_text(self.engine.get_config('player'))
        self.txt_process.set_text(self.engine.get_config('tracker_process'))
        self.txt_searchdir.set_text(self.engine.get_config('searchdir'))
        self.chk_tracker_enabled.set_active(self.engine.get_config('tracker_enabled'))
        self.rbtn_autosend_at_exit.set_active(self.engine.get_config('autosend_at_exit'))
        
        if self.engine.get_config('autoretrieve') == 'always':
            self.rbtn_autoret_always.set_active(True)
        elif self.engine.get_config('autoretrieve') == 'days':
            self.rbtn_autoret_days.set_active(True)
        
        if self.engine.get_config('autosend') == 'always':
            self.rbtn_autosend_always.set_active(True)
        elif self.engine.get_config('autosend') == 'hours':
            self.rbtn_autosend_hours.set_active(True)
        elif self.engine.get_config('autosend') == 'size':
            self.rbtn_autosend_size.set_active(True)
        
        self.spin_autoret_days.set_value(self.engine.get_config('autoretrieve_days'))
        self.spin_autosend_hours.set_value(self.engine.get_config('autosend_hours'))
        self.spin_autosend_size.set_value(self.engine.get_config('autosend_size'))
        
        """GTK Interface Configuration"""
        self.chk_show_tray.set_active(self.config['show_tray'])
        self.chk_close_to_tray.set_active(self.config['close_to_tray'])
    
    def save_config(self):
        """Engine Configuration"""
        self.engine.set_config('player', self.txt_player.get_text())
        self.engine.set_config('tracker_process', self.txt_process.get_text())
        self.engine.set_config('searchdir', self.txt_searchdir.get_text())
        self.engine.set_config('tracker_enabled', self.chk_tracker_enabled.get_active())
        self.engine.set_config('autosend_at_exit', self.rbtn_autosend_at_exit.get_active())
        
        # Auto-retrieve
        if self.rbtn_autoret_always.get_active():
            self.engine.set_config('autoretrieve', 'always')
        elif self.rbtn_autoret_days.get_active():
            self.engine.set_config('autoretrieve', 'days')
        else:
            self.engine.set_config('autoretrieve', 'off')
        
        # Auto-send
        if self.rbtn_autosend_always.get_active():
            self.engine.set_config('autosend', 'always')
        elif self.rbtn_autosend_hours.get_active():
            self.engine.set_config('autosend', 'hours')
        elif self.rbtn_autosend_size.get_active():
            self.engine.set_config('autosend', 'size')
        else:
            self.engine.set_config('autosend', 'off')
        
        self.engine.set_config('autoretrieve_days', self.spin_autoret_days.get_value_as_int())
        self.engine.set_config('autosend_hours', self.spin_autosend_hours.get_value_as_int())
        self.engine.set_config('autosend_size', self.spin_autosend_size.get_value_as_int())
        
        self.engine.save_config()
        
        """GTK Interface configuration"""
        self.config['show_tray'] = self.chk_show_tray.get_active()
        
        if self.chk_show_tray.get_active():
            self.config['close_to_tray'] = self.chk_close_to_tray.get_active()
        else:
            self.config['close_to_tray'] = False
        
        utils.save_config(self.config, self.configfile)
    
    def radio_toggled(self, widget, spin):
        spin.set_sensitive(widget.get_active())
        
    def do_browse(self, widget, title, entry, dironly=False):
        browsew = gtk.FileChooserDialog(title,
                                        None,
                                        gtk.FILE_CHOOSER_ACTION_OPEN,
                                        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        browsew.set_default_response(gtk.RESPONSE_OK)
        
        if dironly:
            browsew.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        
        response = browsew.run()
        if response == gtk.RESPONSE_OK:
            entry.set_text(browsew.get_filename())
        browsew.destroy()
        
    def do_apply(self, widget):
        self.save_config()
        self.destroy()
        
    def do_close(self, widget):
        self.destroy()

class AccountSelectAdd(gtk.Window):
    def __init__(self, pixbufs):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_title('Create Account')
        self.set_border_width(10)
        
        # Labels
        lbl_user = gtk.Label('Username')
        lbl_user.set_size_request(70, -1)
        lbl_passwd = gtk.Label('Password')
        lbl_passwd.set_size_request(70, -1)
        lbl_api = gtk.Label('Website')
        lbl_api.set_size_request(70, -1)
        
        # Entries
        self.txt_user = gtk.Entry(128)
        self.txt_passwd = gtk.Entry(128)
        self.txt_passwd.set_visibility(False)
        
        # Combobox
        self.model_api = gtk.ListStore(str, str, gtk.gdk.Pixbuf)
        
        for (libname, lib) in sorted(utils.available_libs.iteritems()):
            self.model_api.append([libname, lib[0], pixbufs[libname]])
        
        self.cmb_api = gtk.ComboBox(self.model_api)
        cell_icon = gtk.CellRendererPixbuf()
        cell_name = gtk.CellRendererText()
        self.cmb_api.pack_start(cell_icon, False)
        self.cmb_api.pack_start(cell_name, True)
        self.cmb_api.add_attribute(cell_icon, 'pixbuf', 2)
        self.cmb_api.add_attribute(cell_name, 'text', 1)
        
        # Buttons
        alignment = gtk.Alignment(xalign=0.5)
        bottombar = gtk.HBox(False, 5)
        self.add_button = gtk.Button(stock=gtk.STOCK_APPLY)
        close_button = gtk.Button(stock=gtk.STOCK_CLOSE)
        close_button.connect("clicked", self.do_close)
        bottombar.pack_start(self.add_button, False, False, 0)
        bottombar.pack_start(close_button, False, False, 0)
        alignment.add(bottombar)
        
        # HBoxes
        line1 = gtk.HBox(False, 5)
        line1.pack_start(lbl_user, False, False, 0)
        line1.pack_start(self.txt_user, True, True, 0)
        
        line2 = gtk.HBox(False, 5)
        line2.pack_start(lbl_passwd, False, False, 0)
        line2.pack_start(self.txt_passwd, True, True, 0)
        
        line3 = gtk.HBox(False, 5)
        line3.pack_start(lbl_api, False, False, 0)
        line3.pack_start(self.cmb_api, True, True, 0)
        
        # Join HBoxes
        vbox = gtk.VBox(False, 10)
        vbox.pack_start(line1, False, False, 0)
        vbox.pack_start(line2, False, False, 0)
        vbox.pack_start(line3, False, False, 0)
        vbox.pack_start(alignment, False, False, 0)
        
        self.add(vbox)
    
    def do_close(self, widget):
        self.destroy()
    

class ShowSearch(gtk.Window):
    def __init__(self, engine):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        
        self.engine = engine
        
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_title('Search')
        self.set_border_width(10)
        
        vbox = gtk.VBox(False, 10)
        
        searchbar = gtk.HBox(False, 5)
        searchbar.pack_start(gtk.Label('Search'), False, False, 0)
        self.searchtext = gtk.Entry(100)
        searchbar.pack_start(self.searchtext, True, True, 0)
        self.search_button = gtk.Button('Search')
        self.search_button.connect("clicked", self.do_search)
        searchbar.pack_start(self.search_button, False, False, 0)
        
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_size_request(550, 300)
        
        alignment = gtk.Alignment(xalign=1.0)
        bottombar = gtk.HBox(False, 5)
        gtk.stock_add([(gtk.STOCK_APPLY, "Add", 0, 0, "")])
        self.add_button = gtk.Button(stock=gtk.STOCK_APPLY)
        self.add_button.connect("clicked", self.do_add)
        self.add_button.set_sensitive(False)
        close_button = gtk.Button(stock=gtk.STOCK_CLOSE)
        close_button.connect("clicked", self.do_close)
        bottombar.pack_start(self.add_button, False, False, 0)
        bottombar.pack_start(close_button, False, False, 0)
        alignment.add(bottombar)
        
        self.showlist = ShowSearchView()
        self.showlist.get_selection().connect("changed", self.select_show);
        
        sw.add(self.showlist)
        
        vbox.pack_start(searchbar, False, False, 0)
        vbox.pack_start(sw, True, True, 0)
        vbox.pack_start(alignment, False, False, 0)
        self.add(vbox)
    
    def do_add(self, widget):
        # Get show dictionary
        show = None
        for item in self.entries:
            if item['id'] == self.selected_show:
                show = item
                break
        
        if show is not None:
            try:
                self.engine.add_show(show)
                self.do_close()
            except utils.wmalError, e:
                self.error_push(e.message)
        
    def do_search(self, widget):
        threading.Thread(target=self.task_search).start()
    
    def do_close(self, widget=None):
        self.destroy()
    
    def select_show(self, widget):
        # Get selected show ID
        (tree_model, tree_iter) = widget.get_selected()
        if not tree_iter:
            self.allow_buttons_push(False, lists_too=False)
            return
        
        self.selected_show = int(tree_model.get(tree_iter, 0)[0])
        self.add_button.set_sensitive(True)
        
    def task_search(self):
        self.allow_buttons(False)
        self.entries = self.engine.search(self.searchtext.get_text())
        
        gtk.threads_enter()
        self.showlist.append_start()
        for show in self.entries:
            self.showlist.append(show)
        self.showlist.append_finish()
        gtk.threads_leave()
        
        self.allow_buttons(True)
        self.add_button.set_sensitive(False)
    
    def allow_buttons_push(self, boolean):
        self.search_button.set_sensitive(boolean)
        
    def allow_buttons(self, boolean):
        # Thread safe
        gobject.idle_add(self.allow_buttons_push, boolean)
    
    def error(self, msg):
        # Thread safe
        gobject.idle_add(self.error_push, msg)
        
    def error_push(self, msg):
        dialog = gtk.MessageDialog(self, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, msg)
        dialog.show_all()
        dialog.connect("response", self.modal_close)
    
    def modal_close(self, widget, response_id):
        widget.destroy()


class ShowSearchView(gtk.TreeView):
    def __init__(self):
        gtk.TreeView.__init__(self)
    
        self.cols = dict()
        i = 0
        for name in ('ID', 'Title', 'Type', 'Total'):
            self.cols[name] = gtk.TreeViewColumn(name)
            self.cols[name].set_sort_column_id(i)
            self.append_column(self.cols[name])
            i += 1
        
        renderer_id = gtk.CellRendererText()
        self.cols['ID'].pack_start(renderer_id, False)
        self.cols['ID'].add_attribute(renderer_id, 'text', 0)
        
        renderer_title = gtk.CellRendererText()
        self.cols['Title'].pack_start(renderer_title, False)
        self.cols['Title'].set_resizable(True)
        #self.cols['Title'].set_expand(True)
        self.cols['Title'].add_attribute(renderer_title, 'text', 1)
        self.cols['Title'].add_attribute(renderer_title, 'foreground', 4)
        
        renderer_type = gtk.CellRendererText()
        self.cols['Type'].pack_start(renderer_type, False)
        self.cols['Type'].add_attribute(renderer_type, 'text', 2)
        
        renderer_total = gtk.CellRendererText()
        self.cols['Total'].pack_start(renderer_total, False)
        self.cols['Total'].add_attribute(renderer_total, 'text', 3)
        
        self.store = gtk.ListStore(str, str, str, str, str)
        self.set_model(self.store)
    
    def append_start(self):
        self.freeze_child_notify()
        self.store.clear()
        
    def append(self, show):
        if show['status'] == 'Currently Airing':
            color = 'blue'
        else:
            color = 'black'
        
        row = [show['id'], show['title'], show['type'], show['total'], color]
        self.store.append(row)
        
    def append_finish(self):
        self.thaw_child_notify()
        self.store.set_sort_column_id(1, gtk.SORT_ASCENDING)
    
def main():
    app = wmal_gtk()
    try:
        gtk.gdk.threads_enter()
        app.main()
    except utils.wmalFatal, e:
        md = gtk.MessageDialog(None, 
            gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, 
            gtk.BUTTONS_CLOSE, e.message)
        md.run()
        md.destroy()
    finally:
        gtk.gdk.threads_leave()
    

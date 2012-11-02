#!/usr/bin/python

# wMAL-gtk v0.1
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

import gobject
import pygtk
pygtk.require('2.0')
import gtk
gtk.gdk.threads_init() # We'll use threads

import os
import time
import threading
import Image
import urllib2 as urllib
from cStringIO import StringIO

import modules.messenger as messenger
import modules.engine as engine
import modules.utils as utils

    
class wmal_gtk(object):
    engine = None
    show_lists = dict()
    image_thread = None
    close_thread = None
    can_close = False
    
    def main(self):
        # Create engine
        self.engine = engine.Engine()
        
        self.main = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.main.set_position(gtk.WIN_POS_CENTER)
        self.main.connect("delete_event", self.delete_event)
        self.main.connect('destroy', self.on_destroy)
        self.main.set_title('wMAL-gtk v0.1')
        
        # Menus
        mb_show = gtk.Menu()
        mb_play = gtk.ImageMenuItem(gtk.STOCK_MEDIA_PLAY)
        mb_delete = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        mb_delete.connect("activate", self.do_delete)
        mb_exit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        mb_exit.connect("activate", self.delete_event, None)
        mb_show.append(mb_play)
        mb_show.append(mb_delete)
        mb_show.append(gtk.SeparatorMenuItem())
        mb_show.append(mb_exit)
        
        mb_list = gtk.Menu()
        mb_addsearch = gtk.MenuItem("Add/Search Shows")
        mb_addsearch.connect("activate", self.do_addsearch)
        gtk.stock_add([(gtk.STOCK_REFRESH, "Sync", 0, 0, "")])
        mb_sync = gtk.ImageMenuItem(gtk.STOCK_REFRESH)
        mb_sync.connect("activate", self.do_sync)
        
        mb_options = gtk.Menu()
        
        self.mb_api_menu = gtk.Menu()
        mb_api = gtk.MenuItem("API")
        mb_api.set_submenu(self.mb_api_menu)
        
        self.mb_mediatype_menu = gtk.Menu()
        mb_mediatype = gtk.MenuItem("Mediatype")
        mb_mediatype.set_submenu(self.mb_mediatype_menu)
        
        mb_about = gtk.ImageMenuItem(gtk.STOCK_ABOUT)
        mb_about.connect("activate", self.on_about)
        
        mb_list.append(mb_addsearch)
        mb_list.append(mb_sync)
        mb_options.append(mb_api)
        mb_options.append(mb_mediatype)
        mb_options.append(mb_about)
        
        # Root menubar
        root_menu1 = gtk.MenuItem("Show")
        root_menu1.set_submenu(mb_show)
        root_menu2 = gtk.MenuItem("List")
        root_menu2.set_submenu(mb_list)
        root_menu3 = gtk.MenuItem("Options")
        root_menu3.set_submenu(mb_options)
        mb = gtk.MenuBar()
        mb.append(root_menu1)
        mb.append(root_menu2)
        mb.append(root_menu3)
        
        # Create vertical box
        vbox = gtk.VBox(False, 6)
        self.main.add(vbox)
        
        vbox.pack_start(mb, False, False, 0)
        
        top_hbox = gtk.HBox(False, 10)
        top_hbox.set_border_width(5)

        self.show_image = gtk.Image()
        self.show_image.set_size_request(100, 149)
        top_hbox.pack_start(self.show_image, False, False, 0)
        
        # Right box
        top_right_box = gtk.VBox(False, 5)
        
        # Line 1: Title
        line1 = gtk.HBox(False, 5)
        self.show_title = gtk.Label('<span size="14000"><b>-</b></span>')
        self.show_title.set_use_markup(True)
        self.show_title.set_alignment(0, 0.5)
        line1.pack_start(self.show_title, True, True, 0)
        
        # Spinner
        self.spinner = gtk.Spinner()
        alignment1 = gtk.Alignment(xalign=1, yalign=0)
        alignment1.add(self.spinner)
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
        self.play_button.connect("clicked", self.do_play)
        self.play_button.set_sensitive(False)
        line2.pack_start(self.play_button, False, False, 0)
        
        top_right_box.pack_start(line2, True, False, 0)
        
        # Disable play button if it's not supported by the mediatype
        if not self.engine.mediainfo['can_play']:
            self.play_button.set_sensitive(False)
        
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

        top_hbox.pack_start(top_right_box, True, True, 0)
        vbox.pack_start(top_hbox, False, False, 0)
        
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
        self.statusbar.push(0, 'wMAL-gtk v0.1')
        vbox.pack_start(self.statusbar, False, False, 0)
        
        # Engine configuration
        self.engine.set_message_handler(self.message_handler)
        self.engine.connect_signal('episode_changed', self.changed_show)
        self.engine.connect_signal('score_changed', self.changed_show)
        self.engine.connect_signal('status_changed', self.changed_show_status)
        self.engine.connect_signal('show_added', self.changed_show_status)
        self.engine.connect_signal('show_deleted', self.changed_show_status)
        
        self.selected_show = 0
        
        self.main.show_all()
        self.main.show()
        self.allow_buttons(False)
        self.start_engine()
        
        gtk.main()
    
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
    
    def delete_event(self, widget, event, data=None):
        if self.close_thread is None:
            self.close_thread = threading.Thread(target=self.task_unload).start()
        return True
    
    def do_addsearch(self, widget):
        win = ShowSearch(self.engine)
        win.show_all()
        
    def do_reload(self, widget, api, mediatype):
        threading.Thread(target=self.task_reload, args=[api, mediatype]).start()
        
    def do_play(self, widget):
        threading.Thread(target=self.task_play).start()
    
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
    
    def task_play(self):
        self.allow_buttons(False)
        
        show = self.engine.get_show_info(self.selected_show)
        ep = self.show_ep_num.get_value_as_int()
        try:
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
        
    def do_sync(self, widget):
        threading.Thread(target=self.task_sync).start()
    
    def task_sync(self):
        self.allow_buttons(False)
        self.engine.list_upload()
        self.engine.list_download()
        gtk.threads_enter()
        self.build_list()
        gtk.threads_leave()
        self.status("Ready.")
        self.allow_buttons(True)
        
    def start_engine(self):
        print "Starting engine..."
        threading.Thread(target=self.task_start_engine).start()
    
    def task_start_engine(self):
        if not self.engine.loaded:
            self.engine.start()
        
        gtk.threads_enter()
        self.statusbox.handler_block(self.statusbox_handler)
        self._create_lists()
        self.build_list()
        self.main.set_title('wMAL-gtk v0.1 [%s (%s)]' % (self.engine.api_info['name'], self.engine.api_info['mediatype']))
        
        # Clear and build API and mediatypes menus
        for i in self.mb_api_menu.get_children():
            self.mb_api_menu.remove(i)
        for i in self.mb_mediatype_menu.get_children():
            self.mb_mediatype_menu.remove(i)
        
        for api in self.engine.config.keys():
            if api != 'main':
                item = gtk.RadioMenuItem(None, api)
                if api == self.engine.config['main']['api']:
                    item.set_active(True)   # This signals 'activate' so beware
                item.connect("activate", self.do_reload, api, None)
                self.mb_api_menu.append(item)
                item.show()
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
    
    def task_reload(self, api, mediatype):
        try:
            self.engine.reload(api=api, mediatype=mediatype)
        except utils.wmalError, e:
            self.error(e.message)
        
        # Refresh the GUI
        self.task_start_engine()
        
    def select_show(self, widget):
        print "select show"
        
        (tree_model, tree_iter) = widget.get_selected()
        if not tree_iter:
            print "Unselected show"
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
            filename = utils.get_filename('cache', "%s_%d.jpg" % (self.engine.config['main']['api'], show['id']))
            
            if os.path.isfile(filename):
                self.show_image.set_from_file(filename)
            else:
                self.image_thread = ImageTask(self.show_image, show['image'], filename)
                self.image_thread.start()
        
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
        about.set_version("0.1")
        about.set_comments("wMAL is an open source client for media tracking websites.")
        about.set_website("http://github.com/z411/wmal-python")
        about.set_copyright("(c) z411")
        about.run()
        about.destroy()
        
    def message_handler(self, classname, msgtype, msg):
        # Thread safe
        print msg
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
            
            if self.engine.mediainfo['can_update']:
                self.update_button.set_sensitive(boolean)
                self.show_ep_num.set_sensitive(boolean)
            
            self.scoreset_button.set_sensitive(boolean)
            self.show_score.set_sensitive(boolean)
            self.statusbox.set_sensitive(boolean)
        
        if boolean == True:
            self.spinner.stop()
            self.spinner.set_visible(False)
        else:
            self.spinner.set_visible(True)
            self.spinner.start()

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
        self.show_image.set_from_file(self.local)
        gtk.threads_leave()
        print "done"
        
    def cancel(self):
        self.cancelled = True
        
class ShowView(gtk.TreeView):
    def __init__(self, status, has_progress=True):
        gtk.TreeView.__init__(self)
        
        self.has_progress = has_progress
        self.status_filter = status
        
        self.set_enable_search(True)
        self.set_search_column(1)
        
        self.cols = dict()
        i = 0
        for name in ('ID', 'Title', 'Progress', 'Score', 'Percent'):
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
        self.cols['Title'].add_attribute(renderer_title, 'foreground', 5)
        
        renderer_progress = gtk.CellRendererText()
        self.cols['Progress'].pack_start(renderer_progress, False)
        self.cols['Progress'].add_attribute(renderer_progress, 'text', 2)
        
        renderer_score = gtk.CellRendererText()
        self.cols['Score'].pack_start(renderer_score, False)
        self.cols['Score'].add_attribute(renderer_score, 'text', 3)
        
        renderer_percent = gtk.CellRendererProgress()
        self.cols['Percent'].pack_start(renderer_percent, False)
        self.cols['Percent'].add_attribute(renderer_percent, 'value', 4)
        renderer_percent.set_fixed_size(100, -1)
        
        self.store = gtk.ListStore(str, str, str, str, int, str)
        self.set_model(self.store)
            
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
        
        if show['status'] == 1:
            color = 'blue'
        elif show['status'] == 3:
            color = 'yellow'
        else:
            color = 'black'
        
        row = [show['id'], show['title'], episodes_str, show['my_score'], progress, color]
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
                return
        
        print "Warning: Show ID not found in ShowView (%d)" % show['id']
    
    def select(self, show):
        """Select specified row"""
        for row in self.store:
            if int(row[0]) == show['id']:
                selection = self.get_selection()
                selection.select_iter(row.iter)
                break


class ShowSearch(gtk.Window):
    def __init__(self, engine):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        
        self.engine = engine
        
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_title('Search')
        self.set_border_width(5)
        
        vbox = gtk.VBox(False, 5)
        
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
        self.add_button = gtk.Button(stock=gtk.STOCK_ADD)
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
            print "Unselected show"
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
    
if __name__ == '__main__':
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
    

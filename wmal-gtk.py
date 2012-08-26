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
        statuses_nums = self.engine.statuses_nums()
        statuses_names = self.engine.statuses()
        
        self.main = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.main.set_position(gtk.WIN_POS_CENTER)
        self.main.connect("delete_event", self.delete_event)
        self.main.connect('destroy', self.on_destroy)
        self.main.set_title('wMAL-gtk v0.1')
        #self.main.set_size_request(500,500)
        
        # Menus
        mb_show = gtk.Menu()
        mb_play = gtk.MenuItem("Play")
        #mb_exit = gtk.MenuItem("Exit")
        mb_exit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        mb_exit.connect("activate", self.on_destroy)
        mb_show.append(mb_play)
        mb_show.append(gtk.SeparatorMenuItem())
        mb_show.append(mb_exit)
        
        mb_options = gtk.Menu()
        mb_sync = gtk.MenuItem("Sync")
        mb_sync.connect("activate", self.do_sync)
        mb_about = gtk.MenuItem("About")
        mb_about.connect("activate", self.on_about)
        mb_options.append(mb_sync)
        mb_options.append(mb_about)
        
        # Root menubar
        root_menu1 = gtk.MenuItem("Show")
        root_menu1.set_submenu(mb_show)
        root_menu2 = gtk.MenuItem("Options")
        root_menu2.set_submenu(mb_options)
        mb = gtk.MenuBar()
        mb.append(root_menu1)
        mb.append(root_menu2)
        
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
        self.show_title = gtk.Label('<span size="14000"><b>Show title</b></span>')
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
        line2_t = gtk.Label('  Episode')
        line2_t.set_size_request(70, -1)
        line2_t.set_alignment(0, 0.5)
        line2.pack_start(line2_t, False, False, 0)
        self.show_ep_num = gtk.SpinButton()
        #self.show_ep_num.connect("value_changed", self.do_update)
        line2.pack_start(self.show_ep_num, False, False, 0)
        
        # Buttons
        top_buttons = gtk.HBox(False, 5)
        
        self.update_button = gtk.Button('Update')
        self.update_button.connect("clicked", self.do_update)
        line2.pack_start(self.update_button, False, False, 0)
        
        self.play_button = gtk.Button('Play')
        self.play_button.connect("clicked", self.do_play)
        line2.pack_start(self.play_button, False, False, 0)
        
        top_right_box.pack_start(line2, True, False, 0)
        
        # Line 3: Score
        line3 = gtk.HBox(False, 5)
        line3_t = gtk.Label('  Score')
        line3_t.set_size_request(70, -1)
        line3_t.set_alignment(0, 0.5)
        line3.pack_start(line3_t, False, False, 0)
        self.show_score = gtk.SpinButton()
        self.show_score.set_adjustment(gtk.Adjustment(upper=10, step_incr=1))
        line3.pack_start(self.show_score, False, False, 0)
        
        top_right_box.pack_start(line3, True, False, 0)
        
        # Line 4: Status
        line4 = gtk.HBox(False, 5)
        line4_t = gtk.Label('  Status')
        line4_t.set_size_request(70, -1)
        line4_t.set_alignment(0, 0.5)
        line4.pack_start(line4_t, False, False, 0)
        
        self.statusmodel = gtk.ListStore(int, str)
        for status in statuses_nums:
            self.statusmodel.append([status, statuses_names[status]])
            
        self.statusbox = gtk.ComboBox(self.statusmodel)
        cell = gtk.CellRendererText()
        self.statusbox.pack_start(cell, True)
        self.statusbox.add_attribute(cell, 'text', 1)
        self.statusbox_handler = self.statusbox.connect("changed", self.do_status);
        
        alignment = gtk.Alignment(xalign=0, yalign=0.5)
        alignment.add(self.statusbox)
        
        line4.pack_start(alignment, True, True, 0)
        
        top_right_box.pack_start(line4, True, False, 0)

        top_hbox.pack_start(top_right_box, True, True, 0)
        vbox.pack_start(top_hbox, False, False, 0)
        
        # Create lists
        self.notebook = gtk.Notebook()
        self.notebook.set_tab_pos(gtk.POS_TOP)
        self.notebook.set_scrollable(True)
        self.notebook.set_border_width(3)
        
        for status in statuses_nums:
            name = statuses_names[status]
            
            sw = gtk.ScrolledWindow()
            sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            sw.set_size_request(550, 300)
            sw.set_border_width(5)
        
            self.show_lists[status] = ShowView(status)
            self.show_lists[status].get_selection().connect("changed", self.select_show);
            self.show_lists[status].pagenumber = self.notebook.get_n_pages()
            sw.add(self.show_lists[status])
            
            self.notebook.append_page(sw, gtk.Label(name))
        
        vbox.pack_start(self.notebook, True, True, 0)

        self.statusbar = gtk.Statusbar()
        self.statusbar.push(0, 'wMAL-gtk v0.1')
        vbox.pack_start(self.statusbar, False, False, 0)
        self.engine.set_message_handler(self.message_handler)
        
        
        self.main.show_all()
        self.main.show()
        self.allow_buttons(False)
        self.start_engine()
        
        gtk.main()
        
    def on_destroy(self, widget):
        gtk.main_quit()
    
    def delete_event(self, widget, event, data=None):
        if self.close_thread is None:
            self.close_thread = threading.Thread(target=self.task_unload).start()
        return True
    
    def do_play(self, widget):
        threading.Thread(target=self.task_play).start()
    
    def do_update(self, widget):
        ep = self.show_ep_num.get_value_as_int()
        try:
            show = self.engine.set_episode(self.selected_show, ep)
            status = show['my_status']
            self.show_lists[status].update(show)
        except utils.wmalError, e:
            self.error(e.message)
    
    def do_score(self, widget):
        score = self.show_score.get_value_as_int()
        try:
            show = self.engine.set_score(self.selected_show, score)
            status = show['my_status']
            self.show_lists[status].update(show)
        except utils.wmalError, e:
            self.error(e.message)
            
    def do_status(self, widget):
        statusiter = self.statusbox.get_active_iter()
        status = self.statusmodel.get(statusiter, 0)[0]
        
        try:
            show = self.engine.set_status(self.selected_show, status)
            
            # Rebuild lists
            self.build_list()
            
            status = show['my_status']
            self.show_lists[status].update(show)
            
            pagenumber = self.show_lists[status].pagenumber
            self.notebook.set_current_page(pagenumber)
            
            self.show_lists[status].select(show)
        except utils.wmalError, e:
            self.error(e.message)
        
    def task_play(self):
        self.allow_buttons(False)
        
        show = self.engine.get_show_info(self.selected_show)
        ep = self.show_ep_num.get_value_as_int()
        try:
            self.engine.play_episode(show, ep)
        except utils.wmalError, e:
            self.error(e.message)
            print e.message
        self.status("Ready.")
        self.allow_buttons(True)
    
    def task_unload(self):
        print "Unloading engine"
        self.allow_buttons(False)
        self.engine.unload()
        self.can_close = True
        self.main.destroy()
        
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
        self.engine.start()
        
        gtk.threads_enter()
        self.build_list()
        gtk.threads_leave()
        
        self.status("Ready.")
        self.allow_buttons(True)
    
    def select_show(self, widget):
        print "select show"
        
        (tree_model, tree_iter) = widget.get_selected()
        if not tree_iter:
            print "Unselected show"
            return
        
        self.selected_show = int(tree_model.get(tree_iter, 0)[0])
        show = self.engine.get_show_info(self.selected_show)
        
        # Block handlers
        self.statusbox.handler_block(self.statusbox_handler)
        
        if self.image_thread is not None:
            self.image_thread.cancel()
        
        
        self.show_title.set_text('<span size="14000"><b>{0}</b></span>'.format(show['title']))
        self.show_title.set_use_markup(True)
        
        # Episode selector
        adjustment = gtk.Adjustment(upper=show['episodes'], step_incr=1)
        self.show_ep_num.set_adjustment(adjustment)
        if show['my_episodes'] >= show['episodes']:
            self.show_ep_num.set_value(show['my_episodes'])
        else:
            self.show_ep_num.set_value(show['my_episodes'] + 1)
        
        # Status selector
        for i in self.statusmodel:
            if i[0] == show['my_status']:
                self.statusbox.set_active_iter(i.iter)
                break
        
        # Score selector
        self.show_score.set_value(show['my_score'])
        
        # Image
        utils.make_dir('cache')
        filename = utils.get_filename('cache', "%d.jpg" % show['id'])
        
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
        if msgtype != messenger.TYPE_DEBUG:
            gobject.idle_add(self.status_push, "%s: %s" % (classname, msg))
    
    def error(self, msg):
        # Thread safe
        gobject.idle_add(self.error_push, msg)
        
    def error_push(self, msg):
        dialog = gtk.MessageDialog(self.main, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, msg)
        dialog.show_all()
        dialog.connect("response", self.error_close)
    
    def error_close(self, widget, response_id):
        widget.destroy()
        
    def status(self, msg):
        # Thread safe
        gobject.idle_add(self.status_push, msg)
    
    def status_push(self, msg):
        self.statusbar.push(0, msg)
    
    def allow_buttons(self, boolean):
        # Thread safe
        gobject.idle_add(self.allow_buttons_push, boolean)
        
    def allow_buttons_push(self, boolean):
        if boolean == True:
            self.spinner.stop()
            self.spinner.set_visible(False)
        else:
            self.spinner.set_visible(True)
            self.spinner.start()
        
        for widget in self.show_lists.itervalues():
            widget.set_sensitive(boolean)
        
        self.play_button.set_sensitive(boolean)
        self.update_button.set_sensitive(boolean)
        self.show_ep_num.set_sensitive(boolean)

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
    def __init__(self, status):
        gtk.TreeView.__init__(self)
        
        self.status_filter = status
        
        self.enable_search = True
        self.search_column = 2
        
        self.cols = dict()
        i = 0
        for name in ('ID', 'Title', 'Episodes', 'Score', 'Progress'):
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
        
        renderer_episodes = gtk.CellRendererText()
        self.cols['Episodes'].pack_start(renderer_episodes, False)
        self.cols['Episodes'].add_attribute(renderer_episodes, 'text', 2)
        
        renderer_score = gtk.CellRendererText()
        self.cols['Score'].pack_start(renderer_score, False)
        self.cols['Score'].add_attribute(renderer_score, 'text', 3)
        
        renderer_progress = gtk.CellRendererProgress()
        self.cols['Progress'].pack_start(renderer_progress, False)
        self.cols['Progress'].add_attribute(renderer_progress, 'value', 4)
        renderer_progress.set_fixed_size(100, -1)
        
        self.store = gtk.ListStore(str, str, str, str, int, str)
        self.set_model(self.store)
            
    def append_start(self):
        self.freeze_child_notify()
        self.store.clear()
        
    def append(self, show):
        if show['episodes'] and show['my_episodes'] <= show['episodes']:
            progress = (float(show['my_episodes']) / show['episodes']) * 100
        else:
            progress = 0
        episodes_str = "%d / %d" % (show['my_episodes'], show['episodes'])
        
        if show['status'] == 1:
            color = 'blue'
        else:
            color = 'black'
        
        row = [show['id'], show['title'], episodes_str, show['my_score'], progress, color]
        self.store.append(row)
        
    def append_finish(self):
        self.thaw_child_notify()
        self.store.set_sort_column_id(1, gtk.SORT_ASCENDING)
        #self.set_model(self.store)
        
    def get_showid(self):
        selection = self.get_selection()
        if selection is not None:
            selection.set_mode(gtk.SELECTION_SINGLE)
            (tree_model, tree_iter) = selection.get_selected()
            return tree_model.get(tree_iter, 0)[0]
    
    def update(self, show):
        for row in self.store:
            if int(row[0]) == show['id']:
                if show['episodes']:
                    progress = (float(show['my_episodes']) / show['episodes']) * 100
                else:
                    progress = 0
                episodes_str = "%d / %d" % (show['my_episodes'], show['episodes'])
                
                row[2] = episodes_str
                row[3] = show['my_score']
                row[4] = progress
                return
        
        print "Warning: Show ID not found in ShowView (%d)" % show['id']
    
    def select(self, show):
        """Select specified row"""
        for row in self.store:
            if int(row[0]) == show['id']:
                selection = self.get_selection()
                selection.select_iter(row.iter)
                break

if __name__ == '__main__':
    app = wmal_gtk()
    gtk.gdk.threads_enter()
    app.main()
    gtk.gdk.threads_leave()
    

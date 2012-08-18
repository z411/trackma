#!/usr/bin/python

# wMAL-curses v0.1
# Lightweight urwid+curses based script for using data from MyAnimeList.
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

import urwid.curses_display
import urwid

import modules.engine as engine
import modules.messenger as messenger
import modules.utils as utils
from operator import itemgetter
from itertools import cycle

class wMAL_urwid(object):
    """
    Main class for the urwid version of wMAL
    """
    
    """Main objects"""
    engine = None
    mainloop = None
    cur_sort = 'title'
    sorts_iter = cycle(('id', 'title', 'my_episodes', 'episodes'))
    
    """Widgets"""
    header = None
    listbox = None
    view = None
    
    def __init__(self):
        """Creates main widgets and creates mainloop"""
        
        palette = [
        ('body','', ''),
        ('focus','standout', ''),
        ('head','light red', 'black'),
        ('header','bold', ''),
        ('status', 'yellow', 'dark blue'),
        ]
        
        self.header_title = urwid.Text('wMAL-urwid v0.1')
        self.header_filter = urwid.Text('Filter:watching')
        self.header_sort = urwid.Text('Sort:title')
        self.header = urwid.AttrMap(urwid.Columns([
            self.header_title,
            ('fixed', 23, self.header_filter),
            ('fixed', 20, self.header_sort)]), 'status')
        
        self.top_pile = urwid.Pile([self.header,
            urwid.AttrMap(urwid.Text('F2:Filter  F3:Sort  F4:Update  F5:Play  F10:Sync  F12:Quit'), 'status')
        ])
        
        self.statusbar = urwid.AttrMap(urwid.Text('wMAL-urwid v0.1'), 'status')
        
        self.listheader = urwid.AttrMap(
            urwid.Columns([
                ('fixed', 7, urwid.Text('ID')),
                ('weight', 1, urwid.Text('Title')),
                ('fixed', 15, urwid.Text('Episodes')),
            ]), 'header')
        
        self.listwalker = urwid.SimpleListWalker([])
        self.listbox = urwid.ListBox(self.listwalker)
        self.listframe = urwid.Frame(self.listbox, header=self.listheader)
            
        self.view = urwid.Frame(urwid.AttrWrap(self.listframe, 'body'), header=self.top_pile, footer=self.statusbar)
        self.mainloop = urwid.MainLoop(self.view, palette, unhandled_input=self.keystroke, screen=urwid.raw_display.Screen())
        
        self.mainloop.set_alarm_in(0, self.start)                       # See dev note [1]
        #self.idlehandle = self.mainloop.event_loop.enter_idle(self.start) # See dev note [1]
        self.mainloop.run()
    
    def start(self, loop, data):
        """Starts the engine"""
        self.engine = engine.Engine(self.message_handler)
        self.engine.start()
        
        self.filters = self.engine.statuses()
        self.filters_iter = cycle(self.engine.statuses_nums())
        
        self.cur_filter = self.filters_iter.next()
        print self.cur_filter
        
        self.build_list()
        
        self.status('Ready.')
    
    def clear_list(self):
        try:
            while self.listwalker.pop():
                pass
        except IndexError:
            pass
        
    def build_list(self):
        showlist = self.engine.filter_list(self.cur_filter)
        sortedlist = sorted(showlist, key=itemgetter(self.cur_sort))
        for show in sortedlist:
            self.listwalker.append(ShowItem(show))
        
    def status(self, msg):
        self.statusbar.base_widget.set_text(msg)
        
    def message_handler(self, classname, msgtype, msg):
        if msgtype != messenger.TYPE_DEBUG:
            self.status(msg)
            self.mainloop.draw_screen()
        
    def keystroke(self, input):
        if input == 'f2':
            self.do_filter()
        elif input == 'f3':
            self.do_sort()
        elif input == 'f4':
            self.do_update()
        elif input == 'f5':
            self.do_play()
        elif input == 'f10':
            self.do_sync()
        elif input == 'f12':
            self.do_quit()

        #if input is 'enter':
        #    focus = self.listbox.get_focus()[0].showid
        #    # set anime
    
    def do_filter(self):
        _filter = self.filters_iter.next()
        self.cur_filter = _filter
        self.header_filter.set_text("Filter:%s" % self.filters[_filter])
        self.clear_list()
        self.build_list()
    
    def do_sort(self):
        _sort = self.sorts_iter.next()
        self.cur_sort = _sort
        self.header_sort.set_text("Sort:%s" % _sort)
        self.clear_list()
        self.build_list()
    
    def do_update(self):
        showid = self.listbox.get_focus()[0].showid
        show = self.engine.get_show_info(showid)
        self.ask('[Update] Episode # to update to: ', self.update_request, show['my_episodes'])
        
    def do_play(self):
        show = self.listbox.get_focus()[0].show
        self.ask('[Play] Episode # to play: ', self.play_request, show['my_episodes']+1)
    
    def do_sync(self):
        self.engine.list_upload()
        self.engine.list_download()
        self.clear_list()
        self.build_list()
        self.status("Ready.")
    
    def do_quit(self):
        self.engine.unload()
        raise urwid.ExitMainLoop()
    
    def update_request(self, data):
        self.ask_finish(self.update_request)
        if data:
            item = self.listbox.get_focus()[0]
            
            try:
                show = self.engine.set_episode(item.showid, int(data))
            except utils.wmalError, e:
                self.status("Error: %s" % e.message)
                return
            
            item.update(show)
    
    def play_request(self, data):
        self.ask_finish(self.play_request)
        if data:
            item = self.listbox.get_focus()[0]
            show = self.engine.get_show_info(item.showid)
            
            try:
                played_episode = self.engine.play_episode(show, int(data))
            except utils.wmalError, e:
                self.status("Error: %s" % e.message)
                return
            
            if played_episode == (show['my_episodes'] + 1):
                self.ask("Update %s to episode %d? [y/N] " % (show['title'], played_episode), self.update_next_request)
            else:
                self.status('Ready.')
    
    def update_next_request(self, data):
        self.ask_finish(self.update_next_request)
        if data == 'y':
            item = self.listbox.get_focus()[0]
            next_episode = show['my_episodes'] + 1
            
            try:
                show = self.engine.set_episode(item.showid, next_episode)
            except utils.wmalError, e:
                self.status("Error: %s" % e.message)
                return
            
            item.update(show)
        
        self.status('Ready.')
        
    def ask(self, msg, callback, data=u''):
        self.asker = Asker(msg, str(data))
        self.view.set_footer(urwid.AttrWrap(self.asker, 'status'))
        self.view.set_focus('footer')
        urwid.connect_signal(self.asker, 'done', callback)
    
    def ask_finish(self, callback):
        self.view.set_focus('body')
        urwid.disconnect_signal(self, self.asker, 'done', callback)
        self.view.set_footer(self.statusbar)
        
class ShowItem(urwid.WidgetWrap):
    def __init__ (self, show):
        self.episodes_str = urwid.Text("{0:3} / {1}".format(show['my_episodes'], show['episodes']))
        
        self.showid = show['id']
        self.item = [
            ('fixed', 7, urwid.Text("%d" % self.showid)),
            ('weight', 1, urwid.Text(show['title'])),
            ('fixed', 15, self.episodes_str),
        ]
        w = urwid.AttrWrap(urwid.Columns(self.item), 'body', 'focus')
        self.__super.__init__(w)
    
    def get_showid(self):
        return self.showid
    
    def update(self, show):
        if show['id'] == self.showid:
            self.episodes_str.set_text("{0:3} / {1}".format(show['my_episodes'], show['episodes']))
        else:
            print "Warning: Tried to update a show with a different ID! (%d -> %d)" % (show['id'], self.showid)
        
    def selectable (self):
        return True

    def keypress(self, size, key):
        return key
    

class Asker(urwid.Edit):
    __metaclass__ = urwid.signals.MetaSignals
    signals = ['done']

    def keypress(self, size, key):
        if key == 'enter':
            urwid.emit_signal(self, 'done', self.get_edit_text())
            return
        elif key == 'esc':
            urwid.emit_signal(self, 'done', None)
            return

        urwid.Edit.keypress(self, size, key)


if __name__ == '__main__':
    wMAL_urwid()

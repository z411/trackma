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

try:
    import urwid.curses_display
except ImportError:
    pass

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
    sorts_iter = cycle(('id', 'title', 'my_progress', 'total', 'my_score'))
    
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
        ('window', 'yellow', 'dark blue'),
        ('button', 'black', 'light gray'),
        ('button hilight', 'white', 'dark red'),
        ]
        
        self.header_title = urwid.Text('wMAL-curses v0.1')
        self.header_api = urwid.Text('API:')
        self.header_filter = urwid.Text('Filter:watching')
        self.header_sort = urwid.Text('Sort:title')
        self.header = urwid.AttrMap(urwid.Columns([
            self.header_title,
            ('fixed', 23, self.header_filter),
            ('fixed', 17, self.header_sort),
            ('fixed', 16, self.header_api)]), 'status')
        
        self.top_pile = urwid.Pile([self.header,
            urwid.AttrMap(urwid.Text('F2:Filter  F3:Sort  F4:Update  F5:Play  F6:Status  F7:Score  F10:Sync  F12:Quit'), 'status')
        ])
        
        self.statusbar = urwid.AttrMap(urwid.Text('wMAL-urwid v0.1'), 'status')
        
        self.listheader = urwid.AttrMap(
            urwid.Columns([
                ('fixed', 7, urwid.Text('ID')),
                ('weight', 1, urwid.Text('Title')),
                ('fixed', 10, urwid.Text('Progress')),
                ('fixed', 7, urwid.Text('Score')),
            ]), 'header')
        
        self.listwalker = urwid.SimpleListWalker([])
        self.listbox = urwid.ListBox(self.listwalker)
        self.listframe = urwid.Frame(self.listbox, header=self.listheader)
            
        self.view = urwid.Frame(urwid.AttrWrap(self.listframe, 'body'), header=self.top_pile, footer=self.statusbar)
        self.mainloop = urwid.MainLoop(self.view, palette, unhandled_input=self.keystroke, screen=urwid.raw_display.Screen())
        
        self.mainloop.set_alarm_in(0, self.start)
        self.mainloop.run()
    
    def start(self, loop, data):
        """Starts the engine"""
        self.engine = engine.Engine(self.message_handler)
        self.engine.start()
        
        self.header_api.set_text('API:%s' % self.engine.api_info['name'])
        self.filters = self.engine.mediainfo['statuses_dict']
        self.filters_nums = self.engine.mediainfo['statuses']
        self.filters_iter = cycle(self.engine.mediainfo['statuses'])
        
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
            self.listwalker.append(ShowItem(show, self.engine.mediainfo['has_progress']))
        
    def status(self, msg):
        self.statusbar.base_widget.set_text(msg)
        
    def message_handler(self, classname, msgtype, msg):
        if msgtype != messenger.TYPE_DEBUG:
            self.status(msg)
            self.mainloop.draw_screen()
        
    def keystroke(self, input):
        if input == 'f1':
            self.do_help()
        elif input == 'f2':
            self.do_filter()
        elif input == 'f3':
            self.do_sort()
        elif input == 'f4':
            self.do_update()
        elif input == 'f5':
            self.do_play()
        elif input == 'f6':
            self.do_status()
        elif input == 'f7':
            self.do_score()
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
        self.ask('[Update] Episode # to update to: ', self.update_request, show['my_progress'])
        
    def do_play(self):
        showid = self.listbox.get_focus()[0].showid
        show = self.engine.get_show_info(showid)
        self.ask('[Play] Episode # to play: ', self.play_request, show['my_progress']+1)
    
    def do_sync(self):
        self.engine.list_upload()
        self.engine.list_download()
        self.clear_list()
        self.build_list()
        self.status("Ready.")
    
    def do_help(self):
        helptext = "wMAL-curses v0.1  by z411 (electrik.persona@gmail.com)\n\n"
        helptext += "wMAL is an open source client for media tracking websites.\n"
        helptext += "http://github.com/z411/wmal-python\n\n"
        pile = urwid.Pile([urwid.Text(helptext), urwid.AttrWrap(urwid.Button('OK'), 'button', 'button hilight')])
        self.dialog = Dialog(pile, self.mainloop, width=('relative', 80))
        self.dialog.show()
        
    def do_score(self):
        showid = self.listbox.get_focus()[0].showid
        show = self.engine.get_show_info(showid)
        self.ask('[Score] Score to change to: ', self.score_request, show['my_score'])
        
    def do_status(self):
        showid = self.listbox.get_focus()[0].showid
        show = self.engine.get_show_info(showid)
        
        buttons = list()
        num = 1
        selected = 1
        title = urwid.Text('Choose status:')
        title.align = 'center'
        buttons.append(title)
        for status in self.filters_nums:
            name = self.filters[status]
            button = urwid.Button(name, self.status_request, status)
            button._label.align = 'center'
            buttons.append(urwid.AttrWrap(button, 'button', 'button hilight'))
            if status == show['my_status']:
                selected = num
            num += 1
        pile = urwid.Pile(buttons)
        pile.set_focus(selected)
        self.dialog = Dialog(pile, self.mainloop, width=22)
        self.dialog.show()
        
    def do_quit(self):
        self.engine.unload()
        raise urwid.ExitMainLoop()
        
    def status_request(self, widget, data):
        self.dialog.close()
        if data:
            item = self.listbox.get_focus()[0]
            
            try:
                show = self.engine.set_status(item.showid, int(data))
            except utils.wmalError, e:
                self.status("Error: %s" % e.message)
                return
            
            item.update(show)
            
            self.cur_filter = show['my_status']
            self.header_filter.set_text("Filter:%s" % self.filters[self.cur_filter])
            self.clear_list()
            self.build_list()
            
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
    
    def score_request(self, data):
        self.ask_finish(self.score_request)
        if data:
            item = self.listbox.get_focus()[0]
            
            try:
                show = self.engine.set_score(item.showid, int(data))
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
            
            if played_episode == (show['my_progress'] + 1):
                self.ask("Update %s to episode %d? [y/N] " % (show['title'], played_episode), self.update_next_request)
            else:
                self.status('Ready.')
    
    def update_next_request(self, data):
        self.ask_finish(self.update_next_request)
        if data == 'y':
            item = self.listbox.get_focus()[0]
            show = self.engine.get_show_info(item.showid)
            next_episode = show['my_progress'] + 1
            
            try:
                show = self.engine.set_episode(item.showid, next_episode)
            except utils.wmalError, e:
                self.status("Error: %s" % e.message)
                return
            
            item.update(show)
        else:
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

class Dialog(urwid.Overlay):
    def __init__(self, widget, loop, width=30):
        self.widget = urwid.AttrWrap(urwid.LineBox(widget), 'window')
        self.oldwidget = loop.widget
        self.loop = loop
        self.__super.__init__(self.widget, loop.widget,
                align="center",
                width=width,
                valign="middle",
                height=None)
    
    def show(self):
        self.loop.widget = self
        
    def close(self):
        self.loop.widget = self.oldwidget
        
    def keypress(self, size, key):
        if key in ('up', 'down', 'enter'):
            self.widget.keypress(size, key)
        elif key == 'esc':
            self.close()
        
    
class ShowItem(urwid.WidgetWrap):
    def __init__ (self, show, has_progress=True):
        if has_progress:
            self.episodes_str = urwid.Text("{0:3} / {1}".format(show['my_progress'], show['total']))
        else:
            self.episodes_str = urwid.Text("-")
        
        self.score_str = urwid.Text("{0:^5}".format(show['my_score']))
        self.has_progress = has_progress
        
        self.showid = show['id']
        self.item = [
            ('fixed', 7, urwid.Text("%d" % self.showid)),
            ('weight', 1, urwid.Text(show['title'])),
            ('fixed', 10, self.episodes_str),
            ('fixed', 7, self.score_str),
        ]
        w = urwid.AttrWrap(urwid.Columns(self.item), 'body', 'focus')
        self.__super.__init__(w)
    
    def get_showid(self):
        return self.showid
    
    def update(self, show):
        if show['id'] == self.showid:
            if self.has_progress:
                self.episodes_str.set_text("{0:3} / {1}".format(show['my_progress'], show['total']))
            self.score_str.set_text("{0:^5}".format(show['my_score']))
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
    try:
        wMAL_urwid()
    except utils.wmalFatal, e:
        print e.message

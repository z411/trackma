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
import re

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
        ('item_airing', 'light blue', ''),
        ('item_notaired', 'yellow', ''),
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
            urwid.AttrMap(urwid.Text('F1:Help  F2:Filter  F3:Sort  F4:Update  F5:Play  F6:Status  F7:Score  F12:Quit'), 'status')
        ])
        
        self.statusbar = urwid.AttrMap(urwid.Text('wMAL-urwid v0.1'), 'status')
        
        self.listheader = urwid.AttrMap(
            urwid.Columns([
                ('fixed', 7, urwid.Text('ID')),
                ('weight', 1, urwid.Text('Title')),
                ('fixed', 10, urwid.Text('Progress')),
                ('fixed', 7, urwid.Text('Score')),
            ]), 'header')
        
        self.listwalker = ShowWalker([])
        self.listbox = urwid.ListBox(self.listwalker)
        self.listframe = urwid.Frame(self.listbox, header=self.listheader)
            
        self.view = urwid.Frame(urwid.AttrWrap(self.listframe, 'body'), header=self.top_pile, footer=self.statusbar)
        self.mainloop = urwid.MainLoop(self.view, palette, unhandled_input=self.keystroke, screen=urwid.raw_display.Screen())
        
        self.mainloop.set_alarm_in(0, self.start)
        self.mainloop.run()
    
    def _rebuild(self):
        self.header_api.set_text('API:%s' % self.engine.api_info['name'])
        self.filters = self.engine.mediainfo['statuses_dict']
        self.filters_nums = self.engine.mediainfo['statuses']
        self.filters_iter = cycle(self.engine.mediainfo['statuses'])
        
        self.cur_filter = self.filters_iter.next()
        print self.cur_filter
        
        self.clear_list()
        self.build_list()
        
        self.status('Ready.')
        
    def start(self, loop, data):
        """Starts the engine"""
        # Engine configuration
        self.engine = engine.Engine(self.message_handler)
        self.engine.connect_signal('episode_changed', self.changed_show)
        self.engine.connect_signal('score_changed', self.changed_show)
        self.engine.connect_signal('status_changed', self.changed_show_status)
        self.engine.connect_signal('show_deleted', self.changed_list)
        # Engine start and list rebuild
        self.engine.start()
        self._rebuild()
        
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
        elif input == 'S':
            self.do_sync()
        elif input == 'a':
            self.do_addsearch()
        elif input == 'c':
            self.do_reload()
        elif input == 'd':
            self.do_delete()
        elif input == 'f12':
            self.do_quit()
        elif input == '/':
            self.do_search('')

        #if input is 'enter':
        #    focus = self.listbox.get_focus()[0].showid
        #    # set anime
    
    def do_addsearch(self):
        self.dialog = AddDialog(self.mainloop, width=('relative', 80))
        self.dialog.show()
    
    def do_delete(self):
        self.question('Delete selected show? [y/N] ', self.delete_request)
        
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
        helptext += "This program is licensed under the GPLv3,\nfor more information read COPYING file.\n\n"
        helptext += "More controls:\n  /:Search\n  a:Add\n  c:Change API/Mediatype\n"
        helptext += "  d:Delete\n  S:Sync\n"
        ok_button = urwid.Button('OK', self.help_close)
        ok_button_wrap = urwid.Padding(urwid.AttrWrap(ok_button, 'button', 'button hilight'), 'center', 6)
        pile = urwid.Pile([urwid.Text(helptext), ok_button_wrap])
        self.dialog = Dialog(pile, self.mainloop, width=62)
        self.dialog.show()
    
    def help_close(self, widget):
        self.dialog.close()
        
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
        
    def do_reload(self):
        # Create a list of buttons to select the API
        rb_apis = []
        apis = []
        for api in self.engine.config.keys():
            if api != "main":
                but = urwid.RadioButton(rb_apis, api)
                # Make it selected if it's the current API
                if self.engine.config['main']['api'] == api:
                    but.set_state(True)
                urwid.connect_signal(but, 'change', self.reload_request, [api, None])
                apis.append(urwid.AttrWrap(but, 'button', 'button hilight'))
        api = urwid.Columns([urwid.Text('API:'), urwid.Pile(apis)])
        
        # Create a list of buttons to select the mediatype
        rb_mt = []
        mediatypes = []
        for mediatype in self.engine.api_info['supported_mediatypes']:
            but = urwid.RadioButton(rb_mt, mediatype)
            # Make it selected if it's the current mediatype
            if self.engine.api_info['mediatype'] == mediatype:
                but.set_state(True)
            urwid.connect_signal(but, 'change', self.reload_request, [None, mediatype])
            mediatypes.append(urwid.AttrWrap(but, 'button', 'button hilight'))
        mediatype = urwid.Columns([urwid.Text('Mediatype:'), urwid.Pile(mediatypes)])
        
        main_pile = urwid.Pile([mediatype, urwid.Divider(), api])
        self.dialog = Dialog(main_pile, self.mainloop, width=30)
        self.dialog.show()
        
    def do_quit(self):
        self.engine.unload()
        raise urwid.ExitMainLoop()
    
    def delete_request(self, data):
        self.ask_finish(self.delete_request)
        if data == 'y':
            showid = self.listbox.get_focus()[0].showid
            show = self.engine.get_show_info(showid)
            
            try:
                show = self.engine.delete_show(show)
            except utils.wmalError, e:
                self.status("Error: %s" % e.message)
        
    def status_request(self, widget, data):
        self.dialog.close()
        if data:
            item = self.listbox.get_focus()[0]
            
            try:
                show = self.engine.set_status(item.showid, int(data))
            except utils.wmalError, e:
                self.status("Error: %s" % e.message)
                return
    
    def reload_request(self, widget, selected, data):
        if selected:
            self.dialog.close()
            self.engine.reload(data[0], data[1])
            self._rebuild()
        
    def update_request(self, data):
        self.ask_finish(self.update_request)
        if data:
            item = self.listbox.get_focus()[0]
            
            try:
                show = self.engine.set_episode(item.showid, int(data))
            except utils.wmalError, e:
                self.status("Error: %s" % e.message)
                return
    
    def score_request(self, data):
        self.ask_finish(self.score_request)
        if data:
            item = self.listbox.get_focus()[0]
            
            try:
                show = self.engine.set_score(item.showid, int(data))
            except utils.wmalError, e:
                self.status("Error: %s" % e.message)
                return
    
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
                self.question("Update %s to episode %d? [y/N] " % (show['title'], played_episode), self.update_next_request)
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
        else:
            self.status('Ready.')
    
    def changed_show(self, show):
        self.listwalker.update_show(show)
    
    def changed_show_status(self, show):
        self.listwalker.update_show(show)
        
        self.cur_filter = show['my_status']
        self.header_filter.set_text("Filter:%s" % self.filters[self.cur_filter])
        self.clear_list()
        self.build_list()
        
        self.listwalker.select_show(show)
    
    def changed_list(self, show):
        self.clear_list()
        self.build_list()
        
    def ask(self, msg, callback, data=u''):
        self.asker = Asker(msg, str(data))
        self.view.set_footer(urwid.AttrWrap(self.asker, 'status'))
        self.view.set_focus('footer')
        urwid.connect_signal(self.asker, 'done', callback)
    
    def question(self, msg, callback, data=u''):
        self.asker = QuestionAsker(msg, str(data))
        self.view.set_footer(urwid.AttrWrap(self.asker, 'status'))
        self.view.set_focus('footer')
        urwid.connect_signal(self.asker, 'done', callback)
    
    def ask_finish(self, callback):
        self.view.set_focus('body')
        urwid.disconnect_signal(self, self.asker, 'done', callback)
        self.view.set_footer(self.statusbar)
    
    def do_search(self, key=''):
        self.ask('Search: ', self.search_request, key)
        #urwid.connect_signal(self.asker, 'change', self.search_live)
        
    #def search_live(self, widget, data):
    #    if data:
    #        self.listwalker.select_match(data)
        
    def search_request(self, data):
        if data:
            self.ask_finish(self.search_request)
            self.listwalker.select_match(data)

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
        if key in ('up', 'down', 'left', 'right', 'enter'):
            self.widget.keypress(size, key)
        elif key == 'esc':
            self.close()

class AddDialog(Dialog):
    def __init__(self, loop, width=30):
        self.topask = Asker('Search:')
        urwid.connect_signal(self.topask, 'done', self.search)
        listheader = urwid.Columns([
                ('fixed', 7, urwid.Text('ID')),
                ('weight', 1, urwid.Text('Title')),
                ('fixed', 10, urwid.Text('Type')),
                ('fixed', 7, urwid.Text('Total')),
            ])
        
        self.listwalker = urwid.SimpleListWalker([])
        listbox = urwid.BoxAdapter(urwid.ListBox(self.listwalker), 10)
        #self.listframe = urwid.BoxAdapter(urwid.Frame(listbox, header=listheader), 10)
        
        #self.frame = urwid.BoxAdapter(urwid.Frame(self.listframe, header=top), 10)
        self.frame = urwid.Pile([self.topask, listheader, listbox])
        
        self.__super.__init__(self.frame, loop, width)
    
    def search(self, data):
        if data:
            self.listwalker.append(urwid.Text(data))
    
    def keypress(self, size, key):
        if key in ('up', 'down', 'left', 'right', 'enter'):
            self.widget.keypress(size, key)
        elif key == 'esc':
            self.close()
        else:
            self.topask.keypress(size, key)
    
class ShowWalker(urwid.SimpleListWalker):
    def _get_showitem(self, showid):
        for i, item in enumerate(self):
            if showid == item.showid:
                return (i, item)
        raise Exception('Show not found in ShowWalker.')
    
    def update_show(self, show):
        (position, showitem) = self._get_showitem(show['id'])
        showitem.update(show)
    
    def select_show(self, show):
        (position, showitem) = self._get_showitem(show['id'])
        self.set_focus(position)
    
    def select_match(self, searchstr):
        for i, item in enumerate(self):
            if re.match(searchstr, item.showtitle, re.I):
                self.set_focus(i)
                break
    
class ShowItem(urwid.WidgetWrap):
    def __init__(self, show, has_progress=True):
        if has_progress:
            self.episodes_str = urwid.Text("{0:3} / {1}".format(show['my_progress'], show['total']))
        else:
            self.episodes_str = urwid.Text("-")
        
        self.score_str = urwid.Text("{0:^5}".format(show['my_score']))
        #self.score_str = urwid.Text(str(show['status']))
        self.has_progress = has_progress
        
        self.showid = show['id']
        self.showtitle = show['title']
        self.item = [
            ('fixed', 7, urwid.Text("%d" % self.showid)),
            ('weight', 1, urwid.Text(show['title'])),
            ('fixed', 10, self.episodes_str),
            ('fixed', 7, self.score_str),
        ]
        
        if show['status'] == 1:
            _color = 'item_airing'
        elif show['status'] == 3:
            _color = 'item_notaired'
        else:
            _color = 'body'
        
        w = urwid.AttrWrap(urwid.Columns(self.item), _color, 'focus')
        
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

class QuestionAsker(Asker):
    def keypress(self, size, key):
        urwid.emit_signal(self, 'done', key)
    
if __name__ == '__main__':
    try:
        wMAL_urwid()
    except utils.wmalFatal, e:
        print e.message

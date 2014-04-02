# wMAL-curses v0.2
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
import sys
import webbrowser

from wmal.engine import Engine
from wmal.accounts import AccountManager

import wmal.messenger as messenger
import wmal.utils as utils

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
    keymapping = dict()
    positions = list()
    last_search = None
    
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
        ('error', 'light red', 'dark blue'),
        ('window', 'yellow', 'dark blue'),
        ('button', 'black', 'light gray'),
        ('button hilight', 'white', 'dark red'),
        ('item_airing', 'dark blue', ''),
        ('item_notaired', 'yellow', ''),
        ('item_neweps', 'white', 'brown'),
        ('item_updated', 'white', 'dark green'),
        ('item_playing', 'white', 'dark blue'),
        ('info_title', 'light red', ''),
        ('info_section', 'dark blue', ''),
        ]
        
        keymap = utils.parse_config(utils.get_root_filename('keymap.json'), utils.keymap_defaults)
        self.keymapping = self.map_key_to_func(keymap)
        
        sys.stdout.write("\x1b]0;wMAL-curses "+utils.VERSION+"\x07");
        self.header_title = urwid.Text('wMAL-curses ' + utils.VERSION)
        self.header_api = urwid.Text('API:')
        self.header_filter = urwid.Text('Filter:watching')
        self.header_sort = urwid.Text('Sort:title')
        self.header = urwid.AttrMap(urwid.Columns([
            self.header_title,
            ('fixed', 23, self.header_filter),
            ('fixed', 17, self.header_sort),
            ('fixed', 16, self.header_api)]), 'status')
        
        
        top_text = keymap['help'] + ':Help  ' + keymap['sort'] +':Sort  ' + \
                   keymap['update'] + ':Update  ' + keymap['play'] + ':Play  ' + \
                   keymap['status'] + ':Status  ' + keymap['score'] + ':Score  ' + \
                   keymap['quit'] + ':Quit'
        self.top_pile = urwid.Pile([self.header,
            urwid.AttrMap(urwid.Text(top_text), 'status')
        ])
        
        self.statusbar = urwid.AttrMap(urwid.Text('wMAL-curses '+utils.VERSION), 'status')
        
        self.listheader = urwid.AttrMap(
            urwid.Columns([
                ('weight', 1, urwid.Text('Title')),
                ('fixed', 10, urwid.Text('Progress')),
                ('fixed', 7, urwid.Text('Score')),
            ]), 'header')
        
        self.listwalker = ShowWalker([])
        self.listbox = urwid.ListBox(self.listwalker)
        self.listframe = urwid.Frame(self.listbox, header=self.listheader)

        self.viewing_info = False
            
        self.view = urwid.Frame(self.listframe, header=self.top_pile, footer=self.statusbar)
        self.mainloop = urwid.MainLoop(self.view, palette, unhandled_input=self.keystroke, screen=urwid.raw_display.Screen())
        
        self.mainloop.set_alarm_in(0, self.do_switch_account)
        self.mainloop.run()
        
    def map_key_to_func(self, keymap):
        keymapping = dict()
        funcmap = { 'help': self.do_help, 
                    'prev_filter': self.do_prev_filter,
                    'next_filter': self.do_next_filter,
                    'sort': self.do_sort,
                    'update': self.do_update,
                    'play': self.do_play,
                    'status': self.do_status,
                    'score': self.do_score,
                    'send': self.do_send,
                    'retrieve': self.do_retrieve,
                    'addsearch': self.do_addsearch,
                    'reload': self.do_reload,
                    'switch_account': self.do_switch_account,
                    'delete': self.do_delete,
                    'quit': self.do_quit,
                    'altname': self.do_altname,
                    'search': self.do_search,
                    'neweps': self.do_neweps,
                    'details': self.do_info,
                    'details_exit': self.do_info_exit,
                    'open_web': self.do_open_web,
                    }
        
        for key, value in keymap.items():
            try:
                keymapping.update({value: funcmap[key]})
            except KeyError:
                # keymap.json requested an action not available in funcmap
                pass
        return keymapping
    
    def _rebuild(self):
        self.header_api.set_text('API:%s' % self.engine.api_info['name'])
        self.lists = dict()
        self.filters = self.engine.mediainfo['statuses_dict']
        self.filters_nums = self.engine.mediainfo['statuses']
        
        for status in self.filters_nums:
            #self.lists = ShowWalker([])
            #self.listbox = urwid.ListBox(self.listwalker)
            self.lists[status] = urwid.ListBox(ShowWalker([]))
            self._rebuild_list(status)

        self.set_filter(0)

        self.status('Ready.')
    
    def _rebuild_all_lists(self):
        for status in self.lists.keys():
            self._rebuild_list(status)
        
    def start(self, account):
        """Starts the engine"""
        # Engine configuration
        self.status("Starting engine...")
        self.engine = Engine(account, self.message_handler)
        self.engine.connect_signal('episode_changed', self.changed_show)
        self.engine.connect_signal('score_changed', self.changed_show)
        self.engine.connect_signal('status_changed', self.changed_show_status)
        self.engine.connect_signal('playing', self.playing_show)
        self.engine.connect_signal('show_added', self.changed_list)
        self.engine.connect_signal('show_deleted', self.changed_list)

        # Engine start and list rebuildi
        self.status("Building lists...")
        self.engine.start()
        self._rebuild()
    
    def set_filter(self, filter_num):
        self.cur_filter = filter_num
        _filter = self.filters_nums[self.cur_filter]
        self.header_filter.set_text("Filter:%s" % self.filters[_filter])

        self.listframe.body = self.lists[_filter]

    def _get_cur_list(self):
        _filter = self.filters_nums[self.cur_filter]
        return self.lists[_filter].body

    def _rebuild_list(self, filter_num):
        w = self.lists[filter_num].body

        self.lists[filter_num].body[:] = []
        
        showlist = self.engine.filter_list(filter_num)
        sortedlist = sorted(showlist, key=itemgetter(self.cur_sort))
        for show in sortedlist:
            w.append(ShowItem(show, self.engine.mediainfo['has_progress'], self.engine.altname(show['id'])))
    
    def _get_selected_item(self):
        return self._get_cur_list().get_focus()[0]

    def status(self, msg):
        self.statusbar.base_widget.set_text(msg)

    def error(self, msg):
        self.statusbar.base_widget.set_text([('error', "Error: %s" % msg)])
        
    def message_handler(self, classname, msgtype, msg):
        if msgtype != messenger.TYPE_DEBUG:
            try:
                self.status(msg)
                self.mainloop.draw_screen()
            except AssertionError:
                print(msg)
        
    def keystroke(self, input):
        try:
            self.keymapping[input]()
        except KeyError:
            # Unbinded key pressed; do nothing
            pass

    def do_switch_account(self, loop=None, data=None):
        manager = AccountManager()
        
        if self.engine is None:
            if manager.get_default():
                self.start(manager.get_default())
            else:
                self.dialog = AccountDialog(self.mainloop, manager, False)
                urwid.connect_signal(self.dialog, 'done', self.start)
        else:
            self.dialog = AccountDialog(self.mainloop, manager, True)
            urwid.connect_signal(self.dialog, 'done', self.do_reload_engine)
        
    def do_addsearch(self):
        self.ask('Search on remote: ', self.addsearch_request)
    
    def do_delete(self):
        self.question('Delete selected show? [y/n] ', self.delete_request)
        
    def do_prev_filter(self):
        if self.cur_filter > 0:
            self.set_filter(self.cur_filter - 1)

    def do_next_filter(self):
        if self.cur_filter < len(self.filters)-1:
            self.set_filter(self.cur_filter + 1)

    def do_sort(self):
        self.status("Sorting...")
        _sort = self.sorts_iter.next()
        self.cur_sort = _sort
        self.header_sort.set_text("Sort:%s" % _sort)
        self._rebuild_all_lists()
        self.status("Ready.")
    
    def do_update(self):
        showid = self._get_selected_item().showid
        show = self.engine.get_show_info(showid)
        self.ask('[Update] Episode # to update to: ', self.update_request, show['my_progress'])
        
    def do_play(self):
        showid = self._get_selected_item().showid
        show = self.engine.get_show_info(showid)
        self.ask('[Play] Episode # to play: ', self.play_request, show['my_progress']+1)
    
    def do_send(self):
        self.engine.list_upload()
        self._rebuild_all_lists();
        self.status("Ready.")

    def do_retrieve(self):
        try:
            self.engine.list_download()
            self._rebuild_all_lists()
            self.status("Ready.")
        except utils.wmalError, e:
            self.error(e.message)
    
    def do_help(self):
        helptext = "wMAL-curses "+utils.VERSION+"  by z411 (electrik.persona@gmail.com)\n\n"
        helptext += "wMAL is an open source client for media tracking websites.\n"
        helptext += "http://github.com/z411/wmal-python\n\n"
        helptext += "This program is licensed under the GPLv3,\nfor more information read COPYING file.\n\n"
        helptext += "More controls:\n  Left/Right:View status\n  /:Search\n  a:Add\n  c:Change API/Mediatype\n"
        helptext += "  d:Delete\n  s:Send changes\n  R:Retrieve list\n  Enter: View details\n  O: Open website\n  A:Set alternative title\n  N:Search for new episodes\n  F9: Change account"
        ok_button = urwid.Button('OK', self.help_close)
        ok_button_wrap = urwid.Padding(urwid.AttrMap(ok_button, 'button', 'button hilight'), 'center', 6)
        pile = urwid.Pile([urwid.Text(helptext), ok_button_wrap])
        self.dialog = Dialog(pile, self.mainloop, width=62, title='About/Help')
        self.dialog.show()
    
    def help_close(self, widget):
        self.dialog.close()
    
    def do_altname(self):
        showid = self._get_selected_item().showid
        show = self.engine.get_show_info(showid)
        self.status(show['title'])
        self.ask('[Altname] New alternative name: ', self.altname_request, self.engine.altname(showid))

    def do_score(self):
        showid = self._get_selected_item().showid
        show = self.engine.get_show_info(showid)
        self.ask('[Score] Score to change to: ', self.score_request, show['my_score'])
        
    def do_status(self):
        showid = self._get_selected_item().showid
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
            buttons.append(urwid.AttrMap(button, 'button', 'button hilight'))
            if status == show['my_status']:
                selected = num
            num += 1
        pile = urwid.Pile(buttons)
        pile.set_focus(selected)
        self.dialog = Dialog(pile, self.mainloop, width=22)
        self.dialog.show()
        
    def do_reload(self):
        # Create a list of buttons to select the mediatype
        rb_mt = []
        mediatypes = []
        for mediatype in self.engine.api_info['supported_mediatypes']:
            but = urwid.RadioButton(rb_mt, mediatype)
            # Make it selected if it's the current mediatype
            if self.engine.api_info['mediatype'] == mediatype:
                but.set_state(True)
            urwid.connect_signal(but, 'change', self.reload_request, [None, mediatype])
            mediatypes.append(urwid.AttrMap(but, 'button', 'button hilight'))
        mediatype = urwid.Columns([urwid.Text('Mediatype:'), urwid.Pile(mediatypes)])
        
        #main_pile = urwid.Pile([mediatype, urwid.Divider(), api])
        self.dialog = Dialog(mediatype, self.mainloop, width=30, title='Change media type')
        self.dialog.show()
    
    def do_reload_engine(self, account=None, mediatype=None):
        self.engine.reload(account, mediatype)
        self._rebuild()
    
    def do_open_web(self):
        showid = self._get_selected_item().showid
        show = self.engine.get_show_info(showid)
        if show['url']:
            webbrowser.open(show['url'], 2, True)
 
    def do_info(self):
        if self.viewing_info:
            return

        showid = self._get_selected_item().showid
        show = self.engine.get_show_info(showid)

        self.status("Getting show details...")
        details = self.engine.get_show_details(show)

        title = urwid.Text( ('info_title', show['title']), 'center', 'any')
        widgets = []
        for line in details['extra']:
            if line[0] and line[1]:
                widgets.append( urwid.Text( ('info_section', "%s: " % line[0] ) ) )
                if isinstance(line[1], dict):
                    linestr = repr(line[1])
                elif isinstance(line[1], int):
                    linestr = str(line[1])
                else:
                    linestr = line[1]

                widgets.append( urwid.Padding(urwid.Text( linestr + "\n" ), left=3) )
        
        self.view.body = urwid.Frame(urwid.ListBox(widgets), header=title)
        self.viewing_info = True
        self.status("Detail View | ESC:Return  Up/Down:Scroll  O:View website")
    
    def do_info_exit(self):
        if self.viewing_info:
            self.view.body = self.listframe
            self.viewing_info = False
            self.status("Ready.")

    def do_neweps(self):
        try:
            _filter = self.filters_nums[self.cur_filter]
            filtered = self.engine.filter_list(_filter)

            shows = self.engine.get_new_episodes(filtered)
            self._rebuild()

            self.status("Ready.")
        except utils.wmalError, e:
            self.error(e.message)

    def do_quit(self):
        self.engine.unload()
        raise urwid.ExitMainLoop()
    
    def addsearch_request(self, data):
        self.ask_finish(self.addsearch_request)
        if data:
            shows = self.engine.search(data)
            if len(shows) > 0:
                self.status("Ready.")
                self.dialog = AddDialog(self.mainloop, self.engine, showlist=shows, width=('relative', 80))
                urwid.connect_signal(self.dialog, 'done', self.addsearch_do)
                self.dialog.show()
            else:
                self.status("No results.")
    
    def addsearch_do(self, show):
        self.dialog.close()
        # Add show as current status
        show['my_status'] = self.filters_nums[self.cur_filter]
        try:
            self.engine.add_show(show)
        except utils.wmalError, e:
            self.error(e.message)
        
    def delete_request(self, data):
        self.ask_finish(self.delete_request)
        if data == 'y':
            showid = self._get_selected_item().showid
            show = self.engine.get_show_info(showid)
            
            try:
                show = self.engine.delete_show(show)
            except utils.wmalError, e:
                self.error(e.message)
        
    def status_request(self, widget, data):
        self.dialog.close()
        if data:
            item = self._get_selected_item()
            
            try:
                show = self.engine.set_status(item.showid, data)
            except utils.wmalError, e:
                self.error(e.message)
                return
    
    def reload_request(self, widget, selected, data):
        if selected:
            self.dialog.close()
            self.do_reload_engine(data[0], data[1])
    
    def update_request(self, data):
        self.ask_finish(self.update_request)
        if data:
            item = self._get_selected_item()
            
            try:
                show = self.engine.set_episode(item.showid, data)
            except utils.wmalError, e:
                self.error(e.message)
                return
    
    def score_request(self, data):
        self.ask_finish(self.score_request)
        if data:
            item = self._get_selected_item()
            
            try:
                show = self.engine.set_score(item.showid, data)
            except utils.wmalError, e:
                self.error(e.message)
                return
    
    def altname_request(self, data):
        self.ask_finish(self.altname_request)
        if data:
            item = self._get_selected_item()

            try:
                self.engine.altname(item.showid, data)
                item.update_altname(self.engine.altname(item.showid))
            except utils.wmalError, e:
                self.error(e.message)
                return

    def play_request(self, data):
        self.ask_finish(self.play_request)
        if data:
            item = self._get_selected_item()
            show = self.engine.get_show_info(item.showid)
            
            try:
                played_episode = self.engine.play_episode(show, data)
            except utils.wmalError, e:
                self.error(e.message)
                return
            
            if played_episode == (show['my_progress'] + 1):
                self.question("Update %s to episode %d? [y/N] " % (show['title'], played_episode), self.update_next_request)
            else:
                self.status('Ready.')
    
    def update_next_request(self, data):
        self.ask_finish(self.update_next_request)
        if data == 'y':
            item = self._get_selected_item()
            show = self.engine.get_show_info(item.showid)
            next_episode = show['my_progress'] + 1
            
            try:
                show = self.engine.set_episode(item.showid, next_episode)
            except utils.wmalError, e:
                self.error(e.message)
                return
        else:
            self.status('Ready.')
    
    def changed_show(self, show):
        status = show['my_status']
        self.lists[status].body.update_show(show)
        self.mainloop.draw_screen()

    def changed_show_status(self, show):
        self._rebuild_all_lists()
        
        go_filter = 0
        for _filter in self.filters_nums:
            if _filter == show['my_status']:
                break
            go_filter += 1

        self.set_filter(go_filter)
        self._get_cur_list().select_show(show)

    def playing_show(self, show, is_playing):
        status = show['my_status']
        self.lists[status].body.playing_show(show, is_playing)
        self.mainloop.draw_screen()
    
    def changed_list(self, show):
        self._rebuild_list(show['my_status'])
        
    def ask(self, msg, callback, data=u''):
        self.asker = Asker(msg, str(data))
        self.view.set_footer(urwid.AttrMap(self.asker, 'status'))
        self.view.set_focus('footer')
        urwid.connect_signal(self.asker, 'done', callback)
    
    def question(self, msg, callback, data=u''):
        self.asker = QuestionAsker(msg, str(data))
        self.view.set_footer(urwid.AttrMap(self.asker, 'status'))
        self.view.set_focus('footer')
        urwid.connect_signal(self.asker, 'done', callback)
    
    def ask_finish(self, callback):
        self.view.set_focus('body')
        urwid.disconnect_signal(self, self.asker, 'done', callback)
        self.view.set_footer(self.statusbar)
    
    def do_search(self, key=''):
        if self.last_search:
            text = "Search forward [%s]: " % self.last_search
        else:
            text = "Search forward: "

        self.ask(text, self.search_request, key)
        #urwid.connect_signal(self.asker, 'change', self.search_live)
        
    #def search_live(self, widget, data):
    #    if data:
    #        self.listwalker.select_match(data)
        
    def search_request(self, data):
        self.ask_finish(self.search_request)
        if data:
            self.last_search = data
            self._get_cur_list().select_match(data)
        elif self.last_search:
            self._get_cur_list().select_match(self.last_search) 

class Dialog(urwid.Overlay):
    def __init__(self, widget, loop, width=30, height=None, title=''):
        self.widget = urwid.AttrMap(urwid.LineBox(widget, title=title), 'window')
        self.oldwidget = loop.widget
        self.loop = loop
        self.__super.__init__(self.widget, loop.widget,
                align="center",
                width=width,
                valign="middle",
                height=height)
    
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
    __metaclass__ = urwid.signals.MetaSignals
    signals = ['done']
    
    def __init__(self, loop, engine, showlist={}, width=30):
        self.viewing_info = False
        self.engine = engine

        self.listheader = urwid.Columns([
                ('fixed', 7, urwid.Text('ID')),
                ('weight', 1, urwid.Text('Title')),
                ('fixed', 10, urwid.Text('Type')),
                ('fixed', 7, urwid.Text('Total')),
            ])
        
        self.listwalker = urwid.SimpleListWalker([])
        self.listbox = urwid.ListBox(self.listwalker)
        
        # Add results to the list
        for show in showlist:
            self.listwalker.append(SearchItem(show))
        
        self.info_txt = urwid.Text("Add View | Enter:Add  i:Info  O:Website  Esc:Cancel")
        self.frame = urwid.Frame(self.listbox, header=self.listheader, footer=self.info_txt)
        self.__super.__init__(self.frame, loop, width=width, height=('relative', 80), title='Search results')
    
    def keypress(self, size, key):
        if key in ('up', 'down', 'left', 'right', 'tab'):
            self.widget.keypress(size, key)
        elif key == 'enter':
            show = self.listwalker.get_focus()[0].show
            urwid.emit_signal(self, 'done', show)
        elif key == 'i':
            show = self.listwalker.get_focus()[0].show
            self.do_info()
        elif key == 'O':
            show = self.listwalker.get_focus()[0].show
            webbrowser.open(show['url'], 2, True)
        elif key == 'esc':
            self.do_info_exit()

    def do_info(self):
        if self.viewing_info:
            return

        show = self.listwalker.get_focus()[0].show

        #self.status("Getting show details...")
        details = self.engine.get_show_details(show)

        title = urwid.Text( ('info_title', show['title']), 'center', 'any')
        widgets = []
        for line in details['extra']:
            if line[0] and line[1]:
                widgets.append( urwid.Text( ('info_section', "%s: " % line[0] ) ) )
                if isinstance(line[1], dict):
                    linestr = repr(line[1])
                elif isinstance(line[1], int):
                    linestr = str(line[1])
                else:
                    linestr = line[1]

                widgets.append( urwid.Padding(urwid.Text( linestr + "\n" ), left=3) )
        
        self.frame.body = urwid.ListBox(widgets)
        self.frame.header = title
        self.viewing_info = True
        self.info_txt.set_text("Detail View | ESC:Return  Up/Down:Scroll  O:View website")
    
    def do_info_exit(self):
        if self.viewing_info:
            self.frame.body = self.listbox
            self.frame.header = self.listheader
            self.info_txt.set_text("Add View | Enter:Add  i:Info  O:Website  Esc:Cancel")
            self.viewing_info = False
        else:
            self.close()
 
class AccountDialog(Dialog):
    __metaclass__ = urwid.signals.MetaSignals
    signals = ['done']
    adding_data = dict()
    
    def __init__(self, loop, manager, switch=False, width=50):
        self.switch = switch
        self.manager = manager
        
        listheader = urwid.Columns([
                ('weight', 1, urwid.Text('Username')),
                ('fixed', 15, urwid.Text('Site')),
            ])
        
        self.listwalker = urwid.SimpleListWalker([])
        listbox = urwid.ListBox(self.listwalker)
        
        self.build_list()
              
        self.foot = urwid.Text('enter:Use once  r:Use always  a:Add  D:Delete')
        self.frame = urwid.Frame(listbox, header=listheader, footer=self.foot)
        self.__super.__init__(self.frame, loop, width=width, height=15, title='Select Account')
        
        self.adding = False

        self.show()
    
    def build_list(self):
        self.listwalker[:] = []

        for k, account in self.manager.get_accounts():
            self.listwalker.append(AccountItem(k, account))

    def keypress(self, size, key):
        #if key in ('up', 'down', 'left', 'right', 'tab'):
        #    self.widget.keypress(size, key)
        if self.adding:
            if key == 'esc':
                self.foot_clear()
            else:
                self.widget.keypress(size, key)
        else:
            if key == 'enter':
                self.do_select(False)
            elif key == 'a':
                self.do_add_username()
            elif key == 'r':
                self.do_select(True)
            elif key == 'D':
                self.do_delete_ask()
            elif key == 'esc':
                self.close()
                if not self.switch:
                    raise urwid.ExitMainLoop()
            else:
                self.widget.keypress(size, key)
    
    def do_add_username(self):
        self.adding = True
        ask = Asker("Username: ")
        self.frame.footer = ask
        self.frame.set_focus('footer')
        urwid.connect_signal(ask, 'done', self.do_add_password)

    def do_add_password(self, data):
        self.adding_data['username'] = data
        ask = Asker("Password: ")
        self.frame.footer = ask
        urwid.connect_signal(ask, 'done', self.do_add_api)

    def do_add_api(self, data):
        self.adding_data['password'] = data

        available_libs = ', '.join(sorted(utils.available_libs.iterkeys()))
        ask = Asker("API (%s): " % available_libs)
        self.frame.footer = ask
        urwid.connect_signal(ask, 'done', self.do_add)
    
    def do_delete_ask(self):
        self.adding = True
        ask = QuestionAsker("Do you want to delete this account? [y/n] ")
        self.frame.footer = ask
        self.frame.set_focus('footer')
        urwid.connect_signal(ask, 'done', self.do_delete)

    def do_delete(self, data):
        if data == 'y':
            accountitem = self.listwalker.get_focus()[0]
            self.manager.delete_account(accountitem.num)

        self.build_list()
        self.foot_clear()

    def do_add(self, data):
        username = self.adding_data['username']
        password = self.adding_data['password']
        api = data

        try:
            self.manager.add_account(username, password, api)
        except utils.AccountError, e:
            self.adding = False
            self.frame.footer = urwid.Text("Error: %s" % e.message)
            self.frame.set_focus('body')
            return

        self.build_list()
        self.foot_clear()

    def foot_clear(self):
        self.adding = False
        self.frame.footer = self.foot
        self.frame.set_focus('body')
    
    def do_select(self, remember):
        accountitem = self.listwalker.get_focus()[0]
        if remember:
            self.manager.set_default(accountitem.num)
        else:
            self.manager.set_default(None)
        urwid.emit_signal(self, 'done', accountitem.account)
        self.close()

class AccountItem(urwid.WidgetWrap):
    def __init__(self, num, account):
        self.num = num
        self.account = account
        self.item = [
            ('weight', 1, urwid.Text(account['username'])),
            ('fixed', 15, urwid.Text(account['api'])),
        ]
        w = urwid.AttrMap(urwid.Columns(self.item), 'window', 'focus')
        self.__super.__init__(w)
    
    def selectable(self):
        return True

    def keypress(self, size, key):
        return key
    
class SearchItem(urwid.WidgetWrap):
    def __init__(self, show, has_progress=True):
        self.show = show
        self.item = [
            ('weight', 1, urwid.Text(show['title'])),
            ('fixed', 10, urwid.Text(str(show['type']))),
            ('fixed', 7, urwid.Text("%d" % show['total'])),
        ]
        w = urwid.AttrMap(urwid.Columns(self.item), 'window', 'focus')
        self.__super.__init__(w)
    
    def selectable(self):
        return True

    def keypress(self, size, key):
        return key
    
class ShowWalker(urwid.SimpleListWalker):
    def _get_showitem(self, showid):
        for i, item in enumerate(self):
            if showid == item.showid:
                return (i, item)
        #raise Exception('Show not found in ShowWalker.')
        return (None, None)
    
    def highlight_show(self, show, tocolor):
        (position, showitem) = self._get_showitem(show['id'])
        showitem.highlight(tocolor)

    def update_show(self, show):
        (position, showitem) = self._get_showitem(show['id'])
        if showitem:
            showitem.update(show)
            return True
        else:
            return False
    
    def playing_show(self, show, is_playing):
        (position, showitem) = self._get_showitem(show['id'])
        if showitem:
            showitem.playing = is_playing
            showitem.highlight(show)
            return True
        else:
            return False

    def select_show(self, show):
        (position, showitem) = self._get_showitem(show['id'])
        if showitem:
            self.set_focus(position)
    
    def select_match(self, searchstr):
        pos = self.get_focus()[1]
        for i, item in enumerate(self):
            if i <= pos:
                continue
            if re.search(searchstr, item.showtitle, re.I):
                self.set_focus(i)
                break
    
class ShowItem(urwid.WidgetWrap):
    def __init__(self, show, has_progress=True, altname=None):
        if has_progress:
            self.episodes_str = urwid.Text("{0:3} / {1}".format(show['my_progress'], show['total']))
        else:
            self.episodes_str = urwid.Text("-")
        
        self.score_str = urwid.Text("{0:^5}".format(show['my_score']))
        self.has_progress = has_progress
        self.playing = False

        self.show = show
        self.showid = show['id']

        self.showtitle = show['title']
        if altname:
            self.showtitle += " (%s)" % altname
        self.title_str = urwid.Text(self.showtitle)

        self.item = [
            ('weight', 1, self.title_str),
            ('fixed', 10, self.episodes_str),
            ('fixed', 7, self.score_str),
        ]
        
        # If the show should be highlighted, do it
        # otherwise color it according to its status
        if self.playing:
            self.color = 'item_playing'
        elif show.get('queued'):
            self.color = 'item_updated'
        elif show.get('neweps'):
            self.color = 'item_neweps'
        elif show['status'] == 1:
            self.color = 'item_airing'
        elif show['status'] == 3:
            self.color = 'item_notaired'
        else:
            self.color = 'body'
        
        self.m = urwid.AttrMap(urwid.Columns(self.item), self.color, 'focus')
        
        self.__super.__init__(self.m)
    
    def get_showid(self):
        return self.showid
    
    def update(self, show):
        if show['id'] == self.showid:
            # Update progress
            if self.has_progress:
                self.episodes_str.set_text("{0:3} / {1}".format(show['my_progress'], show['total']))
            self.score_str.set_text("{0:^5}".format(show['my_score']))
            
            # Update color
            self.highlight(show)
        else:
            print "Warning: Tried to update a show with a different ID! (%d -> %d)" % (show['id'], self.showid)

    def update_altname(self, altname):
        # Update title
        self.showtitle = "%s (%s)" % (self.show['title'], altname)
        self.title_str.set_text(self.showtitle)
    
    def highlight(self, show):
        if self.playing:
            self.color = 'item_playing'
        elif show.get('queued'):
            self.color = 'item_updated'
        elif show.get('neweps'):
            self.color = 'item_neweps'
        elif show['status'] == 1:
            self.color = 'item_airing'
        elif show['status'] == 3:
            self.color = 'item_notaired'
        else:
            self.color = 'body'
        
        self.m.set_attr_map({None: self.color})

    def selectable(self):
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
        if key.lower() in 'yn':
            urwid.emit_signal(self, 'done', key.lower())
    
def main():
    try:
        wMAL_urwid()
    except utils.wmalFatal, e:
        print "Fatal error: %s" % e.message

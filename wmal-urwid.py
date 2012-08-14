#!/usr/bin/python
import urwid
import engine
import utils
from operator import itemgetter
from itertools import cycle

class wMAL_urwid(object):
    """
    Main class for the urwid version of wMAL
    """
    
    """Main objects"""
    engine = None
    mainloop = None
    cur_filter = 1
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
            ('fixed', 20, self.header_filter),
            ('fixed', 20, self.header_sort)]), 'status')
        
        self.top_pile = urwid.Pile([self.header,
            urwid.AttrMap(urwid.Text('F1:Filter  F2:Sort  F3:Update  F4:Play  F10:Sync  F12:Quit'), 'status')
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
        self.mainloop = urwid.MainLoop(self.view, palette, unhandled_input=self.keystroke)
    
    def start(self):
        """Runs the main loop"""
        self.engine = engine.Engine(self.message_handler)
        self.engine.start()
        
        self.filters = self.engine.statuses_keys()
        self.filters_iter = cycle(self.engine.statuses_keys())
        
        self.build_list()
        
        self.status('Ready.')
        self.mainloop.run()
    
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
        self.status(msg)
        
    def keystroke(self, input):
        if input == 'f1':
            self.do_filter()
        elif input == 'f2':
            self.do_sort()
        elif input == 'f4':
            self.do_play()
        elif input == 'f12':
            raise urwid.ExitMainLoop()

        #if input is 'enter':
        #    focus = self.listbox.get_focus()[0].showid
        #    # set anime
    
    def do_filter(self):
        _filter = self.filters_iter.next()
        self.cur_filter = self.filters[_filter]
        self.header_filter.set_text("Filter:%s" % _filter)
        self.clear_list()
        self.build_list()
    
    def do_sort(self):
        _sort = self.sorts_iter.next()
        self.cur_sort = _sort
        self.header_sort.set_text("Sort:%s" % _sort)
        self.clear_list()
        self.build_list()
    
    def do_play(self):
        self.asker = Asker('Episde # to play: ')
        self.view.set_footer(urwid.AttrWrap(self.asker, 'status'))
        self.view.set_focus('footer')
        urwid.connect_signal(self.asker, 'done', self.play_request)
    
    def play_request(self, data):
        self.view.set_focus('body')
        urwid.disconnect_signal(self, self.asker, 'done', self.play_request)
        self.view.set_footer(self.statusbar)
        if data:
            item = self.listbox.get_focus()[0]
            show = item.show
            
            try:
                self.engine.play_episode(show, int(data))
            except utils.wmalError, e:
                self.status("Error: %s" % e.message)
                return
            
            self.status('Ready.')
            #show['my_episodes'] = int(data)
            #item.show = show
        
class ShowItem(urwid.WidgetWrap):
    def __init__ (self, show):
        self.episodes_str = urwid.Text('')
        
        self.show = show
        self.showid = show['id']
        self.item = [
            ('fixed', 7, urwid.Text("%d" % self.showid)),
            ('weight', 1, urwid.Text(show['title'])),
            ('fixed', 15, self.episodes_str),
        ]
        w = urwid.AttrWrap(urwid.Columns(self.item), 'body', 'focus')
        self.__super.__init__(w)
    
    def get_show(self):
        return self._show
    
    def set_show(self, show):
        self.episodes_str.set_text("{0:3} / {1}".format(show['my_episodes'], show['episodes']))
        self._show = show
        
    def selectable (self):
        return True

    def keypress(self, size, key):
        return key
    
    show = property(get_show, set_show)

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
    wMAL_urwid().start()

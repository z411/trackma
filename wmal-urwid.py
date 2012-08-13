#!/usr/bin/python
import urwid
import engine
from operator import itemgetter

class wMAL_urwid(object):
    """
    Main class for the urwid version of wMAL
    """
    
    """Main objects"""
    engine = None
    mainloop = None
    filter_num = 1
    sort = 'title'
    
    """Widgets"""
    header = None
    listbox = None
    view = None
    
    def __init__(self):
        """Creates main widgets and creates mainloop"""
        
        palette = [
        ('body','white', '', 'standout'),
        ('focus','dark red', '', 'standout'),
        ('head','light red', 'black'),
        ('status', 'yellow', 'dark blue', 'standout'),
        ]
        
        self.header = urwid.AttrMap(urwid.Text('wMAL-urwid v0.1'), 'status')
        self.statusbar = urwid.AttrMap(urwid.Text('wMAL-urwid v0.1'), 'status')
        
        #self.topinfo = urwid.Padding(urwid.Text('Show Title:\nWatched Episodes:\nScore:'), left=10, right=10)
        
        self.listheader = urwid.AttrMap(urwid.Text('wMAL-urwid v0.1'), 'head')
        self.listheader = urwid.Columns([
            ('fixed', 7, urwid.Text('ID')),
            ('weight', 1, urwid.Text('Title')),
            ('fixed', 15, urwid.Text('Episodes')),
        ])
        
        self.listwalker = urwid.SimpleListWalker([])
        self.listbox = urwid.ListBox(self.listwalker)
        self.listframe = urwid.Frame(self.listbox, header=self.listheader)
            
        self.view = urwid.Frame(urwid.AttrWrap(self.listframe, 'body'), header=self.header, footer=self.statusbar)
        self.mainloop = urwid.MainLoop(self.view, palette, unhandled_input=self.keystroke)
    
    def start(self):
        """Runs the main loop"""
        self.engine = engine.Engine(self.message_handler)
        self.engine.start()
        self.build_list()
        self.status('Ready.')
        
        self.mainloop.run()
    
    def build_list(self):
        showlist = self.engine.filter_list(self.filter_num)
        sortedlist = sorted(showlist, key=itemgetter(self.sort))
        for show in sortedlist:
            self.listwalker.append(ShowItem(show))
        
    def status(self, msg):
        self.statusbar.base_widget.set_text(msg)
        
    def message_handler(self, classname, msgtype, msg):
        self.status(msg)
        
    def keystroke(self, input):
        if input in ('q', 'Q'):
            raise urwid.ExitMainLoop()

        if input is 'enter':
            focus = self.listbox.get_focus()[0].showid
            self.view.set_header(urwid.AttrWrap(urwid.Text(
                'selected: %s' % str(focus)), 'head'))
        

class ShowItem(urwid.WidgetWrap):
    def __init__ (self, show):
        self.showid = show['id']
        self.item = [
            ('fixed', 7, urwid.AttrWrap(urwid.Text("%d" % self.showid), 'body', 'focus')),
            ('weight', 1, urwid.AttrWrap(urwid.Text(show['title']), 'body', 'focus')),
            ('fixed', 15, urwid.AttrWrap(urwid.Text("%d / %d" % (show['my_episodes'], show['episodes'])), 'body', 'focus')),
        ]
        w = urwid.Columns(self.item)
        self.__super.__init__(w)

    def selectable (self):
        return True

    def keypress(self, size, key):
        return key

if __name__ == '__main__':
    wmal = wMAL_urwid()
    wmal.start()

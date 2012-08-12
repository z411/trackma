#!/usr/bin/python

import sys
import readline
import cmd
import re
from operator import itemgetter # Used for sorting list

import messenger
import engine

_DEBUG = True
_COLOR_ENGINE = '\033[0;32m'
_COLOR_DATA = '\033[0;33m'
_COLOR_API = '\033[0;34m'
_COLOR_ERROR = '\033[0;31m'
_COLOR_FATAL = '\033[1;31m'
_COLOR_RESET = '\033[0m'

_COLOR_AIRING = '\033[0;34m'

class wmal_cmd(cmd.Cmd):
    """
    Main program, inherits from the useful Cmd class
    for interactive console
    """
    engine = None
    filter_num = 1
    sort = 'title'
    
    __re_cmd = re.compile(r"([-\w]+|\".*\")")
    
    def start(self):
        """
        Initializes the engine
        
        Creates an Engine object and starts it, then returns the result.
        """
        print 'wMAL v0.1  Copyright (C) 2012  z411'
        print 'This program comes with ABSOLUTELY NO WARRANTY; for details type `license\''
        print 'This is free software, and you are welcome to redistribute it'
        print 'under certain conditions; type `license conditions\' for details.'
        print
        print 'Initializing engine...'
        self.engine = engine.Engine(self.messagehandler)
        return self.engine.start()
    
    def do_filter(self, arg):
        """
        filter - Changes the filtering of list by status
        
        Usage: filter <filter type>
        """
        statuses = self.engine.statuses()
        statuses_keys = self.engine.statuses_keys()
        if arg:
            try:
                self.filter_num = statuses_keys[arg]
                self.prompt = 'MAL ' + statuses[self.filter_num] + '> '
            except KeyError:
                print "Invalid filter."
        else:
            print "Missing arguments."
    
    def do_sort(self, arg):
        """
        sort - Change sort
        
        Usage: sort <sort type>
        Available types: id, title, my_episodes, episodes
        """
        sorts = ('id', 'title', 'my_episodes', 'episodes')
        if arg in sorts:
            self.sort = arg
        else:
            print "Invalid sort."
        
    def do_list(self, arg):
        """
        list - Lists all shows available as a nice formatted list.
        """
        showlist = self.engine.filter_list(self.filter_num)
        sortedlist = sorted(showlist, key=itemgetter(self.sort)) 
        make_list(sortedlist)
    
    def do_search(self, arg):
        """
        search - Does a regex search on shows and lists the matches.
        
        Usage: search <pattern>
        """
        if(arg):
            showlist = self.engine.regex_list(arg)
            sortedlist = sorted(showlist, key=itemgetter(self.sort)) 
            make_list(sortedlist)
        else:
            print "Missing arguments."
    
    def do_update(self, arg):
        """
        update - Updates the episode of a show.
        
        Usage: update <show id or name> <episode number>
        """
        if arg:
            args = self.parse_args(arg)
            self.engine.set_episode(args[0], args[1])
        else:
            print "Missing arguments."
        
    def do_quit(self, arg):
        """Quits the program."""
        self.engine.unload()
        print 'Bye!'
        sys.exit(0)
    
    def complete_update(self, text, line, begidx, endidx):
        if text:
            return self.engine.regex_list_titles(text)
    
    def parse_args(self, arg):
        if arg:
            return list(v.strip('"') for v in self.__re_cmd.findall(arg))
        
    def messagehandler(self, classname, msgtype, msg):
        """
        Handles and shows messages coming from
        the engine messenger to provide feedback.
        """
        color_escape = ''
        color_reset = _COLOR_RESET
        
        if classname == 'Engine':
            color_escape = _COLOR_ENGINE
        elif classname == 'Data':
            color_escape = _COLOR_DATA
        elif classname.startswith('lib'):
            color_escape = _COLOR_API
        else:
            color_reset = ''
        
        if msgtype == messenger.TYPE_INFO:
            print color_escape + classname + ': ' + msg + color_reset
        elif msgtype == messenger.TYPE_ERROR:
            print _COLOR_ERROR + classname + ' error: ' + msg + _COLOR_RESET
        elif msgtype == messenger.TYPE_FATAL:
            print _COLOR_FATAL + classname + ' CRASH: ' + msg + _COLOR_RESET
            sys.exit(-1)
        elif _DEBUG and msgtype == messenger.TYPE_DEBUG:
            print color_escape + classname + ': ' + msg + color_reset

def make_list(showlist):
    """
    Helper function for printing a formatted show list
    """
    # Column widths
    col_id_length = 8
    col_title_length = 5
    col_episodes_length = 9
    
    # Find wider title
    for show in showlist:
        if len(show['title']) > col_title_length:
            col_title_length = len(show['title'])
        
    # Print header
    print   '| ' + \
            'ID'.           ljust(col_id_length) + \
            'Title'.        ljust(col_title_length) + ' ' + \
            'Episodes'.     ljust(col_episodes_length) + '|'
    
    # List shows
    for show in showlist:
        episodes_str = str(show['my_episodes']).rjust(3) + ' / ' + str(show['episodes'])
        if show['status'] == 1:
            title_str = _COLOR_AIRING + show['title'] + _COLOR_RESET
        else:
            title_str = show['title']
        
        print '| ' + \
              str(show['id']).      ljust(col_id_length) + \
              title_str +      '.' * (col_title_length-len(show['title'])) + ' ' + \
              episodes_str.     ljust(col_episodes_length) + '|'
    
    # Print result count
    print str(len(showlist)) + ' results'
    print
    
if __name__ == '__main__':
    main_cmd = wmal_cmd()
    main_cmd.prompt = 'MAL> '
    if main_cmd.start():
        print
        print "Ready. Type 'help' for a list of commands."
        print "Press tab for autocompletion and up/down for command history."
        print
        main_cmd.cmdloop()
    else:
        print "Couldn't start engine."

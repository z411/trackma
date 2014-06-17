# This file is part of wMAL.
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

import sys
try:
    import readline
except ImportError:
    pass # readline is optional
import cmd
import re
from operator import itemgetter # Used for sorting list

from wmal.engine import Engine
from wmal.accounts import AccountManager

import wmal.messenger as messenger
import wmal.utils as utils

_DEBUG = False
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
    completekey = 'Tab'
    cmdqueue = []
    stdout = sys.stdout
    
    __re_cmd = re.compile(r"([-\w]+|\".*\")")   # Args parser
    
    def __init__(self):
        print 'wMAL v'+utils.VERSION+'  Copyright (C) 2012  z411'
        print 'This program comes with ABSOLUTELY NO WARRANTY; for details type `info\''
        print 'This is free software, and you are welcome to redistribute it'
        print 'under certain conditions; see the file COPYING for details.'
        print

        self.accountman = wmal_accounts()
        self.account = self.accountman.select_account()

    def _update_prompt(self):
        self.prompt = "{0}({1}) {2}> ".format(self.engine.api_info['name'], self.engine.api_info['mediatype'], self.engine.mediainfo['statuses_dict'][self.filter_num])

    def start(self):
        """
        Initializes the engine
        
        Creates an Engine object and starts it.
        """
        print 'Initializing engine...'
        self.engine = Engine(self.account, self.messagehandler)
        self.engine.start()
        
        # Start with default filter selected
        self.filter_num = self.engine.mediainfo['statuses'][0]
        self._update_prompt()
    
    def do_account(self, arg):
        """
        account - Switch to a different account

        Usage: account
        """

        self.account = self.accountman.select_account()
        self.engine.reload(account=self.account)
    
    def do_filter(self, arg):
        """
        filter - Changes the filtering of list by status; call with no arguments to see available filters
        
        Usage: filter [filter type]
        """
        # Query the engine for the available statuses
        # that the user can choose
        
        if arg:
            try:
                args = self.parse_args(arg)
                self.filter_num = self._guess_status(args[0].lower())
                self._update_prompt()
            except KeyError:
                print "Invalid filter."
        else:
            print "Available filters: %s" % ', '.join( v.lower().replace(' ', '') for v in self.engine.mediainfo['statuses_dict'].values() )
    
    def do_sort(self, arg):
        """
        sort - Change sort
        
        Usage: sort <sort type>
        Available types: id, title, my_progress, episodes
        """
        sorts = ('id', 'title', 'my_progress', 'total')
        if arg in sorts:
            self.sort = arg
        else:
            print "Invalid sort."
    
    def do_mediatype(self, arg):
        """
        mediatype - Reloads engine with different mediatype; call with no arguments to see supported mediatypes
        
        Usage: mediatype [mediatype]
        """
        if arg:
            args = self.parse_args(arg)
            if args[0] in self.engine.api_info['supported_mediatypes']:
                self.engine.reload(mediatype=args[0])
            
                # Start with default filter selected
                self.filter_num = self.engine.mediainfo['statuses'][0]
                self.prompt = "{0}({1}) {1}> ".format(self.engine.api_info['name'], self.engine.api_info['mediatype'], self.engine.mediainfo['statuses_dict'][self.filter_num])
                self._update_prompt()
            else:
                print "Invalid mediatype."
        else:
            print "Supported mediatypes: %s" % ', '.join(self.engine.api_info['supported_mediatypes'])
        
    def do_list(self, arg):
        """
        list - Lists all shows available as a nice formatted list.
        """
        # Queries the engine for a list and sorts it
        # using the current sort
        showlist = self.engine.filter_list(self.filter_num)
        sortedlist = sorted(showlist, key=itemgetter(self.sort)) 
        self._make_list(sortedlist)
    
    def do_info(self, arg):
        if(arg):
            show = self.engine.get_show_info_title(arg)
            details = self.engine.get_show_details(show)
            print "Title: %s" % details['title']
            for line in details['extra']:
                print "%s: %s" % line
        else:
            print "Missing arguments."
    
    def do_search(self, arg):
        """
        search - Does a regex search on shows and lists the matches.
        
        Usage: search <pattern>
        
        """
        if(arg):
            showlist = self.engine.regex_list(arg)
            sortedlist = sorted(showlist, key=itemgetter(self.sort)) 
            self._make_list(sortedlist)
        else:
            print "Missing arguments."
    
    def do_add(self, arg):
        """
        add - Searches for a show and adds it
        
        Usage: add <pattern>
        
        """
        if(arg):
            entries = self.engine.search(arg)
            for i, entry in enumerate(entries, start=1):
                print "%d: (%s) %s" % (i, entry['type'], entry['title'])
            do_update = raw_input("Choose show to add (blank to cancel): ")
            if do_update != '':
                try:
                    show = entries[int(do_update)-1]
                except ValueError:
                    print "Choice must be numeric."
                    return
                except IndexError:
                    print "Invalid show."
                    return
                
                # Tell the engine to add the show
                try:
                    self.engine.add_show(show)
                except utils.wmalError, e:
                    self.display_error(e)
    
    def do_delete(self, arg):
        """
        delete - Deltes a show from the list
        
        Usage: delete <show id or title>
        
        """
        if(arg):
            args = self.parse_args(arg)
            
            try:
                show = self.engine.get_show_info_title(args[0])
                
                do_delete = raw_input("Delete %s? [y/N] " % show['title'])
                if do_delete.lower() == 'y':
                    self.engine.delete_show(show)
            except utils.wmalError, e:
                self.display_error(e)
        
    def do_neweps(self, arg):
        showlist = self.engine.filter_list(self.filter_num)
        results = self.engine.get_new_episodes(showlist)
        for show in results:
            print show['title']
        
    def do_play(self, arg):
        if arg:
            try:
                args = self.parse_args(arg)
                show = self.engine.get_show_info_title(args[0])
                episode = 0
                
                # If the user specified an episode, play it
                # otherwise play the next episode not watched yet
                try:
                    episode = args[1]
                    if episode == (show['my_progress'] + 1):
                        playing_next = True
                    else:
                        playing_next = False
                except IndexError:
                    playing_next = True
                
                played_episode = self.engine.play_episode(show, episode)
                
                # Ask if we should update the show to the last episode
                if played_episode and playing_next:
                    do_update = raw_input("Should I update %s to episode %d? [y/N] " % (show['title'], played_episode))
                    if do_update.lower() == 'y':
                        self.engine.set_episode(show['id'], played_episode)
            except utils.wmalError, e:
                self.display_error(e)
        else:
            print "Missing arguments."
        
    def do_update(self, arg):
        """
        update - Updates the episode of a show.
        
        Usage: update <show id or name> <episode number>
        """
        if arg:
            args = self.parse_args(arg)
            try:
                show = self.engine.get_show_info_title(args[0])
                self.engine.set_episode(show['id'], args[1])
            except IndexError:
                print "Missing arguments."
            except utils.wmalError, e:
                self.display_error(e)
        else:
            print "Missing arguments."
    
    def do_score(self, arg):
        """
        score - Changes the given score of a show.
        
        Usage: update <show id or name> <score>
        """
        if arg:
            args = self.parse_args(arg)
            try:
                self.engine.set_score(args[0], args[1])
            except IndexError:
                print "Missing arguments."
            except utils.wmalError, e:
                self.display_error(e)
        else:
            print "Missing arguments."
    
    def do_status(self, arg):
        """
        status - Changes the status of a show.
        
        Usage: status <show id or name> <status name>
        """
        if arg:
            args = self.parse_args(arg)
            try:
                _showname = args[0]
                _filter = args[1]
            except IndexError:
                print "Missing arguments."
            
            try:
                _filter_num = self._guess_status(_filter)
            except KeyError:
                print "Invalid filter."
                return
            
            try:
                self.engine.set_status(_showname, _filter_num)
            except utils.wmalError, e:
                self.display_error(e)
        
    def do_send(self, arg):
        try:
            self.engine.list_upload()
        except utils.wmalError, e:
            self.display_error(e)
    
    def do_retrieve(self, arg):
        try:
            self.engine.list_download()
        except utils.wmalError, e:
            self.display_error(e)
    
    def do_undoall(self, arg):
        """
        undo - Undo all changes
        
        Usage: undoall
        """
        try:
            self.engine.undoall()
        except utils.wmalError, e:
            self.display_error(e)
        
    def do_viewqueue(self, arg):
        queue = self.engine.get_queue()
        if len(queue):
            print "Queue:"
            for show in queue:
                print "- %s" % show['title']
        else:
            print "Queue is empty."
    
    def do_quit(self, arg):
        """Quits the program."""
        try:
            self.engine.unload()
        except utils.wmalError, e:
            self.display_error(e)
        
        print 'Bye!'
        sys.exit(0)
    
    def do_EOF(self, arg):
        print
        self.do_quit(arg)
    
    def do_track(self, arg):
        self.engine.track_process()
    
    def complete_update(self, text, line, begidx, endidx):
        if text:
            return self.engine.regex_list_titles(text)
    
    def complete_play(self, text, line, begidx, endidx):
        if text:
            return self.engine.regex_list_titles(text)
    
    def complete_score(self, text, line, begidx, endidx):
        if text:
            return self.engine.regex_list_titles(text)
    
    def complete_status(self, text, line, begidx, endidx):
        if text:
            return self.engine.regex_list_titles(text)
    
    def complete_delete(self, text, line, begidx, endidx):
        if text:
            return self.engine.regex_list_titles(text)
    
    def complete_filter(self, text, line, begidx, endidx):
        return (v.lower().replace(' ', '') for v in self.engine.mediainfo['statuses_dict'].values())
    
    def parse_args(self, arg):
        if arg:
            return list(v.strip('"') for v in self.__re_cmd.findall(arg))
    
    def display_error(self, e):
        print "%s%s: %s%s" % (_COLOR_ERROR, type(e), e.message, _COLOR_RESET)
    
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
            print "%s%s: %s%s" % (color_escape, classname, msg, color_reset)
        elif msgtype == messenger.TYPE_WARN:
            print "%s%s warning: %s%s" % (color_escape, classname, msg, color_reset)
        elif _DEBUG and msgtype == messenger.TYPE_DEBUG:
            print "%s%s: %s%s" % (color_escape, classname, msg, color_reset)
    
    def _guess_status(self, string):
        for k, v in self.engine.mediainfo['statuses_dict'].items():
            if string.lower() == v.lower().replace(' ', ''):
                return k
        raise KeyError

    def _make_list(self, showlist):
        """
        Helper function for printing a formatted show list
        """
        # Fixed column widths
        col_id_length = 7
        col_title_length = 5
        col_episodes_length = 9
        
        # Calculate maximum width for the title column
        # based on the width of the terminal
        (height, width) = utils.get_terminal_size()
        max_title_length = width - col_id_length - col_episodes_length - 5
        
        # Find the widest title so we can adjust the title column
        for show in showlist:
            if len(show['title']) > col_title_length:
                if len(show['title']) > max_title_length:
                    # Stop if we exceeded the maximum column width
                    col_title_length = max_title_length
                    break
                else:
                    col_title_length = len(show['title'])
            
        # Print header
        print "| {0:{1}} {2:{3}}|".format(
                'Title',    col_title_length,
                'Progress', col_episodes_length)
        
        # List shows
        for show in showlist:
            if self.engine.mediainfo['has_progress']:
                episodes_str = "{0:3} / {1}".format(show['my_progress'], show['total'])
            else:
                episodes_str = "-"
            
            # Truncate title if needed
            title_str = show['title'].encode('utf-8')
            title_str = title_str[:max_title_length] if len(title_str) > max_title_length else title_str
            
            # Color title according to status
            if show['status'] == 1:
                colored_title = _COLOR_AIRING + title_str + _COLOR_RESET
            else:
                colored_title = title_str
            
            print "| {0}{1} {2:{3}}|".format(
                colored_title,
                '.' * (col_title_length-len(show['title'])),
                episodes_str,
                col_episodes_length)
        
        # Print result count
        print '%d results' % len(showlist)
        print

class wmal_accounts(AccountManager):
    def select_account(self):
        while True:
            print '--- Accounts ---'
            self.list_accounts()
            key = raw_input("Input account number ([a]dd, [c]ancel, [d]elete, [q]uit): ")

            if key.lower() == 'a':
                available_libs = ', '.join(sorted(utils.available_libs.iterkeys()))
                
                print "--- Add account ---"
                import getpass
                username = raw_input('Enter username: ')
                password = getpass.getpass('Enter password (no echo): ')
                api = raw_input('Enter API (%s): ' % available_libs)
                
                try:
                    self.add_account(username, password, api)
                    print 'Done.'
                except utils.AccountError, e:
                    print 'Error: %s' % e.message
            elif key.lower() == 'd':
                print "--- Delete account ---"
                num = raw_input('Account number to delete: ')
                num = int(num)
                confirm = raw_input("Are you sure you want to delete account %d (%s)? [y/N] " % (num, self.get_account(num)['username']))
                if confirm.lower() == 'y':
                    self.delete_account(num)
                    print 'Account %d deleted.' % num
            elif key.lower() == 'q':
                sys.exit(0)
            else:
                try:
                    num = int(key)
                    return self.get_account(num)
                except ValueError:
                    print "Invalid value."
                except IndexError:
                    print "Account doesn't exist."
    
    def list_accounts(self):
        accounts = self.get_accounts()

        print "Available accounts:"
        i = 0
        for k, account in accounts:
            print "%d: %s (%s)" % (k, account['username'], account['api'])
            i += 1

        if i == 0:
            print "No accounts."


def main():
    main_cmd = wmal_cmd()
    try:
        main_cmd.start()
        print
        print "Ready. Type 'help' for a list of commands."
        print "Press tab for autocompletion and up/down for command history."
        print
        main_cmd.cmdloop()
    except utils.wmalFatal, e:
        print "%s%s: %s%s" % (_COLOR_FATAL, type(e), e.message, _COLOR_RESET)
    

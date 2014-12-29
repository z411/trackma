# This file is part of Trackma.
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
import shlex
import re
from operator import itemgetter # Used for sorting list

from trackma.engine import Engine
from trackma.accounts import AccountManager

import trackma.messenger as messenger
import trackma.utils as utils

_DEBUG = False
_COLOR_ENGINE = '\033[0;32m'
_COLOR_DATA = '\033[0;33m'
_COLOR_API = '\033[0;34m'
_COLOR_TRACKER = '\033[0;35m'
_COLOR_ERROR = '\033[0;31m'
_COLOR_FATAL = '\033[1;31m'
_COLOR_RESET = '\033[0m'

_COLOR_AIRING = '\033[0;34m'

class Trackma_cmd(cmd.Cmd):
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
    sortedlist = []
    
    def __init__(self):
        print 'Trackma v'+utils.VERSION+'  Copyright (C) 2012  z411'
        print 'This program comes with ABSOLUTELY NO WARRANTY; for details type `info\''
        print 'This is free software, and you are welcome to redistribute it'
        print 'under certain conditions; see the file COPYING for details.'
        print

        self.accountman = Trackma_accounts()
        self.account = self.accountman.select_account(False)

    def _update_prompt(self):
        self.prompt = "{0}({1}) {2}> ".format(self.engine.api_info['name'], self.engine.api_info['mediatype'], self.engine.mediainfo['statuses_dict'][self.filter_num])

    def _load_list(self, *args):
        showlist = self.engine.filter_list(self.filter_num)
        self.sortedlist = sorted(showlist, key=itemgetter(self.sort)) 

    def _get_show(self, title):
        # Attempt parsing list index
        # otherwise use title
        try:
            index = int(title)-1
            return self.sortedlist[index]
        except (ValueError, AttributeError, IndexError):
            return self.engine.get_show_info_title(title)

    def start(self):
        """
        Initializes the engine
        
        Creates an Engine object and starts it.
        """
        print 'Initializing engine...'
        self.engine = Engine(self.account, self.messagehandler)
        self.engine.connect_signal('show_added', self._load_list)
        self.engine.connect_signal('show_deleted', self._load_list)
        self.engine.connect_signal('status_changed', self._load_list)
        self.engine.connect_signal('episode_changed', self._load_list)
        self.engine.start()
        
        # Start with default filter selected
        self.filter_num = self.engine.mediainfo['statuses'][0]
        self._load_list()
        self._update_prompt()
    
    def do_account(self, arg):
        """
        account - Switch to a different account

        Usage: account
        """

        self.account = self.accountman.select_account(True)
        self.engine.reload(account=self.account)

        # Start with default filter selected
        self.filter_num = self.engine.mediainfo['statuses'][0]
        self._load_list()
        self._update_prompt()

    def do_filter(self, arg):
        """
        filter - Changes the filtering of list by status; call with no arguments to see available filters
        
        Usage: filter [filter type]
        """
        # Query the engine for the available statuses
        # that the user can choose
        if self.parse_args(arg):
            try:
                args = self.parse_args(arg)
                self.filter_num = self._guess_status(args[0].lower())
                self._load_list()
                self._update_prompt()
            except KeyError:
                print "Invalid filter."
        else:
            print "Available filters: %s" % ', '.join( v.lower().replace(' ', '') for v in self.engine.mediainfo['statuses_dict'].values() )
    
    def do_sort(self, arg):
        """
        sort - Change sort
        
        Usage: sort <sort type>
        Available types: id, title, my_progress, total, my_score
        """
        sorts = ('id', 'title', 'my_progress', 'total', 'my_score')
        if arg in sorts:
            self.sort = arg
            self._load_list()
        else:
            print "Invalid sort."
    
    def do_mediatype(self, arg):
        """
        mediatype - Reloads engine with different mediatype; call with no arguments to see supported mediatypes
        
        Usage: mediatype [mediatype]
        """
        if self.parse_args(arg):
            args = self.parse_args(arg)
            if args[0] in self.engine.api_info['supported_mediatypes']:
                self.engine.reload(mediatype=args[0])
            
                # Start with default filter selected
                self.filter_num = self.engine.mediainfo['statuses'][0]
                self._load_list()
                self._update_prompt()
            else:
                print "Invalid mediatype."
        else:
            print "Supported mediatypes: %s" % ', '.join(self.engine.api_info['supported_mediatypes'])
        
    def do_list(self, arg):
        """
        list - Lists all shows available as a nice formatted list.
        """
        # Show the list in memory
        self._make_list(self.sortedlist)
    
    def do_info(self, arg):
        if(arg):
            try:
                show = self.engine.get_show_info_title(arg)
                details = self.engine.get_show_details(show)
            except utils.TrackmaError, e:
                self.display_error(e)
                return

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
            try:
                entries = self.engine.search(arg)
            except utils.TrackmaError, e:
                self.display_error(e)
                return
            
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
                except utils.TrackmaError, e:
                    self.display_error(e)
    
    def do_delete(self, arg):
        """
        delete - Deltes a show from the list
        
        Usage: delete <show id or title>
        
        """
        if self.parse_args(arg):
            args = self.parse_args(arg)
            
            try:
                show = self._get_show(args[0])
                
                do_delete = raw_input("Delete %s? [y/N] " % show['title'])
                if do_delete.lower() == 'y':
                    self.engine.delete_show(show)
            except utils.TrackmaError, e:
                self.display_error(e)
        
    def do_neweps(self, arg):
        showlist = self.engine.filter_list(self.filter_num)
        results = self.engine.get_new_episodes(showlist)
        for show in results:
            print show['title']
        
    def do_play(self, arg):
        if self.parse_args(arg):
            try:
                args = self.parse_args(arg)
                episode = 0
                show = self._get_show(args[0])
                
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
            except utils.TrackmaError, e:
                self.display_error(e)
        else:
            print "Missing arguments."
        
    def do_update(self, arg):
        """
        update - Updates the episode of a show.
        
        Usage: update <show id or name> <episode number>
        """
        if self.parse_args(arg):
            args = self.parse_args(arg)
            try:
                show = self._get_show(args[0])
                self.engine.set_episode(show['id'], args[1])
            except IndexError:
                print "Missing arguments."
            except utils.TrackmaError, e:
                self.display_error(e)
        else:
            print "Missing arguments."
    
    def do_score(self, arg):
        """
        score - Changes the given score of a show.
        
        Usage: update <show id or name> <score>
        """
        if self.parse_args(arg):
            args = self.parse_args(arg)
            try:
                show = self._get_show(args[0])
                self.engine.set_score(show['id'], args[1])
            except IndexError:
                print "Missing arguments."
            except utils.TrackmaError, e:
                self.display_error(e)
        else:
            print "Missing arguments."
    
    def do_status(self, arg):
        """
        status - Changes the status of a show.
        
        Usage: status <show id or name> <status name>
        """
        if self.parse_args(arg):
            args = self.parse_args(arg)
            try:
                _showtitle = args[0]
                _filter = args[1]
            except IndexError:
                print "Missing arguments."
                return
            
            try:
                _filter_num = self._guess_status(_filter)
            except KeyError:
                print "Invalid filter."
                return
            
            try:
                show = self._get_show(_showtitle)
                self.engine.set_status(show['id'], _filter_num)
            except utils.TrackmaError, e:
                self.display_error(e)
        
    def do_send(self, arg):
        try:
            self.engine.list_upload()
        except utils.TrackmaError, e:
            self.display_error(e)
    
    def do_retrieve(self, arg):
        try:
            self.engine.list_download()
        except utils.TrackmaError, e:
            self.display_error(e)
    
    def do_undoall(self, arg):
        """
        undo - Undo all changes
        
        Usage: undoall
        """
        try:
            self.engine.undoall()
        except utils.TrackmaError, e:
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
        except utils.TrackmaError, e:
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
            return shlex.split(arg)
    
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
        elif classname == 'Tracker':
            color_escape = _COLOR_TRACKER
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
        col_index_length = 6
        col_title_length = 5
        col_episodes_length = 9
        col_score_length = 6
        
        # Calculate maximum width for the title column
        # based on the width of the terminal
        (height, width) = utils.get_terminal_size()
        max_title_length = width - col_id_length - col_episodes_length - col_score_length - col_index_length - 5
        
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
        print "| {0:{1}} {2:{3}} {4:{5}} {6:{7}} |".format(
                'Index',    col_index_length,
                'Title',    col_title_length,
                'Progress', col_episodes_length,
                'Score',    col_score_length)
        
        # List shows
        for index, show in enumerate(showlist, 1):
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
            
            print "| {0:^{1}} {2}{3} {4:{5}} {6:^{7}} |".format(
                index, col_index_length,
                colored_title,
                '.' * (col_title_length-len(show['title'])),
                episodes_str, col_episodes_length,
                show['my_score'], col_score_length)
        
        # Print result count
        print '%d results' % len(showlist)
        print

class Trackma_accounts(AccountManager):
    def _get_id(self, index):
        if index < 1:
            raise IndexError

        return self.indexes[index-1]

    def select_account(self, bypass):
        if not bypass and self.get_default():
            return self.get_default()
        if self.get_default():
            self.set_default(None)

        while True:
            print '--- Accounts ---'
            self.list_accounts()
            key = raw_input("Input account number ([r#]emember, [a]dd, [c]ancel, [d]elete, [q]uit): ")

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
                try:
                    num = int(num)
                    account_id = self._get_id(num)
                    confirm = raw_input("Are you sure you want to delete account %d (%s)? [y/N] " % (num, self.get_account(account_id)['username']))
                    if confirm.lower() == 'y':
                        self.delete_account(account_id)
                        print 'Account %d deleted.' % num
                except ValueError:
                    print "Invalid value."
                except IndexError:
                    print "Account doesn't exist."
            elif key.lower() == 'q':
                sys.exit(0)
            else:
                try:
                    if key[0] == 'r':
                        key = key[1:]
                        remember = True
                    else:
                        remember = False

                    num = int(key)
                    account_id = self._get_id(num)
                    if remember:
                        self.set_default(account_id)

                    return self.get_account(account_id)
                except ValueError:
                    print "Invalid value."
                except IndexError:
                    print "Account doesn't exist."
    
    def list_accounts(self):
        accounts = self.get_accounts()
        self.indexes = []

        print "Available accounts:"
        i = 0
        if accounts:
            for k, account in accounts:
                print "%i: %s (%s)" % (i+1, account['username'], account['api'])
                self.indexes.append(k)
                i += 1
        else:
            print "No accounts."


def main():
    main_cmd = Trackma_cmd()
    try:
        main_cmd.start()
        print
        print "Ready. Type 'help' for a list of commands."
        print "Press tab for autocompletion and up/down for command history."
        print
        main_cmd.cmdloop()
    except utils.TrackmaFatal, e:
        print "%s%s: %s%s" % (_COLOR_FATAL, type(e), e.message, _COLOR_RESET)
    

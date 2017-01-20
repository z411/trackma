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
    has_readline = True
except ImportError:
    has_readline = False
    pass # readline is optional

import cmd
import shlex
import textwrap
import re
import getopt
from operator import itemgetter # Used for sorting list

from trackma.engine import Engine
from trackma.accounts import AccountManager
from trackma import messenger
from trackma import utils

_COLOR_RESET = '\033[0m'
_COLOR_ENGINE = '\033[0;32m'
_COLOR_DATA = '\033[0;33m'
_COLOR_API = '\033[0;34m'
_COLOR_TRACKER = '\033[0;35m'
_COLOR_ERROR = '\033[0;31m'
_COLOR_FATAL = '\033[1;31m'

_COLOR_AIRING = '\033[0;34m'

# We must use mark these with special characters for
# readline to calculate line width correctly
_PCOLOR_RESET = '\001\033[0m\002'
_PCOLOR_USER = '\001\033[0;32m\002'
_PCOLOR_API = '\001\033[0;34m\002'
_PCOLOR_MEDIATYPE = '\001\033[0;33m\002'
_PCOLOR_FILTER = '\001\033[0;35m\002'


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
    in_prompt = False
    sortedlist = []
    needed_args = {
        'altname':      (1, 2),
        'filter':       (0, 1),
        'sort':         1,
        'mediatype':    (0, 1),
        'info':         1,
        'search':       1,
        'add':          1,
        'delete':       1,
        'play':         (1, 2),
        'update':       2,
        'score':        2,
        'status':       2,
    }

    def __init__(self, account_num=None, debug=False):
        print('Trackma v'+utils.VERSION+'  Copyright (C) 2012-2017  z411')
        print('This program comes with ABSOLUTELY NO WARRANTY; for details type `about\'')
        print('This is free software, and you are welcome to redistribute it')
        print('under certain conditions; see the COPYING file for details.')
        print()

        self.debug = debug

        self.accountman = Trackma_accounts()
        if account_num:
            try:
                self.account = self.accountman.get_account(int(account_num))
            except KeyError:
                print("Account {} doesn't exist.".format(account_num))
                self.account = self.accountman.select_account(True)
            except ValueError:
                print("Account {} must be numeric.".format(account_num))
                self.account = self.accountman.select_account(True)
        else:
            self.account = self.accountman.select_account(False)

    def _update_prompt(self):
        self.prompt = "{c_u}{u}{c_r} [{c_a}{a}{c_r}] ({c_mt}{mt}{c_r}) {c_s}{s}{c_r} >> ".format(
                u  = self.engine.get_userconfig('username'),
                a  = self.engine.api_info['shortname'],
                mt = self.engine.api_info['mediatype'],
                s  = self.engine.mediainfo['statuses_dict'][self.filter_num].lower().replace(' ', ''),
                c_r  = _PCOLOR_RESET,
                c_u  = _PCOLOR_USER,
                c_a  = _PCOLOR_API,
                c_mt = _PCOLOR_MEDIATYPE,
                c_s  = _COLOR_RESET
        )

    def _load_list(self, *args):
        showlist = self.engine.filter_list(self.filter_num)
        sortedlist = sorted(showlist, key=itemgetter(self.sort))
        self.sortedlist = list(enumerate(sortedlist, 1))

    def _get_show(self, title):
        # Attempt parsing list index
        # otherwise use title
        try:
            index = int(title)-1
            return self.sortedlist[index][1]
        except (ValueError, AttributeError, IndexError):
            return self.engine.get_show_info_title(title)

    def _ask_update(self, show, episode):
        do = input("Should I update {} to episode {}? [y/N] ".format(show['title'], episode))
        if do.lower() == 'y':
            self.engine.set_episode(show['id'], episode)

    def _ask_add(self, show_title, episode):
        do = input("Should I search for the show {}? [y/N] ".format(show_title))
        if do.lower() == 'y':
            self.do_add([show_title])

    def start(self):
        """
        Initializes the engine

        Creates an Engine object and starts it.
        """
        print('Initializing engine...')
        self.engine = Engine(self.account, self.messagehandler)
        self.engine.connect_signal('show_added', self._load_list)
        self.engine.connect_signal('show_deleted', self._load_list)
        self.engine.connect_signal('status_changed', self._load_list)
        self.engine.connect_signal('episode_changed', self._load_list)
        self.engine.connect_signal('prompt_for_update', self._ask_update)
        self.engine.connect_signal('prompt_for_add', self._ask_add)
        self.engine.start()

        # Start with default filter selected
        self.filter_num = self.engine.mediainfo['statuses'][0]
        self._load_list()
        self._update_prompt()

        print()
        print("Ready. Type 'help' for a list of commands.")
        print("Press tab for autocompletion and up/down for command history.")
        self.do_filter(None) # Show available filters
        print()

    def do_about(self, args):
        print("Trackma {}  by z411 (z411@omaera.org)".format(utils.VERSION))
        print("Trackma is an open source client for media tracking websites.")
        print("https://github.com/z411/trackma")
        print()
        print("This program is licensed under the GPLv3 and it comes with ASOLUTELY NO WARRANTY.")
        print("Many contributors have helped to run this project; for more information see the AUTHORS file.")
        print("For more information about the license, see the COPYING file.")
        print()
        print("If you encounter any problems please report them in https://github.com/z411/trackma/issues")
        print()
        print("This is the CLI version of Trackma. To see available commands type `help'.")
        print("For other available interfaces please see the README file.")
        print()

    def do_help(self, arg):
        if arg:
            try:
                doc = getattr(self, 'do_' + arg).__doc__
                if doc:
                    (name, args, expl, usage) = self._parse_doc(arg, doc)

                    print()
                    print(name)
                    for line in expl:
                        print("  {}".format(line))
                    if args:
                        print("\n  Arguments:")
                        for arg in args:
                            if arg[2]:
                                print("    {}: {}".format(arg[0], arg[1]))
                            else:
                                print("    {} (optional): {}".format(arg[0], arg[1]))
                    if usage:
                        print("\n  Usage: " + usage)
                    print()
                    return
            except AttributeError:
                pass

            print("No help available.")
            return
        else:
            CMD_LENGTH = 11
            ARG_LENGTH = 13

            (height, width) = utils.get_terminal_size()
            prev_width = CMD_LENGTH + ARG_LENGTH + 3

            tw = textwrap.TextWrapper()
            tw.width = width - 2
            tw.subsequent_indent = ' ' * prev_width

            print()
            print(" {0:>{1}} {2:{3}} {4}".format(
                    'command', CMD_LENGTH,
                    'args', ARG_LENGTH,
                    'description'))
            print(" " + "-"*(min(prev_width+81, width-3)))

            names = self.get_names()
            names.sort()
            cmds = []
            for name in names:
                if name[:3] == 'do_':
                    doc = getattr(self, name).__doc__
                    if not doc:
                        continue

                    cmd = name[3:]
                    (name, args, expl, usage) = self._parse_doc(cmd, doc)

                    line = " {0:>{1}} {2:{3}} {4}".format(
                           name, CMD_LENGTH,
                           '<' + ','.join( a[0] for a in args) + '>', ARG_LENGTH,
                           expl[0])
                    print(tw.fill(line))

            print()
            print("Use `help <command>` for detailed information.")
            print()


    def do_account(self, args):
        """
        Switch to a different account.
        """

        self.account = self.accountman.select_account(True)
        self.engine.reload(account=self.account)

        # Start with default filter selected
        self.filter_num = self.engine.mediainfo['statuses'][0]
        self._load_list()
        self._update_prompt()

    def do_filter(self, args):
        """
        Changes the filtering of list by status.s

        :optparam status Name of status to filter
        :usage filter [filter type]
        """
        # Query the engine for the available statuses
        # that the user can choose
        if args:
            try:
                self.filter_num = self._guess_status(args[0].lower())
                self._load_list()
                self._update_prompt()
            except KeyError:
                print("Invalid filter.")
        else:
            print("Available statuses: %s" % ', '.join( v.lower().replace(' ', '') for v in self.engine.mediainfo['statuses_dict'].values() ))

    def do_sort(self, args):
        """
        Change of the lists

        :param type Sort type; available types: id, title, my_progress, total, my_score
        :usage sort <sort type>
        """
        sorts = ('id', 'title', 'my_progress', 'total', 'my_score')
        if args[0] in sorts:
            self.sort = args[0]
            self._load_list()
        else:
            print("Invalid sort.")

    def do_mediatype(self, args):
        """
        Reloads engine with different mediatype.
        Call with no arguments to see supported mediatypes.

        :optparam mediatype Mediatype name
        :usage mediatype [mediatype]
        """
        if args:
            if args[0] in self.engine.api_info['supported_mediatypes']:
                self.engine.reload(mediatype=args[0])

                # Start with default filter selected
                self.filter_num = self.engine.mediainfo['statuses'][0]
                self._load_list()
                self._update_prompt()
            else:
                print("Invalid mediatype.")
        else:
            print("Supported mediatypes: %s" % ', '.join(self.engine.api_info['supported_mediatypes']))

    def do_ls(self,args):
        self.do_list(args)

    def do_list(self, args):
        """
        Lists all shows available in the local list.

        :name list|ls
        """
        # Show the list in memory
        self._make_list(self.sortedlist)

    def do_info(self, args):
        """
        Gets detailed information about a local show.

        :param show Show index or title.
        :usage info <show index or title>
        """
        try:
            show = self._get_show(args[0])
            details = self.engine.get_show_details(show)
        except utils.TrackmaError as e:
            self.display_error(e)
            return

        print(details['title'])
        print("-" * len(details['title']))
        print(show['url'])
        print()

        for line in details['extra']:
            print("%s: %s" % line)

    def do_search(self, args):
        """
        Does a regex search on shows in the local lists.

        :param pattern Regex pattern to search for.
        :usage search <pattern>
        """
        sortedlist = list(v for v in self.sortedlist if re.search(args[0], v[1]['title'], re.I))
        self._make_list(sortedlist)

    def do_add(self, args):
        """
        Search for a show in the remote service and add it.

        :param pattern Show criteria to search.
        :usage add <pattern>
        """
        try:
            entries = self.engine.search(args[0])
        except utils.TrackmaError as e:
            self.display_error(e)
            return

        for i, entry in enumerate(entries, start=1):
            print("%d: (%s) %s" % (i, entry['type'], entry['title']))
        do_update = input("Choose show to add (blank to cancel): ")
        if do_update != '':
            try:
                show = entries[int(do_update)-1]
            except ValueError:
                print("Choice must be numeric.")
                return
            except IndexError:
                print("Invalid show.")
                return

            # Tell the engine to add the show
            try:
                self.engine.add_show(show, self.filter_num)
            except utils.TrackmaError as e:
                self.display_error(e)

    def do_delete(self, args):
        """
        Deletes a show from the local list.

        :param show Show index or title.
        :usage delete <show index or title>
        """
        try:
            show = self._get_show(args[0])

            do_delete = input("Delete %s? [y/N] " % show['title'])
            if do_delete.lower() == 'y':
                self.engine.delete_show(show)
        except utils.TrackmaError as e:
            self.display_error(e)

    def do_rescan(self, args):
        """
        Re-scans the local library.
        """
        self.engine.scan_library(rescan=True)

    def do_random(self, args):
        """
        Starts the media player with a random new episode.
        """
        try:
            self.engine.play_random()
        except utils.TrackmaError as e:
            self.display_error(e)

    def do_tracker(self, args):
        """
        Shows information about the tracker, if it's running.

        :usage trackmer
        """
        try:
            info = self.engine.tracker_status()
            print("- Tracker status -")

            if info:
                if info['state'] == utils.TRACKER_NOVIDEO:
                    state = 'No video'
                elif info['state'] == utils.TRACKER_PLAYING:
                    state = 'Playing'
                elif info['state'] == utils.TRACKER_UNRECOGNIZED:
                    state = 'Unrecognized'
                elif info['state'] == utils.TRACKER_NOT_FOUND:
                    state = 'Not found'
                elif info['state'] == utils.TRACKER_IGNORED:
                    state = 'Ignored'
                else:
                    state = 'N/A'

                print("State: {}".format(state))
                print("Filename: {}".format(info['filename'] or 'N/A'))
                print("Timer: {}".format(info['timer'] or 'N/A'))
                if info['show']:
                    (show, ep) = info['show']
                    print("Show: {}\nEpisode: {}".format(show['title'], ep))
                else:
                    print("Show: N/A")
            else:
                print("Not started")
        except utils.TrackmaError as e:
            self.display_error(e)

    def do_play(self, args):
        """
        Starts the media player with the specified episode number (next if not specified).

        :param show Episode index or title.
        :optparam ep Episode number. Assume next if not specified.
        :usage play <show index or title> [episode number]
        """
        try:
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
        except utils.TrackmaError as e:
            self.display_error(e)

    def do_update(self, args):
        """
        Updates the progress of a show to the specified episode.

        :param show Show index or name.
        :param ep Episode number (numeric).
        :usage update <show index or name> <episode number>
        """
        try:
            show = self._get_show(args[0])
            self.engine.set_episode(show['id'], args[1])
        except IndexError:
            print("Missing arguments.")
        except utils.TrackmaError as e:
            self.display_error(e)

    def do_score(self, args):
        """
        Changes the score of a show.

        :param show Show index or name.
        :param score Score to set (numeric/decimal).
        :usage score <show index or name> <score>
        """
        try:
            show = self._get_show(args[0])
            self.engine.set_score(show['id'], args[1])
        except IndexError:
            print("Missing arguments.")
        except utils.TrackmaError as e:
            self.display_error(e)

    def do_status(self, args):
        """
        Changes the status of a show.
        Use the command `filter` without arguments to see the available statuses.

        :param show Show index or name.
        :param status Status name. Use `filter` without args to list them.
        :usage status <show index or name> <status name>
        """
        try:
            _showtitle = args[0]
            _filter = args[1]
        except IndexError:
            print("Missing arguments.")
            return

        try:
            _filter_num = self._guess_status(_filter)
        except KeyError:
            print("Invalid filter.")
            return

        try:
            show = self._get_show(_showtitle)
            self.engine.set_status(show['id'], _filter_num)
        except utils.TrackmaError as e:
            self.display_error(e)

    def do_altname(self, args):
        """
        Changes the alternative name of a show.
        Use the command 'altname' without arguments to clear the alternative
        name.

        :param show Show index or name
        :param alt  The alternative name. Use `altname` without alt to clear it
        :usage altname <show index or name> <alternative name>
        """
        try:
            altnames = self.engine.altnames()
            show = self._get_show(args[0])
            altname = args[1] if len(args) > 1 else ''
            self.engine.altname(show['id'],altname)
        except IndexError:
            print("Missing arguments")
            return
        except utils.TrackmaError as e:
            self.display_error(e)

    def do_send(self, args):
        """
        Sends queued changes to the remote service.
        """
        try:
            self.engine.list_upload()
        except utils.TrackmaError as e:
            self.display_error(e)

    def do_retrieve(self, args):
        """
        Retrieves the remote list overwrites the local one.
        """
        try:
            if self.engine.get_queue():
                answer = input("There are unqueued changes. Overwrite local list? [y/N] ")
                if answer.lower() == 'y':
                    self.engine.list_download()
            else:
                self.engine.list_download()
            self._load_list()
        except utils.TrackmaError as e:
            self.display_error(e)

    def do_undoall(self, args):
        """
        Undo all changes in queue.
        """
        try:
            self.engine.undoall()
        except utils.TrackmaError as e:
            self.display_error(e)

    def do_viewqueue(self, args):
        """
        List the queued changes.
        """
        queue = self.engine.get_queue()
        if len(queue):
            print("Queue:")
            for show in queue:
                print("- %s" % show['title'])
        else:
            print("Queue is empty.")

    def do_exit(self, args):
        self.do_quit(args)

    def do_quit(self, args):
        """
        Quits the program.

        :name quit|exit
        """
        try:
            self.engine.unload()
        except utils.TrackmaError as e:
            self.display_error(e)

        print('Bye!')
        sys.exit(0)

    def do_EOF(self, args):
        print()
        self.do_quit(args)

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
        return [v.lower().replace(' ', '') for v in self.engine.mediainfo['statuses_dict'].values()]

    def parse_args(self, arg):
        if arg:
            return shlex.split(arg)
        else:
            return []

    def emptyline(self):
        return

    def preloop(self):
        """ Override. """
        self.in_prompt = True

    def precmd(self, line):
        """ Override. """
        self.in_prompt = False
        return line

    def postcmd(self, stop, line):
        """ Override. """
        self.in_prompt = True
        return stop

    def onecmd(self, line):
        """ Override. """
        cmd, arg, line = self.parseline(line)
        if not line:
            return self.emptyline()
        if cmd is None:
            return self.default(line)
        self.lastcmd = line
        if line == 'EOF' :
            self.lastcmd = ''
        if cmd == '':
            return self.default(line)
        elif cmd == 'help':
            return self.do_help(arg)
        else:
            return self.execute(cmd, arg, line)

    def execute(self, cmd, arg, line):
        try:
            func = getattr(self, 'do_' + cmd)
        except AttributeError:
            return self.default(line)

        args = self.parse_args(arg)

        try:
            needed = self.needed_args[cmd]
        except KeyError:
            needed = 0

        if isinstance(needed, int):
            needed = (needed, needed)

        if needed[0] <= len(args) <= needed[1]:
            return func(args)
        else:
            print("Incorrent number of arguments. See `help %s`" % cmd)

    def display_error(self, e):
        print("%s%s: %s%s" % (_COLOR_ERROR, type(e).__name__, e, _COLOR_RESET))

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
        elif classname.startswith('Tracker'):
            color_escape = _COLOR_TRACKER
        else:
            color_reset = ''

        if msgtype == messenger.TYPE_INFO:
            out = "%s%s: %s%s" % (color_escape, classname, msg, color_reset)
        elif msgtype == messenger.TYPE_WARN:
            out = "%s%s warning: %s%s" % (color_escape, classname, msg, color_reset)
        elif self.debug and msgtype == messenger.TYPE_DEBUG:
            out = "[D] %s%s: %s%s" % (color_escape, classname, msg, color_reset)
        else:
            return # Unrecognized message, don't show anything

        if has_readline and self.in_prompt:
            # If we're in a prompt and receive a message
            # (often from the tracker) we need to clear the line
            # first, show the message, then re-show the prompt.
            buf = readline.get_line_buffer()
            self.stdout.write('\r' + ' '*(len(self.prompt)+len(buf)) + '\r')

            print(out)

            self.stdout.write(self.prompt + buf)
            self.stdout.flush()
        else:
            print(out)

    def _guess_status(self, string):
        for k, v in self.engine.mediainfo['statuses_dict'].items():
            if string.lower() == v.lower().replace(' ', ''):
                return k
        raise KeyError

    def _parse_doc(self, cmd, doc):
        lines = doc.split('\n')
        name = cmd
        args = []
        expl = []
        usage = None

        for line in lines:
            line = line.strip()
            if line[:6] == ":param":
                args.append( line[7:].split(' ', 1) + [True] )
            elif line[:9] == ":optparam":
                args.append( line[10:].split(' ', 1) + [False] )
            elif line[:6] == ':usage':
                usage = line[7:]
            elif line[:5] == ':name':
                name = line[6:]
            elif line:
                expl.append(line)

        return (name, args, expl, usage)

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
        altnames = self.engine.altnames()

        # Calculate maximum width for the title column
        # based on the width of the terminal
        (height, width) = utils.get_terminal_size()
        max_title_length = width - col_id_length - col_episodes_length - col_score_length - col_index_length - 5

        # Find the widest title so we can adjust the title column
        for index, show in showlist:
            if len(show['title']) > col_title_length:
                if len(show['title']) > max_title_length:
                    # Stop if we exceeded the maximum column width
                    col_title_length = max_title_length
                    break
                else:
                    col_title_length = len(show['title'])

        # Print header
        print("| {0:{1}} {2:{3}} {4:{5}} {6:{7}} |".format(
                'Index',    col_index_length,
                'Title',    max_title_length,
                'Progress', col_episodes_length,
                'Score',    col_score_length))

        # List shows
        for index, show in showlist:
            if self.engine.mediainfo['has_progress']:
                episodes_str = "{0:3} / {1}".format(show['my_progress'], show['total'] or '?')
            else:
                episodes_str = "-"

            #Get title (and alt. title) and if need be, truncate it
            title_str = show['title']
            if altnames.get(show['id']):
                title_str += "[{}]".format(altnames.get(show['id']))
            title_str = title_str[:max_title_length] if len(title_str) > max_title_length else title_str

            # Color title according to status
            if show['status'] == utils.STATUS_AIRING:
                colored_title = _COLOR_AIRING + title_str + _COLOR_RESET
            else:
                colored_title = title_str

            print("| {0:^{1}} {2}{3} {4:{5}} {6:^{7}} |".format(
                index, col_index_length,
                colored_title,
                '.' * (max_title_length-len(title_str)),
                episodes_str, col_episodes_length,
                show['my_score'], col_score_length))

        # Print result count
        print('%d results' % len(showlist))
        print()

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
            print('--- Accounts ---')
            self.list_accounts()
            key = input("Input account number ([r#]emember, [a]dd, [c]ancel, [d]elete, [q]uit): ")

            if key.lower() == 'a':
                available_libs = ', '.join(sorted(utils.available_libs.keys()))

                print("--- Add account ---")
                import getpass
                api = input('Enter API (%s): ' % available_libs)
                try:
                    selected_api = utils.available_libs[api]
                except KeyError:
                    print("Invalid API.")
                    continue

                if selected_api[2] == utils.LOGIN_PASSWD:
                    username = input('Enter username: ')
                    password = getpass.getpass('Enter password (no echo): ')
                elif selected_api[2] == utils.LOGIN_OAUTH:
                    username = input('Enter account name: ')
                    print('OAuth Authentication')
                    print('--------------------')
                    print('This website requires OAuth authentication.')
                    print('Please go to the following URL with your browser,')
                    print('follow the steps and paste the given PIN code here.')
                    print()
                    print(selected_api[3])
                    print()
                    password = input('PIN: ')

                try:
                    self.add_account(username, password, api)
                    print('Done.')
                except utils.AccountError as e:
                    print('Error: %s' % e)
            elif key.lower() == 'd':
                print("--- Delete account ---")
                num = input('Account number to delete: ')
                try:
                    num = int(num)
                    account_id = self._get_id(num)
                    confirm = input("Are you sure you want to delete account %d (%s)? [y/N] " % (num, self.get_account(account_id)['username']))
                    if confirm.lower() == 'y':
                        self.delete_account(account_id)
                        print('Account %d deleted.' % num)
                except ValueError:
                    print("Invalid value.")
                except IndexError:
                    print("Account doesn't exist.")
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
                    print("Invalid value.")
                except IndexError:
                    print("Account doesn't exist.")

    def list_accounts(self):
        accounts = self.get_accounts()
        self.indexes = []

        print("Available accounts:")
        i = 0
        if accounts:
            for k, account in accounts:
                print("%i: %s (%s)" % (i+1, account['username'], account['api']))
                self.indexes.append(k)
                i += 1
        else:
            print("No accounts.")


def usage():
    print("Usage: trackma [options]")
    print()
    print("Options:")
    print("  -a --account\tPre-selects account number")
    print("  -d --debug\tShows debugging information")
    print("  -h --help\tShows this help")
    print()
    print("Example:")
    print("  trackma -a3")
    print("or:")
    print("  trackma --account=3")
    sys.exit()

def main():
    # Process args
    debug = False
    account_num = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], "ha:d", ["help", "account=", "debug"])
    except getopt.GetoptError as err:
        print(err)
        usage()

    for o, a in opts:
        if o in ('-a', '--account'):
            print("Using account {}.".format(a))
            account_num = a
        elif o in ('-d', '--debug'):
            print("Enabling debug messages.")
            debug = True
        elif o in ('-h', '--help'):
            usage()

    # Boot Trackma CLI
    main_cmd = Trackma_cmd(account_num, debug)
    try:
        main_cmd.start()
        main_cmd.cmdloop()
    except utils.TrackmaFatal as e:
        print("%s%s: %s%s" % (_COLOR_FATAL, type(e).__name__, e, _COLOR_RESET))

if __name__ == '__main__':
    main()

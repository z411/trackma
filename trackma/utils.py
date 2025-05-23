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

import copy
import datetime
import difflib
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from enum import Enum, auto

VERSION = '0.9'

DATADIR = os.path.dirname(__file__) + '/data'


class Login(Enum):
    PASSWD = auto()
    OAUTH = auto()
    OAUTH_PKCE = auto()


class BaseEnum(Enum):
    @classmethod
    def find(cls, name):
        try:
            return cls(name)
        except ValueError:
            pass
        try:
            return cls[name.upper().replace(' ', '_')]
        except KeyError:
            pass
        return cls.UNKNOWN

    @classmethod
    def from_int(cls, index):
        try:
            return list(cls.__members__.values())[index]
        except IndexError:
            return cls.UNKNOWN

    def __int__(self):
        try:
            return list(self.__class__.__members__.values()).index(self)
        except IndexError:
            return list(self.__class__.__members__.values()).index(self.__class__.UNKNOWN)

    def __lt__(self, other):
        return int(self) < int(other)

    def __le__(self, other):
        return int(self) <= int(other)

    def __gt__(self, other):
        return int(self) > int(other)

    def __ge__(self, other):
        return int(self) >= int(other)

    def __add__(self, other):
        if isinstance(other, str):
            return str(self) + other
        else:
            return super().__add__(other)

    def __str__(self):
        if isinstance(self.value, (str,)):
            return self.value
        else:
            return self.name.replace('_', ' ')


class Status(BaseEnum):
    UNKNOWN = 'Unknown'
    ONGOING = 'Ongoing'
    FINISHED = 'Finished'
    NOTYET = 'Not yet started'
    CANCELLED = 'Cancelled'
    OTHER = 'Other'

    # aliases
    AIRING = ONGOING
    RELEASING = ONGOING
    PUBLISHING = ONGOING
    CURRENTLY_AIRING = ONGOING
    FINISHED_AIRING = FINISHED
    NOT_YET_AIRED = NOTYET
    NOT_YET_RELEASED = NOTYET
    NOT_YET_PUBLISHED = NOTYET


class Type(BaseEnum):
    UNKNOWN = "Unknown"
    OTHER = "Other"

    # anime
    TV = "TV"
    MOVIE = "Movie"
    OVA = "OVA"
    SPECIAL = "Special"

    # manga
    MANGA = "Manga"
    NOVEL = "Novel"
    ONE_SHOT = "One Shot"

    # aliases
    SP = SPECIAL
    MUSIC = OTHER
    ONA = OVA


class Tracker(Enum):
    NOVIDEO = auto()
    PLAYING = auto()
    UNRECOGNIZED = auto()
    NOT_FOUND = auto()
    IGNORED = auto()


class Season(Enum):
    WINTER = 'Winter'
    SPRING = 'Spring'
    SUMMER = 'Summer'
    FALL = 'Fall'


class SearchMethod(Enum):
    KEYWORD = auto()
    SEASON = auto()

    # aliases
    KW = KEYWORD


HOME = os.path.expanduser("~")
EXTENSIONS = ('.mkv', '.mp4', '.avi', '.ts')

# Put the available APIs here
available_libs = {
    'anilist':   ('Anilist',      DATADIR + '/anilist.jpg',     Login.OAUTH,
                  "https://anilist.co/api/v2/oauth/authorize?client_id=537&response_type=token"),
    'kitsu':     ('Kitsu',        DATADIR + '/kitsu.png',       Login.PASSWD),
    'mal':       ('MyAnimeList',  DATADIR + '/mal.jpg',     Login.OAUTH_PKCE,
                  "https://myanimelist.net/v1/oauth2/authorize?response_type=code&client_id=32c510ab2f47a1048a8dd24de266dc0c&code_challenge=%s"),
    'shikimori': ('Shikimori',    DATADIR + '/shikimori.jpg',   Login.OAUTH,
                  "https://shikimori.one/oauth/authorize?client_id=Jfu9MKkUKPG4fOC95A6uwUVLHy3pwMo3jJB7YLSp7Ro&redirect_uri=urn%3Aietf%3Awg%3Aoauth%3A2.0%3Aoob&response_type=code&scope=user_rates"),
    'vndb':      ('VNDB',         DATADIR + '/vndb.jpg',        Login.PASSWD),
}

available_trackers = [
    ('auto', 'Auto-detect'),
    ('inotify_auto', 'inotify'),
    ('polling', 'Polling (lsof)'),
    ('mpris', 'MPRIS'),
    ('plex', 'Plex Media Server'),
    ('jellyfin', 'Jellyfin'),
    ('kodi', 'Kodi'),
    ('win32', 'Win32'),
]

available_parsers = [
    ('aie', 'AnimeInfoExtractor (Default)'),
    ('anitopy', 'Anitopy (Experimental)'),
]

def oauth_generate_pkce() -> str:
    import secrets

    token = secrets.token_urlsafe(100)
    return token[:128]


def parse_config(filename, default):
    config = copy.copy(default)

    try:
        with open(filename) as configfile:
            loaded_config = json.load(configfile)
            if 'colors' in config and 'colors' in loaded_config:
                # Need to prevent nested dict from being overwritten with an incomplete dict
                config['colors'].update(loaded_config['colors'])
                loaded_config['colors'] = config['colors']
            config.update(loaded_config)
    except IOError:
        # Will just use the default config
        # and create the file for manual editing
        save_config(config, filename)
    except ValueError:
        # There's a syntax error in the config file
        errorString = "Erroneous config %s requires manual fixing or deletion to proceed." % filename
        log_error(errorString)
        raise TrackmaFatal(errorString)

    return config


def save_config(config_dict, filename):
    path = os.path.dirname(filename)
    if not os.path.isdir(path):
        os.mkdir(path)

    with open(filename, 'wb') as configfile:
        configfile.write(json.dumps(config_dict, sort_keys=True,
                                    indent=4, separators=(',', ': ')).encode('utf-8'))


def load_data(filename):
    with open(filename, 'rb') as datafile:
        return pickle.load(datafile, encoding='bytes')


def save_data(data, filename):
    with open(filename, 'wb') as datafile:
        pickle.dump(data, datafile, protocol=2)


def log_error(msg):
    with open(to_data_path('error.log'), 'a') as logfile:
        logfile.write(msg)


def expand_path(path):
    return os.path.expanduser(path)


def expand_paths(paths):
    return (expand_path(path) for path in paths)


def is_media(filename):
    return os.path.splitext(filename)[1] in EXTENSIONS


def get_any(dict_, *keys, default=None):
    """Get the first key present on a dict."""
    for key in keys:
        value = dict_.get(key, Ellipsis)
        if value is not Ellipsis:
            return value
    return default


def regex_find_videos(subdirectory=''):
    if subdirectory:
        path = os.path.expanduser(subdirectory)
    else:
        path = os.getcwd()

    for root, dirs, names in os.walk(path, followlinks=True):
        for filename in names:
            if is_media(filename):
                yield (os.path.join(root, filename), filename)


def regex_rename_files(pattern, source_dir, dest_dir):
    in_path = os.path.expanduser(os.path.join('~', '.trackma', source_dir))
    out_path = os.path.expanduser(os.path.join('~', '.trackma', dest_dir))
    for filename in os.listdir(in_path):
        if re.match(pattern, filename):
            in_file = os.path.join(in_path, filename)
            out_file = os.path.join(out_path, filename)
            os.rename(in_file, out_file)


def list_library(path):
    for root, dirs, names in os.walk(path, followlinks=True):
        for filename in names:
            yield (os.path.join(root, filename), filename)


def make_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def dir_exists(dirname):
    return os.path.isdir(dirname)


def file_exists(filename):
    return os.path.isfile(filename)


def file_older_than(filename, mtime):
    return os.path.getmtime(filename) < time.time() - mtime


def try_files(filenames):
    for filename in filenames:
        if file_exists(filename):
            return filename


def sync_file(fname, sync_url):
    if not sync_url:
        return False

    import urllib.request
    import socket

    try:
        with urllib.request.urlopen(sync_url) as r, open(fname, 'wb') as f:
            shutil.copyfileobj(r, f)
    except (socket.timeout, urllib.error.URLError):
        return False

    return True


def copy_file(src, dest):
    shutil.copy(src, dest)


def to_config_path(*paths):
    if dir_exists(os.path.join(HOME, ".trackma")):
        return os.path.join(HOME, ".trackma", *paths)

    return os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config")), "trackma", *paths)


def to_data_path(*paths):
    if dir_exists(os.path.join(HOME, ".trackma")):
        return os.path.join(HOME, ".trackma", *paths)

    return os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(HOME, ".local", "share")), "trackma", *paths)


def to_cache_path(*paths):
    if dir_exists(os.path.join(HOME, ".trackma")):
        return os.path.join(HOME, ".trackma", "cache", *paths)

    return os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(HOME, ".cache")), "trackma", *paths)


def change_permissions(filename, mode):
    os.chmod(filename, mode)


def estimate_aired_episodes(show):
    """ Estimate how many episodes have passed since airing """

    if show['status'] == Status.FINISHED:
        return show['total']
    elif show['status'] == Status.NOTYET:
        return 0
    # It's airing, so we make an estimate based on available information
    elif show['status'] == Status.AIRING:
        if 'next_ep_number' in show:  # Do we have the upcoming episode number?
            return show['next_ep_number'] - 1
        elif show['start_date']:  # Do we know when it started? Let's just assume 1 episode = 1 week
            days = (datetime.datetime.now() - show['start_date']).days
            if days <= 0:
                return 0

            eps = days // 7 + 1
            if show['total'] and eps > show['total']:
                return show['total']
            return eps
    return 0


def guess_show(show_title, tracker_list):
    """ Take a title and search for it fuzzily in the tracker list """
    (showlist, altnames_map) = tracker_list

    # Return the show immediately if we find an altname for it
    if altnames_map and show_title.lower() in altnames_map:
        showid = altnames_map[show_title.lower()]

        if showid in showlist:
            return showlist[showid]

    # Use difflib to see if the show title is similar to
    # one we have in the list
    highest_ratio = (None, 0)
    matcher = difflib.SequenceMatcher()
    matcher.set_seq1(show_title.lower())

    # Compare to every show in our list to see which one
    # has the most similar name
    for item in showlist.values():
        # Make sure to search through all the aliases
        for title in item['titles']:
            matcher.set_seq2(title.lower())
            ratio = matcher.ratio()
            if ratio > highest_ratio[1]:
                highest_ratio = (item, ratio)

    playing_show = highest_ratio[0]
    if highest_ratio[1] > 0.7:
        return playing_show


def redirect_show(show_tuple, redirections, tracker_list):
    """ Use a redirection dictionary and return the new show ID and episode accordingly """
    if not redirections:
        return show_tuple

    (show, ep) = show_tuple
    if show.get('total') and ep <= show['total']:
        # redirect only for invalid ep
        return show_tuple

    showlist = tracker_list[0]
    if show['id'] in redirections:
        for redirection in redirections[show['id']]:
            (src_eps, dst_id, dst_eps) = redirection

            if (src_eps[1] == -1 and ep >= src_eps[0]) or (ep in range(src_eps[0], src_eps[1] + 1)):
                new_show_id = dst_id
                new_ep = ep + (dst_eps[0] - src_eps[0])

                if new_show_id in showlist:
                    return (showlist[new_show_id], new_ep)

    return show_tuple


def open_folder(path):
    if sys.platform == 'darwin':
        spawn_process(["open", path])
    elif sys.platform == 'win32':
        spawn_process(["explorer", path])
    else:
        spawn_process(["xdg-open", path])


_spawned_processes = []


def _poll_spawned_processes():
    """Periodically poll and prune process handles to prevent zombies."""
    while True:
        time.sleep(5)
        _spawned_processes[:] = [child for child in _spawned_processes if child.poll() is None]


_process_collector_thread = None


def spawn_process(arg_list):
    """
    Helper generic function to spawn a subprocess.

    The handles are collected and periodically polled
    to prevent zombie processes on *NIX.
    """
    global _process_collector_thread

    if not arg_list:
        return

    proc = subprocess.Popen(arg_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _spawned_processes.append(proc)

    if not _process_collector_thread:
        _process_collector_thread = threading.Thread(target=_poll_spawned_processes, daemon=True)
        _process_collector_thread.start()


def get_terminal_size(fd=1):
    """
    Returns height and width of current terminal. First tries to get
    size via termios.TIOCGWINSZ, then from environment. Defaults to 25
    lines x 80 columns if both methods fail.

    :param fd: file descriptor (default: 1=stdout)
    """
    try:
        import fcntl
        import termios
        import struct
        hw = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
    except Exception:
        try:
            width = int(os.environ.get('COLUMNS', 80))
            height = int(os.environ.get('LINES', 25))
            hw = (height, width)
        except Exception:
            hw = (25, 80)

    return hw


def show():
    return {
        'id':           0,
        'title':        '',
        'url':          '',
        'aliases':      [],
        'my_id':        None,
        'my_progress':  0,
        'my_status':    1,
        'my_score':     0,
        'my_start_date':  None,
        'my_finish_date': None,
        'type':         0,
        'status':       0,
        'total':        0,
        'start_date':   None,
        'end_date':     None,
        'image':        '',
        'image_thumb':  '',
        'queued':       False,
    }


class TrackmaError(Exception):
    pass


class EngineError(TrackmaError):
    pass


class DataError(TrackmaError):
    pass


class APIError(TrackmaError):
    pass


class AccountError(TrackmaError):
    pass


class TrackmaFatal(Exception):
    pass


class EngineFatal(TrackmaFatal):
    pass


class DataFatal(TrackmaFatal):
    pass


class APIFatal(TrackmaFatal):
    pass


# Configuration defaults
config_defaults = {
    'player': 'mpv',
    'searchdir': ['~/Videos'],
    'tracker_enabled': True,
    'tracker_update_wait_s': 120,
    'tracker_update_close': False,
    'tracker_update_prompt': False,
    'tracker_not_found_prompt': False,
    'tracker_interval': 10,
    'tracker_process': 'mplayer|mplayer2|mpv',
    'tracker_ignore_not_next': True,
    'autoretrieve': 'days',
    'autoretrieve_days': 3,
    'autosend': 'minutes',
    'autosend_minutes': 60,
    'autosend_size': 5,
    'autosend_at_exit': True,
    'library_autoscan': True,
    'library_full_path': False,
    'scan_whole_list': False,
    'debug_disable_lock': True,
    'auto_status_change': True,
    'auto_status_change_if_scored': True,
    'auto_date_change': True,
    'tracker_type': "auto",
    'plex_host': "localhost",
    'plex_port': "32400",
    'plex_obey_update_wait_s': False,
    'plex_user': '',
    'plex_passwd': '',
    'plex_uuid': str(uuid.uuid1()),
    'plex_ssl': False,
    'jellyfin_host': "localhost",
    'jellyfin_port': "8096",
    'jellyfin_api_key': '',
    'jellyfin_user': '',
    'kodi_host': "localhost",
    'kodi_port': "8080",
    'kodi_obey_update_wait_s': False,
    'kodi_user': '',
    'kodi_passwd': '',
    'redirections_url': 'https://raw.githubusercontent.com/erengy/anime-relations/master/anime-relations.txt',
    'redirections_time': 1,
    'use_hooks': True,
    'title_parser': 'aie',
}

userconfig_defaults = {
    'mediatype': '',
    'userid': 0,
    'username': '',
}

curses_defaults = {
    'show_help': True,
    'keymap': {
        'help': '?',
        'prev_filter': 'left',
        'next_filter': 'right',
        'sort': 'f3',
        'sort_order': 'r',
        'update': 'u',
        'play': 'p',
        'openfolder': 'o',
        'play_random': '&',
        'status': 'f6',
        'score': 'z',
        'send': 's',
        'retrieve': 'R',
        'addsearch': 'a',
        'reload': 'c',
        'switch_account': 'f9',
        'delete': 'd',
        'quit': 'q',
        'altname': 'A',
        'search': '/',
        'neweps': 'N',
        'details': 'enter',
        'details_exit': 'esc',
        'open_web': 'O',
        'left': 'h',
        'up': 'k',
        'down': 'j',
        'right': 'l',
        'page_up': 'K',
        'page_down': 'J',
    },
    'palette': {
        'body':             ('', ''),
        'focus':            ('standout', ''),
        'head':             ('light red', 'black'),
        'header':           ('bold', ''),
        'status':           ('white', 'dark blue'),
        'error':            ('light red', 'dark blue'),
        'window':           ('white', 'dark blue'),
        'button':           ('black', 'light gray'),
        'button hilight':   ('white', 'dark red'),
        'item_airing':      ('dark blue', ''),
        'item_notaired':    ('yellow', ''),
        'item_neweps':      ('white', 'brown'),
        'item_updated':     ('white', 'dark green'),
        'item_playing':     ('white', 'dark blue'),
        'info_title':       ('light red', ''),
        'info_section':     ('dark blue', ''),
    }
}

gtk_defaults = {
    'show_tray': True,
    'close_to_tray': True,
    'start_in_tray': False,
    'tray_api_icon': False,
    'remember_geometry': False,
    'last_width': 740,
    'last_height': 480,
    'visible_columns': ['Title', 'Progress', 'Score', 'Percent'],
    'episodebar_style': 1,
    'colors': {
        'is_airing': '#0099CC',
        'is_playing': '#6C2DC7',
        'is_queued': '#54C571',
        'new_episode': '#FBB917',
        'not_aired': '#999900',
        'progress_bg': '#E5E5E5',
        'progress_fg': '#99B3CC',
        'progress_sub_bg': '#B3B3B3',
        'progress_sub_fg': '#668099',
        'progress_complete': '#99CCB3',
    },
}

qt_defaults = {
    'show_tray': True,
    'close_to_tray': True,
    'notifications': True,
    'start_in_tray': False,
    'tray_api_icon': False,
    'remember_geometry': False,
    'remember_columns': False,
    'last_x': 0,
    'last_y': 0,
    'last_width': 740,
    'last_height': 480,
    'visible_columns': ['Title', 'Progress', 'Score', 'Percent'],
    'inline_edit': True,
    'columns_state': None,
    'columns_per_api': False,
    'episodebar_style': 1,
    'episodebar_text': False,
    'filter_bar_position': 2,
    'filter_global': False,
    'colors': {
        'is_airing': '#D2FAFA',
        'is_playing': '#9696FA',
        'is_queued': '#D2FAD2',
        'new_episode': '#FAFA82',
        'not_aired': '#FAFAD2',
        'progress_bg': '#F5F5F5',
        'progress_fg': '#74C0FA',
        'progress_sub_bg': '#D2D2D2',
        'progress_sub_fg': '#5187B1',
        'progress_complete': '#00D200',
    },
    'sort_index': 1,
    'sort_order': 0,
}

qt_per_api_defaults = {
    'visible_columns': ['Title', 'Progress', 'Score', 'Percent'],
    'columns_state': None,
}

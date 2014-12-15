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

import os, re, shutil, copy
import subprocess
import json

VERSION = '0.3'

datadir = os.path.dirname(__file__)

# Put the available APIs here
available_libs = {
    'hb':       ('Hummingbird',  datadir + '/data/hb.jpg'),
    'mal':      ('MyAnimeList',  datadir + '/data/mal.jpg'),
    'melative': ('Melative',     datadir + '/data/melative.jpg'),
    'vndb':     ('VNDB',         datadir + '/data/vndb.jpg'),
}


def parse_config(filename, default):
    config = copy.copy(default)

    try:
        with open(filename) as configfile:
            config.update(json.load(configfile))
    except IOError:
        # Will just use the default config
        # and create the file for manual editing
        save_config(config, filename)
    
    return config

def save_config(config_dict, filename):
    path = os.path.dirname(filename)
    if not os.path.isdir(path):
        os.mkdir(path)

    with open(filename, 'wb') as configfile:
        json.dump(config_dict, configfile, sort_keys=True,
                  indent=4, separators=(',', ': '))

def log_error(msg):
    with open(get_root_filename('error.log'), 'a') as logfile:
        logfile.write(msg.encode('utf-8'))
    
def regex_find_videos(extensions, subdirectory=''):
    __re = re.compile(extensions, re.I)
    
    if subdirectory:
        path = os.path.expanduser(subdirectory)
    else:
        path = os.getcwd()
    for root, dirs, names in os.walk(path, followlinks=True):
        for filename in names:
            # Filename manipulation
            
            extension = os.path.splitext(filename)[1][1:]
            match = __re.match(extension)
            if match:
                yield ( os.path.join(root, filename), filename )

def make_dir(directory):
    path = os.path.expanduser(os.path.join('~', '.trackma', directory))
    if not os.path.isdir(path):
        os.mkdir(path)
    
def dir_exists(dirname):
    return os.path.isdir(dirname)

def file_exists(filename):
    return os.path.isfile(filename)

def copy_file(src, dest):
    shutil.copy(src, dest)

def get_filename(subdir, filename):
    return os.path.expanduser(os.path.join('~', '.trackma', subdir, filename))
    
def get_root_filename(filename):
    return os.path.expanduser(os.path.join('~', '.trackma', filename))
    
def get_terminal_size(fd=1):
    """
    Returns height and width of current terminal. First tries to get
    size via termios.TIOCGWINSZ, then from environment. Defaults to 25
    lines x 80 columns if both methods fail.
 
    :param fd: file descriptor (default: 1=stdout)
    """
    try:
        import fcntl, termios, struct
        hw = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
    except:
        try:
            hw = (os.environ['LINES'], os.environ['COLUMNS'])
        except:  
            hw = (25, 80)
 
    return hw

def show():
    return {
        'id':           0,
        'title':        '',
        'url':          '',
        'aliases':      [],
        'my_progress':  0,
        'my_status':    1,
        'my_score':     0,
        'my_start_date':  None,
        'my_finish_date': None,
        'type':         0,
        'status':       0,
        'total':        0,
        'start_date':   None,
        'end_date':  None,
        'image':        '',
        'queued':       False,
        'neweps':       False,
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
    'searchdir': '/home/user/Videos',
    'tracker_enabled': True,
    'tracker_update_wait': 5,
    'tracker_interval': 60,
    'tracker_process': 'mplayer|mplayer2|mpv',
    'autoretrieve': 'days',
    'autoretrieve_days': 3,
    'autosend': 'hours',
    'autosend_hours': 5,
    'autosend_size': 5,
    'autosend_at_exit': True,
    'debug_disable_lock': True,
    'auto_status_change': True,
    'auto_status_change_if_scored': True,
    'auto_date_change': True,
}
userconfig_defaults = {
    'mediatype': '',
}
keymap_defaults = {
    'help': 'f1',
    'prev_filter': 'left',
    'next_filter': 'right',
    'sort': 'f3',
    'update': 'f4',
    'play': 'f5',
    'status': 'f6',
    'score': 'f7',
    'send': 's',
    'retrieve': 'R',
    'addsearch': 'a',
    'reload': 'c',
    'switch_account': 'f9',
    'delete': 'd',
    'quit': 'f12',
    'altname': 'A',
    'search': '/',
    'neweps': 'N',
    'details': 'enter',
    'details_exit': 'esc',
    'open_web': 'O',
}

gtk_defaults = {
    'show_tray': True,
    'close_to_tray': True,
    'start_in_tray': False,
}

qt_defaults = {
    'show_tray': True,
    'close_to_tray': True,
    'notifications': True,
    'start_in_tray': False,
}

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

import os, re, shutil
import json

datadir = os.path.dirname(__file__)

# Put the available APIs here
available_libs = {
    'mal':      ('MyAnimeList',  datadir + '/data/mal.jpg'),
    'malu':     ('MAL Unoffic.', datadir + '/data/malu.jpg'),
    'melative': ('Melative',     datadir + '/data/melative.jpg'),
    'vndb':     ('VNDB',         datadir + '/data/vndb.jpg'),
}

def parse_config(filename, default):
    config = default
    try:
        with open(filename) as configfile:
            config.update(json.load(configfile))
    except IOError:
        # Will just use the default config
        pass
    
    return config

def save_config(config_dict, filename):
    with open(filename, 'wb') as configfile:
        json.dump(config_dict, configfile, sort_keys=True,
                  indent=4, separators=(',', ': '))

def regex_find_file(regex, subdirectory=''):
    __re = re.compile(regex, re.I)
    
    if subdirectory:
        path = subdirectory
    else:
        path = os.getcwd()
    for root, dirs, names in os.walk(path):
        for filename in names:
            if __re.search(filename):
                return os.path.join(root, filename)
    return False

def make_dir(directory):
    path = os.path.expanduser(os.path.join('~', '.wmal', directory))
    if not os.path.isdir(path):
        os.mkdir(path)
    
def file_exists(filename):
    return os.path.isfile(filename)

def copy_file(src, dest):
    shutil.copy(src, dest)

def get_filename(subdir, filename):
    return os.path.expanduser(os.path.join('~', '.wmal', subdir, filename))
    
def get_root_filename(filename):
    return os.path.expanduser(os.path.join('~', '.wmal', filename))
    
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
        'my_progress':  0,
        'my_status':    1,
        'my_score':     0,
        'type':         0,
        'status':       0,
        'total':        0,
        'image':        '',
    }

class wmalError(Exception):
    pass

class EngineError(wmalError):
    pass

class DataError(wmalError):
    pass

class APIError(wmalError):
    pass

class wmalFatal(Exception):
    pass

class EngineFatal(wmalFatal):
    pass

class DataFatal(wmalFatal):
    pass

class APIFatal(wmalFatal):
    pass
    
# Configuration defaults
config_defaults = {
    'player': 'mpv',
    'searchdir': '/home/user/Videos',
    'tracker_enabled': True,
    'tracker_update_wait': 5,
    'tracker_interval': 120,
    'tracker_process': 'mplayer|mplayer2|mpv',
    'autoretrieve': 'days',
    'autoretrieve_days': 3,
    'autosend': 'hours',
    'autosend_hours': 5,
    'autosend_size': 5,
    'autosend_at_exit': True,
    'debug_disable_lock': True,
    'auto_status_change': True,
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
    'search': '/',
}

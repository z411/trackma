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
from ConfigParser import SafeConfigParser

def parse_config(filename):
    options = dict()
    config = SafeConfigParser()
    config.read(filename)
    for section in config.sections():
        options[section] = dict()
        for (k, v) in config.items(section):
            options[section][k] = v
    
    return options

def save_config(config_dict, filename):
    config = SafeConfigParser()
    for section_name, section in config_dict.iteritems():
        config.add_section(section_name)
        for (k, v) in section.iteritems():
            config.set(section_name, k, v)

    with open(filename, 'wb') as configfile:
        config.write(configfile)

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

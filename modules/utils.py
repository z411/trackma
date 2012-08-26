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

import os, re

COMMENT_CHAR = '#'
OPTION_CHAR =  '='

def parse_config(filename):
    options = {}
    f = open(filename)
    for line in f:
        # Remove comments
        if COMMENT_CHAR in line:
            line, comment = line.split(COMMENT_CHAR, 1)
        # Store options
        if OPTION_CHAR in line:
            option, value = line.split(OPTION_CHAR, 1)
            option = option.strip()
            value = value.strip()
            options[option] = value
    f.close()
    return options

def regex_find_file(regex, subdirectory=''):
    __re = re.compile(regex)
    
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

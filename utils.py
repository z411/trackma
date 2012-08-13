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

def get_filename(filename):
    return os.path.expanduser(os.path.join('~', '.wmal-python', filename))
    
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

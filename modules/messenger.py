TYPE_DEBUG = 1
TYPE_INFO = 2
#TYPE_ERROR = 3
#TYPE_FATAL = 4
TYPE_WARN = 5

class Messenger(object):
    _handler = None
    
    def __init__(self, handler):
        self._handler = handler
    
    def set_handler(self, handler):
        self._handler = handler
    
    def debug(self, classname, msg):
        if self._handler:
            self._handler(classname, TYPE_DEBUG, msg)
        
    def info(self, classname, msg):
        if self._handler:
            self._handler(classname, TYPE_INFO, msg)
    
    def warn(self, classname, msg):
        if self._handler:
            self._handler(classname, TYPE_WARN, msg)

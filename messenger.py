TYPE_DEBUG = 1
TYPE_INFO = 2
TYPE_ERROR = 3
TYPE_FATAL = 4

class Messenger:
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
    
    def error(self, classname, msg):
        if self._handler:
            self._handler(classname, TYPE_ERROR, msg)
    
    def fatal(self, classname, msg):
        if self._handler:
            self._handler(classname, TYPE_FATAL, msg)

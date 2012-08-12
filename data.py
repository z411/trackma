import messenger
import libmal
import cPickle
import os.path

class Data:
    """
    Data Handler Class
    
    Class for keeping data in memory, handling list cache and
    update queues. Gets commands from the engine and sends
    commands to the API if necessary.
    """
    name = 'Data'
    
    msg = None
    api = None
    showlist = None
    queue = list()
    config = dict()
    
    def __init__(self, messenger, config):
        self.msg = messenger
        self.config = config
    
    def start(self):
        """Initialize the data handler and its children"""
        self.msg.info(self.name, "Version v0.1")
        
        # Init API
        self.api = libmal.libmal(self.msg, self.config['username'], self.config['password'])
        
        # If cache exists, load from it
        # otherwise query the API for a remote list
        if self._cache_exists():
            self._load_cache()
        else:
            if not self.api.check_credentials():
                self.msg.fatal(self.name, "Can't log-in.")
                return False
            
            self._download_data()
            self._save_cache()
        
        if not self.showlist:
            self.msg.fatal(self.name, "Can't fetch list.")
            return False
        
        if self._queue_exists():
            self._load_queue()
            
        return True
    
    def unload(self):
        self.msg.debug(self.name, "Unloading...")
        self.process_queue()
    
    def get(self):
        """Get list from memory"""
        return self.showlist
    
    def queue_update(self, show):
        """Insert update into queue"""
        self.queue.insert(0, show)
        self.msg.info(self.name, 'Queued update for ' + show['title'])
        self._save_queue()
    
    def process_queue(self):
        """Process stuff in queue"""
        if len(self.queue):
            self.msg.info(self.name, 'Processing queue...')
            for i in xrange(len(self.queue)):
                show = self.queue.pop(0)
                print 'update' + repr(show)
            
            self._save_queue()
        else:
            self.msg.debug(self.name, 'No items in queue.')
        
    def _load_cache(self):
        self.msg.debug(self.name, "Reading cache...")
        self.showlist = cPickle.load( open( "cache.db", "rb" ) )
    
    def _save_cache(self):
        self.msg.debug(self.name, "Saving cache...")
        cPickle.dump(self.showlist, open( "cache.db", "wb" ) )
    
    def _load_queue(self):
        self.msg.debug(self.name, "Reading queue...")
        self.queue = cPickle.load( open( "queue.db", "rb" ) )
    
    def _save_queue(self):
        self.msg.debug(self.name, "Saving queue...")
        cPickle.dump(self.queue, open( "queue.db", "wb" ) )
        
    def _download_data(self):
        self.showlist = self.api.fetch_list()
        
    def _cache_exists(self):
        return os.path.isfile('cache.db')
    
    def _queue_exists(self):
        return os.path.isfile('queue.db')

STATUSES = {
    1: 'Watching',
    2: 'Completed',
    3: 'On Hold',
    4: 'Dropped',
    6: 'Plan to Watch' }

STATUSES_KEYS = {
    'watching': 1,
    'completed': 2,
    'onhold': 3,
    'dropped': 4,
    'plantowatch': 6 }

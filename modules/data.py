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

import cPickle
import os.path

import messenger
import utils
import sys

class Data(object):
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
        self.msg.info(self.name, "Version v0.1")
        
        # Import the API
        # TODO : Dangerous stuff, we should do an alphanumeric test or something.
        libbase = self.config['main']['api']
        mediatype = self.config[libbase]['mediatype']
        
        libname = "lib{0}".format(libbase)
        try:
            modulename = "modules.{0}".format(libname)
            self.msg.info(self.name, "Using %s (%s)" % (libname, mediatype))
            __import__(modulename)
            apimodule = sys.modules[modulename]
        except ImportError, e:
            raise utils.DataFatal("Couldn't import API module: %s" % e.message)
        
        # Check if there's a username
        if self.config[libbase]['username'] == 'CHANGEME':
            raise utils.EngineFatal("Please set your username and password in the config file.")
        
        # Get files
        utils.make_dir(libbase)
        self.queue_file = utils.get_filename(libbase, '%s.queue' % mediatype)
        self.cache_file = utils.get_filename(libbase, '%s.db' % mediatype)
        self.lock_file = utils.get_filename(libbase, 'lock')
        
        # Instance API
        # TODO : Dangerous stuff, we should do an alphanumeric test or something.
        libclass = getattr(apimodule, libname)
        self.api = libclass(self.msg, self.config[libbase])
    
    def set_message_handler(self, message_handler):
        self.msg = message_handler
        self.api.set_message_handler(self.msg)
        
    def start(self):
        """Initialize the data handler and its children"""
        # Lock the database
        self.msg.debug(self.name, "Locking database...")
        self._lock()
        
        # If cache exists, load from it
        # otherwise query the API for a remote list
        if self._cache_exists():
            self._load_cache()
        else:
            try:
                #self.api.check_credentials()
                self.download_data()
            except utils.APIError, e:
                raise utils.APIFatal(e.message)
            
            self._save_cache()
        
        if self._queue_exists():
            self._load_queue()
            
        return (self.api.api_info, self.api.media_info())
    
    def unload(self):
        self.msg.debug(self.name, "Unloading...")
        self.process_queue()
        
        self.msg.debug(self.name, "Unlocking database...")
        self._unlock()
    
    def get(self):
        """Get list from memory"""
        return self.showlist
    
    def queue_update(self, show, key, value):
        """Do update and insert into queue"""
        if key not in show.keys():
            raise utils.DataError('Invalid key for queue update.')
        
        # Do update on memory
        show[key] = value
        
        # Check if the show is already in queue
        exists = False
        for q in self.queue:
            if q['id'] == show['id']:
                # Add the changed value to the already existing queue item
                q[key] = value
                exists = True
                break
            
        if not exists:
            # Create queue item and append it
            item = {'id': show['id'], 'title': show['title']}
            item[key] = value
            self.queue.append(item)
        
        self.msg.info(self.name, "Queued update for %s" % show['title'])
        self._save_queue()
        self._save_cache()
    
    def queue_clear(self):
        if len(self.queue) == 0:
            raise utils.DataError('Queue is already empty.')
        
        self.queue = []
        self._save_queue()
        self.msg.info(self.name, "Cleared queue.")
        
    def process_queue(self):
        """Process stuff in queue"""
        if len(self.queue):
            self.msg.info(self.name, 'Processing queue...')
            
            # Check log-in TODO
            #try:
            #    self.api.check_credentials()
            #except utils.APIError, e:
            #    raise utils.DataError("Can't process queue, will leave unsynced. Reason: %s" % e.message)
            
            # Run through queue
            for i in xrange(len(self.queue)):
                show = self.queue.pop(0)
                try:
                    self.api.update_show(show)
                except utils.APIError, e:
                    self.msg.warn(self.name, "Can't process %s, will leave unsynced." % show['title'])
                    self.msg.debug(self.name, "Info: %s" % e.message)
                    self.queue.append(show)
            
            self._save_queue()
        else:
            self.msg.debug(self.name, 'No items in queue.')
        
    def _load_cache(self):
        self.msg.debug(self.name, "Reading cache...")
        self.showlist = cPickle.load( open( self.cache_file , "rb" ) )
    
    def _save_cache(self):
        self.msg.debug(self.name, "Saving cache...")
        cPickle.dump(self.showlist, open( self.cache_file , "wb" ) )
    
    def _load_queue(self):
        self.msg.debug(self.name, "Reading queue...")
        self.queue = cPickle.load( open( self.queue_file , "rb" ) )
    
    def _save_queue(self):
        self.msg.debug(self.name, "Saving queue...")
        cPickle.dump(self.queue, open( self.queue_file , "wb" ) )
        
    def download_data(self):
        self.showlist = self.api.fetch_list()
        
    def _cache_exists(self):
        return os.path.isfile(self.cache_file)
    
    def _queue_exists(self):
        return os.path.isfile(self.queue_file)
    
    def _lock(self):
        if os.path.isfile(self.lock_file):
            raise utils.DataFatal("Database is locked by another process. "
                            "If you\'re sure there's no other process is using it, "
                            "remove the file ~/.wmal/lock")
        
        f = open(self.lock_file, 'w')
        f.close()
    
    def _unlock(self):
        os.unlink(self.lock_file)
    
    def get_api_info(self):
        return (self.api.api_info, self.api.media_info())

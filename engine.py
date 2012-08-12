import messenger
import data
import utils
import re

class Engine:
    """
    Engine class
    
    Controller that handles commands from the visual client
    and then queries the Data Handler for the necessary data.
    """
    data_handler = None
    config = dict()
    msg = None
    
    name = 'Engine'
    
    def __init__(self, message_handler=None):
        self.msg = messenger.Messenger(message_handler)
        self.msg.info(self.name, 'Version v0.1')
        
    def start(self):
        """Starts the engine."""
        self.msg.info(self.name, 'Reading config file...')
        try:
            self.config = utils.parse_config('wmal.conf')
        except IOError:
            self.msg.fatal(self.name, "Couldn't open config file.")
            return False
        
        # Check if there's a username
        if self.config['username'] == 'CHANGEME':
            self.msg.fatal(self.name, "Please set your username and password in the config file.")
            return False
        
        # Create data handler and start it
        self.data_handler = data.Data(self.msg, self.config)
        if not self.data_handler.start():
            self.msg.fatal(self.name, "Couldn't open data handler.")
            return False
        
        return True
    
    def unload(self):
        self.msg.debug(self.name, "Unloading...")
        self.data_handler.unload()
        
    def get_list(self):
        """Requests the full show list from the data handler."""
        return self.data_handler.get().values()
    
    def get_show_info(self, pattern):
        showdict = self.data_handler.get()
        
        if pattern.isdigit():
            # ID lookup
            try:
                return showdict[int(pattern)]
            except KeyError:
                self.msg.error(self.name, "Show not found.")
                return False
        else:
            # Title lookup, slower
            for k, show in showdict.iteritems():
                if show['title'] == pattern:
                    return show
            self.msg.error(self.name, "Show not found.")
            return False
    
    def regex_list(self, pattern):
        showlist = self.data_handler.get()
        return list(v for k, v in showlist.iteritems() if re.match(pattern, v['title'], re.I))
        
    def regex_list_titles(self, pattern):
        showlist = self.data_handler.get()
        newlist = list()
        for k, v in showlist.iteritems():
            if re.match(pattern, v['title'], re.I):
                if ' ' in v['title']:
                    newlist.append('"' + v['title'] + '"')
                else:
                    newlist.append(v['title'])
                    
        return newlist
    
    def set_episode(self, show_pattern, newep):
        # Check for the episode number
        try:
            newep = int(newep)
        except ValueError:
            self.msg.error(self.name, 'Episode must be numeric.')
            return False
        
        # Get the show and update it
        show = self.get_show_info(show_pattern)
        if show:
            # More checks
            if show['episodes'] and newep > show['episodes']:
                self.msg.error(self.name, 'Episode out of limits.')
                return False
            if show['my_episodes'] == newep:
                self.msg.error(self.name, 'Show already at episode ' + str(newep))
                return False
            
            # Change episode
            show['my_episodes'] = newep;
            self.msg.info(self.name, 'Updating show ' + show['title'] + ' to episode ' + str(newep) + '...')
            self.data_handler.queue_update(show)
            
            return True
        else:
            self.msg.error(self.name, 'Show not found.')
            return False
        
    def filter_list(self, filter_num):
        showlist = self.data_handler.get()
        if filter_num:
            return list(v for k, v in showlist.iteritems() if v['my_status'] == filter_num)
        else:
            return showlist.values()
            
    def statuses(self):
        return data.STATUSES
    
    def statuses_keys(self):
        return data.STATUSES_KEYS

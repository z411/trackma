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

import re
import subprocess

import messenger
import data
import utils

class Engine:
    """
    Main engine class
    
    Controller that handles commands from the visual client
    and then queries the Data Handler for the necessary data.
    It doesn't care about how the data is fetched, it just
    handles the commands coming from the visual client.

    message_handler: Reference to a function for the engine
      to send to. Optional.
    """
    data_handler = None
    config = dict()
    msg = None
    loaded = False
    
    name = 'Engine'
    
    def __init__(self, message_handler=None):
        """Reads configuration file and asks the data handler for the API info."""
        self.msg = messenger.Messenger(message_handler)
        self.msg.info(self.name, 'Version v0.1')
        
        # Create home directory
        utils.make_dir('')
        configfile = utils.get_root_filename('wmal.conf')
        
        # Create config file if it doesn't exist
        if not utils.file_exists(configfile):
            utils.copy_file('wmal.conf.example', configfile)
            
        self.msg.info(self.name, 'Reading config file...')
        try:
            self.config = utils.parse_config(configfile)
        except IOError:
            raise utils.EngineFatal("Couldn't open config file.")
        
        self._init_data_handler()
    
    def _init_data_handler(self):
        # Create data handler
        self.data_handler = data.Data(self.msg, self.config)
        
        # Record the API details
        (self.api_info, self.mediainfo) = self.data_handler.get_api_info()
    
    def set_message_handler(self, message_handler):
        """Changes the data handler even after the class initialization."""
        self.msg = messenger.Messenger(message_handler)
        self.data_handler.set_message_handler(self.msg)
        
    def start(self):
        """
        Starts the engine
        
        This function should be called before doing anything with the engine,
        as it initializes the data handler.
        """
        if self.loaded:
            raise utils.wmalError("Already loaded.")
        
        # Start the data handler
        try:
            (self.api_info, self.mediainfo) = self.data_handler.start()
        except utils.DataError, e:
            raise utils.DataFatal(e.message)
        except utils.APIError, e:
            raise utils.APIFatal(e.message)
        
        self.loaded = True
        return True
    
    def unload(self):
        """
        Closes the data handler and closes the engine

        This should be called when closing the client application, or when you're
        sure you're not going to use the engine anymore. This does all the necessary
        procedures to close the data handler and then itself.
        
        """
        #if not self.loaded:
        #    raise utils.wmalError("Engine is not loaded.")
        
        self.msg.debug(self.name, "Unloading...")
        self.data_handler.unload()
        self.loaded = False
    
    def reload(self, api=None, mediatype=None):
        """Changes the API and/or mediatype and reloads itself."""
        if not self.loaded:
            raise utils.wmalError("Engine is not loaded.")
        
        to_api = self.config['main']['api']
        
        if api:
            if api in self.config.keys():
                to_api = api
            else:
                raise utils.EngineError('Unsupported API: %s' % api)
        if mediatype:
            to_mediatype = mediatype
        else:
            to_mediatype = self.config[to_api]['mediatype']
            
        self.unload()
        self.config['main']['api'] = to_api
        self.config[to_api]['mediatype'] = to_mediatype
        self._init_data_handler()
        self.start()
        
    def get_list(self):
        """Requests the full show list from the data handler."""
        return self.data_handler.get().values()
    
    def get_show_info(self, pattern):
        """
        Returns the complete info for a show
        
        It asks the data handler for the full details of a show, and returns it as
        a show dictionary.

        pattern: The show ID as a number or the full show title.
        
        """
        showdict = self.data_handler.get()
        
        try:
            # ID lookup
            showid = int(pattern)
            
            try:
                return showdict[showid]
            except KeyError:
                raise utils.EngineError("Show not found.")
            
        except ValueError:
            # Do title lookup, slower
            for k, show in showdict.iteritems():
                if show['title'] == pattern:
                    return show
            raise utils.EngineError("Show not found.")
    
    def regex_list(self, regex):
        """
        Searches for a show and returns a list with the matches
        
        It asks the data handler to do a regex search for a show and returns the
        list with all the matches.
        
        pattern: Regex string to search in the show title
        
        """
        showlist = self.data_handler.get()
        return list(v for k, v in showlist.iteritems() if re.match(regex, v['title'], re.I))
        
    def regex_list_titles(self, pattern):
        # TODO : Temporal hack for the client autocomplete function
        showlist = self.data_handler.get()
        newlist = list()
        for k, v in showlist.iteritems():
            if re.match(pattern, v['title'], re.I):
                if ' ' in v['title']:
                    newlist.append('"' + v['title'] + '" ')
                else:
                    newlist.append(v['title'] + ' ')
                    
        return newlist
    
    def set_episode(self, show_pattern, newep):
        """
        Updates the progress for a show
        
        It asks the data handler to update the progress of the specified show to
        a specified number.

        show_pattern: ID or full title of the show
        newep: The progress number to update the show to

        """
        # Check if operation is supported by the API
        if not self.mediainfo['can_update']:
            raise utils.EngineError('Operation not supported by API.')
        
        # Check for the episode number
        try:
            newep = int(newep)
        except ValueError:
            raise utils.EngineError('Episode must be numeric.')
        
        # Get the show and update it
        show = self.get_show_info(show_pattern)
        # More checks
        if show['total'] and newep > show['total']:
            raise utils.EngineError('Episode out of limits.')
        if show['my_progress'] == newep:
            raise utils.EngineError("Show already at episode %d" % newep)
        
        # Change episode
        self.msg.info(self.name, "Updating show %s to episode %d..." % (show['title'], newep))
        self.data_handler.queue_update(show, 'my_progress', newep)
        
        return show
    
    def set_score(self, show_pattern, newscore):
        """
        Updates the score for a show
        
        It asks the data handler to update the score of the specified show
        to a specified number.

        show_pattern: ID or full title of the show
        newscore: The score number to update the show to
        
        """
        # Check if operation is supported by the API
        if not self.mediainfo['can_score']:
            raise utils.EngineError('Operation not supported by API.')
        
        # Check for the correctness of the score
        try:
            newscore = int(newscore)
        except ValueError:
            raise utils.EngineError('Score must be numeric.')
        
        # Get the show and update it
        show = self.get_show_info(show_pattern)
        # More checks
        if newscore > 10:
            raise utils.EngineError('Score out of limits.')
        if show['my_score'] == newscore:
            raise utils.EngineError("Score already at %d" % newscore)
        
        # Change score
        self.msg.info(self.name, "Updating show %s to score %d..." % (show['title'], newscore))
        self.data_handler.queue_update(show, 'my_score', newscore)
        
        return show
    
    def set_status(self, show_pattern, newstatus):
        """
        Updates the status for a show
        
        It asks the data handler to update the status of the specified show
        to a specified number.

        show_pattern: ID or full title of the show
        newstatus: The status number to update the show to

        """
        # Check if operation is supported by the API
        if not self.mediainfo['can_status']:
            raise utils.EngineError('Operation not supported by API.')
        
        # Check for the correctness of the score
        try:
            newstatus = int(newstatus)
        except ValueError:
            raise utils.EngineError('Status must be numeric.')
        
        # Get the show and update it
        _statuses = self.mediainfo['statuses_dict']
        show = self.get_show_info(show_pattern)
        # More checks
        if show['my_status'] == newstatus:
            raise utils.EngineError("Show already in %s." % _statuses[newstatus])
        
        # Change score
        self.msg.info(self.name, "Updating show %s status to %s..." % (show['title'], _statuses[newstatus]))
        self.data_handler.queue_update(show, 'my_status', newstatus)
        
        return show
    
    def play_episode(self, show, playep=0):
        """
        Searches the hard disk for an episode and plays the episode
        
        Does a local search in the hard disk (in the folder specified by the config file)
        for the specified episode for the specified show.

        show: Show dictionary
        playep: Episode to play. Optional. If none specified, the next episode will be played.


        """
        # Check if operation is supported by the API
        if not self.mediainfo['can_play']:
            raise utils.EngineError('Operation not supported by API.')
            
        if show:
            searchfile = show['title']
            searchfile = searchfile.replace(',', ',?')
            searchfile = searchfile.replace('.', '.?')
            searchfile = searchfile.replace(' ', '.')
            
            playing_next = False
            if not playep:
                playep = show['my_progress'] + 1
                playing_next = True
                
            searchep = str(playep).zfill(2)
            
            # Do the file search
            self.msg.info(self.name, "Searching for %s %s..." % (show['title'], searchep))
            
            regex = searchfile + r".*\D" + searchep + r"\D.*(mkv|mp4|avi)"
            filename = utils.regex_find_file(regex, self.config['main']['searchdir'])
            if filename:
                self.msg.info(self.name, 'Found. Starting player...')
                subprocess.call([self.config['main']['player'], filename])
                return playep
            else:
                raise utils.EngineError('Episode file not found.')
    
    def undoall(self):
        """Clears the data handler queue."""
        return self.data_handler.queue_clear()
        
    def filter_list(self, filter_num):
        """
        Returns a list filtered by status
        
        It asks the data handler to fetch the list and filter it by the specified status.

        filter_num = Status number

        """
        showlist = self.data_handler.get()
        if filter_num:
            return list(v for k, v in showlist.iteritems() if v['my_status'] == filter_num)
        else:
            return showlist.values()
    
    def list_download(self):
        """Asks the data handler to download the remote list."""
        self.data_handler.download_data()
    
    def list_upload(self):
        """Asks the data handler to upload the remote list."""
        self.data_handler.process_queue()
    
    def get_queue(self):
        """Asks the data handler for the current queue."""
        return self.data_handler.queue
    


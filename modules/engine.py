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
    
    def set_message_handler(self, message_handler):
        self.msg = messenger.Messenger(message_handler)
        
    def start(self):
        """Starts the engine."""
        self.msg.info(self.name, 'Reading config file...')
        try:
            self.config = utils.parse_config(utils.get_filename('wmal.conf'))
        except IOError:
            raise utils.EngineFatal("Couldn't open config file.")
        
        # Check if there's a username
        if self.config['username'] == 'CHANGEME':
            raise utils.EngineFatal("Please set your username and password in the config file.")
        
        # Create data handler and start it
        try:
            self.data_handler = data.Data(self.msg, self.config)
            self.data_handler.start()
        except utils.DataError, e:
            raise utils.DataFatal(e.message)
        except utils.APIError, e:
            raise utils.APIFatal(e.message)
        
        return True
    
    def unload(self):
        self.msg.debug(self.name, "Unloading...")
        self.data_handler.unload()
        
    def get_list(self):
        """Requests the full show list from the data handler."""
        return self.data_handler.get().values()
    
    def get_show_info(self, pattern):
        """Looks up the data handler for a specified show and returns it"""
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
    
    def regex_list(self, pattern):
        """Matches the list against a regex pattern and returns a new list"""
        showlist = self.data_handler.get()
        return list(v for k, v in showlist.iteritems() if re.match(pattern, v['title'], re.I))
        
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
        """Tells the data handler to update a show episode"""
        # Check for the episode number
        try:
            newep = int(newep)
        except ValueError:
            raise utils.EngineError('Episode must be numeric.')
        
        # Get the show and update it
        show = self.get_show_info(show_pattern)
        # More checks
        if show['episodes'] and newep > show['episodes']:
            raise utils.EngineError('Episode out of limits.')
        if show['my_episodes'] == newep:
            raise utils.EngineError("Show already at episode %d" % newep)
        
        # Change episode
        #show['my_episodes'] = newep;
        self.msg.info(self.name, "Updating show %s to episode %d..." % (show['title'], newep))
        self.data_handler.queue_update(show, 'my_episodes', newep)
        
        return show
    
    def set_score(self, show_pattern, newscore):
        """Tells the data handler to update a show score"""
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
        """Tells the data handler to update a show score"""
        # Check for the correctness of the score
        try:
            newstatus = int(newstatus)
        except ValueError:
            raise utils.EngineError('Status must be numeric.')
        
        # Get the show and update it
        _statuses = self.statuses()
        show = self.get_show_info(show_pattern)
        # More checks
        if show['my_status'] == newstatus:
            raise utils.EngineError("Show already in %s." % _statuses[newstatus])
        
        # Change score
        self.msg.info(self.name, "Updating show %s status to %s..." % (show['title'], _statuses[newstatus]))
        self.data_handler.queue_update(show, 'my_status', newstatus)
        
        return show
    
    def play_episode(self, show, playep=0):
        """Searches the hard disk for an episode and launches the media player for it"""
        if show:
            searchfile = show['title']
            searchfile = searchfile.replace(',', ',?')
            searchfile = searchfile.replace('.', '.?')
            searchfile = searchfile.replace(' ', '.')
            
            playing_next = False
            if not playep:
                playep = show['my_episodes'] + 1
                playing_next = True
                
            searchep = str(playep).zfill(2)
            
            # Do the file search
            self.msg.info(self.name, "Searching for %s %s..." % (show['title'], searchep))
            
            regex = searchfile + r".*\D" + searchep + r"\D.*(mkv|mp4|avi)"
            filename = utils.regex_find_file(regex, self.config['searchdir'])
            if filename:
                self.msg.info(self.name, 'Found. Starting player...')
                subprocess.call([self.config['player'], filename])
                return playep
            else:
                raise utils.EngineError('Episode file not found.')
    
    def undoall(self):
        return self.data_handler.queue_clear()
        
    def filter_list(self, filter_num):
        """Returns a list of shows only of a specified status"""
        showlist = self.data_handler.get()
        if filter_num:
            return list(v for k, v in showlist.iteritems() if v['my_status'] == filter_num)
        else:
            return showlist.values()
    
    def list_download(self):
        self.data_handler.download_data()
    
    def list_upload(self):
        self.data_handler.process_queue()
    
    def get_queue(self):
        return self.data_handler.queue
        
    def statuses(self):
        return data.STATUSES
    
    def statuses_nums(self):
        return data.STATUSES_NUMS
    
    def statuses_keys(self):
        return data.STATUSES_KEYS


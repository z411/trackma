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

VERSION = 'v0.2'

import re
import os
import subprocess
import atexit

import difflib
import threading
import time
import webbrowser

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
    playing = False
    last_show = None
    
    name = 'Engine'
    
    signals = { 'show_added':       None,
                'show_deleted':     None,
                'episode_changed':  None,
                'score_changed':    None,
                'status_changed':   None,
                'playing':          None, }
    
    def __init__(self, account, message_handler=None):
        """Reads configuration file and asks the data handler for the API info."""
        self.msg = messenger.Messenger(message_handler)
        self.msg.info(self.name, 'Version '+VERSION)

        # Register cleanup function when program exits
        atexit.register(self._cleanup)
        
        self.load(account)
        self._init_data_handler()
    
    def load(self, account):
        self.account = account
        
        # Create home directory
        utils.make_dir('')
        self.configfile = utils.get_root_filename('config.json')
        
        # Create user directory
        userfolder = "%s.%s" % (account['username'], account['api'])
        utils.make_dir(userfolder)
        self.userconfigfile = utils.get_filename(userfolder, 'user.json')
        
        self.msg.info(self.name, 'Reading config files...')
        try:
            self.config = utils.parse_config(self.configfile, utils.config_defaults)
            self.userconfig = utils.parse_config(self.userconfigfile, utils.userconfig_defaults)
        except IOError:
            raise utils.EngineFatal("Couldn't open config file.")
        
    def _init_data_handler(self):
        # Create data handler
        self.data_handler = data.Data(self.msg, self.config, self.account, self.userconfig)
        
        # Record the API details
        (self.api_info, self.mediainfo) = self.data_handler.get_api_info()
    
    def _emit_signal(self, signal, args=None):
        try:
            if self.signals[signal]:
                self.signals[signal](args)
        except KeyError:
            raise Exception("Call to undefined signal.")

    def _cleanup(self):
        # If the engine wasn't closed for whatever reason, do it
        if self.loaded:
            self.unload()
    
    def connect_signal(self, signal, callback):
        try:
            self.signals[signal] = callback
        except KeyError:
            raise utils.EngineFatal("Invalid signal.")
        
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
        
        # Start tracker
        if self.mediainfo.get('can_play') and self.config['tracker_enabled']:
            tracker_args = (
                            int(self.config['tracker_interval']),
                            int(self.config['tracker_update_wait']),
                           )
            tracker_t = threading.Thread(target=self.tracker, args=tracker_args)
            tracker_t.daemon = True
            tracker_t.start()
        
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
        
        if self.last_show:
            self.data_handler.set_show_attr(self.last_show, 'playing', False)
            self._emit_signal('playing', self.last_show)
         
        self.msg.info(self.name, "Unloading...")
        self.data_handler.unload()
        
        # Save config file
        #utils.save_config(self.config, self.configfile)
        utils.save_config(self.userconfig, self.userconfigfile)
        
        self.loaded = False
    
    def reload(self, account=None, mediatype=None):
        """Changes the API and/or mediatype and reloads itself."""
        if not self.loaded:
            raise utils.wmalError("Engine is not loaded.")
        
        self.unload()
        
        if account:
            self.load(account)
        if mediatype:
            self.userconfig['mediatype'] = mediatype
        
        self._init_data_handler()
        self.start()
    
    def get_config(self, key):
        """Returns the specified key from the configuration"""
        return self.config[key]
    
    def set_config(self, key, value):
        """Writes the defined key to the configuration"""
        self.config[key] = value
        
    def save_config(self):
        """Writes configuration files"""
        
        # Save config file
        utils.save_config(self.config, self.configfile)
        utils.save_config(self.userconfig, self.userconfigfile)
        
    def get_list(self):
        """Requests the full show list from the data handler."""
        return self.data_handler.get().itervalues()
    
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
    
    def get_show_details(self, show):
        return self.data_handler.info_get(show)
        
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
    
    def search(self, criteria):
        """
        Calls the API to do a search in the remote list
        
        This will immediatly call the API and request a list of
        shows matching the criteria. This is useful to add a show.
        
        citeria: Search keyword
        
        """
        return self.data_handler.search(criteria)
    
    def add_show(self, show):
        """
        Adds a show to the list
        
        It adds a show to the list and queues the list update
        for the next sync.
        
        show: Full show dictionary
        
        """
        # Check if operation is supported by the API
        if not self.mediainfo.get('can_add'):
            raise utils.EngineError('Operation not supported by API.')
        
        # Add in data handler
        self.data_handler.queue_add(show)
        
        # Emit signal
        self._emit_signal('show_added', show)
        
    def set_episode(self, show_pattern, newep):
        """
        Updates the progress for a show
        
        It asks the data handler to update the progress of the specified show to
        a specified number.

        show_pattern: ID or full title of the show
        newep: The progress number to update the show to

        """
        # Check if operation is supported by the API
        if not self.mediainfo.get('can_update'):
            raise utils.EngineError('Operation not supported by API.')
        
        # Check for the episode number
        try:
            newep = int(newep)
        except ValueError:
            raise utils.EngineError('Episode must be numeric.')
        
        # Get the show info
        show = self.get_show_info(show_pattern)
        # More checks
        if show['total'] and newep > show['total']:
            raise utils.EngineError('Episode out of limits.')
        if show['my_progress'] == newep:
            raise utils.EngineError("Show already at episode %d" % newep)
        
        # Change episode
        self.msg.info(self.name, "Updating show %s to episode %d..." % (show['title'], newep))
        self.data_handler.queue_update(show, 'my_progress', newep)

        # Change status if required
        if self.config['auto_status_change']:
            if newep == 1 and self.mediainfo.get('status_start'):
                self.data_handler.queue_update(show, 'my_status', self.mediainfo['status_start'])
                self._emit_signal('status_changed', show)
            elif newep == show['total'] and self.mediainfo.get('status_finish'):
                self.data_handler.queue_update(show, 'my_status', self.mediainfo['status_finish'])
                self._emit_signal('status_changed', show)

        # Emit signal
        self._emit_signal('episode_changed', show)
        
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
        if not self.mediainfo.get('can_score'):
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
        
        # Emit signal
        self._emit_signal('score_changed', show)
        
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
        if not self.mediainfo.get('can_status'):
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
        
        # Emit signal
        self._emit_signal('status_changed', show)
        
        return show
    
    def delete_show(self, show):
        """
        Deletes a show completely from the list
        
        show: Show dictionary
        
        """
        if not self.mediainfo.get('can_delete'):
            raise utils.EngineError('Operation not supported by API.')
        
        # Add in data handler
        self.data_handler.queue_delete(show)
        
        # Emit signal
        self._emit_signal('show_deleted', show)
        
    def _search_video(self, titles, episode):
        searchfile = '|'.join(titles)
        searchfile = searchfile.replace(',', ',?')
        searchfile = searchfile.replace('.', '.?')
        searchfile = searchfile.replace('!', '[!]?')
        searchfile = searchfile.replace('?', '[?]?')
        searchfile = searchfile.replace(' ', '.?')    
        searchep = str(episode).zfill(2)
        
        # Do the file search
        regex = "(%s).*\D%s\D.*(mkv|mp4|avi)" % (searchfile, searchep)
        return utils.regex_find_file(regex, self.config['searchdir'])
    
    def get_new_episodes(self, showlist):
        results = list()
        total = len(showlist)
        
        for i, show in enumerate(showlist):
            self.msg.info(self.name, "Searching %d/%d..." % (i+1, total))

            titles = [show['title']]
            titles.extend(show['aliases'])
            
            filename = self._search_video(titles, show['my_progress']+1)
            if filename:
                self.data_handler.set_show_attr(show, 'neweps', True)
                results.append(show)
        return results
        
    def play_episode(self, show, playep=0):
        """
        Searches the hard disk for an episode and plays the episode
        
        Does a local search in the hard disk (in the folder specified by the config file)
        for the specified episode for the specified show.

        show: Show dictionary
        playep: Episode to play. Optional. If none specified, the next episode will be played.


        """
        # Check if operation is supported by the API
        if not self.mediainfo.get('can_play'):
            raise utils.EngineError('Operation not supported by API.')

        try:
            playep = int(playep)
        except ValueError:
            raise utils.EngineError('Episode must be numeric.')
            
        if show:
            playing_next = False
            if not playep:
                playep = show['my_progress'] + 1
                playing_next = True
            
            if show['total'] and playep > show['total']:
                raise utils.EngineError('Episode beyond limits.')
            
            self.msg.info(self.name, "Searching for %s %s..." % (show['title'], playep))
            
            if self.data_handler.altname_get(show['id']):
                titles = [ self.data_handler.altname_get(show['id']) ]
            else:
                titles = [show['title']]
                titles.extend(show['aliases'])
            
            filename = self._search_video(titles, playep)
            if filename:
                self.msg.info(self.name, 'Found. Starting player...')
                self.playing = True
                try:
                    subprocess.call([self.config['player'], filename])
                except OSError:
                    raise utils.EngineError('Player not found.')
                self.playing = False
                return playep
            else:
                raise utils.EngineError('Episode file not found.')
    
    def undoall(self):
        """Clears the data handler queue."""
        return self.data_handler.queue_clear()
       
    def altname(self, showid, newname=None):
        if newname:
            self.data_handler.altname_set(showid, newname)
        else:
            return self.data_handler.altname_get(showid)

    def filter_list(self, filter_num):
        """
        Returns a list filtered by status
        
        It asks the data handler to fetch the list and filter it by the specified status.

        filter_num = Status number

        """
        showlist = self.data_handler.get()
        return list(v for k, v in showlist.iteritems() if v['my_status'] == filter_num)
    
    def tracker(self, interval, wait):
        """
        Tracker loop to be used in a thread
        
        """
        self.last_show = None
        last_time = 0
        last_updated = False
        wait_s = wait * 60
        
        while True:
            # This runs the tracker and returns the playing show, if any
            result = self.track_process()
            
            if result:
                (show, episode) = result
                
                if not self.last_show or show['id'] != self.last_show['id'] or episode != last_episode:
                    # There's a new show detected, so
                    # let's save the show information and
                    # the time we detected it first
                    
                    # But if we're watching a new show, let's make sure turn off
                    # the Playing flag on that one first
                    if self.last_show and self.last_show != show:
                        self.data_handler.set_show_attr(self.last_show, 'playing', False)
                        self._emit_signal('playing', self.last_show)
 

                    self.last_show = show
                    self.data_handler.set_show_attr(show, 'playing', True)
                    self._emit_signal('playing', show)
 
                    last_episode = episode
                    last_time = time.time()
                    last_updated = False
                
                if not last_updated:
                    # Check if we need to update the show yet
                    if episode == (show['my_progress'] + 1):
                        timedif = time.time() - last_time
                        
                        if timedif > wait_s:
                            # Time has passed, let's update
                            self.set_episode(show['id'], episode)
                            
                            last_updated = True
                        else:
                            self.msg.info(self.name, 'Will update %s %d in %d seconds' % (self.last_show['title'], episode, wait_s-timedif))
                    else:
                        # We shouldn't update to this episode!
                        self.msg.warn(self.name, 'Player is not playing the next episode of %s. Ignoring.' % self.last_show['title'])
                        last_updated = True
                else:
                    # The episode was updated already. do nothing
                    pass
            else:
                # There isn't any show playing right now
                # Check if the player was closed
                if self.last_show:
                    if not last_updated:
                        self.msg.info(self.name, 'Player was closed before update.')
                    
                    self.data_handler.set_show_attr(self.last_show, 'playing', False)
                    self._emit_signal('playing', self.last_show)
                    self.last_show = None
                    last_updated = False
                    last_time = 0
            
            # Wait for the interval before running check again
            time.sleep(interval)
    
    def track_process(self):
        if self.playing:
            # Don't do anything if the engine is busy playing a file
            return None
        
        filename = self._playing_file(self.config['tracker_process'], self.config['searchdir'])
        
        if filename:
            # Do a regex to the filename to get
            # the show title and episode number
            reg = re.compile(r"(\[.+\])?([ \w\d\-,@.:;!\?]+) - ([ \d]+) ")
            show_raw = filename.replace("_"," ").replace("v2","").strip()
            show_match = reg.match(show_raw)
            if not show_match:
                self.msg.warn(self.name, 'Regex error. Check logs.')
                utils.log_error("[Regex error] Tracker: %s / Dir: %s / Processed filename: %s\n" % (self.config['tracker_process'], self.config['searchdir'], show_raw))
                return None
            
            show_title = show_match.group(2).strip()
            show_ep = int(show_match.group(3).strip())
            
            # Use difflib to see if the show title is similar to
            # one we have in the list
            highest_ratio = (None, 0)
            for show in self.get_list():
                ratio = difflib.SequenceMatcher(None, show['title'], show_title)
                ratio = ratio.ratio()
                if ratio > highest_ratio[1]:
                    highest_ratio = (show, ratio)
            
            playing_show = highest_ratio[0]
            if highest_ratio[1] > 0.7:
                return (playing_show, show_ep)
            else:
                self.msg.warn(self.name, 'Found player but show not in list.')
        
        return None
    
    def _playing_file(self, players, searchdir):
        """
        Returns the files a process is playing
        
        """
        lsof = subprocess.Popen(['lsof', '-n', '-c', ''.join(['/', players, '/']), '-Fn', searchdir], stdout=subprocess.PIPE)
        output = lsof.communicate()[0]
        fileregex = re.compile("n(.*(\.mkv|\.mp4|\.avi))")
        
        for line in output.splitlines():
            match = fileregex.match(line)
            if match is not None:
                return os.path.basename(match.group(1))
        
        return False
        
    def list_download(self):
        """Asks the data handler to download the remote list."""
        self.data_handler.download_data()
    
    def list_upload(self):
        """Asks the data handler to upload the remote list."""
        result = self.data_handler.process_queue()
        #for show in result:
        #    self._emit_signal('episode_changed', show)

    def get_queue(self):
        """Asks the data handler for the current queue."""
        return self.data_handler.queue
    

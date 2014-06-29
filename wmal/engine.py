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
    The engine is the controller that handles commands coming from
    the user interface and then queries the Data Handler for the necessary data.
    It doesn't control nor care about how the data is fetched by the Data Handler.
    
    After instantiating this class, the :func:`start` must be run to initialize the engine.
    Likewise, the :func:`unload` function must be called when you're done using the engine.
    
    The account and mediatype can be changed later on the fly by calling :func:`reload`.
    
    The **account** parameter is an account dictionary passed by an Account Manager
    and is used to run the engine.
    
    The **message_handler** is a reference to a messaging function for the engine
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
                'show_synced':      None,
                'queue_changed':    None,
                'playing':          None, }
    
    def __init__(self, account, message_handler=None):
        """Reads configuration file and asks the data handler for the API info."""
        self.msg = messenger.Messenger(message_handler)
        self.msg.info(self.name, 'Version '+utils.VERSION)

        # Register cleanup function when program exits
        atexit.register(self._cleanup)
        
        self._load(account)
        self._init_data_handler()
    
    def _load(self, account):
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
        self.data_handler.connect_signal('show_synced', self._data_show_synced)
        self.data_handler.connect_signal('queue_changed', self._data_queue_changed)
        
        # Record the API details
        (self.api_info, self.mediainfo) = self.data_handler.get_api_info()
    
    def _data_show_synced(self, show):
        self._emit_signal('show_synced', show)
    
    def _data_queue_changed(self, queue):
        self._emit_signal('queue_changed', queue)
        
    def _emit_signal(self, signal, *args):
        try:
            if self.signals[signal]:
                self.signals[signal](*args)
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
        """Changes the message handler function on the fly."""
        self.msg = messenger.Messenger(message_handler)
        self.data_handler.set_message_handler(self.msg)
        
    def start(self):
        """
        Starts the engine.
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
            self.msg.debug(self.name, 'Enabling tracker...')
            tracker_t.start()
        
        self.loaded = True
        return True
    
    def unload(self):
        """
        Closes the data handler and closes the engine cleanly.
        This should be called when closing the client application, or when you're
        sure you're not going to use the engine anymore. This does all the necessary
        procedures to close the data handler cleanly and then itself.
        
        """
        #if not self.loaded:
        #    raise utils.wmalError("Engine is not loaded.")
        
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
            self._load(account)
        if mediatype:
            self.userconfig['mediatype'] = mediatype
        
        self._init_data_handler()
        self.start()
    
    def get_config(self, key):
        """Returns the specified key from the configuration."""
        return self.config[key]
    
    def set_config(self, key, value):
        """
        Writes the defined key to the configuration.
        Note that this writes the configuration only to memory; when you're
        done doing all necessary changes, make sure to write the configuration file
        with :func:`save_config`."""
        self.config[key] = value
        
    def save_config(self):
        """Writes all configuration files to disk."""
        
        # Save config file
        utils.save_config(self.config, self.configfile)
        utils.save_config(self.userconfig, self.userconfigfile)
        
    def get_list(self):
        """
        Returns the full show list requested from the data handler as a list of show dictionaries.
        If you only need shows in a specified status, use :func:`filter_list`.
        """
        return self.data_handler.get().itervalues()
    
    def get_show_info(self, showid):
        """
        Returns the show dictionary for the specified **showid**.
        """
        showdict = self.data_handler.get()
        
        try:
            return showdict[showid]
        except KeyError:
            raise utils.EngineError("Show not found.")

    def get_show_info_title(self, pattern):
        showdict = self.data_handler.get()           
        # Do title lookup, slower
        for k, show in showdict.iteritems():
            if show['title'] == pattern:
                return show
        raise utils.EngineError("Show not found.")
    
    def get_show_details(self, show):
        """
        Returns detailed information about **show** requested from the data handler.
        """
        return self.data_handler.info_get(show)
        
    def regex_list(self, regex):
        """
        It asks the data handler to do a regex search for a show and returns the
        list of show dictionaries with all the matches.
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
    
    def get_show_titles(self, show):
        if self.data_handler.altname_get(show['id']):
            return [ self.data_handler.altname_get(show['id']) ]
        else:
            return [show['title']] + show['aliases']

    def search(self, criteria):
        """
        Request a remote list of shows matching the criteria
        and returns it as a list of show dictionaries.
        This is useful to add a show.
        """
        return self.data_handler.search(criteria)
    
    def add_show(self, show):
        """
        Adds **show** to the list and queues the list update
        for the next sync.
        """
        # Check if operation is supported by the API
        if not self.mediainfo.get('can_add'):
            raise utils.EngineError('Operation not supported by API.')
        
        # Add in data handler
        self.data_handler.queue_add(show)
        
        # Emit signal
        self._emit_signal('show_added', show)
        
    def set_episode(self, showid, newep):
        """
        Updates the progress of the specified **showid** to **newep**
        and queues the list update for the next sync.
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
        show = self.get_show_info(showid)
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
                self.set_status(show['id'], self.mediainfo['status_start'])
            elif newep == show['total'] and self.mediainfo.get('status_finish'):
                self.set_status(show['id'], self.mediainfo['status_finish'])
        
        # Clear neweps flag
        if self.data_handler.get_show_attr(show, 'neweps'):
            self.data_handler.set_show_attr(show, 'neweps', False)

        # Emit signal
        self._emit_signal('episode_changed', show)
        
        return show
    
    def set_score(self, showid, newscore):
        """
        Updates the score of the specified **showid** to **newscore**
        and queues the list update for the next sync.
        """
        # Check if operation is supported by the API
        if not self.mediainfo.get('can_score'):
            raise utils.EngineError('Operation not supported by API.')
        
        # Check for the correctness of the score
        try:
            # Use float if the mediainfo supports it
            if self.mediainfo['score_decimals']:
                newscore = float(newscore)
            else:
                newscore = int(newscore)
        except ValueError:
            raise utils.EngineError('Invalid score.')
        
        # Get the show and update it
        show = self.get_show_info(showid)
        # More checks
        if newscore > self.mediainfo['score_max']:
            raise utils.EngineError('Score out of limits.')
        if show['my_score'] == newscore:
            raise utils.EngineError("Score already at %d" % newscore)
        
        # Change score
        self.msg.info(self.name, "Updating show %s to score %d..." % (show['title'], newscore))
        self.data_handler.queue_update(show, 'my_score', newscore)
        
        # Emit signal
        self._emit_signal('score_changed', show)
        
        return show
    
    def set_status(self, showid, newstatus):
        """
        Updates the score of the specified **showid** to **newstatus** (number)
        and queues the list update for the next sync.
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
        show = self.get_show_info(showid)
        # More checks
        if show['my_status'] == newstatus:
            raise utils.EngineError("Show already in %s." % _statuses[newstatus])
        
        # Change status
        old_status = show['my_status']
        self.msg.info(self.name, "Updating show %s status to %s..." % (show['title'], _statuses[newstatus]))
        self.data_handler.queue_update(show, 'my_status', newstatus)
        
        # Emit signal
        self._emit_signal('status_changed', show, old_status)
        
        return show
    
    def delete_show(self, show):
        """
        Deletes **show** completely from the list and queues the list update for the next sync.
        """
        if not self.mediainfo.get('can_delete'):
            raise utils.EngineError('Operation not supported by API.')
        
        # Add in data handler
        self.data_handler.queue_delete(show)
        
        # Emit signal
        self._emit_signal('show_deleted', show)
        
    def _search_video(self, titles, episode):
        best_candidate = (None, 0)

        matcher = difflib.SequenceMatcher()

        # Check over video files and propose our best candidate
        for (fullpath, filename) in utils.regex_find_videos('mkv|mp4|avi', self.config['searchdir']):
            # Use our analyze function to see what's the title and episode of the file
            (candidate_title, candidate_episode) = utils.analyze(filename)

            # Skip this file if we couldn't analyze it or it isn't the episode we want
            if not candidate_title or candidate_episode != episode:
                continue
            
            matcher.set_seq1(candidate_title.lower())

            # We remember to compare all titles (aliases and whatnot)
            for requested_title in titles:
                matcher.set_seq2(requested_title.lower())
                ratio = matcher.ratio()

                # Propose as our new candidate if its ratio is
                # better than threshold and it's better than
                # what we've seen yet
                if ratio > 0.7 and ratio > best_candidate[1]:
                    best_candidate = (fullpath, ratio)

        return best_candidate[0]
    
    def get_new_episodes(self, showlist):
        results = list()
        total = len(showlist)
        
        for i, show in enumerate(showlist):
            self.msg.info(self.name, "Searching %d/%d..." % (i+1, total))

            titles = self.get_show_titles(show)

            filename = self._search_video(titles, show['my_progress']+1)
            if filename:
                self.data_handler.set_show_attr(show, 'neweps', True)
                results.append(show)
        return results
        
    def play_episode(self, show, playep=0):
        """
        Does a local search in the hard disk (in the folder specified by the config file)
        for the specified episode (**playep**) for the specified **show**.
        
        If no **playep** is specified, the next episode of the show will be played.
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
            
            titles = self.get_show_titles(show)

            filename = self._search_video(titles, playep)
            if filename:
                self.msg.info(self.name, 'Found. Starting player...')
                self.playing = True
                try:
                    subprocess.call([self.config['player'], filename])
                except OSError:
                    raise utils.EngineError('Player not found, check your config.json')
                self.playing = False
                return playep
            else:
                raise utils.EngineError('Episode file not found.')
    
    def undoall(self):
        """Clears the data handler queue and discards any unsynced change."""
        return self.data_handler.queue_clear()
       
    def altname(self, showid, newname=None):
        """
        If **newname** is specified, it gets the alternate name of **showid**.
        Otherwise, it sets the alternate name of **showid** to **newname**.
        """
        if newname is not None:
            if newname == '':
                self.data_handler.altname_clear(showid)
                self.msg.info(self.name, 'Cleared alternate name.')
            else:
                self.data_handler.altname_set(showid, newname)
                self.msg.info(self.name, 'Changed alternate name to %s.' % newname)
        else:
            return self.data_handler.altname_get(showid)

    def filter_list(self, status_num):
        """
        Returns a show list with the shows in the specified **status_num** status.
        If you need a list with all the shows, use :func:`get_list`.
        """
        showlist = self.data_handler.get()
        return list(v for k, v in showlist.iteritems() if v['my_status'] == status_num)
    
    def tracker(self, interval, wait):
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
                        self._emit_signal('playing', self.last_show, False, 0)
 

                    self.last_show = show
                    self._emit_signal('playing', show, True, episode)
 
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
                    
                    self._emit_signal('playing', self.last_show, False)
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
            (show_title, show_ep) = utils.analyze(filename)
            if not show_title:
                self.msg.warn(self.name, 'Regex error. Check logs.')
                utils.log_error("[Regex error] Tracker: %s / Dir: %s / Processed filename: %s\n" % (self.config['tracker_process'], self.config['searchdir'], show_raw))
                return None
            
            # Use difflib to see if the show title is similar to
            # one we have in the list
            highest_ratio = (None, 0)
            matcher = difflib.SequenceMatcher()
            matcher.set_seq1(show_title.lower())
            
            # Compare to every show in our list to see which one
            # has the most similar name
            for show in self.get_list():
                titles = self.get_show_titles(show)
                # Make sure to search through all the aliases
                for title in titles:
                    matcher.set_seq2(title.lower())
                    ratio = matcher.ratio()
                    if ratio > highest_ratio[1]:
                        highest_ratio = (show, ratio)
            
            playing_show = highest_ratio[0]
            if highest_ratio[1] > 0.7:
                return (playing_show, show_ep)
            else:
                self.msg.warn(self.name, 'Found player but show not in list.')
        
        return None
    
    def _playing_file(self, players, searchdir):
        lsof = subprocess.Popen(['lsof', '-n', '-c', ''.join(['/', players, '/']), '-Fn'], stdout=subprocess.PIPE)
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
        """Asks the data handler to upload the unsynced changes in the queue."""
        result = self.data_handler.process_queue()
        #for show in result:
        #    self._emit_signal('episode_changed', show)

    def get_queue(self):
        """Asks the data handler for the items in the current queue."""
        return self.data_handler.queue
    

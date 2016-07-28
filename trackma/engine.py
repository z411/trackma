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
import threading
import difflib
import time
import datetime
import random
import shlex
from decimal import Decimal

from trackma import messenger
from trackma import data
from trackma import tracker
from trackma import utils
from trackma.extras import AnimeInfoExtractor

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
    tracker = None
    config = dict()
    msg = None
    loaded = False
    playing = False
    hooks_available = False

    name = 'Engine'

    signals = { 'show_added':        None,
                'show_deleted':      None,
                'episode_changed':   None,
                'score_changed':     None,
                'status_changed':    None,
                'show_synced':       None,
                'sync_complete':     None,
                'queue_changed':     None,
                'playing':           None,
                'prompt_for_update': None, }

    def __init__(self, account, message_handler=None):
        """Reads configuration file and asks the data handler for the API info."""
        self.msg = messenger.Messenger(message_handler)

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

        self.msg.info(self.name, 'Trackma v{0} - using account {1}({2}).'.format(
            utils.VERSION, account['username'], account['api']))
        self.msg.info(self.name, 'Reading config files...')
        try:
            self.config = utils.parse_config(self.configfile, utils.config_defaults)
        except IOError:
            raise utils.EngineFatal("Couldn't open config file.")

        # Load hook file
        if os.path.exists(utils.get_root_filename('hook.py')):
            import sys
            sys.path[0:0] = [utils.get_root()]
            try:
                self.msg.info(self.name, "Importing user hooks (hook.py)...")
                global hook
                import hook
                self.hooks_available = True
            except ImportError:
                self.msg.warn(self.name, "Error importing hooks.")
            del sys.path[0]

    def _init_data_handler(self, mediatype=None):
        # Create data handler
        self.data_handler = data.Data(self.msg, self.config, self.account, mediatype)
        self.data_handler.connect_signal('show_synced', self._data_show_synced)
        self.data_handler.connect_signal('sync_complete', self._data_sync_complete)
        self.data_handler.connect_signal('queue_changed', self._data_queue_changed)

        # Record the API details
        (self.api_info, self.mediainfo) = self.data_handler.get_api_info()

    def _data_show_synced(self, show, changes):
        self._emit_signal('show_synced', show, changes)

    def _data_sync_complete(self, items):
        self._emit_signal('sync_complete', items)

    def _data_queue_changed(self, queue):
        self._emit_signal('queue_changed', queue)

    def _tracker_playing(self, showid, playing, episode):
        show = self.get_show_info(showid)
        self._emit_signal('playing', show, playing, episode)

    def _tracker_update(self, showid, episode):
        show = self.get_show_info(showid)
        if self.config['tracker_update_prompt']:
            self._emit_signal('prompt_for_update', show, episode)
        else:
            self.set_episode(show['id'], episode)

    def _emit_signal(self, signal, *args):
        try:
            if self.signals[signal]:
                self.signals[signal](*args)
            if self.hooks_available:
                method = getattr(hook, signal)
                self.msg.debug(self.name, "Calling hook %s..." % signal)
                method(self, *args)
        except AttributeError:
            pass

    def _get_tracker_list(self, filter_num=None):
        tracker_list = []
        if filter_num:
            source_list = self.filter_list(filter_num)
        else:
            source_list = self.get_list()

        for show in source_list:
            tracker_list.append({'id': show['id'],
                                 'title': show['title'],
                                 'my_progress': show['my_progress'],
                                 'type': None,
                             'titles': self.data_handler.get_show_titles(show),
                             }) # TODO types

        return tracker_list

    def _update_tracker(self):
        if self.tracker:
            self.tracker.update_list(self._get_tracker_list())

    def _cleanup(self):
        # If the engine wasn't closed for whatever reason, do it
        if self.loaded:
            self.msg.info(self.name, "Forcing exit...")
            self.data_handler.unload(True)
            self.loaded = False

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
            raise utils.TrackmaError("Already loaded.")

        # Start the data handler
        try:
            (self.api_info, self.mediainfo) = self.data_handler.start()
        except utils.DataError as e:
            raise utils.DataFatal(str(e))
        except utils.APIError as e:
            raise utils.APIFatal(str(e))

        # Start tracker
        if self.mediainfo.get('can_play') and self.config['tracker_enabled']:
            self.tracker = tracker.Tracker(self.msg,
                                   self._get_tracker_list(),
                                   self.config['tracker_process'],
                                   self.config['searchdir'],
                                   int(self.config['tracker_interval']),
                                   int(self.config['tracker_update_wait_s']),
                                   self.config['tracker_update_close'],
                                  )
            self.tracker.connect_signal('playing', self._tracker_playing)
            self.tracker.connect_signal('update', self._tracker_update)

        self.loaded = True
        return True

    def unload(self):
        """
        Closes the data handler and closes the engine cleanly.
        This should be called when closing the client application, or when you're
        sure you're not going to use the engine anymore. This does all the necessary
        procedures to close the data handler cleanly and then itself.

        """
        if self.loaded:
            self.msg.info(self.name, "Unloading...")
            self.data_handler.unload()

            self.loaded = False

    def reload(self, account=None, mediatype=None):
        """Changes the API and/or mediatype and reloads itself."""
        if self.loaded:
            self.unload()

        if account:
            self._load(account)

        self._init_data_handler(mediatype)
        self.start()

    def get_config(self, key):
        """Returns the specified key from the configuration."""
        return self.config[key]

    def get_userconfig(self, key):
        return self.data_handler.userconfig[key]

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

    def get_list(self):
        """
        Returns the full show list requested from the data handler as a list of show dictionaries.
        If you only need shows in a specified status, use :func:`filter_list`.
        """
        return self.data_handler.get().values()

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
        for k, show in showdict.items():
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
        return list(v for k, v in showlist.items() if re.match(regex, v['title'], re.I))

    def regex_list_titles(self, pattern):
        # TODO : Temporal hack for the client autocomplete function
        showlist = self.data_handler.get()
        newlist = list()
        for k, v in showlist.items():
            if re.match(pattern, v['title'], re.I):
                if ' ' in v['title']:
                    newlist.append('"' + v['title'] + '" ')
                else:
                    newlist.append(v['title'] + ' ')

        return newlist

    def search(self, criteria):
        """
        Request a remote list of shows matching the criteria
        and returns it as a list of show dictionaries.
        This is useful to add a show.
        """
        return self.data_handler.search(str(criteria).strip())

    def add_show(self, show, status=None):
        """
        Adds **show** to the list and queues the list update
        for the next sync.
        """
        # Check if operation is supported by the API
        if not self.mediainfo.get('can_add'):
            raise utils.EngineError('Operation not supported by API.')

        # Set to the requested status
        if status:
            if status not in self.mediainfo['statuses']:
                raise utils.EngineError('Invalid status.')

            show['my_status'] = status

        # Add in data handler
        self.data_handler.queue_add(show)

        # Update the tracker with the new information
        self._update_tracker()

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
        if (show['total'] and newep > show['total']) or newep < 0:
            raise utils.EngineError('Episode out of limits.')
        if show['my_progress'] == newep:
            raise utils.EngineError("Show already at episode %d" % newep)

        # Change episode
        self.msg.info(self.name, "Updating show %s to episode %d..." % (show['title'], newep))
        self.data_handler.queue_update(show, 'my_progress', newep)

        # Emit signal
        self._emit_signal('episode_changed', show)

        # Change status if required
        if self.config['auto_status_change'] and self.mediainfo.get('can_status'):
            try:
                if newep == show['total'] and self.mediainfo.get('status_finish'):
                    if (
                        not self.config['auto_status_change_if_scored'] or
                        not self.mediainfo.get('can_score') or
                        show['my_score']
                    ):
                        # Change to finished status
                        self.set_status(show['id'], self.mediainfo['status_finish'])
                    else:
                        self.msg.warn(self.name, "Updated episode but status won't be changed until a score is set.")
                elif newep == 1 and self.mediainfo.get('status_start'):
                    # Change to watching status
                    self.set_status(show['id'], self.mediainfo['status_start'])
            except utils.EngineError as e:
                # Only warn about engine errors since status change here is not crtical
                self.msg.warn(self.name, 'Updated episode but status wasn\'t changed: %s' % e)

        # Change dates if required
        if self.config['auto_date_change'] and self.mediainfo.get('can_date'):
            start_date = finish_date = None

            try:
                if newep == 1:
                    start_date = datetime.date.today()
                if newep == show['total']:
                    finish_date = datetime.date.today()

                self.set_dates(show['id'], start_date, finish_date)
            except utils.EngineError as e:
                # Only warn about engine errors since date change here is not crtical
                self.msg.warn(self.name, 'Updated episode but dates weren\'t changed: %s' % e)

        # Clear neweps flag
        if self.data_handler.get_show_attr(show, 'neweps'):
            self.data_handler.set_show_attr(show, 'neweps', False)

        # Update the tracker with the new information
        self._update_tracker()

        return show

    def set_dates(self, showid, start_date=None, finish_date=None):
        """
        Updates the start date and finish date of a show.
        If any of the two are None, it won't be changed.
        """
        if not self.mediainfo.get('can_date'):
            raise utils.EngineError('Operation not supported by API.')

        show = self.get_show_info(showid)

        # Change the start date if required
        if start_date:
            if not isinstance(start_date, datetime.date):
                raise utils.EngineError('start_date must be a Date object.')
            self.data_handler.queue_update(show, 'my_start_date', start_date)

        if finish_date:
            if not isinstance(finish_date, datetime.date):
                raise utils.EngineError('finish_date must be a Date object.')
            self.data_handler.queue_update(show, 'my_finish_date', finish_date)

    def set_score(self, showid, newscore):
        """
        Updates the score of the specified **showid** to **newscore**
        and queues the list update for the next sync.
        """
        # Check if operation is supported by the API
        if not self.mediainfo.get('can_score'):
            raise utils.EngineError('Operation not supported by API.')

        # Check for the correctness of the score
        if (Decimal(str(newscore)) % Decimal(str(self.mediainfo['score_step']))) != 0:
            raise utils.EngineError('Invalid score.')

        # Convert to proper type
        if isinstance( self.mediainfo['score_step'], int ):
            newscore = int(newscore)
        else:
            newscore = float(newscore)

        # Get the show and update it
        show = self.get_show_info(showid)
        # More checks
        if newscore > self.mediainfo['score_max']:
            raise utils.EngineError('Score out of limits.')
        if show['my_score'] == newscore:
            raise utils.EngineError("Score already at %s" % newscore)

        # Change score
        self.msg.info(self.name, "Updating show %s to score %s..." % (show['title'], newscore))
        self.data_handler.queue_update(show, 'my_score', newscore)

        # Emit signal
        self._emit_signal('score_changed', show)

        # Change status if required
        if (
            show['total'] and
            show['my_progress'] == show['total'] and
            show['my_score'] and
            self.mediainfo.get('can_status') and
            self.config['auto_status_change'] and
            self.config['auto_status_change_if_scored'] and
            self.mediainfo.get('status_finish')
        ):
            try:
                self.set_status(show['id'], self.mediainfo['status_finish'])
            except utils.EngineError as e:
                # Only warn about engine errors since status change here is not crtical
                self.msg.warn(self.name, 'Updated episode but status wasn\'t changed: %s' % e)

        return show

    def set_status(self, showid, newstatus):
        """
        Updates the score of the specified **showid** to **newstatus** (number)
        and queues the list update for the next sync.
        """
        # Check if operation is supported by the API
        if not self.mediainfo.get('can_status'):
            raise utils.EngineError('Operation not supported by API.')

        try:
            newstatus = int(newstatus)
        except ValueError:
            pass # It's not necessary for it to be an int

        # Check if the status is valid
        _statuses = self.mediainfo['statuses_dict']
        if newstatus not in _statuses.keys():
            raise utils.EngineError('Invalid status.')

        # Get the show and update it
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

    def set_tags(self, showid, newtags):
        """
        Updates the tags of the specified **showid** to **newtags**
        and queues the list update for the next sync.
        """
        # Check if operation is supported by the API
        if 'can_tag' not in self.mediainfo or not self.mediainfo.get('can_tag'):
            raise utils.EngineError('Operation not supported by API.')

        # Get the show and update it
        show = self.get_show_info(showid)
        # More checks
        if show['my_tags'] == newtags:
            raise utils.EngineError("Tags already %s" % newtags)

        # Change score
        self.msg.info(self.name, "Updating show %s to tags '%s'..." % (show['title'], newtags))
        self.data_handler.queue_update(show, 'my_tags', newtags)

        # Emit signal
        self._emit_signal('tags_changed', show)

        return show

    def delete_show(self, show):
        """
        Deletes **show** completely from the list and queues the list update for the next sync.
        """
        if not self.mediainfo.get('can_delete'):
            raise utils.EngineError('Operation not supported by API.')

        # Add in data handler
        self.data_handler.queue_delete(show)

        # Update the tracker with the new information
        self._update_tracker()

        # Emit signal
        self._emit_signal('show_deleted', show)

    def _search_video(self, titles, episode):
        best_candidate = (None, 0, None)

        matcher = difflib.SequenceMatcher()

        # Check over video files and propose our best candidate
        for (fullpath, filename) in utils.regex_find_videos('mkv|mp4|avi', self.config['searchdir']):
            # Analyze what's the title and episode of the file
            aie = AnimeInfoExtractor(filename)
            candidate_title = aie.getName()
            candidate_episode_start, candidate_episode_end = aie.getEpisodeNumbers()

            # Skip this file if we couldn't analyze it
            if not candidate_title:
                continue
            if candidate_episode_start is None:
                continue

            # Skip this file if it isn't the episode we want
            if candidate_episode_end is None:
                if episode != candidate_episode_start:
                    continue
            else:
                if not (candidate_episode_start <= episode <= candidate_episode_end):
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
                    best_candidate = (fullpath, ratio, aie.getEpisode())

        return best_candidate[0], best_candidate[2]

    def get_new_episodes(self, showlist):
        results = list()
        total = len(showlist)
        t = time.time()

        for i, show in enumerate(showlist):
            self.msg.info(self.name, "Searching %d/%d..." % (i+1, total))

            titles = self.data_handler.get_show_titles(show)

            (filename, ep) = self._search_video(titles, show['my_progress']+1)
            if filename:
                self.data_handler.set_show_attr(show, 'neweps', True)
                results.append(show)

        self.msg.info(self.name, "Time: %s" % (time.time() - t))
        return results

    def library(self):
        return self.data_handler.library_get()

    def scan_library(self, my_status=None, ignorecache=False):
        # Check if operation is supported by the API
        if not self.mediainfo.get('can_play'):
            raise utils.EngineError('Operation not supported by current site or mediatype.')
        if not self.config['searchdir']:
            raise utils.EngineError('Media directory is not set.')
        if not utils.dir_exists(self.config['searchdir']):
            raise utils.EngineError('The set media directory doesn\'t exist.')

        t = time.time()
        library = {}
        library_cache = self.data_handler.library_cache_get()

        if not my_status:
            my_status = self.mediainfo['status_start']

        self.msg.info(self.name, "Scanning local library...")
        tracker_list = self._get_tracker_list(my_status)

        # Do a full listing of the media directory
        for fullpath, filename in utils.regex_find_videos('mkv|mp4|avi', self.config['searchdir']):
            show_id = None
            if not ignorecache and filename in library_cache.keys():
                # If the filename was already seen before
                # use the cached information, if there's no information (None)
                # then it means it doesn't correspond to any show in the list
                # and can be safely skipped.
                if library_cache[filename]:
                    show_id = library_cache[filename][0]
                    show_ep = library_cache[filename][1]
                else:
                    continue
            else:
                # If the filename has not been seen, extract
                # the information from the filename and do a fuzzy search
                # on the user's list. Cache the information.
                # If it fails, cache it as None.
                aie = AnimeInfoExtractor(filename)
                (show_title, show_ep) = (aie.getName(), aie.getEpisode())
                if show_title:
                    show = utils.guess_show(show_title, tracker_list)
                    if show:
                        show_id = show['id']
                        library_cache[filename] = (show['id'], show_ep)
                    else:
                        library_cache[filename] = None
                else:
                    library_cache[filename] = None

            # After we got our information, add it to our library
            if show_id:
                if show_id not in library.keys():
                    library[show_id] = {}
                library[show_id][show_ep] = fullpath

        self.msg.debug(self.name, "Time: %s" % (time.time() - t))
        self.data_handler.library_save(library)
        self.data_handler.library_cache_save(library_cache)
        return library

    def play_random(self):
        """
        This function will pick a random show that has a new episode to watch
        and play it.
        """
        library = self.library()
        newep = []

        self.msg.info(self.name, 'Looking for random episode.')

        for showid, eps in library.items():
            show = self.get_show_info(showid)
            if show['my_progress'] + 1 in eps.keys():
                newep.append(show)


        if not newep:
            raise utils.EngineError('No new episodes found to pick from.')

        show = random.choice(newep)
        ep = self.play_episode(show)
        return (show, ep)

    def play_episode(self, show, playep=0):
        """
        Does a local search in the hard disk (in the folder specified by the config file)
        for the specified episode (**playep**) for the specified **show**.

        If no **playep** is specified, the next episode of the show will be played.
        """
        # Check if operation is supported by the API
        if not self.mediainfo.get('can_play'):
            raise utils.EngineError('Operation not supported by current site or mediatype.')
        if not self.config['searchdir']:
            raise utils.EngineError('Media directory is not set.')
        if not utils.dir_exists(self.config['searchdir']):
            raise utils.EngineError('The set media directory doesn\'t exist.')

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

            titles = self.data_handler.get_show_titles(show)

            filename, endep = self._search_video(titles, playep)
            if filename:
                self.msg.info(self.name, 'Found. Starting player...')
                arg_list = shlex.split(self.config['player'])
                arg_list.append(filename)
                try:
                    with open(os.devnull, 'wb') as DEVNULL:
                        subprocess.Popen(arg_list, stdout=DEVNULL, stderr=DEVNULL)
                except OSError:
                    raise utils.EngineError('Player not found, check your config.json')
                return endep
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

    def altnames(self):
        """
        Gets a dictionary of all set alternative names.
        """
        return self.data_handler.altnames_get()

    def filter_list(self, status_num):
        """
        Returns a show list with the shows in the specified **status_num** status.
        If you need a list with all the shows, use :func:`get_list`.
        """
        showlist = self.data_handler.get()
        return list(v for k, v in showlist.items() if v['my_status'] == status_num)

    def list_download(self):
        """Asks the data handler to download the remote list."""
        self.undoall()
        self.data_handler.download_data()
        self._update_tracker()

    def list_upload(self):
        """Asks the data handler to upload the unsynced changes in the queue."""
        result = self.data_handler.process_queue()
        #for show in result:
        #    self._emit_signal('episode_changed', show)

    def get_queue(self):
        """Asks the data handler for the items in the current queue."""
        return self.data_handler.queue


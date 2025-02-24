# This file is part of Trackma.
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

import datetime
import os
import random
import re
import shlex
import shutil
import sys
import time
from decimal import Decimal
from functools import lru_cache, partial
from pathlib import Path

from trackma import data
from trackma import messenger
from trackma import utils
from trackma.extras import redirections
from trackma.parser import get_parser_class


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
    redirections = None
    config = {}
    msg = None
    loaded = False
    playing = False
    hooks_available = []

    name = 'Engine'

    signals = {'show_added':        None,
               'show_deleted':      None,
               'episode_changed':   None,
               'score_changed':     None,
               'status_changed':    None,
               'show_synced':       None,
               'sync_complete':     None,
               'queue_changed':     None,
               'playing':           None,
               'prompt_for_update': None,
               'prompt_for_add':    None,
               'tracker_state':     None,
               'episode_missing': None,
               }

    def __init__(self, account=None, message_handler=None, accountnum=None):
        self.msg = messenger.Messenger(message_handler, self.name)

        # Utility parameter to get the account from the account manager
        if accountnum:
            from trackma import accounts
            account = accounts.AccountManager().get_account(accountnum)

        # Initialize
        self._load(account)
        self._init_data_handler()

    def _load(self, account):
        self.account = account

        # Create home directory
        utils.make_dir(utils.to_config_path())
        self.configfile = utils.to_config_path('config.json')

        # Create user directory
        userfolder = "%s.%s" % (account['username'], account['api'])
        utils.make_dir(utils.to_data_path(userfolder))

        self.msg.info('Trackma v{0} - using account {1}({2}).'.format(
            utils.VERSION, account['username'], account['api']))
        self.msg.info('Reading config files...')
        try:
            self.config = utils.parse_config(
                self.configfile, utils.config_defaults)
        except IOError:
            raise utils.EngineFatal("Couldn't open config file.")

        # Expand media directories and ignore those that don't exist
        if isinstance(self.config['searchdir'], str):
            # Compatibility: Turn a string of a single directory into a list
            self.msg.debug("Fixing string searchdir to list.")
            self.config['searchdir'] = [self.config['searchdir']]

        self.searchdirs = [path for path in utils.expand_paths(
            self.config['searchdir']) if self._searchdir_exists(path)]

    def _init_data_handler(self, mediatype=None):
        # Create data handler
        self.data_handler = data.Data(
            self.msg, self.config, self.account, mediatype)
        self.data_handler.connect_signal('show_synced', self._data_show_synced)
        self.data_handler.connect_signal(
            'sync_complete', self._data_sync_complete)
        self.data_handler.connect_signal(
            'queue_changed', self._data_queue_changed)

        # Record the API details
        (self.api_info, self.mediainfo) = self.data_handler.get_api_info()

    def _data_show_synced(self, show, changes):
        self._emit_signal('show_synced', show, changes)

    def _data_sync_complete(self, items):
        self._emit_signal('sync_complete', items)

    def _data_queue_changed(self, queue):
        self._emit_signal('queue_changed', queue)

    def _tracker_detected(self, path, filename):
        self.add_to_library(path, filename)

    def _tracker_removed(self, path, filename):
        self.remove_from_library(path, filename)

    def _tracker_playing(self, showid, playing, episode):
        show = self.get_show_info(showid)
        self._emit_signal('playing', show, playing, episode)

    def _tracker_update(self, show, episode):
        if self.config['tracker_update_prompt']:
            self.msg.info("Prompting for update.")
            self._emit_signal('prompt_for_update', show, episode)
        else:
            try:
                self.set_episode(show['id'], episode)
            except utils.TrackmaError as e:
                self.msg.warn("Can't update episode: {}".format(e))

    def _tracker_unrecognised(self, show, episode):
        if self.config['tracker_not_found_prompt']:
            self._emit_signal('prompt_for_add', show, episode)

    def _tracker_state(self, status):
        self._emit_signal('tracker_state', status)

    def _emit_signal(self, signal, *args):
        try:
            # Call the signal function
            if self.signals[signal]:
                self.signals[signal](*args)
        except AttributeError:
            pass

        # If there are loaded hooks, call the functions in all of them
        for module in self.hooks_available:
            method = getattr(module, signal, None)
            if method is not None:
                self.msg.debug("Calling hook {}:{}...".format(
                    module.__name__, signal))
                try:
                    method(self, *args)
                except Exception as err:
                    self.msg.warn("Exception on hook {}:{}: {}".format(
                        module.__name__, signal, err))

    def _get_tracker_list(self, filter_num=None):
        tracker_list = {}
        if isinstance(filter_num, type(None)):
            source_list = self.get_list()
        elif isinstance(filter_num, list):
            source_list = []
            for status in filter_num:
                if status is not self.mediainfo['statuses_finish']:
                    self.msg.debug("Scanning for "
                                   "{}".format(self.mediainfo['statuses_dict'][status]))
                    source_list = source_list + self.filter_list(status)
        else:
            source_list = self.filter_list(filter_num)

        for show in source_list:
            tracker_list[show['id']] = {
                'id': show['id'],
                'title': show['title'],
                'my_progress': show['my_progress'],
                'total': show['total'],
                'type': None,
                'titles': self.data_handler.get_show_titles(show),
            }

        altnames_map = self.data_handler.get_altnames_map()
        return (tracker_list, altnames_map)

    def _update_tracker(self):
        if self.tracker:
            self.tracker.update_list(self._get_tracker_list())

    def _cleanup(self):
        # If the engine wasn't closed for whatever reason, do it
        if self.loaded:
            self.msg.info("Forcing exit...")
            self.data_handler.unload(True)
            if self.tracker:
                self.tracker.disable()
            self.loaded = False

    def connect_signal(self, signal, callback):
        try:
            self.signals[signal] = callback
        except KeyError:
            raise utils.EngineFatal("Invalid signal.")

    def set_message_handler(self, message_handler):
        """Changes the message handler function on the fly."""
        self.msg = messenger.Messenger(message_handler, self.name)
        self.data_handler.set_message_handler(self.msg)

    def start(self):
        """
        Starts the engine.
        This function should be called before doing anything with the engine,
        as it initializes the data handler.
        """
        if self.loaded:
            raise utils.TrackmaError("Already loaded.")

        self.msg.debug("Starting engine...")

        # Start the data handler
        try:
            (self.api_info, self.mediainfo) = self.data_handler.start()
        except utils.DataError as e:
            raise utils.DataFatal(str(e))
        except utils.APIError as e:
            raise utils.APIFatal(str(e))

        # Load redirection file if supported
        api = self.api_info['shortname']
        mediatype = self.data_handler.userconfig['mediatype']
        if redirections.supports(api, mediatype):
            if utils.file_exists(utils.to_config_path('anime-relations.txt')):
                fname = utils.to_config_path('anime-relations.txt')
                self.msg.debug("Using user-provided redirection file.")
            else:
                fname = utils.to_data_path('anime-relations.txt')
                if self.config['redirections_time'] and (
                        not utils.file_exists(fname) or
                        utils.file_older_than(fname, self.config['redirections_time'] * 86400)):
                    self.msg.info("Syncing redirection file...")
                    self.msg.debug("Syncing from: %s" %
                                   self.config['redirections_url'])
                    utils.sync_file(fname, self.config['redirections_url'])

            if not utils.file_exists(fname):
                self.msg.debug("Defaulting to repo provided redirections file.")
                fname = utils.DATADIR + '/anime-relations/anime-relations.txt'

            self.msg.info("Parsing redirection file...")
            try:
                self.redirections = redirections.parse_anime_relations(
                    fname, api)
            except Exception as e:
                self.msg.warn("Error parsing anime-relations.txt!")
                self.msg.debug("{}".format(e))

        # Determine parser library
        try:
            self.msg.debug(self.name, "Initializing parser...")
            self.parser_class = get_parser_class(self.msg, self.config['title_parser'])
        except ImportError as e:
            self.msg.warn(self.name, "Couldn't import specified parser: {}; {}".format(
                self.config['title_parser'], e))

        # Rescan library if necessary
        if self.config['library_autoscan']:
            try:
                self.scan_library()
            except utils.TrackmaError as e:
                self.msg.warn("Can't auto-scan library: {}".format(e))

        # Load hook files
        if self.config['use_hooks']:
            hooks_dir = utils.to_config_path('hooks')
            if os.path.isdir(hooks_dir):
                import pkgutil
                import importlib

                self.msg.info("Importing user hooks...")
                for loader, name, ispkg in pkgutil.iter_modules([hooks_dir]):
                    # List all the hook files in the hooks folder, import them
                    # and call the init() function if they have them
                    # We build the list "hooks available" with the loaded modules
                    # for later calls.
                    try:
                        self.msg.debug("Importing hook {}...".format(name))
                        module = importlib.import_module(os.path.basename(hooks_dir) + '.' + name)
                        if hasattr(module, 'init'):
                            module.init(self)
                        self.hooks_available.append(module)
                    except ImportError:
                        self.msg.warn("Error importing hook {}.".format(name))
                        self.msg.exception(sys.exc_info())

        # Start tracker
        if self.mediainfo.get('can_play') and self.config['tracker_enabled']:
            self.msg.debug("Initializing tracker...")
            try:
                TrackerClass = self._get_tracker_class(
                    self.config['tracker_type'])

                self.tracker = TrackerClass(self.msg,
                                            self._get_tracker_list(),
                                            self.config,
                                            self.searchdirs,
                                            self.redirections,
                                            )
                self.tracker.connect_signal('detected', self._tracker_detected)
                self.tracker.connect_signal('removed', self._tracker_removed)
                self.tracker.connect_signal('playing', self._tracker_playing)
                self.tracker.connect_signal('update', self._tracker_update)
                self.tracker.connect_signal(
                    'unrecognised', self._tracker_unrecognised)
                self.tracker.connect_signal('state', self._tracker_state)
            except ImportError:
                self.msg.warn("Couldn't import specified tracker: {}".format(
                    self.config['tracker_type']))
                self.msg.exception(sys.exc_info())

        self.loaded = True
        self.msg.debug("Engine started")
        return True

    def unload(self):
        """
        Closes the data handler and closes the engine cleanly.
        This should be called when closing the client application, or when you're
        sure you're not going to use the engine anymore. This does all the necessary
        procedures to close the data handler cleanly and then itself.

        """
        if self.loaded:
            self.msg.info("Unloading...")
            self.data_handler.unload()
            if self.tracker:
                self.tracker.disable()

            # If there are loaded hooks, unload them
            self.msg.info("Unloading user hooks...")
            for module in self.hooks_available.copy():
                self.msg.debug("Unloading hook {}...".format(
                    module.__name__))
                try:
                    if hasattr(module, 'destroy'):
                        module.destroy(self)
                    self.hooks_available.remove(module)
                except Exception as err:
                    self.msg.warn("Error destroying hook {}: {}".format(
                        module.__name__, err))

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

    def get_show_info(self, showid=None, title=None, filename=None):
        """
        Returns the show dictionary for the specified **showid**.
        """
        showdict = self.data_handler.get()

        if showid:
            # Get show by ID
            try:
                return showdict[showid]
            except KeyError:
                raise utils.EngineError("Show not found.")
        elif title:
            showdict = self.data_handler.get()
            # Get show by title, slower
            for show in showdict.values():
                if show['title'] == title:
                    return show
            raise utils.EngineError("Show not found.")
        elif filename:
            # Guess show by filename
            self.msg.debug("Guessing by filename.")

            anime_info = self.parser_class(self.msg, filename)
            (show_title, ep) = anime_info.getName(), anime_info.getEpisode()
            self.msg.debug("Show guess: {}".format(show_title))

            if show_title:
                tracker_list = self._get_tracker_list()

                show = utils.guess_show(show_title, tracker_list)
                if show:
                    return utils.redirect_show((show, ep), self.redirections, tracker_list)
                else:
                    raise utils.EngineError("Show not found.")
            else:
                raise utils.EngineError("File name not recognized.")

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
        return list(v for k, v in showlist.items() if re.search(regex, v['title'], re.I))

    def regex_list_titles(self, pattern):
        # TODO : Temporal hack for the client autocomplete function
        showlist = self.data_handler.get()
        newlist = list()
        for v in showlist.values():
            if re.match(pattern, v['title'], re.I):
                if ' ' in v['title']:
                    newlist.append('"' + v['title'] + '" ')
                else:
                    newlist.append(v['title'] + ' ')

        return newlist

    def tracker_status(self):
        """
        Asks the tracker for its current status.
        """

        if self.tracker:
            return self.tracker.get_status()

        return None

    def search(self, criteria, method=utils.SearchMethod.KW):
        """
        Request a remote list of shows matching the criteria
        and returns it as a list of show dictionaries.
        This is useful to add a show.
        """
        if method not in self.mediainfo.get('search_methods', [utils.SearchMethod.KW]):
            raise utils.EngineError(
                'Search method not supported by API or mediatype.')

        return self.data_handler.search(criteria, method)

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
        self.msg.info("Updating show %s to episode %d..." %
                      (show['title'], newep))
        self.data_handler.queue_update(show, 'my_progress', newep)

        # Emit signal
        self._emit_signal('episode_changed', show)

        # Change status if required
        if self.config['auto_status_change'] and self.mediainfo.get('can_status'):
            try:
                if newep == show['total'] and self.mediainfo.get('statuses_finish'):
                    if (
                            not self.config['auto_status_change_if_scored'] or
                            not self.mediainfo.get('can_score') or
                            show['my_score']
                    ):
                        # Change to finished status
                        self.set_status(
                            show['id'], self._guess_new_finish(show))
                    else:
                        self.msg.warn("Updated episode but status won't be changed until a score is set.")
                elif newep == 1 and self.mediainfo.get('statuses_start'):
                    # Change to start status
                    self.set_status(show['id'], self._guess_new_start(show))
            except utils.EngineError as e:
                # Only warn about engine errors since status change here is not critical
                self.msg.warn('Updated episode but status wasn\'t changed: %s' % e)

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
                # Only warn about engine errors since date change here is not critical
                self.msg.warn('Updated episode but dates weren\'t changed: %s' % e)

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
        if isinstance(self.mediainfo['score_step'], int):
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
        self.msg.info("Updating show %s to score %s..." %
                      (show['title'], newscore))
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
                self.mediainfo.get('statuses_finish')
        ):
            try:
                self.set_status(show['id'], self._guess_new_finish(show))
            except utils.EngineError as e:
                # Only warn about engine errors since status change here is not critical
                self.msg.warn('Updated episode but status wasn\'t changed: %s' % e)

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
            pass  # It's not necessary for it to be an int

        # Check if the status is valid
        _statuses = self.mediainfo['statuses_dict']
        if newstatus not in _statuses:
            raise utils.EngineError('Invalid status.')

        # Get the show and update it
        show = self.get_show_info(showid)
        # More checks
        if show['my_status'] == newstatus:
            raise utils.EngineError("Show already in %s." %
                                    _statuses[newstatus])

        # Change status
        old_status = show['my_status']
        self.msg.info("Updating show %s status to %s..." %
                      (show['title'], _statuses[newstatus]))
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
        self.msg.info("Updating show %s to tags '%s'..." %
                      (show['title'], newtags))
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

    def library(self):
        return self.data_handler.library_get()

    def scan_library(self, my_status=None, rescan=False, path=None):
        # Check if operation is supported by the API
        if not self.mediainfo.get('can_play'):
            raise utils.EngineError(
                'Operation not supported by current site or mediatype.')
        if not self.config['searchdir']:
            raise utils.EngineError('Media directories not set.')

        t = time.time()
        library = {}
        library_cache = self.data_handler.library_cache_get()

        if not my_status:
            if self.config['scan_whole_list']:
                my_status = self.mediainfo['statuses']
            else:
                my_status = self.mediainfo.get(
                    'statuses_library', self.mediainfo['statuses_start'])

        if rescan:
            self.msg.info("Scanning local library (overriding cache)...")
        else:
            self.msg.info("Scanning local library...")

        tracker_list = self._get_tracker_list(my_status)
        guess_show = lru_cache(partial(utils.guess_show, tracker_list=tracker_list))

        paths = [path] if path else self.searchdirs
        for searchdir in paths:
            self.msg.debug("Directory: %s" % searchdir)

            # Do a full listing of the media directory
            for fullpath, filename in utils.regex_find_videos(searchdir):
                if self.config['library_full_path']:
                    filename = self._get_relative_path_or_basename(searchdir, fullpath)
                (library, library_cache) = self._add_show_to_library(
                    library, library_cache, rescan, fullpath, filename, tracker_list, guess_show)

            self.msg.debug("Time: %s" % (time.time() - t))
            self.data_handler.library_save(library)
            self.data_handler.library_cache_save(library_cache)
        return library

    def remove_from_library(self, path, filename):
        library = self.data_handler.library_get()
        library_cache = self.data_handler.library_cache_get()
        tracker_list = self._get_tracker_list()
        fullpath = path+"/"+filename
        # Only remove if the filename matches library entry
        if filename in library_cache and library_cache[filename]:
            (show_id, show_ep) = library_cache[filename]
            if show_id and show_ep and show_id \
                    and library.get(show_id, {}).get(show_ep) == fullpath:
                self.msg.debug("File removed from local library: %s" % fullpath)
                library_cache.pop(filename, None)
                library[show_id].pop(show_ep, None)

    def add_to_library(self, path, filename, rescan=False):
        # The inotify tracker tells us when files are created in
        # or moved within our library directory, so we call this.
        library = self.data_handler.library_get()
        library_cache = self.data_handler.library_cache_get()
        tracker_list = self._get_tracker_list()
        fullpath = path+"/"+filename
        guess_show = partial(utils.guess_show, tracker_list=tracker_list)
        self._add_show_to_library(
            library, library_cache, rescan, fullpath, filename, tracker_list, guess_show)

    def _add_show_to_library(self, library, library_cache, rescan, fullpath, filename, tracker_list, guess_show):
        show_id = None
        if not rescan and filename in library_cache:
            # If the filename was already seen before
            # use the cached information, if there's no information (None)
            # then it means it doesn't correspond to any show in the list
            # and can be safely skipped.
            if library_cache[filename]:
                (show_id, show_ep) = library_cache[filename]
                if type(show_ep) is tuple:
                    (show_ep_start, show_ep_end) = show_ep
                else:
                    show_ep_start = show_ep_end = show_ep
            else:
                return library, library_cache
        else:
            # If the filename has not been seen, extract
            # the information from the filename and do a fuzzy search
            # on the user's list. Cache the information.
            # If it fails, cache it as None.
            anime_info = self.parser_class(self.msg, filename)
            show_title = anime_info.getName()
            (show_ep_start, show_ep_end) = anime_info.getEpisodeNumbers(True)
            if show_title:
                show = guess_show(show_title)
                if show:
                    self.msg.debug("Adding to library: {}".format(fullpath))
                    self.msg.debug("Show guess: {}".format(show_title))

                    if show_ep_start == show_ep_end:
                        # TODO : Support redirections for episode ranges
                        (show, show_ep) = utils.redirect_show(
                            (show, show_ep_start), self.redirections, tracker_list)
                        show_ep_end = show_ep_start = show_ep

                        self.msg.debug("Redirected to: {} - {}".format(
                            show['title'], show_ep))
                        library_cache[filename] = (show['id'], show_ep)
                    else:
                        library_cache[filename] = (
                            show['id'], (show_ep_start, show_ep_end))

                    show_id = show['id']
                else:
                    self.msg.debug("Unable to match '{}', skipping: {}"
                                   .format(show_title, fullpath))
                    library_cache[filename] = None
            else:
                self.msg.debug("Not recognized, skipping: {}".format(fullpath))
                library_cache[filename] = None

        # After we got our information, add it to our library
        if show_id:
            if show_id not in library:
                library[show_id] = {}
            for show_ep in range(show_ep_start, show_ep_end+1):
                library[show_id][show_ep] = fullpath

        return library, library_cache

    def get_episode_path(self, show, episode=0):
        """
        This function returns the full path of the requested episode from the requested show.
        If the episode is unspecified, it will return any episode from the requested show.
        """
        library = self.library()
        showid = show['id']

        if showid not in library:
            raise utils.EngineError('Show not in library.')

        # Get the specified episode, otherwise get any if unspecified
        if episode:
            if episode not in library[showid]:
                raise utils.EngineError('Episode not in library.')
            return library[showid][episode]
        else:
            return next(iter(library[showid].values()))

    def play_random(self):
        """
        This function will pick a random show that has a new episode to watch
        and return the arguments to play it.
        """
        library = self.library()
        newep = []

        self.msg.info('Looking for random episode.')

        for showid, eps in library.items():
            try:
                show = self.get_show_info(showid)
            except utils.EngineError:
                continue # In library but not available
            if show['my_progress'] + 1 in eps:
                newep.append(show)

        if not newep:
            raise utils.EngineError('No new episodes found to pick from.')

        show = random.choice(newep)
        return self.play_episode(show)

    def play_episode(self, show, playep=0):
        """
        Does a local search in the hard disk (in the folder specified by the config file)
        for the specified episode (**playep**) for the specified **show**.

        If no **playep** is specified, the next episode of the show will be returned.
        """
        # Check if operation is supported by the API
        if not self.mediainfo.get('can_play'):
            raise utils.EngineError(
                'Operation not supported by current site or mediatype.')

        try:
            playep = int(playep)
        except ValueError:
            raise utils.EngineError('Episode must be numeric.')

        if not show:
            raise utils.EngineError('Show given is invalid')

        if playep <= 0:
            playep = show['my_progress'] + 1

        if show['total'] and playep > show['total']:
            raise utils.EngineError('Episode beyond limits.')

        self.msg.info("Getting '%s' episode '%s' from library..." %
                        (show['title'], playep))

        try:
            filename = self.get_episode_path(show, playep)
        except utils.EngineError:
            self.msg.info("Episode not found. Calling hooks...")
            self._emit_signal("episode_missing", show, playep)
            return []

        self.msg.info('Found. Starting player...')
        args = shlex.split(self.config['player'])

        if not args:
            raise utils.EngineError('Player not set up, check your config.json')

        args[0] = shutil.which(args[0])

        if not args[0]:
            raise utils.EngineError('Player not found, check your config.json')

        args.append(filename)
        return args

    def queue_clear(self):
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
                self.msg.info('Cleared alternate name.')
            else:
                self.data_handler.altname_set(showid, newname)
                self.msg.info('Changed alternate name to %s.' % newname)
            # Update the tracker with the new altname
            self._update_tracker()
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
        self.data_handler.queue_clear()
        self.data_handler.download_data()
        self._update_tracker()

    def list_upload(self):
        """Asks the data handler to upload the unsynced changes in the queue."""
        self.data_handler.process_queue()
        # for show in result:
        #    self._emit_signal('episode_changed', show)

    def get_queue(self):
        """Asks the data handler for the items in the current queue."""
        return self.data_handler.queue

    def _get_relative_path_or_basename(self, searchdir, fullpath):
        """Determine the path relative to a directory or the basename if not a sub-path.

        Used for including the folder name(s) for show detection.
        """
        path = Path(fullpath)
        try:
            return str(path.relative_to(searchdir))
        except ValueError:
            return path.basename

    def _searchdir_exists(self, path):
        """Variation of dir_exists that warns the user if the path doesn't exist."""
        if not utils.dir_exists(path):
            self.msg.warn("The specified media directory {} doesn't exist!".format(path))
            return False
        return True

    def _guess_new_finish(self, show):
        try:
            # Use corresponding finish status if we're already in a start status
            new_index = self.mediainfo['statuses_start'].index(
                show['my_status'])
            new_status = self.mediainfo['statuses_finish'][new_index]
        except ValueError:
            new_status = self.mediainfo['statuses_finish'][0]
        except IndexError:
            new_status = self.mediainfo['statuses_finish'][-1]

        return new_status

    def _guess_new_start(self, show):
        try:
            # Use following start status if we're already in a finish status
            new_index = self.mediainfo['statuses_finish'].index(
                show['my_status'])
            new_status = self.mediainfo['statuses_start'][new_index+1]
        except ValueError:
            new_status = self.mediainfo['statuses_start'][0]
        except IndexError:
            new_status = self.mediainfo['statuses_start'][-1]

        return new_status

    def _get_tracker_class(self, ttype):
        # Choose the tracker we want to start
        if ttype == 'plex':
            from trackma.tracker.plex import PlexTracker
            return PlexTracker
        if ttype == 'jellyfin':
            from trackma.tracker.jellyfin import JellyfinTracker
            return JellyfinTracker
        elif ttype == 'kodi':
            from trackma.tracker.kodi import KodiTracker
            return KodiTracker
        elif ttype == 'mpris':
            from trackma.tracker.mpris import MprisTracker
            return MprisTracker
        elif ttype == 'inotify_auto':
            try:
                return self._get_tracker_class('pyinotify')
            except ImportError:
                return self._get_tracker_class('inotify')
        elif ttype == 'pyinotify':
            from trackma.tracker.pyinotify import pyinotifyTracker
            return pyinotifyTracker
        elif ttype == 'inotify':
            from trackma.tracker.inotify import inotifyTracker
            return inotifyTracker
        elif ttype == 'win32':
            from trackma.tracker.win32 import Win32Tracker
            return Win32Tracker
        elif ttype == 'polling':
            from trackma.tracker.polling import PollingTracker
            return PollingTracker
        else:
            # Guess the working tracker
            if os.name == 'nt':
                return self._get_tracker_class('win32')

            # Try trackers in this order: pyinotify, inotify, polling
            try:
                return self._get_tracker_class('inotify_auto')
            except ImportError:
                return self._get_tracker_class('polling')

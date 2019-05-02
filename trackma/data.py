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

import os.path
import sys
import threading
import time

from trackma import utils

class Data:
    """
    Data Handler Class

    Class for keeping data in memory, handling list cache and
    update queues. This module cares about keeping the data
    safe and up to date, and it handles commands given by the engine,
    and communicates with the API whenever it's necessary.

    messenger: Messenger object to send useful messages to
    config: Parsed configuration dictionary (given by the engine)

    """
    name = 'Data'
    version = 6

    msg = None
    api = None
    showlist = None
    infocache = dict()
    queue = list()
    config = dict()
    meta = {'lastget': 0, 'lastsend': 0, 'version': '', 'apiversion': '', 'altnames': {}, 'library': {}, 'library_cache': {}, }

    autosend_timer = None

    signals = {
        'show_synced':       None,
        'sync_complete':     None,
        'queue_changed':     None,
    }

    def __init__(self, messenger, config, account, mediatype):
        """Checks if the config is correct and creates an API object."""
        self.msg = messenger
        self.config = config
        self.msg.info(self.name, "Initializing...")

        # Get filenames
        userfolder = "%s.%s" % (account['username'], account['api'])
        self.userconfig_file =  utils.to_data_path(userfolder, 'user.json')

        # Handle userconfig and media type to load
        self._load_userconfig()
        if mediatype:
            self.userconfig['mediatype'] = mediatype
            self._save_userconfig()

        # Import the API
        libbase = account['api']
        libname = "lib{0}".format(libbase)
        try:
            modulename = "trackma.lib.{0}".format(libname)
            __import__(modulename)
            apimodule = sys.modules[modulename]
        except ImportError as e:
            raise utils.DataFatal("Couldn't import API module: %s" % e)

        # Instance API
        libclass = getattr(apimodule, libname)
        self.api = libclass(self.msg, account, self.userconfig)

        # Get API version
        self.api_version = self.api.api_info['version']

        # Set mediatype
        mediatype = self.userconfig.get('mediatype')
        self.msg.info(self.name, "Using %s (%s)" % (libname, mediatype))

        # Get filenames
        self.queue_file = utils.to_data_path(userfolder, '%s.queue' % mediatype)
        self.info_file  = utils.to_data_path(userfolder,  '%s.info' % mediatype)
        self.cache_file = utils.to_data_path(userfolder, '%s.list' % mediatype)
        self.meta_file  = utils.to_data_path(userfolder, '%s.meta' % mediatype)
        self.lock_file  = utils.to_data_path(userfolder,  'lock')

        # Connect signals
        self.api.connect_signal('show_info_changed', self.info_update)
        self.api.connect_signal('userconfig_changed', self.userconfig_update)

    def _emit_signal(self, signal, *args):
        if self.signals[signal]:
            self.signals[signal](*args)

    def _is_queue_ready(self):
        # Checks if queue should be sent ASAP
        # Note: Hours setting is DEPRECATED!
        return (self.config['autosend'] == 'always' or
                (self.config['autosend'] == 'hours' and time.time() - self.meta['lastsend'] >= self.config['autosend_hours']*3600) or
                (self.config['autosend'] == 'minutes' and time.time() - self.meta['lastsend'] >= self.config['autosend_minutes']*60) or
                (self.config['autosend'] == 'size' and len(self.queue) >= self.config['autosend_size']))

    def connect_signal(self, signal, callback):
        try:
            self.signals[signal] = callback
        except KeyError:
            raise utils.DataFatal("Invalid signal.")

    def set_message_handler(self, message_handler):
        self.msg = message_handler
        self.api.set_message_handler(self.msg)

    def start(self):
        """
        Does all necessary tasks to start the data handler

        This should be called before doing any other operation with the data handler,
        as it loads the list cache (or downloads it if necessary) and queue.

        """
        # Lock the database
        self.msg.debug(self.name, "Locking database...")
        self._lock()

        # Load different caches
        if self._meta_exists():
            self._load_meta()

        if self._queue_exists() and self.meta.get('version') == self.version and self.meta.get('apiversion') == self.api_version:
            self._load_queue()
            self._emit_signal('queue_changed', self.queue)

        if self._info_exists() and self.meta.get('version') == self.version and self.meta.get('apiversion') == self.api_version:
            # Load info cache only if we're on the same database version
            self._load_info()

        # If there is a list cache, load from it
        # otherwise query the API for a remote list
        if self._cache_exists() and self.meta.get('version') == self.version and self.meta.get('apiversion') == self.api_version:
            # Auto-send: Process the queue if we're beyond the auto-send time limit for some reason
            if self._is_queue_ready():
                self.process_queue()

            # Auto-retrieve: Redownload list if any autoretrieve condition is met
            if (self.config['autoretrieve'] == 'always' or
               (self.config['autoretrieve'] == 'days' and
                time.time() - self.meta['lastget'] > self.config['autoretrieve_days'] * 84600) or
                self.meta.get('version') != self.version):
                try:
                    # Make sure we process the queue first before overwriting the list
                    # We don't want users losing their changes
                    self.process_queue()
                    self.download_data()
                except utils.APIError as e:
                    self.msg.warn(self.name, "Couldn't download list! Using cache.")
                    self._load_cache()
            elif not self.showlist:
                # If the cache wasn't loaded before, do it now
                self._load_cache()
        else:
            try:
                self.download_data()
            except utils.APIError as e:
                raise utils.APIFatal(str(e))

        # Create autosend thread if needed
        # Note: Hours setting is DEPRECATED!
        if self.config['autosend'] in ('minutes', 'hours'):
            self.autosend()

        return (self.api.api_info, self.api.media_info())

    def unload(self, force=False):
        """
        Does unloading of the data handler

        This should be called whenever the data handler won't be used anymore,
        as it does necessary operations to close the API and the data handler itself.

        """
        self.msg.debug(self.name, "Unloading...")

        # Cancel autosend thread
        if self.autosend_timer:
            self.autosend_timer.cancel()

        # We push changes if specified on config file
        if not force:
            if self.config['autosend_at_exit']:
                self.process_queue()

            self._save_meta()

        self._unlock()

    def get(self):
        """Get list from memory"""
        return self.showlist

    def search(self, criteria, method):
        # Tell API to search
        results = self.api.search(criteria, method)
        self.api.logout()
        if results:
            return results

        raise utils.DataError('No results.')

    def queue_add(self, show):
        """
        Queues a show add

        Calls this to add a show to the list, and the remote add
        will be queued.

        show: Show dictionary

        """
        showid = show['id']

        # Add to the list
        if self.showlist.get(showid):
            raise utils.DataError("Show already in the list.")

        self.showlist[showid] = show

        # Check if the show add is already in queue
        exists = False
        for q in self.queue:
            if q['id'] == showid and q['action'] == 'add':
                # This shouldn't happen
                raise utils.DataError("Show already in the queue.")

        if not exists:
            # Use the whole show as a queue item
            item = show
            item['action'] = 'add'
            self.queue.append(item)

        show['queued'] = True

        self._save_queue()
        self._save_cache()
        self._emit_signal('queue_changed', self.queue)
        self.msg.info(self.name, "Queued add for %s" % show['title'])

    def queue_update(self, show, key, value):
        """
        Queues a show update

        Call this to change anything of an item in the list, as it will be
        modified locally and queued for update in the next remote sync.

        show: Show dictionary
        key: The key that will be modified (it must exist beforehand)
        value: The value that it should be changed to
        """
        if key not in show:
            raise utils.DataError('Invalid key for queue update.')

        # Do update on memory
        show[key] = value

        # Check if the show update is already in queue
        exists = False
        for q in self.queue:
            if q['id'] == show['id'] and q['action'] in ['add', 'update']:
                # Add the changed value to the already existing queue item
                q[key] = value
                exists = True
                break

        if not exists:
            # Create queue item and append it
            item = {'id': show['id'],
                    'my_id': show['my_id'],
                    'action': 'update',
                    'title': show['title'],
                   }
            item[key] = value
            self.queue.append(item)
            
        show['queued'] = True

        self._save_queue()
        self._save_cache()
        self._emit_signal('queue_changed', self.queue)
        self.msg.info(self.name, "Queued update for %s" % show['title'])
        self.msg.debug(self.name, "Queued: {} -> {}".format(key, value))

        # Immediately process the action if necessary
        if self._is_queue_ready():
            self.process_queue()

    def queue_delete(self, show):
        """
        Queues a show delete

        Calls this to delete a show from the list, and the remote delete
        will be queued.

        show: Show dictionary

        """
        showid = show['id']

        # Delete from the list
        if not self.showlist.get(showid):
            raise utils.DataError("Show not in the list.")

        item = self.showlist.pop(showid)

        # Check if the show add is already in queue
        exists = False
        for q in self.queue:
            if q['id'] == showid and q['action'] == 'delete':
                # This shouldn't happen
                raise utils.DataError("Show delete already in the queue.")

        if not exists:
            # Use the whole show as a queue item
            item['action'] = 'delete'
            self.queue.append(item)

        show['queued'] = True

        self._save_queue()
        self._save_cache()
        self._emit_signal('queue_changed', self.queue)
        self.msg.info(self.name, "Queued delete for %s" % item['title'])

    def queue_clear(self):
        """Clears the queue completely."""
        if self.queue:
            self.queue = []
            self._save_queue()
            self._emit_signal('queue_changed', self.queue)
            self.msg.info(self.name, "Cleared queue.")

    def process_queue(self):
        """
        Send updates in queue to the API

        It starts sending all the queued updates to the API for it to update
        the remote list. Any successful updates get removed from the queue,
        and failed updates stay there to be processed the next time.

        """
        if self.queue:
            self.msg.info(self.name, 'Processing queue...')

            # Load the cache if it wasn't loaded for some reason
            if not self.showlist:
                self._load_cache()

            # Check log-in TODO
            #try:
            #    self.api.check_credentials()
            #except utils.APIError as e:
            #    raise utils.DataError("Can't process queue, will leave unsynced. Reason: %s" % e)

            # Run through queue
            items_processed = []
            items_failed = []
            while True:
                try:
                    item = self.queue.pop(0)
                except IndexError:
                    break

                showid = item['id']

                try:
                    show = self.showlist[showid]
                except KeyError:
                    show = None

                try:
                    # Call the API to do the requested operation
                    operation = item.get('action')
                    if operation == 'add':
                        my_id = self.api.add_show(item)

                        if my_id:
                            show['my_id'] = my_id
                    elif operation == 'update':
                        self.api.update_show(item)
                    elif operation == 'delete':
                        self.api.delete_show(item)
                    else:
                        self.msg.warn(self.name, "Unknown operation in queue (%s), skipping..." % repr(operation))

                    if self.showlist.get(showid):
                        self.showlist[showid]['queued'] = False
                        self._emit_signal('show_synced', show, item)

                    items_processed.append((show, item))
                    self._emit_signal('queue_changed', self.queue)
                except utils.APIError as e:
                    self.msg.warn(self.name, "Can't process %s, will leave unsynced." % item['title'])
                    self.msg.debug(self.name, "Info: %s" % e)
                    items_failed.append(item)
                except NotImplementedError:
                    self.msg.warn(self.name, "Operation not implemented in API. Skipping...")
                    items_failed.append(item)
                #except TypeError:
                #    self.msg.warn(self.name, "%s not in list, unexpected. Not changing queued status." % showid)

            if items_failed:
                self.queue += items_failed

            self.api.logout()
            self._save_cache()
            self._save_queue()
            self._emit_signal('sync_complete', items_processed)
        else:
            self.msg.debug(self.name, 'No items in queue.')

        self.meta['lastsend'] = time.time()

    def info_get(self, show):
        try:
            showid = show['id']
            return self.infocache[showid]
        except KeyError:
            return self.api.request_info([show])[0]

    def info_update(self, shows):
        for show in shows:
            showid = show['id']
            self.infocache[showid] = show

        self._save_info()

    def userconfig_update(self):
        self._save_userconfig()

    def altname_get(self, showid):
        return self.meta['altnames'].get(showid, '')

    def altname_set(self, showid, altname):
        self.meta['altnames'][showid] = altname

    def altname_clear(self, showid):
        if showid in self.meta['altnames']:
            del self.meta['altnames'][showid]

    def altnames_get(self):
        return self.meta['altnames']

    def library_get(self):
        return self.meta['library']

    def library_save(self, library):
        self.meta['library'] = library

    def library_cache_get(self):
        return self.meta['library_cache']

    def library_cache_save(self, library_cache):
        self.meta['library_cache'] = library_cache

    def get_show_attr(self, show, key):
        return show.get(key)

    def set_show_attr(self, show, key, value):
        show[key] = value

    def get_show_titles(self, show):
        return [show['title']] + show['aliases']

    def get_altnames_map(self):
        return {name.lower(): showid for showid, name in self.altnames_get().items()}

    def autosend(self):
        # Check if we should autosend now
        if self._is_queue_ready():
            self.process_queue()

        # Repeat check only if the settings are still on autosend
        # Note: Hours setting is DEPRECATED!
        if self.config['autosend'] in ('minutes', 'hours'):
            self.autosend_timer = threading.Timer(3600 if self.config['autosend'] == 'hours' else 60, self.autosend)
            self.autosend_timer.daemon = True
            self.autosend_timer.start()

    def _load_cache(self):
        self.msg.debug(self.name, "Reading cache...")
        self.showlist = utils.load_data(self.cache_file)

    def _save_cache(self):
        self.msg.debug(self.name, "Saving cache...")
        utils.save_data(self.showlist, self.cache_file)

    def _load_info(self):
        self.msg.debug(self.name, "Reading info DB...")
        self.infocache = utils.load_data(self.info_file)

    def _save_info(self):
        self.msg.debug(self.name, "Saving info DB...")
        utils.save_data(self.infocache, self.info_file)

    def _load_userconfig(self):
        self.msg.debug(self.name, "Reading userconfig...")
        self.userconfig = utils.parse_config(self.userconfig_file, utils.userconfig_defaults)

    def _save_userconfig(self):
        self.msg.debug(self.name, "Saving userconfig...")
        utils.save_config(self.userconfig, self.userconfig_file)

    def _load_queue(self):
        self.msg.debug(self.name, "Reading queue...")
        self.queue = utils.load_data(self.queue_file)

    def _save_queue(self):
        self.msg.debug(self.name, "Saving queue...")
        utils.save_data(self.queue, self.queue_file)

    def _load_meta(self):
        self.msg.debug(self.name, "Reading metadata...")
        loadedmeta = utils.load_data(self.meta_file)
        self.meta.update(loadedmeta)

    def _save_meta(self):
        self.msg.debug(self.name, "Saving metadata...")
        utils.save_data(self.meta, self.meta_file)

    def download_data(self):
        """Downloads the remote list and overwrites the cache"""
        self.showlist = self.api.fetch_list()

        if self.api.api_info['merge']:
            # The API needs information to be merged from the
            # info database
            missing = []
            for show in self.showlist.values():
                # Here we search the information in the local
                # info database. If it isn't available, add it
                # to the missing list for them to be requested
                # to the API later.
                showid = show['id']

                try:
                    info = self.infocache[showid]
                except KeyError:
                    missing.append(show)
                    continue

                self.api.merge(show, info)

            # Here we request the missing items and merge them
            # immedately with the list.
            if missing:
                infos = self.api.request_info(missing)
                for info in infos:
                    showid = info['id']
                    self.api.merge(self.showlist[showid], info)

        self._save_cache()
        self.api.logout()

        # Update last retrieved time
        self.meta['lastget'] = time.time()
        self.meta['version'] = self.version
        self.meta['apiversion'] = self.api_version
        self._save_meta()

    def _cache_exists(self):
        return os.path.isfile(self.cache_file)

    def _info_exists(self):
        return os.path.isfile(self.info_file)

    def _queue_exists(self):
        return os.path.isfile(self.queue_file)

    def _meta_exists(self):
        return os.path.isfile(self.meta_file)

    def _lock(self):
        """Creates the database lock, returns an exception if it
        already exists"""
        if self.config['debug_disable_lock']:
            return

        if os.path.isfile(self.lock_file):
            raise utils.DataFatal("Database is locked by another process. "
                                  "If you\'re sure there's no other process is using it, "
                                  "remove the file ~/.trackma/lock")

        f = open(self.lock_file, 'w')
        f.close()

    def _unlock(self):
        """Removes the database lock"""
        if self.config['debug_disable_lock']:
            return

        os.unlink(self.lock_file)

    def get_api_info(self):
        return (self.api.api_info, self.api.media_info())

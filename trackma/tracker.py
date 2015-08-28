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

import subprocess
import threading
import re
import time
import os
from decimal import Decimal
import difflib

import trackma.lib.libplex as libplex
import messenger
import utils

inotify_available = False

STATE_PLAYING = 0
STATE_NOVIDEO = 1
STATE_UNRECOGNIZED = 2
STATE_NOT_FOUND = 3

try:
    import inotifyx
    inotify_available = True
except ImportError:
    pass # If we ignore this the tracker will just use lsof

class AnimeInfoExtractor(object):
    """
    Extracts lots of information about anime from filename alone
    @author: Tyris
    @author: Uriziel
    @note: Thanks for Tyris for providing easy way to extract data
    @note: Does more than what's needed, but that behaviour is well tested
    """
    def __init__(self, filename):
        self.originalFilename = filename
        self.resolution = ''
        self.hash = ''
        self.subberTag = ''
        self.videoType = []
        self.audioType = []
        self.releaseSource = []
        self.extension = ''
        self.episodeStart = ''
        self.episodeEnd = ''
        self.volumeStart = ''
        self.volumeEnd = ''
        self.version = 1
        self.name = ''
        self.pv = -1
        self._processFilename()

    def getName(self):
        return self.name

    def getEpisodeNumbers(self):
        return self.episodeStart, self.episodeEnd

    def getEpisode(self):
        ep = self.episodeStart if self.episodeEnd == '' else self.episodeEnd
        ep = ep if ep != '' else '1'

        return int(ep)

    def __extractExtension(self, filename):
        m = re.search("\.(\w{3})$", filename)
        if m:
            self.extension = m.group(1)
            filename = filename[:-4]
        return filename

    def __cleanUpSpaces(self, filename):
        filename = filename.replace('_', ' ')
        if not ' ' in filename:
            filename = re.sub('([^.])\.([^.])', r'\1 \2', filename)
            # to handle .-. case (where - is any single chara)
            filename = re.sub('([^.])\.([^.])', r'\1 \2', filename)
            # If there are still no spaces try replacing hyphens with spaces
            if not ' ' in filename:
                filename = re.sub('([^\-])-([^\-])', r'\1 \2', filename)
                # to handle -.- case (where . is any single chara)
                filename = re.sub('([^\-])-([^\-])', r'\1 \2', filename)
        return filename

    def __extractSpecialTags(self, filename):
        tags = {'video': ['H264', 'H.264', 'x264', 'XviD', 'DivX', 'MP4'],
            'audio': ['AC3', 'AAC', 'MP3', 'FLAC'],
            'source': ['TV', 'DVD', 'BluRay', 'BD', 'Blu-Ray', 'BDMV']}
        for k, v in tags.iteritems():
            for tag in v:
                m = re.search('(?:[\(\[](?:|[^\)\]]*?[^0-9a-zA-Z\)\]]))(' + tag + ')(?:[^0-9a-zA-Z]|$)', filename, flags=re.IGNORECASE)
                if m:
                    if (k == 'video'):
                        self.videoType.append(tag)
                    elif (k == 'audio'):
                        self.audioType.append(tag)
                    elif (k == 'source'):
                        self.releaseSource.append(tag)
                    filename = filename[:m.start(1)] + '###NO#SUBBER#HERE###' + filename[m.end(1):]  # remove the match
        return filename

    def __extractVideoProfile(self, filename):
        # Check for 8bit/10bit
        tags_10bit = ['Hi10P', 'Hi10', '10bit', '10 bit', '10-bit']
        tags_8bit = ['8bit', '8-bit']
        for tag in tags_10bit:
            if tag in filename:
                self.videoType = ['H264', 'Hi10P']
                # Don't replace Hi10 coz its a subber name
                if tag != 'Hi10':
                    filename = filename.replace(tag, '')
                return filename
        if not self.videoType == ['H264', 'Hi10P']:
            for tag in tags_8bit:
                if tag in filename:
                    self.videoType = ['H264', '8bit']
                    filename = filename.replace(tag, '')
                    return filename
        return filename

    def __extractResolution(self, filename):
        # Match 3 or 4 chars followed by p, i, or x and 3 or 4 more chars, surrounded by any non-alphanumberic chars
        m = re.search('(?:[^0-9a-zA-Z])(\d{3,4}(?:p|i|x\d{3,4}))(?:[^0-9a-zA-Z]|$)', filename)
        if m:
            self.resolution = m.group(1)
            filename = filename[:m.start(1)] + filename[m.end(1):]
        else:
            m = re.search('(?:\[|\(|\d)(HD|SD)(?:\]|\)| |\.)', filename)
            if m:
                self.resolution = m.group(1)
                filename = filename[:m.start(1)] + filename[m.end(1):]
            else:
                m = re.search('(?:\d{1,3})(HD|SD)(?:[^a-zA-Z])', filename)
                if m:
                    self.resolution = m.group(1)
                    filename = filename[:m.start(1)] + filename[m.end(1):]  # Super special case for HD/SD imediately after episode
        return filename

    def __extractHash(self, filename):
        # Match anything in square or round brackets that is 8 hex digits
        m = re.search('(?:\[|\()((?:[A-F]|[a-f]|\d){8})(?:\]|\))', filename)
        if m:
            self.hash = m.group(1)
            filename = filename[:m.start()] + filename[m.end():]
        return filename

    def __checkIfRemux(self, filename):
        m = re.search('(?:[\(\[][^\)\]]*?[^0-9a-zA-Z\)\]]?)(Remux)(?:[^0-9a-zA-Z]|$)', filename, flags=re.IGNORECASE)
        return True if m else False

    def __cleanUpBrackets(self, filename):
        # Can get rid of the brackets that won't contain subber
        filename = re.sub('\((?:[^\)]*?)###NO#SUBBER#HERE##(?:.*?)\)', '', filename)
        filename = re.sub('\[(?:[^\]]*?)###NO#SUBBER#HERE##(?:.*?)\]', '', filename)
        # Strip any empty sets of brackets
        filename = re.sub('(?:\[(?:[^0-9a-zA-Z]*?)\])|(?:\((?:[^0-9a-zA-Z]*?)\))', ' ', filename)
        return filename

    def __extractSubber(self, filename, remux):
        # Extract the subber from square brackets (or round failing that)
        m = re.search('\[([^\. ].*?)\]', filename)
        if m:
            self.subberTag = m.group(1)
            filename = filename[:m.start()] + filename[m.end():]
        else:
            m = re.search('\(([^\. ].*?)\)', filename)
            if m:
                self.subberTag = m.group(1)
                filename = filename[:m.start()] + filename[m.end():]
            else:
                m = re.search('{([^\. ].*?)}', filename)
                if m:
                    self.subberTag = m.group(1)
                    filename = filename[:m.start()] + filename[m.end():]
        self.subberTag = self.subberTag.strip(' -')
        # Add the remux string if this was a remux and its not found in the subber tag
        if remux and not 'remux' in self.subberTag.lower():
            # refind remux and remove it
            m = re.search('(?:[\(\[][^\)\]]*?[^0-9a-zA-Z\)\]]?)(Remux)(?:[^0-9a-zA-Z]|$)', filename, flags=re.IGNORECASE)
            if m:
                filename = filename[:m.start(1)] + filename[m.end(1):]
            if self.subberTag:
                self.subberTag = self.subberTag + '-Remux'
            else:
                self.subberTag = 'Remux'
        return filename

    def __extractVersion(self, filename):
        # Extract the version number (limit at v7 since V8 is possible in a title...)
        m = re.search('(?:[^a-zA-Z])v([0-7])(?:[^0-9a-zA-Z]|$)', filename, flags=re.IGNORECASE)
        if m:
            self.version = int(m.group(1))
            filename = filename[:m.start(1) - 1] + filename[m.end(1):]
        return filename

    def __extractVolumeIfPack(self, filename, title_len):
    # Check if this is a volume pack - only relevant for no extension
        if not self.extension:
            m = re.search('[^0-9a-zA-Z](?:vol(?:ume)?\.? ?)(\d{1,3})(?: ?- ?(?:vol(?:ume)?\.? ?)?(\d{1,3}))?(?:[^0-9a-zA-Z]|$)', filename, flags=re.IGNORECASE)
            if m:
                self.volumeStart = int(m.group(1))
                if m.group(2):
                    self.volumeEnd = int(m.group(2))
                filename = filename[:m.start()] + filename[m.end():]
                title_len = m.start()
        return filename, title_len

    def __extractPv(self, filename):
        # Check if this is a PV release (not relevant if its a pack)
        m = re.search(' PV ?(\d)?(?:[^a-zA-Z0-9]|$)', filename)
        if not self.volumeStart and m:
            self.pv = 0
            if m.group(1):
                self.pv = int(m.group(1))
            filename = filename[:m.start(0)]
        return filename

    def __extractEpisodeNumbers(self, filename):
        # First check for concurrent episodes (with a +)
        m = re.search('[^0-9a-zA-Z](?:E\.?|Ep(?:i|isode)?s?(?: |\.)?)?(\d{1,4})\+(\d{1,4})(?:[^0-9a-zA-Z]|$)', filename, flags=re.IGNORECASE)
        if m:
            start = int(m.group(1))
            end = int(m.group(2))
            if end == start + 1:
                self.episodeStart = start
                self.episodeEnd = end
                filename = filename[:m.start() + 1]
        if not self.episodeStart:
            # Check for multiple episodes
            if self.extension:
                # no spaces allowed around the hyphen
                ep_search_string = '[^0-9a-zA-Z](?:E\.?|Ep(?:i|isode)?(?: |\.)?)?((?:\d{1,3}|1[0-8]\d{2})(?:\.\d{1})?)-(\d{1,4}(?:\.\d{1})?)(?:[^0-9a-zA-Z]|$)'
            else:
                ep_search_string = '[^0-9a-zA-Z](?:E\.?|Ep(?:i|isode)?(?: |\.)?)?((?:\d{1,3}|1[0-8]\d{2})(?:\.\d{1})?) ?- ?(\d{1,4}(?:\.\d{1})?)(?:[^0-9a-zA-Z]|$)'  # probably a pack... so allow spaces around the hyphen
            m = re.search(ep_search_string, filename, flags=re.IGNORECASE)
            if m:
                self.episodeStart = Decimal(m.group(1))
                self.episodeEnd = Decimal(m.group(2))
                filename = filename[:m.start() + 1]
        if not self.episodeStart:
            # Check if there is an episode specifier
            m = re.search('(?:[^0-9a-zA-Z])(E\.?|Ep(?:i|isode)?(?: |\.)?)(\d{1,}(?:\.\d{1})?)(?:[^\d]|$)', filename, flags=re.IGNORECASE)
            if m:
                self.episodeStart = Decimal(m.group(2))
                filename = filename[:m.start() + 1]
        if not self.episodeStart:
            # Check any remaining lonely numbers as episode (towards the end has priority)
            # First try outside brackets
            m = re.search('(?:.*)(?:[^0-9a-zA-Z\.])((?:\d{1,3}|1[0-8]\d{2})(?:\.\d{1})?)(?:[^0-9a-zA-Z]|$)', filename)
            if m:
                self.episodeStart = Decimal(m.group(1))
                filename = filename[:m.start(1)]
        if not self.episodeStart:
            # then allow brackets
            m = re.search('(?:.*)(?:[^0-9a-zA-Z\.\[\(])((?:\d{1,3}|1[0-8]\d{2})(?:\.\d{1})?)(?:[^0-9a-zA-Z\]\)]|$)', filename)
            if m:
                self.episodeStart = Decimal(m.group(1))
                filename = filename[:m.start(1)]
        return filename

    def __extractShowName(self, filename):
        # Unfortunately its very hard to know if there should be brackets in the title...
        # We really should strip brackets... so to anything with brackets in the title: sorry =(
        # Strip anything thats still in brackets, but backup the first case incase it IS the title...
        m = re.search('\[([^\. ].*?)\]', filename)
        backup_title = ''
        if m:
            backup_title = m.group(1)
            filename = filename[:m.start()] + filename[m.end():]
        else:
            m = re.search('\(([^\. ].*?)\)', filename)
            if m:
                backup_title = m.group(1)
                filename = filename[:m.start()] + filename[m.end():]
            else:
                m = re.search('{([^\. ].*?)}', filename)
                if m:
                    backup_title = m.group(1)
                    filename = filename[:m.start()] + filename[m.end():]
        filename = re.sub('(?:\[.*?\])|(?:\(.*?\))', ' ', filename)
        filename = filename.strip(' -')
        filename = re.sub('  (?:.*)', '', filename)
        # Strip any unclosed brackets and anything after them
        filename = re.sub('(.*)(?:[\(\[({].*)$', r'\1', filename)
        self.name = filename.strip(' -')
        if self.name == '':
            self.name = backup_title
        # If we have a subber but no title!? then it must have been a title...
        if self.name == '' and self.subberTag != '':
            self.name = self.subberTag
            self.subberTag = ''

    def _processFilename(self):
        filename = self.originalFilename
        filename = self.__extractExtension(filename)
        filename = self.__cleanUpSpaces(filename)
        filename = self.__extractSpecialTags(filename)
        filename = self.__extractVideoProfile(filename)
        filename = self.__extractResolution(filename)
        filename = self.__extractHash(filename)
        remux = self.__checkIfRemux(filename)
        filename = self.__cleanUpBrackets(filename)
        filename = self.__extractSubber(filename, remux)
        filename = self.__extractVersion(filename)
        # Store the possible length of the title
        title_len = len(filename)
        filename, title_len = self.__extractVolumeIfPack(filename, title_len)
        filename = self.__extractPv(filename)
        if self.pv == -1:
            filename = self.__extractEpisodeNumbers(filename)
        # Truncate remainder to title length if needed (for where volume was found)
        filename = filename[:title_len]
        # Strip any trailing opening brackets
        filename = filename.rstrip('([{')
        self.__extractShowName(filename)


class Tracker(object):
    msg = None
    active = True
    list = None
    last_show_tuple = None
    last_filename = None
    last_state = STATE_NOVIDEO
    last_time = 0
    last_updated = False
    last_close_queue = False
    plex_enabled = False
    plex_log = [None, None]

    name = 'Tracker'

    signals = { 'playing' : None,
                 'update': None, }

    def __init__(self, messenger, tracker_list, process_name, watch_dir, interval, update_wait, update_close):
        self.msg = messenger
        self.msg.info(self.name, 'Initializing...')

        self.list = tracker_list
        self.process_name = process_name
        self.plex_enabled = libplex.get_config()[0]

        tracker_args = (watch_dir, interval)
        #self.wait_s = update_wait * 60
        self.wait_s = 5
        self.wait_close = update_close
        tracker_t = threading.Thread(target=self._tracker, args=tracker_args)
        tracker_t.daemon = True
        self.msg.debug(self.name, 'Enabling tracker...')
        tracker_t.start()

    def set_message_handler(self, message_handler):
        """Changes the message handler function on the fly."""
        self.msg = message_handler

    def disable(self):
        self.active = False

    def enable(self):
        self.active = True

    def update_list(self, tracker_list):
        self.list = tracker_list

    def connect_signal(self, signal, callback):
        try:
            self.signals[signal] = callback
        except KeyError:
            raise utils.EngineFatal("Invalid signal.")

    def _emit_signal(self, signal, *args):
        try:
            if self.signals[signal]:
                self.signals[signal](*args)
        except KeyError:
            raise Exception("Call to undefined signal.")

    def _get_playing_file(self, players):
        try:
            lsof = subprocess.Popen(['lsof', '-n', '-c', ''.join(['/', players, '/']), '-Fn'], stdout=subprocess.PIPE)
        except OSError:
            self.msg.warn(self.name, "Couldn't execute lsof. Disabling tracker.")
            self.disable()
            return False

        output = lsof.communicate()[0].decode('utf-8')
        fileregex = re.compile("n(.*(\.mkv|\.mp4|\.avi))")

        for line in output.splitlines():
            match = fileregex.match(line)
            if match is not None:
                return os.path.basename(match.group(1))

        return False

    def _get_plex_file(self):
        playing_file = libplex.playing_file()
        return playing_file

    def _inotify_watch_recursive(self, fd, watch_dir):
        self.msg.debug(self.name, 'inotify: Watching %s' % watch_dir)
        inotifyx.add_watch(fd, watch_dir.encode('utf-8'), inotifyx.IN_OPEN | inotifyx.IN_CLOSE)

        for root, dirs, files in os.walk(watch_dir):
            for dir_ in dirs:
                self._inotify_watch_recursive(fd, os.path.join(root, dir_))

    def _observe_inotify(self, watch_dir):
        self.msg.info(self.name, 'Using inotify.')

        timeout = -1
        fd = inotifyx.init()
        try:
            self._inotify_watch_recursive(fd, watch_dir)
            while True:
                events = inotifyx.get_events(fd, timeout)
                if events:
                    for event in events:
                        if not event.mask & inotifyx.IN_ISDIR:
                            (state, show_tuple) = self._get_playing_show()
                            self.update_show_if_needed(state, show_tuple)

                            if self.last_state == STATE_NOVIDEO:
                                # Make get_events block indifinitely
                                timeout = -1
                            else:
                                timeout = 1
                else:
                    self.update_show_if_needed(self.last_state, self.last_show_tuple)
        except IOError:
            self.msg.warn(self.name, 'Watch directory not found! Tracker will stop.')
        finally:
            os.close(fd)

    def _observe_polling(self, interval):
        self.msg.warn(self.name, "inotifyx not available; using polling (slow).")
        while True:
            # This runs the tracker and update the playing show if necessary
            (state, show_tuple) = self._get_playing_show()
            self.update_show_if_needed(state, show_tuple)

            # Wait for the interval before running check again
            time.sleep(interval)

    def _observe_plex(self, interval):
        self.msg.info(self.name, "Tracking Plex.")

        while True:
            # This stores the last two states of the plex server and only
            # updates if it's ACTIVE.
            plex_status = libplex.status()
            self.plex_log.append(plex_status)

            if self.plex_log[-1] == "ACTIVE" or self.plex_log[-1] == "IDLE":
                self.wait_s = libplex.timer_from_file()
                (state, show_tuple) = self._get_playing_show()
                self.update_show_if_needed(state, show_tuple)
            elif (self.plex_log[-2] != "NOT_RUNNING" and self.plex_log[-1] == "NOT_RUNNING"):
                self.msg.warn(self.name, "Plex Media Server is not running.")

            del self.plex_log[0]
            # Wait for the interval before running check again
            time.sleep(30)

    def _tracker(self, watch_dir, interval):
        if self.plex_enabled:
            self._observe_plex(interval)
        else:
            if inotify_available:
                self._observe_inotify(watch_dir)
            else:
                self._observe_polling(interval)

    def update_show_if_needed(self, state, show_tuple):
        if show_tuple:
            (show, episode) = show_tuple

            if not self.last_show_tuple or show['id'] != self.last_show_tuple[0]['id'] or episode != self.last_show_tuple[1]:
                # There's a new show detected, so
                # let's save the show information and
                # the time we detected it first

                # But if we're watching a new show, let's make sure turn off
                # the Playing flag on that one first
                if self.last_show_tuple and self.last_show_tuple[0] != show:
                    self._emit_signal('playing', self.last_show_tuple[0]['id'], False, 0)

                self.last_show_tuple = (show, episode)
                self._emit_signal('playing', show['id'], True, episode)

                self.last_time = time.time()
                self.last_updated = False

            if not self.last_updated:
                # Check if we need to update the show yet
                if episode == (show['my_progress'] + 1):
                    timedif = time.time() - self.last_time

                    if timedif > self.wait_s:
                        # Time has passed, let's update
                        if self.wait_close:
                            # Queue update for when the player closes
                            self.msg.info(self.name, 'Waiting for the player to close.')
                            self.last_close_queue = True
                            self.last_updated = True
                        else:
                            # Update now
                            self._emit_signal('update', show['id'], episode)
                            self.last_updated = True
                    else:
                        self.msg.info(self.name, 'Will update %s %d in %d seconds' % (show['title'], episode, self.wait_s-timedif+1))
                else:
                    # We shouldn't update to this episode!
                    self.msg.warn(self.name, 'Player is not playing the next episode of %s. Ignoring.' % show['title'])
                    self.last_updated = True
            else:
                # The episode was updated already. do nothing
                pass
        elif self.last_state != state:
            # React depending on state
            # STATE_NOVIDEO : No video is playing anymroe
            # STATE_UNRECOGNIZED : There's a new video playing but the regex didn't recognize the format
            # STATE_NOT_FOUND : There's a new video playing but an associated show wasn't found
            if state == STATE_NOVIDEO and self.last_show_tuple:
                # Update now if there's an update queued
                if self.last_close_queue:
                    self._emit_signal('update', self.last_show_tuple[0]['id'], self.last_show_tuple[1])
                elif not self.last_updated:
                    self.msg.info(self.name, 'Player was closed before update.')
            elif state == STATE_UNRECOGNIZED:
                self.msg.warn(self.name, 'Found video but the file name format couldn\'t be recognized.')
            elif state == STATE_NOT_FOUND:
                self.msg.warn(self.name, 'Found player but show not in list.')

            # Clear any show previously playing
            if self.last_show_tuple:
                self._emit_signal('playing', self.last_show_tuple[0]['id'], False, self.last_show_tuple[1])
                self.last_updated = False
                self.last_close_queue = False
                self.last_time = 0
                self.last_show_tuple = None

        self.last_state = state

    def _get_playing_show(self):
        if not self.active:
            # Don't do anything if the Tracker is disabled
            return (STATE_NOVIDEO, None)

        if self.plex_enabled:
            filename = self._get_plex_file()
        else:
            filename = self._get_playing_file(self.process_name)

        if filename:
            if filename == self.last_filename:
                # It's the exact same filename, there's no need to do the processing again
                return (4, self.last_show_tuple)

            self.last_filename = filename

            # Do a regex to the filename to get
            # the show title and episode number
            aie = AnimeInfoExtractor(filename)
            (show_title, show_ep) = (aie.getName(), aie.getEpisode())
            if not show_title:
                return (STATE_UNRECOGNIZED, None) # Format not recognized

            playing_show = utils.guess_show(show_title, self.list)
            if playing_show:
                return (STATE_PLAYING, (playing_show, show_ep))
            else:
                return (STATE_NOT_FOUND, None) # Show not in list
        else:
            self.last_filename = None
            return (STATE_NOVIDEO, None) # Not playing

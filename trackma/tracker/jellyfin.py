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

import time
import requests

import trackma.utils as utils
from trackma.tracker import tracker

NOT_RUNNING = 0
ACTIVE = 1
CLAIMED = 2
PLAYING = 3
PAUSED = 4
IDLE = 5


class JellyfinTracker(tracker.TrackerBase):
    name = 'Tracker (Jellyfin)'

    def __init__(self, messenger, tracker_list, config, watch_dirs, redirections=None):
        self.config = config

        self.host_port = self.config['jellyfin_host']+":"+self.config['jellyfin_port']
        self.api_key = self.config['jellyfin_api_key']
        self.username = self.config['jellyfin_user']
        self.status_log = [None, None]
        super().__init__(messenger, tracker_list, config, watch_dirs, redirections)

    def get_jellyfin_status(self, session_state):
        # returns the plex status of the first active session
        #try:
        active = session_state

        if active:
            return ACTIVE
        else:
            return IDLE
        #except urllib.request.URLError as e:
        #    if e.code == 401:
        #        return CLAIMED
        #    else:
        #        return NOT_RUNNING

    def playing_file(self, session_info):
        # returns the filename of the currently playing file
        if self.get_jellyfin_status(session_info[0]) == IDLE:
            return None

        if not session_info[1]:
            state = PLAYING
        else:
            state = PAUSED

        name = session_info[2]

        return (name, state)

    def observe(self, config, watch_dirs):
        self.msg.info(self.name, "Using Jellyfin.")
        session_info = self._get_sessions_info()

        while self.active:
            session_info = self._get_sessions_info()
            self.status_log.append(self.get_jellyfin_status(session_info[0]))

            if self.status_log[-1] == ACTIVE or self.status_log[-1] == IDLE:
                if self.status_log[-1] == IDLE and self.status_log[-2] == NOT_RUNNING:
                    self.msg.info(self.name, "Reconnected to Jellyfin.")
                    self.wait_s = config['tracker_update_wait_s']
                try:
                    player = self.playing_file(session_info)
                    (state, show_tuple) = self._get_playing_show(player[0])
                            
                    self.view_offset = int(session_info[3])

                    self.update_show_if_needed(state, show_tuple)

                    if player[1] == PAUSED:
                        self.pause_timer()
                    elif player[1] == PLAYING:
                        self.resume_timer()

                except:
                    if self.status_log[-1] == IDLE:
                        self.last_filename = None
                        self.update_show_if_needed(0, None)
                    else:
                        pass
            elif self.status_log[-1] == CLAIMED and self.status_log[-2] == CLAIMED:
                self.msg.warn(
                    self.name, "Claimed Plex Media Server, login in the settings and restart trackma.")
            elif self.status_log[-1] == NOT_RUNNING and self.status_log[-2] == NOT_RUNNING:
                self.msg.warn(self.name, "Plex Media Server is not running.")

            del self.status_log[0]

            # Wait for the interval before running check again
            time.sleep(config['tracker_interval'])

    def _get_sessions_info(self):
        # Get the required info from the /status/sessions url
        session_url = "http://"+self.host_port+"/Sessions?api_key={}".format(self.api_key)
        response = requests.get(session_url).json()
        for session in response:
            if not 'UserName' in session:
                continue
            if session['UserName'] != self.username:
                continue

            if not 'NowPlayingItem' in session:
                return (False, None, None, None)

            current_session = session['NowPlayingItem']
            return (
                True,
                session['PlayState']['IsPaused'],
                current_session['Name'],
                int(session['PlayState']['PositionTicks']/10000)
            )

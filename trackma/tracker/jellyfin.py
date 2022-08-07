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

# TODO: Add gui stuff for this

import os
import time

import requests

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

    def observe(self, config, watch_dirs):
        self.msg.info("Using Jellyfin.")

        while self.active:
            session_info = self._get_sessions_info()
            self.status_log.append(session_info['status'])

            if self.status_log[-1] == ACTIVE or self.status_log[-1] == IDLE:
                if self.status_log[-1] == IDLE and self.status_log[-2] == NOT_RUNNING:
                    self.msg.info("Reconnected to Jellyfin.")
                    self.wait_s = config['tracker_update_wait_s']

                try:
                    (state, show_tuple) = self._get_playing_show(session_info['file_name'])

                    self.view_offset = int(session_info['view_offset'])

                    self.update_show_if_needed(state, show_tuple)

                    if session_info['state'] == PAUSED:
                        self.pause_timer()
                    elif session_info['state'] == PLAYING:
                        self.resume_timer()

                except (IndexError, TypeError):
                    if self.status_log[-1] == IDLE:
                        self.last_filename = None
                        self.update_show_if_needed(0, None)
                    else:
                        pass

            elif self.status_log[-1] == CLAIMED and self.status_log[-2] == CLAIMED:
                self.msg.warn("Claimed Jellyfin, login in the settings and restart trackma.")
            elif self.status_log[-1] == NOT_RUNNING and self.status_log[-2] == NOT_RUNNING:
                self.msg.warn("Jellyfin is not running.")

            del self.status_log[0]

            # Wait for the interval before running check again
            time.sleep(config['tracker_interval'])

    def _get_sessions_info(self):
        session_url = self.host_port+"/Sessions?api_key={}".format(self.api_key)

        info = {
            "status": NOT_RUNNING,
            "state": PAUSED,
            "file_name": None,
            "view_offset": None
        }

        try:
            response = requests.get(session_url)
            response_json = response.json()
        except requests.exceptions.ConnectionError:
            return info

        for session in response_json:
            if 'UserName' not in session:
                continue
            if session['UserName'] != self.username:
                continue

            if 'NowPlayingItem' in session:
                current_session = session['NowPlayingItem']
                return {
                    "status": ACTIVE,
                    "state": PAUSED if session['PlayState']['IsPaused'] else PLAYING,
                    "file_name": os.path.basename(current_session['Path']),
                    "view_offset": int(session['PlayState']['PositionTicks']/10000)
                }

        info["status"] = IDLE
        return info

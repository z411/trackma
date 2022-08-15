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

import base64
import json
import time
import urllib.error
import urllib.request

from trackma.tracker import tracker

NOT_RUNNING = 0
IDLE = 1
ACTIVE = 2
AUTH_REQUIRED = 3

PLAYING = 4
PAUSED = 5


class KodiTracker(tracker.TrackerBase):
    name = 'Tracker (Kodi)'

    def __init__(self, messenger, tracker_list, config, watch_dirs, redirections=None):
        self.config = config

        self.host_port = "{}:{}".format(
            self.config['kodi_host'], self.config['kodi_port'])
        self.status_log = [None, None]
        self.headers = {'content-type': 'application/json'}
        super().__init__(messenger, tracker_list, config, watch_dirs, redirections)

    def _get_kodi_status(self):
        # returns the status of the active players (if any)
        try:
            player = self._get_rpc_info("Player.GetActivePlayers")

            if player:
                if player[0]['type'] == "video":
                    return ACTIVE
                else:
                    return IDLE
            else:
                return IDLE
        except urllib.error.URLError as e:
            if hasattr(e, 'code'):
                if e.code == 401:
                    return AUTH_REQUIRED
                else:
                    return NOT_RUNNING
            else:
                return NOT_RUNNING

    def _playing_file(self):
        # returns the filename of the currently playing file
        if self._get_kodi_status() == IDLE:
            return None

        name = self._get_rpc_info("Player.GetItem", {"playerid": 1})[
            'item']['label']
        rstate = self._get_player_props("speed")

        if rstate > 0:
            state = PLAYING
        else:
            state = PAUSED

        return (name, state)

    def _timer_from_file(self):
        # returns 80% of video duration for the update timer,
        # roughly the time of the video minus the OP and ED
        if self._get_kodi_status() == IDLE:
            return None

        totaltime = self._get_player_props("totaltime")
        seconds = (totaltime['hours'] * 3600) + (totaltime['minutes'] * 60) + (totaltime['seconds'])

        return round(seconds*0.80)

    def _get_rpc_info(self, method, params={}):
        url = "http://{}/jsonrpc".format(self.host_port)

        body = {
            "method": method,
            "params": params,
            "jsonrpc": "2.0",
            "id": 0
        }

        if not self.config['kodi_user'] == '':
            req = urllib.request.Request(url, json.dumps(
                body).encode(), headers=self.headers)
            b64 = base64.b64encode(bytes("{}:{}".format(
                self.config['kodi_user'], self.config['kodi_passwd']), 'ascii'))
            req.add_header("Authorization",
                           "Basic {}".format(b64.decode('utf-8')))
        else:
            req = urllib.request.Request(url, json.dumps(
                body).encode(), headers=self.headers)

        response = urllib.request.urlopen(req)
        data = json.loads(response.read().decode())

        return data['result']

    def _get_player_props(self, prop):
        # Get the required info from the player
        props = {
            "playerid": 1,
            "properties": [prop]
        }

        info = self._get_rpc_info("Player.GetProperties", props)

        return info[prop]

    def observe(self, config, watch_dirs):
        self.msg.info("Using Kodi.")

        while self.active:
            self.status_log.append(self._get_kodi_status())

            if self.status_log[-1] == IDLE and self.status_log[-2] == NOT_RUNNING:
                self.msg.info("Reconnected to Kodi.")

            if self.status_log[-1] == ACTIVE:
                if self.config['kodi_obey_update_wait_s']:
                    self.wait_s = config['tracker_update_wait_s']
                else:
                    self.wait_s = self._timer_from_file()

                player = self._playing_file()
                (state, show_tuple) = self._get_playing_show(player[0])

                self.update_show_if_needed(state, show_tuple)

                if player[1] == PAUSED:
                    self.pause_timer()
                elif player[1] == PLAYING:
                    self.resume_timer()

            elif self.status_log[-1] == AUTH_REQUIRED:
                self.msg.warn("Authentication needed by Kodi, login in the settings and restart trackma.")
            elif self.status_log[-1] == NOT_RUNNING:
                self.msg.warn("Kodi HTTP Server is not running.")

            del self.status_log[0]

            # Wait for the interval before running check again
            time.sleep(config['tracker_interval'])

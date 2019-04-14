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

import ntpath
import time
import urllib.parse
import urllib.request
import xml.dom.minidom as xdmd

import trackma.utils as utils
from trackma.tracker import tracker

NOT_RUNNING = 0
ACTIVE = 1
IDLE = 2

class PlexTracker(tracker.TrackerBase):
    name = 'Tracker (Plex)'

    def __init__(self, messenger, tracker_list, process_name, watch_dirs, interval, update_wait, update_close, not_found_prompt):
        self.config = utils.parse_config(utils.to_config_path('config.json'), utils.config_defaults)
        self.host_port = self.config['plex_host']+":"+self.config['plex_port']
        self.update_wait = update_wait
        self.status_log = [None, None]
        self.token = self._get_plex_token()
        super().__init__(messenger, tracker_list, process_name, watch_dirs, interval, update_wait, update_close, not_found_prompt)

    def get_plex_status(self):
        # returns the plex status of the first active session
        try:
            active = int(self._get_sessions_info("MediaContainer", "size"))

            if active:
                return ACTIVE
            else:
                return IDLE
        except urllib.request.URLError:
            return NOT_RUNNING

    def playing_file(self):
        # returns the filename of the currently playing file
        if self.get_plex_status() == IDLE:
            return None

        meta = self._get_sessions_info("Video", "key")
        meta_url = "http://"+self.host_port+meta
        mres = self._get_xml_info(meta_url, "Part", "file")
        name = urllib.parse.unquote(ntpath.basename(mres))

        return name

    def timer_from_file(self):
        # returns 80% of video duration for the update timer,
        # roughly the time of the video minus the OP and ED
        if self.get_plex_status() == IDLE:
            return None

        try:
            duration = int(self._get_sessions_info("Video", "duration"))
            return round((duration*0.80)/60000)*60
        except IndexError:
            return None

    def observe(self, watch_dirs, interval):
        self.msg.info(self.name, "Using Plex.")

        while self.active:
            self.status_log.append(self.get_plex_status())

            if self.status_log[-1] == ACTIVE or self.status_log[-1] == IDLE:
                if self.status_log[-1] == IDLE and self.status_log[-2] == NOT_RUNNING:
                    self.msg.info(self.name, "Reconnected to Plex.")

                if self.config['plex_obey_update_wait_s']:
                    self.wait_s = self.update_wait
                else:
                    self.wait_s = self.timer_from_file()

                try:
                    filename = self.playing_file()
                    (state, show_tuple) = self._get_playing_show(filename)
                    self.update_show_if_needed(state, show_tuple)
                except IndexError:
                    pass
            elif self.status_log[-1] == NOT_RUNNING and self.status_log[-2] == NOT_RUNNING:
                self.msg.warn(self.name, "Plex Media Server is not running.")

            del self.status_log[0]

            # Wait for the interval before running check again
            time.sleep(interval)

    def _get_plex_token(self):
        username = self.config['plex_user']
        password = self.config['plex_passwd']
        uuid = self.config['plex_uuid']

        if not (username and password):
            return ''

        body = bytes('user[login]=%s&user[password]=%s' % (username, password), "utf-8")
        headers = {'X-Plex-Client-Identifier': uuid,
                'X-Plex-Product': "Trackma",
                'X-Plex-Version': utils.VERSION}

        req = urllib.request.Request('https://plex.tv/users/sign_in.xml', body, headers=headers)
        response = urllib.request.urlopen(req)
        data = response.read().decode("utf-8")

        tdoc = xdmd.parseString(data)
        token = tdoc.getElementsByTagName("user")[0].getAttribute("authToken")

        return "?X-Plex-Token="+token

    def _get_xml_info(self, url, tag, attr):
        try:
            uop = urllib.request.urlopen(url)
        except urllib.request.URLError:
            uop = urllib.request.urlopen(url+self.token)

        doc = xdmd.parse(uop)
        res = doc.getElementsByTagName(tag)[0].getAttribute(attr)

        return res

    def _get_sessions_info(self, tag, attr):
        # Get the required info from the /status/sessions url
        session_url = "http://"+self.host_port+"/status/sessions"
        info = self._get_xml_info(session_url, tag, attr)

        return info

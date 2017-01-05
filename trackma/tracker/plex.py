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
from trackma.extras import plex

from trackma.tracker import tracker

class PlexTracker(tracker.TrackerBase):
    name = 'Tracker (Plex)'
    
    def _get_plex_file(self):
        playing_file = plex.playing_file()
        return playing_file

    def observe(self, watch_dir, interval):
        self.msg.info(self.name, "Using Plex.")

        while self.active:
            # This stores the last two states of the plex server and only
            # updates if it's ACTIVE.
            plex_status = plex.status()
            self.plex_log.append(plex_status)

            if self.plex_log[-1] == "ACTIVE" or self.plex_log[-1] == "IDLE":
                self.wait_s = plex.timer_from_file()
                filename = self._get_plex_file()
                (state, show_tuple) = self._get_playing_show(filename)
                self.update_show_if_needed(state, show_tuple)
            elif (self.plex_log[-2] != "NOT_RUNNING" and self.plex_log[-1] == "NOT_RUNNING"):
                self.msg.warn(self.name, "Plex Media Server is not running.")

            del self.plex_log[0]
            # Wait for the interval before running check again
            time.sleep(interval)


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

import ctypes
import time
import re

from trackma.tracker import tracker

class Win32Tracker(tracker.TrackerBase):
    name = 'Tracker (win32)'

    def __init__(self, messenger, tracker_list, config, watch_dirs, redirections=None):
        super().__init__(messenger, tracker_list, config, watch_dirs, redirections)

        self.winregex = re.compile("(\.mkv|\.mp4|\.avi)")

    def _foreach_window(self, hwnd, lParam):
        # Get class name and window title of the current hwnd
        # and add it to the list of the found windows
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)

        buff_class = ctypes.create_unicode_buffer(32)
        buff_title = ctypes.create_unicode_buffer(length + 1)

        ctypes.windll.user32.GetClassNameW(hwnd, buff_class, 32)
        ctypes.windll.user32.GetWindowTextW(hwnd, buff_title, length + 1)

        self.win32_hwnd_list.append( (buff_class.value, buff_title.value) )
        return True

    def _get_playing_file_win32(self):
        # Enumerate all windows using the win32 API
        # This will call _foreach_window for each window handle
        # Then return the window title if the class name matches
        # Currently supporting MPC(-HC) and mpv

        self.win32_hwnd_list = []
        self.EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        ctypes.windll.user32.EnumWindows(self.EnumWindowsProc(self._foreach_window), 0)

        for classname, title in self.win32_hwnd_list:
            if classname == 'MediaPlayerClassicW' and self.winregex.search(title) is not None:
                return title
            elif classname == 'mpv' and self.winregex.search(title) is not None:
                return title.replace('mpv - ', '')

        return False

    def observe(self, config, watch_dirs):
        self.msg.info(self.name, "Using Win32.")

        while self.active:
            # This runs the tracker and update the playing show if necessary
            filename = self._get_playing_file_win32()
            (state, show_tuple) = self._get_playing_show(filename)
            self.update_show_if_needed(state, show_tuple)

            # Wait for the interval before running check again
            time.sleep(1)


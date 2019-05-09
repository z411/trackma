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

import os

from io import BytesIO
import urllib.request

from PyQt5 import QtCore

try:
    from PIL import Image
except ImportError:
    import Image

from trackma.engine import Engine
from trackma import utils

class ImageWorker(QtCore.QThread):
    """
    Image thread

    Downloads an image and shrinks it if necessary.

    """
    cancelled = False
    finished = QtCore.pyqtSignal(str)

    def __init__(self, remote, local, size=None):
        self.remote = remote
        self.local = local
        self.size = size
        super(ImageWorker, self).__init__()

    def __del__(self):
        self.wait()

    def run(self):
        self.cancelled = False

        req = urllib.request.Request(self.remote)
        req.add_header("User-agent", "TrackmaImage/{}".format(utils.VERSION))
        try:
            img_file = BytesIO(urllib.request.urlopen(req).read())
            if self.size:
                if "imaging_available" in os.environ:
                    im = Image.open(img_file)
                    im.thumbnail((self.size[0], self.size[1]), Image.ANTIALIAS)
                    im.convert("RGB").save(self.local)
            else:
                with open(self.local, 'wb') as f:
                    f.write(img_file.read())
        except urllib.error.URLError as e:
            print("Warning: Error getting image ({})".format(e))
            return

        if self.cancelled:
            return

        self.finished.emit(self.local)

    def cancel(self):
        self.cancelled = True


class EngineWorker(QtCore.QThread):
    """
    Worker thread

    Contains the engine and manages every process in a separate thread.

    """
    engine = None
    function = None
    finished = QtCore.pyqtSignal(dict)

    # Message handler signals
    changed_status = QtCore.pyqtSignal(str, int, str)
    raised_error = QtCore.pyqtSignal(str)
    raised_fatal = QtCore.pyqtSignal(str)

    # Event handler signals
    changed_show = QtCore.pyqtSignal(dict)
    changed_show_status = QtCore.pyqtSignal(dict, object)
    changed_list = QtCore.pyqtSignal(dict)
    changed_queue = QtCore.pyqtSignal(int)
    tracker_state = QtCore.pyqtSignal(dict)
    playing_show = QtCore.pyqtSignal(dict, bool, int)
    prompt_for_update = QtCore.pyqtSignal(dict, int)
    prompt_for_add = QtCore.pyqtSignal(dict, int)

    def __init__(self):
        super(EngineWorker, self).__init__()

        self.overrides = {'start': self._start}

    def _messagehandler(self, classname, msgtype, msg):
        self.changed_status.emit(classname, msgtype, msg)

    def _error(self, msg):
        self.raised_error.emit(str(msg))

    def _fatal(self, msg):
        self.raised_fatal.emit(str(msg))

    def _changed_show(self, show, changes=None):
        self.changed_show.emit(show)

    def _changed_show_status(self, show, old_status=None):
        self.changed_show_status.emit(show, old_status)

    def _changed_list(self, show):
        self.changed_list.emit(show)

    def _changed_queue(self, queue):
        self.changed_queue.emit(len(queue))

    def _tracker_state(self, status):
        self.tracker_state.emit(status)

    def _playing_show(self, show, is_playing, episode):
        self.playing_show.emit(show, is_playing, episode)

    def _prompt_for_update(self, show, episode):
        self.prompt_for_update.emit(show, episode)

    def _prompt_for_add(self, show, episode):
        self.prompt_for_add.emit(show, episode)

    # Callable functions
    def _start(self, account):
        self.engine = Engine(account, self._messagehandler)

        self.engine.connect_signal('episode_changed', self._changed_show)
        self.engine.connect_signal('score_changed', self._changed_show)
        self.engine.connect_signal('tags_changed', self._changed_show)
        self.engine.connect_signal('status_changed', self._changed_show_status)
        self.engine.connect_signal('playing', self._playing_show)
        self.engine.connect_signal('show_added', self._changed_list)
        self.engine.connect_signal('show_deleted', self._changed_list)
        self.engine.connect_signal('show_synced', self._changed_show)
        self.engine.connect_signal('queue_changed', self._changed_queue)
        self.engine.connect_signal('prompt_for_update', self._prompt_for_update)
        self.engine.connect_signal('prompt_for_add', self._prompt_for_add)
        self.engine.connect_signal('tracker_state', self._tracker_state)

        self.engine.start()

    def set_function(self, function, ret_function, *args, **kwargs):
        if function in self.overrides:
            self.function = self.overrides[function]
        else:
            self.function = getattr(self.engine, function)

        try:
            self.finished.disconnect()
        except Exception:
            pass

        if ret_function:
            self.finished.connect(ret_function)

        self.args = args
        self.kwargs = kwargs

    def __del__(self):
        self.wait()

    def run(self):
        try:
            ret = self.function(*self.args, **self.kwargs)
            self.finished.emit({'success': True, 'result': ret})
        except utils.TrackmaError as e:
            self._error(e)
            self.finished.emit({'success': False})
        except utils.TrackmaFatal as e:
            self._fatal(e)

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

from trackma.ui.qt.util import worker_call

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
    changed_list = QtCore.pyqtSignal(dict, object)
    changed_queue = QtCore.pyqtSignal(int)
    tracker_state = QtCore.pyqtSignal(int, int)
    playing_show = QtCore.pyqtSignal(dict, bool, int)
    prompt_for_update = QtCore.pyqtSignal(dict, int)
    prompt_for_add = QtCore.pyqtSignal(str, int)

    def __init__(self):
        super(EngineWorker, self).__init__()

        self.function_list = {
            'start': self._start,
            'reload': self._reload,
            'set_episode': self._set_episode,
            'set_score': self._set_score,
            'set_status': self._set_status,
            'set_tags': self._set_tags,
            'play_episode': self._play_episode,
            'play_random': self._play_random,
            'list_download': self._list_download,
            'list_upload': self._list_upload,
            'get_show_details': self._get_show_details,
            'search': self._search,
            'add_show': self._add_show,
            'delete_show': self._delete_show,
            'unload': self._unload,
            'scan_library': self._scan_library,
            'rss_list': self._rss_list,
        }

    def _messagehandler(self, classname, msgtype, msg):
        self.changed_status.emit(classname, msgtype, msg)

    def _error(self, msg):
        self.raised_error.emit(str(msg))

    def _fatal(self, msg):
        self.raised_fatal.emit(str(msg))

    def _changed_show(self, show, changes=None):
        self.changed_show.emit(show)

    def _changed_list(self, show, old_status=None):
        self.changed_list.emit(show, old_status)

    def _changed_queue(self, queue):
        self.changed_queue.emit(len(queue))

    def _tracker_state(self, state, timer):
        self.tracker_state.emit(state, timer)

    def _playing_show(self, show, is_playing, episode):
        self.playing_show.emit(show, is_playing, episode)

    def _prompt_for_update(self, show, episode):
        self.prompt_for_update.emit(show, episode)

    def _prompt_for_add(self, show_title, episode):
        self.prompt_for_add.emit(show_title, episode)

    # Callable functions
    @worker_call
    def _start(self, account):
        self.engine = Engine(account, self._messagehandler)

        self.engine.connect_signal('episode_changed', self._changed_show)
        self.engine.connect_signal('score_changed', self._changed_show)
        self.engine.connect_signal('tags_changed', self._changed_show)
        self.engine.connect_signal('status_changed', self._changed_list)
        self.engine.connect_signal('playing', self._playing_show)
        self.engine.connect_signal('show_added', self._changed_list)
        self.engine.connect_signal('show_deleted', self._changed_list)
        self.engine.connect_signal('show_synced', self._changed_show)
        self.engine.connect_signal('queue_changed', self._changed_queue)
        self.engine.connect_signal('prompt_for_update', self._prompt_for_update)
        self.engine.connect_signal('prompt_for_add', self._prompt_for_add)
        self.engine.connect_signal('tracker_state', self._tracker_state)

        self.engine.start()

    @worker_call
    def _reload(self, account, mediatype):
        return self.engine.reload(account, mediatype)

    @worker_call
    def _unload(self):
        return self.engine.unload()

    @worker_call
    def _scan_library(self):
        return self.engine.scan_library(rescan=True)

    @worker_call
    def _set_episode(self, showid, episode):
        return self.engine.set_episode(showid, episode)

    @worker_call
    def _set_score(self, showid, score):
        return self.engine.set_score(showid, score)

    @worker_call
    def _set_status(self, showid, status):
        return self.engine.set_status(showid, status)

    @worker_call
    def _set_tags(self, showid, tags):
        return self.engine.set_tags(showid, tags)

    @worker_call
    def _play_episode(self, show, episode):
        return self.engine.play_episode(show, episode)

    @worker_call
    def _play_random(self):
        return self.engine.play_random()

    @worker_call
    def _list_download(self):
        self.engine.list_download()

    @worker_call
    def _list_upload(self):
        self.engine.list_upload()

    @worker_call
    def _get_show_details(self, show):
        return self.engine.get_show_details(show)

    @worker_call
    def _rss_list(self, refresh):
        return self.engine.rss_list(refresh)

    @worker_call
    def _search(self, criteria, method):
        return self.engine.search(criteria, method)

    @worker_call
    def _add_show(self, show, status):
        self.engine.add_show(show, status)

    @worker_call
    def _delete_show(self, show):
        self.engine.delete_show(show)

    def set_function(self, function, ret_function, *args, **kwargs):
        self.function = self.function_list[function]

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
            ret = self.function(*self.args,**self.kwargs)
            self.finished.emit(ret)
        except utils.TrackmaFatal as e:
            self._fatal(e)

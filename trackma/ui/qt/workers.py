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
                im = Image.open(img_file)
                im.thumbnail((self.size[0], self.size[1]), Image.ANTIALIAS)
                im.save(self.local)
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

    def __init__(self, account):
        super(EngineWorker, self).__init__()
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

        self.function_list = {
            'start': self._start,
            'reload': self._reload,
            'get_list': self._get_list,
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
    def _start(self):
        try:
            self.engine.start()
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _reload(self, account, mediatype):
        try:
            self.engine.reload(account, mediatype)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _unload(self):
        try:
            self.engine.unload()
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _scan_library(self):
        try:
            self.engine.scan_library(rescan=True)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _get_list(self):
        try:
            showlist = self.engine.get_list()
            altnames = self.engine.altnames()
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True, 'showlist': showlist, 'altnames': altnames}

    def _set_episode(self, showid, episode):
        try:
            self.engine.set_episode(showid, episode)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _set_score(self, showid, score):
        try:
            self.engine.set_score(showid, score)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _set_status(self, showid, status):
        try:
            self.engine.set_status(showid, status)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _set_tags(self, showid, tags):
        try:
            self.engine.set_tags(showid, tags)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _play_episode(self, show, episode):
        try:
            played_ep = self.engine.play_episode(show, episode)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True, 'show': show, 'played_ep': played_ep}

    def _play_random(self):
        try:
            (show, ep) = self.engine.play_random()
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True, 'played_show': show, 'played_ep': ep}

    def _list_download(self):
        try:
            self.engine.list_download()
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _list_upload(self):
        try:
            self.engine.list_upload()
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _get_show_details(self, show):
        try:
            details = self.engine.get_show_details(show)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True, 'details': details}

    def _search(self, terms):
        try:
            results = self.engine.search(terms)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True, 'results': results}

    def _add_show(self, show, status):
        try:
            results = self.engine.add_show(show, status)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

    def _delete_show(self, show):
        try:
            results = self.engine.delete_show(show)
        except utils.TrackmaError as e:
            self._error(e)
            return {'success': False}

        return {'success': True}

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

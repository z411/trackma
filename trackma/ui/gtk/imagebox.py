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
import threading
import urllib.request
from io import BytesIO

from gi.repository import GLib, GdkPixbuf, Gtk

from trackma import utils

try:
    import Image
    imaging_available = True
except ImportError:
    try:
        from PIL import Image
        imaging_available = True
    except ImportError:
        imaging_available = False


class ImageThread(threading.Thread):
    def __init__(self, url, filename, width, height, callback):
        threading.Thread.__init__(self)
        self._url = url
        self._filename = filename
        self._width = width
        self._height = height
        self._callback = callback
        self._stop_request = threading.Event()

    def run(self):
        self._save_image(self._download_file())

        if self._stop_request.is_set():
            return

        if os.path.exists(self._filename):
            GLib.idle_add(self._callback, self._filename)

    def _download_file(self):
        request = urllib.request.Request(self._url)
        request.add_header(
            "User-Agent", "TrackmaImage/{}".format(utils.VERSION))
        return BytesIO(urllib.request.urlopen(request).read())

    def _save_image(self, img_bytes):
        if imaging_available:
            image = Image.open(img_bytes)
            image.thumbnail((self._width, self._height), Image.ANTIALIAS)
            image.convert("RGB").save(self._filename)
        else:
            with open(self._filename, 'wb') as img_file:
                img_file.write(img_bytes.read())

    def stop(self):
        self._stop_request.set()


class ImageBox(Gtk.HBox):
    def __init__(self, width, height):
        Gtk.HBox.__init__(self)

        self._width = width
        self._height = height

        self._image = Gtk.Image()
        self._image.set_size_request(width, height)

        self._label_holder = Gtk.Label()
        self._label_holder.set_size_request(width, height)

        self._image_thread = None

        if imaging_available:
            self.pack_start(self._label_holder, False, False, 0)
            self.pack_start(self._image, False, False, 0)
        else:
            self.pack_start(self._label_holder, False, False, 0)

        self.reset()

    def reset(self):
        if imaging_available:
            self.set_image(utils.DATADIR + '/icon.png')
        else:
            self.set_text("PIL library\nnot available")

    def set_text(self, text):
        self._label_holder.set_text(text)
        self._label_holder.show()
        self._image.hide()

    def set_image(self, filename):
        if not imaging_available:
            return

        pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
        width, height = scale(pixbuf.get_width(),
                              pixbuf.get_height(), self._width, self._height)
        scaled_buf = pixbuf.scale_simple(
            width, height, GdkPixbuf.InterpType.BILINEAR)

        self._image.set_from_pixbuf(scaled_buf)
        self._image.show()
        self._label_holder.hide()

    def set_image_remote(self, url, filename):
        if not imaging_available:
            return

        if self._image_thread:
            self._image_thread.stop()

        self.set_text("Loading...")
        self._image_thread = ImageThread(
            url, filename, self._width, self._height, self.set_image)
        self._image_thread.start()


def scale(w, h, x, y, maximum=True):
    nw = y * w / h
    nh = x * h / w
    if maximum ^ (nw >= x):
        return nw or 1, y
    return x, nh or 1

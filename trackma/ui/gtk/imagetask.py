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
import time
import threading
import urllib.request
from io import BytesIO
from gi.repository import Gdk
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


class ImageTask(threading.Thread):
    cancelled = False

    def __init__(self, show_image, remote, local, size=None):
        self.show_image = show_image
        self.remote = remote
        self.local = local
        self.size = size
        threading.Thread.__init__(self)

    def run(self):
        self.cancelled = False

        time.sleep(1)

        if self.cancelled:
            return

        # If there's a better solution for this please tell me/implement it.

        # If there's a size specified, thumbnail with PIL library
        # otherwise download and save it as it is
        req = urllib.request.Request(self.remote)
        req.add_header("User-agent", "TrackmaImage/{}".format(utils.VERSION))
        img_file = BytesIO(urllib.request.urlopen(req).read())
        if self.size:
            if imaging_available:
                im = Image.open(img_file)
                im.thumbnail((self.size[0], self.size[1]), Image.ANTIALIAS)
                im.convert("RGB").save(self.local)
            else:
                self.show_image.pholder_show("PIL library\nnot available")
        else:
            with open(self.local, 'wb') as f:
                f.write(img_file.read())

        if self.cancelled:
            return

        if os.path.exists(self.local):
            Gdk.threads_enter()
            self.show_image.image_show(self.local)
            Gdk.threads_leave()

    def cancel(self):
        self.cancelled = True


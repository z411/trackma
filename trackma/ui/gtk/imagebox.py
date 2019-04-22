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


import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf


class ImageBox(Gtk.HBox):
    def __init__(self, w, h):
        Gtk.HBox.__init__(self)

        self.w = w
        self.h = h
        self.showing_pholder = False

        self.w_image = Gtk.Image()
        self.w_image.set_size_request(w, h)

        self.w_pholder = Gtk.Label()
        self.w_pholder.set_size_request(w, h)

        self.pack_start(self.w_image, False, False, 0)

    def image_show(self, filename):
        if self.showing_pholder:
            self.remove(self.w_pholder)
            self.pack_start(self.w_image, False, False, 0)
            self.w_image.show()
            self.showing_pholder = False

        pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
        w, h = scale(pixbuf.get_width(), pixbuf.get_height(), self.w, self.h)
        scaled_buf = pixbuf.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
        self.w_image.set_from_pixbuf(scaled_buf)

    def pholder_show(self, msg):
        if not self.showing_pholder:
            self.pack_end(self.w_pholder, False, False, 0)
            self.remove(self.w_image)
            self.w_pholder.show()
            self.showing_pholder = True

        self.w_pholder.set_text(msg)


def scale(w, h, x, y, maximum=True):
    nw = y * w / h
    nh = x * h / w
    if maximum ^ (nw >= x):
        return nw or 1, y
    return x, nh or 1


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


import cgi
import os
import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango, GObject
from trackma.ui.gtk.imagebox import ImageBox
from trackma.ui.gtk.imagetask import ImageTask
from trackma import utils


class ShowInfoBox(Gtk.VBox):
    def __init__(self, engine):
        Gtk.VBox.__init__(self)

        self.engine = engine

        # Title line
        self.w_title = Gtk.Label('')
        self.w_title.set_ellipsize(Pango.EllipsizeMode.END)

        # Middle line (sidebox)
        eventbox_sidebox = Gtk.EventBox()
        self.scrolled_sidebox = Gtk.ScrolledWindow()
        self.scrolled_sidebox.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sidebox = Gtk.HBox()

        alignment_image = Gtk.Alignment(yalign=0.0, xscale=0, yscale=0)
        self.w_image = ImageBox(225, 350)
        alignment_image.add(self.w_image)

        self.w_content = Gtk.Label()

        sidebox.pack_start(alignment_image, False, False, 5)
        sidebox.pack_start(self.w_content, True, True, 5)

        eventbox_sidebox.add(sidebox)

        self.scrolled_sidebox.add_with_viewport(eventbox_sidebox)

        self.pack_start(self.w_title, False, False, 0)
        self.pack_start(self.scrolled_sidebox, True, True, 5)

    def set_size(self, w, h):
        self.scrolled_sidebox.set_size_request(w, h)

    def load(self, show):
        self._show = show

        # Load image
        if show.get('image'):
            imagefile = utils.to_cache_path("%s_%s_f_%s.jpg" % (self.engine.api_info['shortname'], self.engine.api_info['mediatype'], show['id']))

            if os.path.isfile(imagefile):
                self.w_image.image_show(imagefile)
            else:
                self.w_image.pholder_show('Loading...')
                self.image_thread = ImageTask(self.w_image, show['image'], imagefile, (200, 298))
                self.image_thread.start()
        else:
            self.w_image.pholder_show('No Image')


        # Start info loading thread
        threading.Thread(target=self.task_load).start()

    def task_load(self):
        # Thread to ask the engine for show details

        try:
            self.details = self.engine.get_show_details(self._show)
        except utils.TrackmaError as e:
            self.details = None
            self.details_e = e

        GObject.idle_add(self._done)

    def _done(self):
        if self.details:
            # Put the returned details into the lines VBox
            self.w_title.set_text('<span size="14000"><b>{0}</b></span>'.format(cgi.escape(self.details['title'])))
            self.w_title.set_use_markup(True)

            detail = list()
            for line in self.details['extra']:
                if line[0] and line[1]:
                    title, content, *_ = line
                    if isinstance(content, list):
                        content = ", ".join(filter(None, content))
                    detail.append("<b>%s</b>\n%s" % (cgi.escape(str(title)), cgi.escape(str(content))))

            self.w_content.set_text("\n\n".join(detail))
            self.w_content.set_use_markup(True)
            self.w_content.set_size_request(340, -1)

            self.show_all()
        else:
            self.w_title.set_text('Error while getting details.')
            if self.details_e:
                self.w_content.set_text(str(self.details_e))

        self.w_content.set_alignment(0, 0)
        self.w_content.set_line_wrap(True)
        self.w_content.set_size_request(340, -1)


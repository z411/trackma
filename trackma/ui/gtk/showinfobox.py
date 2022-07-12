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

import html
import os
import threading

from gi.repository import GObject, Gtk

from trackma import utils
from trackma.ui.gtk import gtk_dir
from trackma.ui.gtk.imagebox import ImageBox


@Gtk.Template.from_file(os.path.join(gtk_dir, 'data/showinfobox.ui'))
class ShowInfoBox(Gtk.Box):
    __gtype_name__ = 'ShowInfoBox'

    label_title = Gtk.Template.Child()
    data_container = Gtk.Template.Child()
    image_container = Gtk.Template.Child()

    def __init__(self, engine, orientation=Gtk.Orientation.HORIZONTAL):
        Gtk.Box.__init__(self)
        self.init_template()

        self._engine = engine
        self._show = None
        self.image_thread = None
        self.details = None
        self.details_e = None

        self.image_box = ImageBox(225, 300)
        self.image_box.show()
        self.image_container.pack_start(self.image_box, False, False, 0)

        self.data_label = Gtk.Label('')
        self.data_label.set_line_wrap(True)
        self.data_label.set_property('selectable', True)

        if isinstance(orientation, Gtk.Orientation):
            self.data_container.set_orientation(orientation)
        self.data_container.pack_start(self.data_label, True, True, 0)

    def set_size(self, w, h):
        self.scrolled_sidebox.set_size_request(w, h)

    def load(self, show):
        self._show = show

        # Load image
        if show.get('image'):
            utils.make_dir(utils.to_cache_path())
            imagefile = utils.to_cache_path("%s_%s_f_%s.jpg" % (self._engine.api_info['shortname'],
                                                                self._engine.api_info['mediatype'],
                                                                show['id']))

            if os.path.isfile(imagefile):
                self.image_box.set_image(imagefile)
            else:
                self.image_box.set_image_remote(show['image'], imagefile)
        else:
            self.image_box.set_text('No Image')

        # Start info loading thread
        threading.Thread(target=self._show_load_start_task).start()

    def _show_load_start_task(self):
        # Thread to ask the engine for show details
        try:
            self.details = self._engine.get_show_details(self._show)
        except utils.TrackmaError as e:
            self.details = None
            self.details_e = e

        GObject.idle_add(self._show_load_finish_idle)

    def _show_load_finish_idle(self):
        if self.details:
            # Put the returned details into the lines VBox
            self.label_title.set_text(html.escape(self.details['title']))

            detail = list()
            for line in self.details['extra']:
                if line[0] and line[1]:
                    title, content, *_ = line

                    if isinstance(content, list):
                        content = ", ".join(filter(None, content))

                    detail.append("<b>%s</b>\n%s" % (html.escape(str(title)),
                                                     html.escape(str(content))))

            self.data_label.set_text("\n\n".join(detail))
            self.data_label.set_use_markup(True)
        else:
            self.label_title.set_text('Error while getting details.')

            if self.details_e:
                self.data_label.set_text(str(self.details_e))

        self.label_title.show()
        self.data_label.show()

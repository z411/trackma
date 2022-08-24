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
from gi import require_version

require_version('Gtk', '3.0')
require_version('Gdk', '3.0')

from trackma import utils  # noqa: E402
from trackma.ui.gtk.window import TrackmaWindow  # noqa: E402
from gi.repository import GLib, Gio, Gtk  # noqa: E402


class TrackmaApplication(Gtk.Application):
    __gtype_name__ = 'TrackmaApplication'

    def __init__(self):
        super().__init__(
            application_id="com.github.z411.TrackmaGtk",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE | Gio.ApplicationFlags.NON_UNIQUE
        )

        self.debug = False
        self.window = None
        self.add_main_option(
            "debug", ord(
                "d"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, "Show debugging information", None
        )

    def do_startup(self):
        Gtk.Application.do_startup(self)

        self._register_accelerators()

        action = Gio.SimpleAction.new('quit', None)
        action.connect("activate", self._on_quit)
        self.add_action(action)

    def do_activate(self):
        try:
            self.create_window()
        except utils.TrackmaFatal as e:
            self.message_error(e)

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        options = options.end().unpack()
        self.debug = "debug" in options
        self.activate()
        return 0

    def _register_accelerators(self):
        def set_accel(name, accel):
            accel = accel if isinstance(accel, tuple) else (accel,)
            self.set_accels_for_action(name, accel)

        accels = (
            ('win.search', '<Primary>A'),
            ('win.synchronize', '<Primary>S'),
            ('win.upload', '<Primary>E'),
            ('win.download', '<Primary>D'),
            ('win.scanfiles', '<Primary>L'),
            ('win.show-help-overlay', '<Primary>question'),
            ('app.quit', '<Primary>Q'),

            # Shows
            ('win.play_next', '<Primary>N'),
            ('win.play_random', '<Primary>R'),
            ('win.episode_add', '<Primary>Right'),
            ('win.episode_remove', '<Primary>Left'),
            ('win.delete', ('Delete', 'KP_Delete')),
            ('win.copy', '<Primary>C')
        )

        for (name, accel) in accels:
            set_accel(name, accel)

    def create_window(self):
        if not self.window:
            self.window = TrackmaWindow(self, self.debug)

        if not self.window._engine:
            self.window.init_account_selection()

    @staticmethod
    def message_error(error):
        md = Gtk.MessageDialog(
            None,
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CLOSE,
            str(error)
        )
        md.run()
        md.destroy()

    def _on_quit(self, action, param):
        self.window._quit()

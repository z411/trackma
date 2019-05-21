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

import signal
import sys
from trackma.ui.gtk.application import TrackmaApplication
from trackma import utils


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    print("Trackma-gtk v{}".format(utils.VERSION))
    app = TrackmaApplication()
    sys.exit(app.run(sys.argv))


if __name__ == '__main__':
    main()

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

from gi.repository import GObject, Gdk, Gtk, Pango

from trackma import utils


# Declare named constants for the tree references, so it's more unified and easier to read
# Putting them in their own class also enables whatever we might want to do with it in the future.
class TreeConstants:
    SHOW_ID = 0
    TITLE = 1
    MY_PROGRESS = 2
    MY_SCORE = 3
    EPISODES = 4
    SCORE = 5
    TOTAL_EPS = 6
    AIRED_EPS = 7
    AVAILABLE_EPS = 8
    COLOR = 9
    PROGRESS = 10
    START_DATE = 11
    END_DATE = 12
    MY_START_DATE = 13
    MY_FINISH_DATE = 14
    MY_STATUS = 15
    SHOW_STATUS = 16
    NEXT_EPISODE_AIR_TIME_RELATIVE = 17


class ShowListStore(Gtk.ListStore):
    # Determines the structure of the tree and holds the actual data after it is appended from row[].
    # Entry order must match with row[].
    __cols = (
        (TreeConstants.SHOW_ID, int),
        (TreeConstants.TITLE, str),
        (TreeConstants.MY_PROGRESS, int),
        (TreeConstants.MY_SCORE, float),
        (TreeConstants.EPISODES, str),
        (TreeConstants.SCORE, str),
        (TreeConstants.TOTAL_EPS, int),
        (TreeConstants.AIRED_EPS, int),
        (TreeConstants.AVAILABLE_EPS, GObject.TYPE_PYOBJECT),
        (TreeConstants.COLOR, str),
        (TreeConstants.PROGRESS, int),
        (TreeConstants.START_DATE, str),
        (TreeConstants.END_DATE, str),
        (TreeConstants.MY_START_DATE, str),
        (TreeConstants.MY_FINISH_DATE, str),
        (TreeConstants.MY_STATUS, str),
        (TreeConstants.SHOW_STATUS, int),
        (TreeConstants.NEXT_EPISODE_AIR_TIME_RELATIVE, str),
    )

    def __init__(self, decimals=0, colors=None):
        super().__init__(*self.__class__.__columns__())
        if colors is None:
            colors = dict()
        self.colors = colors
        self.decimals = decimals
        self.set_sort_column_id(TreeConstants.TITLE, Gtk.SortType.ASCENDING)

    @staticmethod
    def format_date(date):
        if date:
            try:
                return date.strftime('%Y-%m-%d')
            except ValueError:
                return '?'
        else:
            return '-'

    @classmethod
    def __columns__(cls):
        return (k for i, k in cls.__cols)

    @classmethod
    def column(cls, key):
        try:
            return cls.__cols.index(next(i for i in cls.__cols if i[TreeConstants.SHOW_ID] == key))
        except ValueError:
            return None

    def _get_color(self, show, eps):
        if show.get('queued'):
            return self.colors['is_queued']
        elif eps and max(eps) > show['my_progress']:
            return self.colors['new_episode']
        elif show['status'] == utils.Status.AIRING:
            return self.colors['is_airing']
        elif show['status'] == utils.Status.NOTYET:
            return self.colors['not_aired']
        else:
            return None

    def append(self, show, altname=None, eps=None):
        episodes_str = "{} / {}".format(show['my_progress'],
                                        show['total'] or '?')
        if show['total'] and show['my_progress'] <= show['total']:
            progress = (float(show['my_progress']) / show['total']) * 100
        else:
            progress = 0

        title_str = show['title']
        if altname:
            title_str += " [%s]" % altname

        score_str = "%0.*f" % (self.decimals, show['my_score'])
        aired_eps = utils.estimate_aired_episodes(show)

        if eps:
            available_eps = eps.keys()
        else:
            available_eps = []

        start_date = self.format_date(show['start_date'])
        end_date = self.format_date(show['end_date'])
        my_start_date = self.format_date(show['my_start_date'])
        my_finish_date = self.format_date(show['my_finish_date'])

        # Gets the (short) relative airing time of the next episode compared to UTC
        next_episode_air_time_relative = utils.calculate_relative_time(show['next_ep_time'],
                                                                       utc=True, fulltime=False)

        # Corresponds to __cols, but is used locally to store the data before appending.
        row = [show['id'],
               title_str,
               show['my_progress'],
               show['my_score'],
               episodes_str,
               score_str,
               show['total'],
               aired_eps,
               available_eps,
               self._get_color(show, available_eps),
               progress,
               start_date,
               end_date,
               my_start_date,
               my_finish_date,
               show['my_status'],
               show['status'],
               next_episode_air_time_relative,
               ]
        super().append(row)

    def update_or_append(self, show):
        for row in self:
            if int(row[TreeConstants.SHOW_ID]) == show['id']:
                self.update(show, row)
                return
        self.append(show)

    def update(self, show, row=None):
        if not row:
            for row in self:
                if int(row[TreeConstants.SHOW_ID]) == show['id']:
                    break
        if row and int(row[TreeConstants.SHOW_ID]) == show['id']:
            episodes_str = "{} / {}".format(show['my_progress'],
                                            show['total'] or '?')
            row[TreeConstants.MY_PROGRESS] = show['my_progress']
            row[TreeConstants.EPISODES] = episodes_str

            score_str = "%0.*f" % (self.decimals, show['my_score'])

            row[TreeConstants.MY_SCORE] = show['my_score']
            row[TreeConstants.SCORE] = score_str
            row[TreeConstants.COLOR] = self._get_color(show, row[TreeConstants.AVAILABLE_EPS])
            row[TreeConstants.MY_STATUS] = show['my_status']
        return

        # print("Warning: Show ID not found in ShowView (%d)" % show['id'])

    def update_title(self, show, altname=None):
        for row in self:
            if int(row[TreeConstants.SHOW_ID]) == show['id']:
                if altname:
                    title_str = "%s [%s]" % (show['title'], altname)
                else:
                    title_str = show['title']

                row[TreeConstants.SHOW_ID] = title_str
                return

    def remove(self, show=None, show_id=None):
        for row in self:
            if int(row[TreeConstants.SHOW_ID]) == (show['id'] if show is not None else show_id):
                Gtk.ListStore.remove(self, row.iter)
                return

    def playing(self, show, is_playing):
        # Change the color if the show is currently playing
        for row in self:
            if int(row[TreeConstants.SHOW_ID]) == show['id']:
                if is_playing:
                    row[TreeConstants.COLOR] = self.colors['is_playing']
                else:
                    row[TreeConstants.COLOR] = self._get_color(show, row[TreeConstants.AVAILABLE_EPS])
                return


class ShowListFilter(Gtk.TreeModelFilter):
    def __init__(self, status=None, *args, **kwargs):
        super().__init__(
            *args,
            **kwargs
        )
        self.set_visible_func(self.status_filter)
        self._status = status

    def status_filter(self, model, iterator, data):
        return self._status is None or model[iterator][TreeConstants.MY_STATUS] == self._status

    def get_value(self, obj, key='id'):
        try:
            if type(obj) == Gtk.TreePath:
                obj = self.get_iter(obj)
            if isinstance(key, (str,)):
                key = self.props.child_model.column(key)
            return super().get_value(obj, key)
        except Exception:
            return None


class ShowTreeView(Gtk.TreeView):
    __gsignals__ = {'column-toggled': (GObject.SignalFlags.RUN_LAST,
                                       GObject.TYPE_PYOBJECT, (GObject.TYPE_STRING, GObject.TYPE_BOOLEAN))}

    def __init__(self, colors, visible_columns, status, _list, progress_style=1):
        Gtk.TreeView.__init__(self)

        self.colors = colors
        self.visible_columns = visible_columns
        self.progress_style = progress_style
        self.status = status
        self._list = _list

        self.set_model(
            Gtk.TreeModelSort(
                model=ShowListFilter(
                    status=self.status,
                    child_model=self._list
                )
            )
        )

        self.set_enable_search(True)
        self.set_search_column(TreeConstants.TITLE)
        self.set_property('has-tooltip', True)
        self.connect('query-tooltip', self.show_tooltip)

        self.cols = dict()
        # Defines the default column order as well
        self.available_columns = (
            ('Title', TreeConstants.TITLE),
            ('Watched', TreeConstants.MY_PROGRESS),
            ('Score', TreeConstants.MY_SCORE),
            ('Next episode', TreeConstants.NEXT_EPISODE_AIR_TIME_RELATIVE),
            ('Start', TreeConstants.START_DATE),
            ('End', TreeConstants.END_DATE),
            ('My start', TreeConstants.MY_START_DATE),
            ('My end', TreeConstants.MY_FINISH_DATE),
            ('Progress', TreeConstants.PROGRESS),
        )

        for (name, key) in self.available_columns:
            self.cols[name] = Gtk.TreeViewColumn()
            self.cols[name].set_sort_column_id(key)

            # Set up the percent / progress bar
            if name == 'Progress':
                if self.progress_style == 0:
                    renderer = Gtk.CellRendererProgress()
                    self.cols[name].pack_start(renderer, False)
                    self.cols[name].add_attribute(renderer, 'value', TreeConstants.PROGRESS)
                else:
                    renderer = ProgressCellRenderer(self.colors)
                    self.cols[name].pack_start(renderer, False)
                    self.cols[name].add_attribute(renderer, 'value', TreeConstants.MY_PROGRESS)
                    self.cols[name].add_attribute(renderer, 'total', TreeConstants.TOTAL_EPS)
                    self.cols[name].add_attribute(renderer, 'subvalue', TreeConstants.AIRED_EPS)
                    self.cols[name].add_attribute(renderer, 'eps', TreeConstants.AVAILABLE_EPS)
            else:
                renderer = Gtk.CellRendererText()
                self.cols[name].pack_start(renderer, False)

            if name not in self.visible_columns:
                self.cols[name].set_visible(False)

            # Populate columns
            match name:
                case 'Title':
                    self.cols[name].set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
                    self.cols[name].set_resizable(True)
                    self.cols[name].set_expand(True)
                    self.cols[name].add_attribute(renderer, 'text', TreeConstants.TITLE)
                    self.cols[name].add_attribute(renderer, 'foreground', TreeConstants.COLOR)
                    renderer.set_property('ellipsize', Pango.EllipsizeMode.END)

                case 'Watched':
                    self.cols[name].add_attribute(renderer, 'text', TreeConstants.EPISODES)

                case 'Progress':
                    self.cols[name].set_min_width(200)

                case 'Score':
                    self.cols[name].add_attribute(renderer, 'text', TreeConstants.SCORE)

                case 'Start':
                    self.cols[name].add_attribute(renderer, 'text', TreeConstants.START_DATE)

                case 'End':
                    self.cols[name].add_attribute(renderer, 'text', TreeConstants.END_DATE)

                case 'My start':
                    self.cols[name].add_attribute(renderer, 'text', TreeConstants.MY_START_DATE)

                case 'My end':
                    self.cols[name].add_attribute(renderer, 'text', TreeConstants.MY_FINISH_DATE)

                case 'Next episode':
                    self.cols[name].add_attribute(renderer, 'text', TreeConstants.NEXT_EPISODE_AIR_TIME_RELATIVE)
                    self.get_model().set_sort_func(sort_column_id=TreeConstants.NEXT_EPISODE_AIR_TIME_RELATIVE,
                                                   sort_func=self._next_episode_sort_func, user_data=self)

                case _:
                    pass

            # This is a hack to allow for right-clickable header
            label = Gtk.Label(name)
            label.show()
            self.cols[name].set_widget(label)
            w = self.cols[name].get_widget()
            while not isinstance(w, Gtk.Button):
                w = w.get_parent()
            w.connect('button-press-event', self._header_button_press)

            self.append_column(self.cols[name])

        # for (name, key) in self.available_columns:
        #     self.cols[name] = Gtk.TreeViewColumn(name)
        #     self.cols[name].set_sort_column_id(key)
        #     self.cols[name].set_resizable(False)
        #     self.cols[name].set_reorderable(True)
        #
        #     if name == 'Title':
        #         self.cols[name].set_alignment(0.0)
        #         self.cols[name].set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        #     else:
        #         self.cols[name].set_alignment(0.5)
        #         self.cols[name].set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        #
        #     # This is a hack to allow for right-clickable header
        #     label = Gtk.Label(name)
        #     label.show()
        #     self.cols[name].set_widget(label)
        #
        #     w = self.cols[name].get_widget()
        #     while not isinstance(w, Gtk.Button):
        #         w = w.get_parent()
        #
        #     w.connect('button-press-event', self._header_button_press)
        #
        #     if name not in self.visible_columns:
        #         self.cols[name].set_visible(False)
        #
        #     self.append_column(self.cols[name])

        # renderer_title = Gtk.CellRendererText()
        # self.cols['Title'].pack_start(renderer_title, True)
        # self.cols['Title'].set_resizable(True)
        # self.cols['Title'].set_expand(True)
        # self.cols['Title'].add_attribute(renderer_title, 'text', RowConstants.TITLE)
        # # Using foreground-gdk does not work, possibly due to the timing of it being set
        # self.cols['Title'].add_attribute(renderer_title, 'foreground', RowConstants.COLOR)
        # renderer_title.set_property('ellipsize', Pango.EllipsizeMode.END)
        #
        # renderer_progress = Gtk.CellRendererText()
        # renderer_progress.set_alignment(0.5, 0.5)
        # self.cols['Progress'].set_reorderable(True)
        # self.cols['Progress'].pack_start(renderer_progress, False)
        # self.cols['Progress'].add_attribute(renderer_progress, 'text', RowConstants.EPISODES)
        #
        # if self.progress_style == 0:
        #     renderer_percent = Gtk.CellRendererProgress()
        #     self.cols['Percent'].pack_start(renderer_percent, False)
        #     self.cols['Percent'].add_attribute(renderer_percent, 'value', RowConstants.PROGRESS)
        # else:
        #     renderer_percent = ProgressCellRenderer(self.colors)
        #     self.cols['Percent'].pack_start(renderer_percent, False)
        #     self.cols['Percent'].add_attribute(renderer_percent, 'value', RowConstants.MY_PROGRESS)
        #     self.cols['Percent'].add_attribute(renderer_percent, 'total', RowConstants.TOTAL_EPS)
        #     self.cols['Percent'].add_attribute(renderer_percent, 'subvalue', RowConstants.AIRED_EPS)
        #     self.cols['Percent'].add_attribute(renderer_percent, 'eps', RowConstants.AVAILABLE_EPS)
        # renderer_percent.set_fixed_size(100, -1)
        # self.cols['Percent'].set_min_width(100)
        #
        # renderer_score = Gtk.CellRendererText()
        # renderer_score.set_alignment(0.5, 0.5)
        # self.cols['Score'].pack_end(renderer_score, False)
        # self.cols['Score'].add_attribute(renderer_score, 'text', RowConstants.SCORE)
        #
        # renderer_start = Gtk.CellRendererText()
        # renderer_start.set_alignment(0.5, 0.5)
        # self.cols['Start'].pack_start(renderer_start, False)
        # self.cols['Start'].add_attribute(renderer_start, 'text', RowConstants.START_DATE)
        #
        # renderer_end = Gtk.CellRendererText()
        # renderer_end.set_alignment(0.5, 0.5)
        # self.cols['End'].pack_start(renderer_end, False)
        # self.cols['End'].add_attribute(renderer_end, 'text', RowConstants.END_DATE)
        #
        # renderer_my_start = Gtk.CellRendererText()
        # renderer_my_start.set_alignment(0.5, 0.5)
        # self.cols['My start'].pack_start(renderer_my_start, False)
        # self.cols['My start'].add_attribute(renderer_my_start, 'text', RowConstants.MY_START_DATE)
        #
        # renderer_my_end = Gtk.CellRendererText()
        # renderer_my_end.set_alignment(0.5, 0.5)
        # self.cols['My end'].pack_start(renderer_my_end, False)
        # self.cols['My end'].add_attribute(renderer_my_end, 'text', RowConstants.MY_FINISH_DATE)
        #
        # renderer_next_episode = Gtk.CellRendererText()
        # renderer_next_episode.set_alignment(0.5, 0.5)
        # self.cols['Next episode'].pack_start(renderer_next_episode, False)
        # self.cols['Next episode'].add_attribute(renderer_next_episode, 'text', RowConstants.NEXT_EPISODE_AIR_TIME)

    def _header_button_press(self, button, event):
        if event.button == 3:
            menu = Gtk.Menu()
            for name, sort in self.available_columns:
                is_active = name in self.visible_columns

                item = Gtk.CheckMenuItem(name)
                item.set_active(is_active)
                item.connect('activate', self._header_menu_item,
                             name, not is_active)
                menu.append(item)
                item.show()

            menu.popup_at_pointer(event)
            return True

        return False

    # Time based sort function for the "Next episode" column. Always sorts "-" and "?" below everything.
    @staticmethod
    def _next_episode_sort_func(model, iter1, iter2, user_data) -> int:
        # Get the values from the "Next episode" column for the two rows
        value1 = model.get_value(iter1, TreeConstants.NEXT_EPISODE_AIR_TIME_RELATIVE)
        value2 = model.get_value(iter2, TreeConstants.NEXT_EPISODE_AIR_TIME_RELATIVE)

        sort_order = user_data.cols['Next episode'].get_sort_order()
        special_cases = ('-', '?')

        if value1 in special_cases:
            return 1 if sort_order == Gtk.SortType.ASCENDING else -1
        elif value2 in special_cases:
            return -1 if sort_order == Gtk.SortType.ASCENDING else 1

        # Parse the time intervals, convert everything to minutes and sort accordingly
        days1, hours1, minutes1 = utils.parse_time_interval(value1)
        days2, hours2, minutes2 = utils.parse_time_interval(value2)

        total_minutes1 = days1 * 24 * 60 + hours1 * 60 + minutes1
        total_minutes2 = days2 * 24 * 60 + hours2 * 60 + minutes2

        if total_minutes1 < total_minutes2:
            return -1
        elif total_minutes1 == total_minutes2:
            return 0
        else:
            return 1

    @property
    def filter(self):
        return self.props.model.props.model

    def show_tooltip(self, view, x, y, kbd, tip):
        (has_path, tx, ty,
         model, path, tree_iter) = view.get_tooltip_context(x, y, kbd)
        if not has_path:
            return False

        _, col, _, _ = view.get_path_at_pos(tx, ty)
        if col != self.cols['Progress']:
            return False

        def gv(key):
            return model.get_value(tree_iter, ShowListStore.column(key))

        lines = ["Watched: %d" % gv(TreeConstants.MY_PROGRESS)]

        aired = gv(TreeConstants.AIRED_EPS)
        status = gv(TreeConstants.SHOW_STATUS)
        if aired and not status == utils.Status.NOTYET:
            lines.append("Aired%s: %d" % (
                ' (estimated)' if status == utils.Status.AIRING else '', aired))

        avail_eps = gv(TreeConstants.AVAILABLE_EPS)
        if len(avail_eps) > 0:
            lines.append("Available: %d" % max(avail_eps))

        lines.append("Total: %s" % (gv(TreeConstants.TOTAL_EPS) or '?'))

        tip.set_markup('\n'.join(lines))
        renderer = next(iter(col.get_cells()))
        self.set_tooltip_cell(tip, path, col, renderer)
        return True

    def _header_menu_item(self, w, column_name, visible):
        self.emit('column-toggled', column_name, visible)

    def select(self, show):
        """Select specified row or first if not found"""
        for row in self.get_model():
            if int(row[TreeConstants.SHOW_ID]) == show['id']:
                selection = self.get_selection()
                selection.select_iter(row.iter)
                return

        self.get_selection().select_path(Gtk.TreePath.new_first())


class ProgressCellRenderer(Gtk.CellRenderer):
    value = 0
    subvalue = 0
    _total = 0
    eps = []
    _subheight = 5

    __gproperties__ = {
        "value": (GObject.TYPE_INT, "Value",
                  "Progress percentage", 0, 100000, 0,
                  GObject.ParamFlags.READWRITE),

        "subvalue": (GObject.TYPE_INT, "Subvalue",
                     "Sub percentage", 0, 100000, 0,
                     GObject.ParamFlags.READWRITE),

        "total": (GObject.TYPE_INT, "Total",
                  "Total percentage", 0, 100000, 0,
                  GObject.ParamFlags.READWRITE),

        "eps": (GObject.TYPE_PYOBJECT, "Episodes",
                "Available episodes",
                GObject.ParamFlags.READWRITE),
    }

    def __init__(self, colors):
        Gtk.CellRenderer.__init__(self)
        self.colors = colors
        self.value = self.get_property("value")
        self.subvalue = self.get_property("subvalue")
        self.total = self.get_property("total")
        self.eps = self.get_property("eps")

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    @property
    def total(self):
        return self._total if self._total > 0 else len(self.eps)

    @total.setter
    def total(self, value):
        self._total = value

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_render(self, cr, widget, background_area, cell_area, flags):
        (x, y, w, h) = self._do_get_size(widget, cell_area)

        # set_source_rgb(0.9, 0.9, 0.9)
        cr.set_source_rgb(*self.__get_color(self.colors['progress_bg']))
        cr.rectangle(x, y, w, h)
        cr.fill()

        if not self.total:
            return

        if self.subvalue:
            if self.subvalue > self.total:
                mid = w
            else:
                mid = int(w / float(self.total) * self.subvalue)

            # set_source_rgb(0.7, 0.7, 0.7)
            cr.set_source_rgb(
                *self.__get_color(self.colors['progress_sub_bg']))
            cr.rectangle(x, y + h - self._subheight, mid, h - (h - self._subheight))
            cr.fill()

        if self.value:
            if self.value >= self.total:
                # set_source_rgb(0.6, 0.8, 0.7)
                cr.set_source_rgb(
                    *self.__get_color(self.colors['progress_complete']))
                cr.rectangle(x, y, w, h)
            else:
                mid = int(w / float(self.total) * self.value)
                # set_source_rgb(0.6, 0.7, 0.8)
                cr.set_source_rgb(
                    *self.__get_color(self.colors['progress_fg']))
                cr.rectangle(x, y, mid, h)
            cr.fill()

        if self.eps:
            # set_source_rgb(0.4, 0.5, 0.6)
            cr.set_source_rgb(
                *self.__get_color(self.colors['progress_sub_fg']))
            for episode in self.eps:
                if 0 < episode <= self.total:
                    start = int(w / float(self.total) * (episode - 1))
                    finish = int(w / float(self.total) * episode)
                    cr.rectangle(x + start, y + h - self._subheight,
                                 finish - start, h - (h - self._subheight))
                    cr.fill()

    @classmethod
    def _do_get_size(cls, widget, cell_area):
        if cell_area is None:
            return 0, 0, 0, 0
        x = cell_area.x
        y = cell_area.y
        w = cell_area.width
        h = cell_area.height
        return x, y, w, h

    @staticmethod
    def __get_color(color_string):
        color = Gdk.color_parse(color_string)
        return color.red_float, color.green_float, color.blue_float

from PyQt5 import QtCore, QtGui

from trackma.ui.qt.thumbs import ThumbManager
from trackma.ui.qt.util import getColor, getIcon

from trackma import utils

import datetime

class ShowListModel(QtCore.QAbstractTableModel):
    """
    Main model used in the main window to show
    a list of shows in the user's list.
    """
    COL_ID = 0
    COL_TITLE = 1
    COL_MY_PROGRESS = 2
    COL_MY_SCORE = 3
    COL_PERCENT = 4
    COL_NEXT_EP = 5
    COL_START_DATE = 6
    COL_END_DATE = 7
    COL_MY_START = 8
    COL_MY_FINISH = 9
    COL_MY_TAGS = 10
    COL_MY_STATUS = 11

    columns = ['ID', 'Title', 'Progress', 'Score',
                'Percent', 'Next Episode', 'Start date', 'End date',
                'My start', 'My finish', 'Tags', 'Status']

    editable_columns = [COL_MY_PROGRESS, COL_MY_SCORE]

    common_flags = \
        QtCore.Qt.ItemIsSelectable | \
        QtCore.Qt.ItemIsEnabled | \
        QtCore.Qt.ItemNeverHasChildren

    date_format = "%Y-%m-%d"

    progressChanged = QtCore.pyqtSignal(QtCore.QVariant, int)
    scoreChanged = QtCore.pyqtSignal(QtCore.QVariant, float)

    def __init__(self, parent=None, palette=None):
        self.showlist = None
        self.palette = palette
        self.playing = set()
        self.mediainfo = {}

        super().__init__(parent)

    def setDateFormat(self, date_format):
        self.date_format = date_format

    def setMediaInfo(self, mediainfo):
        self.mediainfo = mediainfo

    def _date(self, obj):
        if obj:
            return obj.strftime(self.date_format)
        else:
            return '-'

    def _calculate_color(self, row, show):
        color = None

        if show['id'] in self.playing:
            color = 'is_playing'
        elif show.get('queued'):
            color = 'is_queued'
        elif self.library.get(show['id']) and max(self.library.get(show['id'])) > show['my_progress']:
            color = 'new_episode'
        elif show['status'] == utils.STATUS_AIRING:
            color = 'is_airing'
        elif show['status'] == utils.STATUS_NOTYET:
            color = 'not_aired'
        else:
            color = None

        if color:
            self.colors[row] = QtGui.QBrush(getColor(self.palette[color]))
        elif row in self.colors:
            del self.colors[row]

    def _calculate_next_ep(self, row, show):
        if self.mediainfo.get('date_next_ep'):
            if 'next_ep_time' in show:
                delta = show['next_ep_time'] - datetime.datetime.utcnow()
                self.next_ep[row] = "%i days, %02d hrs." % (delta.days, delta.seconds/3600)
            elif row in self.next_ep:
                del self.next_ep[row]

    def _calculate_eps(self, row, show):
        aired_eps = utils.estimate_aired_episodes(show)
        library_eps = self.library.get(show['id'])

        if library_eps:
            library_eps = library_eps.keys()

        if aired_eps or library_eps:
            self.eps[row] = (aired_eps, library_eps)
        elif row in self.eps:
            del self.eps[row]

    def setShowList(self, showlist, altnames, library):
        self.beginResetModel()

        self.showlist = list(showlist)
        self.altnames = altnames
        self.library = library

        self.id_map = {}
        self.colors = {}
        self.next_ep = {}
        self.eps = {}

        for row, show in enumerate(self.showlist):
            self.id_map[show['id']] = row
            self._calculate_color(row, show)
            self._calculate_next_ep(row, show)
            self._calculate_eps(row, show)

        self.endResetModel()

    def update(self, showid, is_playing=None):
        # Recalculate color and emit the changed signal
        row = self.id_map[showid]
        show = self.showlist[row]

        if is_playing is not None:
            if is_playing:
                self.playing.add(showid)
            else:
                self.playing.discard(showid)

        self._calculate_color(row, show)
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(self.columns)-1))

    def rowCount(self, parent):
        if self.showlist:
            return len(self.showlist)
        else:
            return 0

    def columnCount(self, parent):
        return len(self.columns)

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.columns[section]

    def setData(self, index, value, role):
        row, column = index.row(), index.column()
        show = self.showlist[row]

        if column == ShowListModel.COL_MY_PROGRESS:
            self.progressChanged.emit(show['id'], value)
        elif column == ShowListModel.COL_MY_SCORE:
            self.scoreChanged.emit(show['id'], value)

        return True

    def data(self, index, role):
        row, column = index.row(), index.column()
        show = self.showlist[row]

        if role == QtCore.Qt.DisplayRole:
            if column == ShowListModel.COL_ID:
                return show['id']
            elif column == ShowListModel.COL_TITLE:
                title_str = show['title']
                if show['id'] in self.altnames:
                    title_str += " [%s]" % self.altnames[show['id']]
                return title_str
            elif column == ShowListModel.COL_MY_PROGRESS:
                return "{} / {}".format(show['my_progress'], show['total'] or '?')
            elif column == ShowListModel.COL_MY_SCORE:
                return show['my_score']
            elif column == ShowListModel.COL_PERCENT:
                #return "{:.0%}".format(show['my_progress'] / 100)
                if not self.mediainfo.get('can_play'):
                    return None

                if show['total']:
                    total = show['total']
                else:
                    total = (int(show['my_progress']/12)+1)*12 # Round up to the next cour

                if row in self.eps:
                    return (show['my_progress'], total, self.eps[row][0], self.eps[row][1])
                else:
                    return (show['my_progress'], total, None, None)
            elif column == ShowListModel.COL_NEXT_EP:
                return self.next_ep.get(row, '-')
            elif column == ShowListModel.COL_START_DATE:
                return self._date(show['start_date'])
            elif column == ShowListModel.COL_END_DATE:
                return self._date(show['end_date'])
            elif column == ShowListModel.COL_MY_START:
                return self._date(show['my_start_date'])
            elif column == ShowListModel.COL_MY_FINISH:
                return self._date(show['my_finish_date'])
            elif column == ShowListModel.COL_MY_TAGS:
                return show.get('my_tags', '-')
            elif column == ShowListModel.COL_MY_STATUS:
                return self.mediainfo['statuses_dict'][show['my_status']]
        elif role == QtCore.Qt.BackgroundRole:
            return self.colors.get(row)
        elif role == QtCore.Qt.DecorationRole:
            if column == ShowListModel.COL_TITLE and show['id'] in self.playing:
                return getIcon('media-playback-start')
        elif role == QtCore.Qt.TextAlignmentRole:
            if column in [ShowListModel.COL_MY_PROGRESS, ShowListModel.COL_MY_SCORE]:
                return QtCore.Qt.AlignHCenter
        elif role == QtCore.Qt.ToolTipRole:
            if column == ShowListModel.COL_PERCENT:
                tooltip = "Watched: %d<br>" % show['my_progress']
                if self.eps.get(row):
                    (aired_eps, library_eps) = self.eps.get(row)
                    if aired_eps:
                        tooltip += "Aired (estimated): %d<br>" % aired_eps
                    if library_eps:
                        tooltip += "Latest available: %d<br>" % max(library_eps)
                tooltip += "Total: %d" % show['total']

                return tooltip
        elif role == QtCore.Qt.EditRole:
            if column == ShowListModel.COL_MY_PROGRESS:
                return (show['my_progress'], show['total'], 0, 1)
            elif column == ShowListModel.COL_MY_SCORE:
                if isinstance(self.mediainfo['score_step'], float):
                    decimals = len(str(self.mediainfo['score_step']).split('.')[1])
                else:
                    decimals = 0

                return (show['my_score'], self.mediainfo['score_max'], decimals, self.mediainfo['score_step'])

    def flags(self, index):
        if index.column() in self.editable_columns:
            return self.common_flags | QtCore.Qt.ItemIsEditable
        else:
            return self.common_flags

class AddTableModel(QtCore.QAbstractTableModel):
    columns = ["Name", "Type", "Total"]
    types = {utils.TYPE_TV: "TV",
             utils.TYPE_MOVIE: "Movie",
             utils.TYPE_OVA: "OVA",
             utils.TYPE_SP: "Special"}

    def __init__(self, parent=None):
        self.results = None

        super().__init__(parent)

    def setResults(self, new_results):
        self.beginResetModel()
        self.results = new_results
        self.endResetModel()

    def rowCount(self, parent):
        if self.results:
            return len(self.results)
        else:
            return 0

    def columnCount(self, parent):
        return 3

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.columns[section]

    def data(self, index, role):
        row, column = index.row(), index.column()

        if role == QtCore.Qt.DisplayRole:
            item = self.results[row]

            if column == 0:
                return item.get('title')
            elif column == 1:
                if 'type' in item:
                    return self.types.get(item['type'], '?')
                else:
                    return '?'
            elif column == 2:
                return item.get('total', '?')


class AddListModel(QtCore.QAbstractListModel):
    """
    List model meant to be used with the Add show list view.

    It manages thumbnails and queues their downloads with the
    ThumbManager as necessary.
    """

    def __init__(self, parent=None, api_info=None):
        self.results = None
        self.thumbs = {}
        self.api_info = api_info

        self.pool = ThumbManager()
        self.pool.itemFinished.connect(self.gotThumb)

        super().__init__(parent)

    def gotThumb(self, iid, thumb):
        iid = int(iid)
        self.thumbs[iid] = thumb.scaled(100, 140, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation);

        self.dataChanged.emit(self.index(iid), self.index(iid))

    def setResults(self, new_results):
        """ This method will process a new list of shows and get their
        thumbnails if necessary. """

        self.beginResetModel()

        self.results = new_results

        self.thumbs.clear()

        if self.results:
            for row, item in enumerate(self.results):
                if item.get('image'):
                    filename = utils.to_cache_path("%s_%s_f_%s.jpg" % (self.api_info['shortname'], self.api_info['mediatype'], item['id']))

                    if self.pool.exists(filename):
                        self.thumbs[row] = self.pool.getThumb(filename).scaled(100, 140, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation);
                    else:
                        self.pool.queueDownload(row, item['image'], filename)

        self.endResetModel()

    def rowCount(self, parent):
        if self.results:
            return len(self.results)
        else:
            return 0

    def data(self, index, role):
        row = index.row()
        if role == QtCore.Qt.DisplayRole:
            return self.results[row]
        elif role == QtCore.Qt.DecorationRole:
            return self.thumbs.get(row)
        elif role == QtCore.Qt.BackgroundRole:
            t = self.results[row].get('type')
            if t == utils.TYPE_TV:
                return QtGui.QColor(202, 253, 150)
            elif t == utils.TYPE_MOVIE:
                return QtGui.QColor(150, 202, 253)
            elif t == utils.TYPE_OVA:
                return QtGui.QColor(253, 253, 150)
            elif t == utils.TYPE_SP:
                return QtGui.QColor(253, 150, 150)
            else:
                return QtGui.QColor(250, 250, 250)

        return None

class AddListProxy(QtCore.QSortFilterProxyModel):
    def lessThan(self, left, right):
        leftData = self.sourceModel().data(left, QtCore.Qt.DisplayRole)
        rightData = self.sourceModel().data(right, QtCore.Qt.DisplayRole)

        return leftData['type'] < rightData['type']

class ShowListProxy(QtCore.QSortFilterProxyModel):
    filter_columns = None
    filter_status = None

    def setFilterStatus(self, status):
        self.filter_status = status
        self.invalidateFilter()

    def clearColumnFilters(self):
        self.filters = {}

    def setFilterColumns(self, columns):
        self.filter_columns = columns
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if self.filter_status is not None and self.sourceModel().showlist[source_row]['my_status'] != self.filter_status:
            return False

        if self.filter_columns:
            for col in range(self.sourceModel().columnCount(source_parent)):
                index = self.sourceModel().index(source_row, col)
                if (col in self.filter_columns and
                    self.filter_columns[col] not in str(self.sourceModel().data(index, QtCore.Qt.DisplayRole))):
                    return False

        return super(ShowListProxy, self).filterAcceptsRow( source_row, source_parent)

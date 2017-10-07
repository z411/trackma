from PyQt5 import QtCore, QtGui

from trackma.ui.qt.thumbs import ThumbManager

from trackma import utils

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
                return self.results[row].get('total')


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
                    filename = utils.get_filename('cache', "%s_%s_f_%s.jpg" % (self.api_info['shortname'], self.api_info['mediatype'], item['id']))
            
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

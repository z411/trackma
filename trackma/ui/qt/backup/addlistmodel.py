from PyQt5 import QtCore

from trackma.ui.qt.ThumbManager import ThumbManager

from trackma import utils

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
            return 6
    
    def data(self, index, role):
        row = index.row()
        if role == QtCore.Qt.DisplayRole:
            return self.results[row]
        elif role == QtCore.Qt.DecorationRole:
            return self.thumbs.get(row)

        return None


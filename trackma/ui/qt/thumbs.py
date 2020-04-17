import queue
import os

from PyQt5 import QtCore, QtGui, QtNetwork

ATTRIB_FILE = 1000
ATTRIB_ID   = 1001

class ThumbManager(QtCore.QObject):
    """
    This class manages the async downloads of thumbnails.
    getThumb gets a thumbnail from the cache, and
    queueDownload starts a remote download.
    
    When a remote download is finished, the itemFinished signal
    is emitted, along with the ID and a QImage object.
    """
    
    itemFinished = QtCore.pyqtSignal(str, QtGui.QImage)
    
    def __init__(self, parent=None):
        self.manager = QtNetwork.QNetworkAccessManager()
        self.queue = queue.Queue()
        self.downloads = {}
        
        super().__init__(parent)
        
    def exists(self, filename):
        return os.path.isfile(filename)

    def getThumb(self, filename):
        return QtGui.QImage(filename)
        
    def queueDownload(self, iid, url, filename):
        self.queue.put((iid, url, filename))
        self.processNext()
        
    def processNext(self):
        if not self.queue.empty() and len(self.downloads) < 3:
            (iid, url, filename) = self.queue.get()
            
            request = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
            request.setAttribute(QtNetwork.QNetworkRequest.Attribute(ATTRIB_FILE), filename);
            request.setAttribute(QtNetwork.QNetworkRequest.Attribute(ATTRIB_ID), iid);

            reply = self.manager.get(request)            
            self.downloads[filename] = reply
            
            reply.finished.connect(self.onItemFinished)
        
    def onItemFinished(self):
        reply = self.sender()
        iid = str(reply.request().attribute(ATTRIB_ID))
        fname = reply.request().attribute(ATTRIB_FILE)
        
        data = reply.readAll()
        image = QtGui.QImage.fromData(data)
        thumb = image.scaled(200, 280, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation);
        thumb.save(fname)
        
        self.downloads.pop(fname)
        self.itemFinished.emit(iid, thumb)
        self.processNext()

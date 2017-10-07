from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QStyledItemDelegate, QStyle

MARGIN = 5
PADDING = 5
WIDTH = 450
MIN_HEIGHT = 200
COLUMN_A = 100
COLUMN_B = 290

class AddListDelegate(QStyledItemDelegate):
    """ This is the delegate that handles the rendering of cards
    in the List View of the Add show dialog. """
    
    def __init__(self, parent=None):
        self.results = None
        
        self.font = QtGui.QFont()
        
        fm = QtGui.QFontMetrics(self.font)
        self.fh = fm.height()

        super().__init__(parent)
        
    def _get_extra(self, extra, key):
        for k, v in extra:
            if k == key:
                return v

    def paint(self, painter, option, index):
        outerRect = option.rect - QtCore.QMargins(MARGIN, MARGIN, MARGIN, MARGIN)
            
        data = index.data()
        thumb = index.data(QtCore.Qt.DecorationRole)
        
        painter.save()
        
        color = index.data(QtCore.Qt.BackgroundRole)
        
        # Draw background box
        painter.setPen(QtGui.QPen(QtGui.QColor(210, 210, 210)))
        painter.setBrush(QtGui.QBrush(color.lighter(135)))
        painter.drawRect(outerRect)
        
        # Prepare to draw inside
        baseRect = outerRect - QtCore.QMargins(PADDING, PADDING, PADDING, PADDING)
        painter.setPen(QtCore.Qt.NoPen)
        
        # Draw thumbnail (if any)
        if thumb:
            painter.drawImage(baseRect.topLeft(), thumb)
        
        # Create text QRect and draw the title background
        textRect = baseRect.adjusted(COLUMN_A+5, 0, 0, 0)
        textRect.setHeight(self.fh + 5)
        painter.setBrush(QtGui.QBrush(color))
        painter.drawRect(textRect);
        
        # Set our font to bold
        bfont = QtGui.QFont(self.font)
        bfont.setWeight(QtGui.QFont.Bold)
        
        painter.setFont(bfont)
        painter.setPen(QtGui.QPen(QtGui.QColor(10, 10, 10)))
        
        # Make some padding
        textRect -= QtCore.QMargins(5, 0, 5, 0)
        
        # Draw title
        painter.drawText(textRect, QtCore.Qt.AlignVCenter, data['title'])
        
        # Draw the details
        textRect.setHeight(self.fh)
        dataRect = textRect.adjusted(75, 0, 0, 0)
        
        textRect.translate(0, self.fh + 10)
        painter.drawText(textRect, QtCore.Qt.AlignTop, "Date")
        textRect.translate(0, self.fh + 5)
        painter.drawText(textRect, QtCore.Qt.AlignTop, "Episodes")
        
        # Draw data
        painter.setFont(self.font)
        
        # Dates
        if data.get('start_date'):
            d_from = data['start_date'].strftime('%d/%m/%y')
        else:
            d_from = '?'
        if data.get('end_date'):
            d_end = data['end_date'].strftime('%d/%m/%y')
        else:
            d_end = '?'
        
        dataRect.translate(0, self.fh + 10)
        painter.drawText(dataRect, QtCore.Qt.AlignTop, "{} to {}".format(d_from, d_end))
        dataRect.translate(0, self.fh + 5)
        painter.drawText(dataRect, QtCore.Qt.AlignTop, str(data.get('total') or '?'))
        
        # Draw synopsis
        textRect.translate(0, self.fh + 5)
        textRect.setBottomRight(baseRect.bottomRight())
        
        if 'extra' in data:
            painter.drawText(textRect, QtCore.Qt.AlignTop | QtCore.Qt.TextWordWrap, self._get_extra(data['extra'], 'Synopsis'))
        
        # Draw select box
        if option.state & QStyle.State_Selected:
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_Overlay)
            #painter.setOpacity(0.5)
            painter.fillRect(outerRect, option.palette.highlight())
        
        painter.restore()
    
    def sizeHint(self, option, index):
        return QtCore.QSize(WIDTH, min(MIN_HEIGHT, self.fh*10+15))

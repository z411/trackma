from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QStyledItemDelegate, QStyle, QDoubleSpinBox, QStyleOptionProgressBar

MARGIN = 5
PADDING = 5
WIDTH = 450
MIN_HEIGHT = 200
COLUMN_A = 100
COLUMN_B = 290

from trackma.ui.qt.util import getColor

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

class ShowsTableDelegate(QStyledItemDelegate):
    """
    Custom delegate that shows a custom progress bar
    for detailed information about episodes, and editing
    the progress and score.
    """
    # Enum BarStyle
    BarStyleBasic = 0   # Basic native ProgressBar appearance
    BarStyle04 = 1      # Rectangular dual bar of Trackma v0.4
    BarStyleHybrid = 2  # Native ProgressBar with v0.4 library subbar overlaid

    _subvalue = -1
    _episodes = []
    _subheight = 5
    _bar_style = BarStyle04
    _show_text = False

    def __init__(self, parent, palette=None):
        self.colors = palette

        super().__init__(parent)

    def paint(self, painter, option, index):
        if index.column() == 4:
            rect = option.rect
            data = index.model().data(index)

            if not data:
                return

            (value, maximum, subvalue, episodes) = data
            m = index.model().sourceModel()

            painter.save()

            if self._bar_style is self.BarStyleBasic:
                prog_options = QStyleOptionProgressBar()
                prog_options.maximum = maximum
                prog_options.progress = value
                prog_options.rect = rect
                prog_options.text = '%d%%' % (value*100/maximum)
                prog_options.textVisible = self._show_text
                option.widget.style().drawControl(QStyle.CE_ProgressBar, prog_options, painter)

            elif self._bar_style is self.BarStyle04:
                painter.setBrush(getColor(self.colors['progress_bg']))
                painter.setPen(QtCore.Qt.transparent)
                painter.drawRect(rect)
                self.paintSubValue(painter, rect, subvalue, maximum)
                if value > 0:
                    if value >= maximum:
                        painter.setBrush(getColor(self.colors['progress_complete']))
                        mid = rect.width()
                    else:
                        painter.setBrush(getColor(self.colors['progress_fg']))
                        mid = int(rect.width() / float(maximum) * value)
                    progressRect = QtCore.QRect(rect.x(), rect.y(), mid, rect.height())
                    painter.drawRect(progressRect)
                self.paintEpisodes(painter, rect, episodes, maximum)

            elif self._bar_style is self.BarStyleHybrid:
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_Source)
                painter.fillRect(rect, QtCore.Qt.transparent)
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
                prog_options = QStyleOptionProgressBar()
                prog_options.maximum = maximum
                prog_options.progress = value
                prog_options.rect = rect
                prog_options.text = '%d%%' % (value*100/maximum)
                option.widget.style().drawControl(QStyle.CE_ProgressBar, prog_options, painter)
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceAtop)
                painter.setPen(QtCore.Qt.transparent)
                self.paintSubValue(painter, rect, subvalue, maximum)
                self.paintEpisodes(painter, rect, episodes, maximum)
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
                if self._show_text:
                    option.widget.style().drawControl(QStyle.CE_ProgressBarLabel, prog_options, painter)

            painter.restore()
        else:
            super().paint(painter, option, index)

    def paintSubValue(self, painter, rect, subvalue, maximum):
        if subvalue and maximum and subvalue <= maximum:
            painter.setBrush(getColor(self.colors['progress_sub_bg']))
            mid = int(rect.width() / float(maximum) * subvalue)
            progressRect = QtCore.QRect(
                rect.x(),
                rect.y()+rect.height()-self._subheight,
                mid,
                rect.height()-(rect.height()-self._subheight)
            )
            painter.drawRect(progressRect)

    def paintEpisodes(self, painter, rect, episodes, maximum):
        if episodes:
            for episode in episodes:
                painter.setBrush(getColor(self.colors['progress_sub_fg']))
                if episode <= maximum:
                    start = int(rect.width() / float(maximum) * (episode - 1))
                    finish = int(rect.width() / float(maximum) * episode)
                    progressRect = QtCore.QRect(
                        rect.x()+start,
                        rect.y()+rect.height()-self._subheight,
                        finish-start,
                        rect.height()-(rect.height()-self._subheight)
                    )
                    painter.drawRect(progressRect)

    def setBarStyle(self, style, show_text):
        self._bar_style = style
        self._show_text = show_text

    def sizeHint(self, option, index):
        return QtCore.QSize(option.rect.width(), QtGui.QFontMetrics(option.font).height() + 2);

    def createEditor(self, parent, option, index):
        editor = QDoubleSpinBox(parent)
        editor.setFrame(False)

        return editor

    def setEditorData(self, editor, index):
        (value, maximum, decimals,step) = index.model().data(index, QtCore.Qt.EditRole)

        editor.setMaximum(maximum or 999)
        editor.setDecimals(decimals or 0)
        editor.setSingleStep(step or 1)

        if value:
            editor.setValue(value)

    def setModelData(self, editor, model, index):
        editor.interpretText()
        old_value = index.model().data(index, QtCore.Qt.EditRole)[0]
        new_value = editor.value()

        if new_value != old_value:
            model.setData(index, new_value, QtCore.Qt.EditRole);


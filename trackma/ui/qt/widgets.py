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

import os
import datetime

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout,
    QScrollArea, QProgressBar, QTableWidget, QTableWidgetItem,
    QTableView, QAbstractItemView, QSplitter, QHeaderView, QListView)

from trackma.ui.qt.delegates import AddListDelegate, ShowsTableDelegate
from trackma.ui.qt.models import AddTableModel, AddListModel, AddListProxy, ShowListModel, ShowListProxy
from trackma.ui.qt.workers import ImageWorker
from trackma.ui.qt.util import getColor

from trackma import utils

pyqt_version = 5

class DetailsWidget(QWidget):
    def __init__(self, parent, worker):
        self.worker = worker

        QWidget.__init__(self, parent)

        # Build layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.show_title = QLabel()
        show_title_font = QtGui.QFont()
        show_title_font.setBold(True)
        show_title_font.setPointSize(12)
        self.show_title.setAlignment( QtCore.Qt.AlignCenter )
        self.show_title.setFont(show_title_font)

        info_area = QWidget()
        info_layout = QGridLayout()

        self.show_image = QLabel()
        self.show_image.setAlignment( QtCore.Qt.AlignTop )
        self.show_info = QLabel()
        self.show_info.setWordWrap(True)
        self.show_info.setAlignment( QtCore.Qt.AlignTop )
        self.show_description = QLabel()
        self.show_description.setWordWrap(True)
        self.show_description.setAlignment( QtCore.Qt.AlignTop )

        info_layout.addWidget( self.show_image,        0,0,1,1 )
        info_layout.addWidget( self.show_info,         1,0,1,1 )
        info_layout.addWidget( self.show_description,  0,1,2,1 )

        info_area.setLayout(info_layout)

        scroll_area = QScrollArea()
        scroll_area.setBackgroundRole(QtGui.QPalette.Light)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(info_area)

        main_layout.addWidget(self.show_title)
        main_layout.addWidget(scroll_area)

        self.setLayout(main_layout)

    def worker_call(self, function, ret_function, *args, **kwargs):
        # Run worker in a thread
        self.worker.set_function(function, ret_function, *args, **kwargs)
        self.worker.start()

    def load(self, show):
        metrics = QtGui.QFontMetrics(self.show_title.font())
        title = metrics.elidedText(show['title'], QtCore.Qt.ElideRight, self.show_title.width())

        self.show_title.setText( "<a href=\"%s\">%s</a>" % (show['url'], title) )
        self.show_title.setTextFormat(QtCore.Qt.RichText)
        self.show_title.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        self.show_title.setOpenExternalLinks(True)

        # Load show info
        self.show_info.setText('Wait...')
        self.worker_call('get_show_details', self.r_details_loaded, show)
        api_info = self.worker.engine.api_info

        # Load show image
        if show.get('image'):
            filename = utils.to_cache_path("%s_%s_f_%s.jpg" % (api_info['shortname'], api_info['mediatype'], show['id']))

            if os.path.isfile(filename):
                self.s_show_image(filename)
            else:
                self.show_image.setText('Downloading...')
                self.image_worker = ImageWorker(show['image'], filename, (200, 280))
                self.image_worker.finished.connect(self.s_show_image)
                self.image_worker.start()
        else:
            self.show_image.setText('No image')

    def s_show_image(self, filename):
        self.show_image.setPixmap( QtGui.QPixmap( filename ) )

    def r_details_loaded(self, result):
        if result['success']:
            details = result['result']

            info_strings = []
            description_strings = []
            description_keys = {'Synopsis', 'English', 'Japanese', 'Synonyms'} # This might come down to personal preference

            for line in details['extra']:
                if line[0] and line[1]:
                    if line[0] in description_keys:
                        description_strings.append( "<h3>%s</h3><p>%s</p>" % (line[0], line[1]) )
                    else:
                        if isinstance(line[1], list):
                            description_strings.append( "<h3>%s</h3><p>%s</p>" % (line[0], ', '.join(line[1])) )
                        elif len("%s" % line[1]) >= 17: # Avoid short tidbits taking up too much vertical space
                            info_strings.append( "<h3>%s</h3><p>%s</p>" % (line[0], line[1]) )
                        else:
                            info_strings.append( "<p><b>%s:</b> %s</p>" % (line[0], line[1]) )

            info_string = ''.join(info_strings)
            self.show_info.setText( info_string )
            description_string = ''.join(description_strings)
            self.show_description.setText( description_string )
        else:
            self.show_info.setText( 'There was an error while getting details.' )

class ShowsTableView(QTableView):
    """
    Regular table widget with context menu for show actions.

    """
    middleClicked = QtCore.pyqtSignal()

    def __init__(self, parent=None, palette=None):
        QTableView.__init__(self, parent)

        model = ShowListModel(palette=palette)
        proxymodel = ShowListProxy()
        proxymodel.setSourceModel(model)
        proxymodel.setFilterKeyColumn(-1)
        self.setModel(proxymodel)

        self.setItemDelegate(ShowsTableDelegate(self, palette=palette))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.horizontalHeader().setHighlightSections(False)
        if pyqt_version is 5:
            self.horizontalHeader().setSectionsMovable(True)
        else:
            self.horizontalHeader().setMovable(True)
        self.horizontalHeader().setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.verticalHeader().hide()
        self.setGridStyle(QtCore.Qt.NoPen)

    def contextMenuEvent(self, event):
        action = self.context_menu.exec_(event.globalPos())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

        if event.button() == QtCore.Qt.MidButton:
            self.middleClicked.emit()


class AddCardView(QListView):
    changed = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None, api_info=None):
        super().__init__(parent)

        m = AddListModel(api_info=api_info)
        proxy = AddListProxy()
        proxy.setSourceModel(m)
        proxy.sort(0, QtCore.Qt.AscendingOrder)

        self.setItemDelegate(AddListDelegate())
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setModel(proxy)

        self.selectionModel().currentRowChanged.connect(self.s_show_selected)

    def s_show_selected(self, new, old=None):
        if not new:
            return

        index = self.model().mapToSource(new).row()
        selected_show = self.getModel().results[index]

        self.changed.emit(selected_show)

    def setResults(self, results):
        self.getModel().setResults(results)

    def getModel(self):
        return self.model().sourceModel()


class AddTableDetailsView(QSplitter):
    """ This is a splitter widget that contains a table and
    a details widget. Used in the Add Show dialog. """

    changed = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None, worker=None):
        super().__init__(parent)

        self.table = QTableView()
        m = AddTableModel()
        proxy = QtCore.QSortFilterProxyModel()
        proxy.setSourceModel(m)

        self.table.setGridStyle(QtCore.Qt.NoPen)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setModel(proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, QtCore.Qt.AscendingOrder)

        if pyqt_version is 5:
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        else:
            self.table.horizontalHeader().setResizeMode(0, QHeaderView.Stretch)

        self.table.selectionModel().currentRowChanged.connect(self.s_show_selected)
        self.addWidget(self.table)

        self.details = DetailsWidget(parent, worker)
        self.addWidget(self.details)

        self.setSizes([1, 1])

    def s_show_selected(self, new, old=None):
        if not new:
            return

        index = self.table.model().mapToSource(new).row()
        selected_show = self.getModel().results[index]
        self.details.load(selected_show)

        self.changed.emit(selected_show)

    def setResults(self, results):
        self.getModel().setResults(results)

    def getModel(self):
        return self.table.model().sourceModel()

    def clearSelection(self):
        return self.table.clearSelection()

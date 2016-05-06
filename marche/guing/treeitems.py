#  -*- coding: utf-8 -*-
# *****************************************************************************
# Copyright (c) 2015 by the authors, see LICENSE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Module authors:
#   Alexander Lenz <alenz@dev-platypus.org>
#
# *****************************************************************************

from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QIcon, QBrush, QColor
from PyQt5.QtWidgets import QTreeWidgetItem, QWidget

from marche.guing.util import loadUi
from marche.jobs import STATE_STR, RUNNING, NOT_RUNNING, WARNING, DEAD, \
    STARTING, STOPPING, INITIALIZING



HOST_TREE_ITEM_TYPE = 1000 + 1
JOB_TREE_ITEM_TYPE = 1000 + 1

STATE_COLORS = {
        RUNNING:      ('green', ''),
        NOT_RUNNING:  ('black', ''),
        DEAD:         ('white', 'red'),
        WARNING:      ('black', 'yellow'),
        STARTING:     ('blue', ''),
        STOPPING:     ('blue', ''),
        INITIALIZING: ('blue', ''),
    }



class HostTreeItem(QTreeWidgetItem):
    def __init__(self, parent, host):
        QTreeWidgetItem.__init__(self, parent, HOST_TREE_ITEM_TYPE)
        self._host = host

        self.setText(0, host.hostname)
        self.setIcon(0, QIcon(':/marche/server.png'))

    @property
    def host(self):
        return self._host


class JobTreeItem(QTreeWidgetItem):
    def __init__(self, parent, host, service, instance, jobInfo, model):
        QTreeWidgetItem.__init__(self, parent, HOST_TREE_ITEM_TYPE)
        self._jobInfo = jobInfo
        self._buttons = JobButtonsWidget(host, service, instance)

        self.setText(0, instance if instance is not None else service)
        self.setExpanded(True)
        self.setTextAlignment(1, Qt.AlignHCenter | Qt.AlignVCenter)
        self.treeWidget().setItemWidget(self, 2, self._buttons)

        if jobInfo is not None:
            self.updateStatus(jobInfo['state'], jobInfo['ext_status'])

        self._buttons.startRequested.connect(model.startService)
        self._buttons.stopRequested.connect(model.stopService)
        self._buttons.restartRequested.connect(model.restartService)


    def updateStatus(self, state, extStatus):
        colors = STATE_COLORS.get(state, ('gray', ''))
        text = STATE_STR[state]

        self.setForeground(1, QBrush(QColor(colors[0]))
                           if colors[0] else QBrush())
        self.setBackground(1, QBrush(QColor(colors[1]))
                           if colors[1] else QBrush())
        self.setText(1, text.center(16))



class JobButtonsWidget(QWidget):
    startRequested = pyqtSignal(object, object,
                                object)  # hostadr, service, instance
    stopRequested = pyqtSignal(object, object,
                                object)  # hostadr, service, instance
    restartRequested = pyqtSignal(object, object,
                                object)  # hostadr, service, instance

    def __init__(self, host, service, instance, parent=None):
        QWidget.__init__(self, parent)
        loadUi(self, 'jobbuttons.ui', subdir='ui')
        self.layout().addStretch(2)

        self._host = host
        self._service = service
        self._instance = instance

        self.startBtn.clicked.connect(self.requestStart)
        self.stopBtn.clicked.connect(self.requestStop)
        self.restartBtn.clicked.connect(self.requestRestart)

    def requestStart(self):
        self.startRequested.emit(self._host, self._service, self._instance)

    def requestStop(self):
        self.stopRequested.emit(self._host, self._service, self._instance)

    def requestRestart(self):
        self.restartRequested.emit(self._host, self._service, self._instance)

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

from PyQt5.QtCore import Qt
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
    def __init__(self, parent, name, jobInfo):
        QTreeWidgetItem.__init__(self, parent, HOST_TREE_ITEM_TYPE)
        self._jobInfo = jobInfo
        self._buttons = JobButtonsWidget()

        self.setText(0, name)
        self.setExpanded(True)
        self.setTextAlignment(1, Qt.AlignHCenter | Qt.AlignVCenter)
        self.treeWidget().setItemWidget(self, 2, self._buttons)

        if jobInfo is not None:
            self.updateStatus(jobInfo['state'], jobInfo['ext_status'])

    def updateStatus(self, state, extStatus):
        colors = STATE_COLORS.get(state, ('gray', ''))
        text = STATE_STR[state]

        self.setForeground(1, QBrush(QColor(colors[0]))
                           if colors[0] else QBrush())
        self.setBackground(1, QBrush(QColor(colors[1]))
                           if colors[1] else QBrush())
        self.setText(1, text.center(16))



class JobButtonsWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        loadUi(self, 'jobbuttons.ui', subdir='ui')
        self.layout().addStretch(2)

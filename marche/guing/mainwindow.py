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

import socket
import ipaddress

import psutil
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QTreeWidgetItem, QInputDialog

import marche.guing.res
from marche.guing.util import loadUi
from marche.guing.model import Model


HOST_TREE_ITEM_TYPE = 1000 + 1


class HostTreeItem(QTreeWidgetItem):
    def __init__(self, parent, host):
        QTreeWidgetItem.__init__(self, parent, HOST_TREE_ITEM_TYPE)
        self._host = host

        self.setText(0, host.hostname)
        self.setIcon(0, QIcon(':/marche/server.png'))

    @property
    def host(self):
        return self._host


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        loadUi(self, 'mainwindow.ui', subdir='ui')

        self._model = Model()
        
        self._model.newHost.connect(self._addHostItem)
        self.actionAddSubnet.triggered.connect(self.addSubnet)

        # start with own subnet
        ownSubnet = self._determineOwnSubnet()
        if ownSubnet:
            self._model.addSubnet(ownSubnet)

    def addSubnet(self):
        subnet, ok = QInputDialog.getText(self,
            'Add subnet',
            'Subnet (netid/prefix):')

        if ok and subnet:
            self._model.addSubnet(subnet)

    def _determineOwnSubnet(self):
        # TODO move to platyutil
        ip = socket.gethostbyname(socket.gethostname())
        ifs = psutil.net_if_addrs()

        for _, addrs in ifs.items():
            for addr in addrs:
                if addr.address == ip:
                    return str(ipaddress.ip_network('%s/%s' % (ip,
                        addr.netmask), False))

    def _addHostItem(self, subnet, host):
        subnetItem = self._ensureSubnetItemExistance(subnet)
        hostItem = HostTreeItem(subnetItem, host)

    def _ensureSubnetItemExistance(self, subnet):
        items = self.srvTree.findItems(subnet, Qt.MatchExactly)
        if items:
            return items[0]

        item = QTreeWidgetItem(self.srvTree)
        item.setText(0, subnet)
        item.setIcon(0, QIcon(':/marche/servers-network.png'))
        item.setExpanded(True)

        return item

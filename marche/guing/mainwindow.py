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

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QTreeWidgetItem, QInputDialog, \
    QWidget, QHeaderView, QMessageBox, QApplication

from marche import get_version
import marche.guing.res  # noqa, pylint: disable=unused-import
from marche.guing.util import loadUi
from marche.utils import determine_subnet
from marche.guing.model import Model
from marche.guing.treeitems import HostTreeItem, JobTreeItem


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        loadUi(self, 'mainwindow.ui', subdir='ui')
        self.srvTree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.jobTree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 4)

        self._displayedHosts = []

        self.srvTree.currentItemChanged.connect(self.onSrvTreeItemChanged)

        self._model = Model()
        self._model.newHost.connect(self.addHostItem)
        self._model.newServiceList.connect(self.updatejobTree)
        self._model.newState.connect(self.updateStatus)

        self.actionAddHost.triggered.connect(self.addHost)
        self.actionAddSubnet.triggered.connect(self.addSubnet)
        self.actionExit.triggered.connect(self.onExit)

        # start with own subnet
        ownSubnet = determine_subnet()
        if ownSubnet:
            self._model.scanSubnet(ownSubnet)

    def addHost(self):
        host, ok = QInputDialog.getText(self,
                                          'Add host',
                                          'Host (host[:port]):')

        if ok and host:
            port = 12132
            if ':' in host:
                host, port = host.split(':')
            try:
                self._model.addHost(host, port)
            except RuntimeError as e:
                QMessageBox.critical(self, 'Could not add %s' % host,
                                     'Could not add %s: %s' % (host, e))

    def addSubnet(self):
        subnet, ok = QInputDialog.getText(self,
                                          'Add subnet',
                                          'Subnet (netid/prefix):')

        if ok and subnet:
            self._model.scanSubnet(subnet)

    def onExit(self):
        self._model.disconnect()
        self.close()

    def addHostItem(self, host):
        subnetItem = self._ensureSubnetItemExistance(host.subnet)
        HostTreeItem(subnetItem, host)

    def _ensureSubnetItemExistance(self, subnet):
        items = self.srvTree.findItems(subnet, Qt.MatchExactly)
        if items:
            return items[0]

        item = QTreeWidgetItem(self.srvTree)
        item.setText(0, subnet)
        item.setIcon(0, QIcon(':/marche/servers-network.png'))
        item.setExpanded(True)

        return item

    def onAbout(self):
        QMessageBox.about(
            self, 'About Marche GUI',
            '''
            <h2>About Marche GUI</h2>
            <p>
                Marche GUI is a graphical interface for the Marche process
                control system.
            </p>
            <h3>Authors:</h3>
            <ul>
                <li>
                    Copyright (C) 2015-2016
                    <a href="mailto:g.brandl@fz-juelich.de">Georg Brandl</a>
                </li>
                <li>
                    Copyright (C) 2015
                    <a href="mailto:alexander.lenz@frm2.tum.de">Alexander
                    Lenz (FRM-II)</a>
                </li>
            </ul>
            <h4 style="margin-top:20px;">Copyright (C) 2015-2016 Dev Platypus</h4>
            <table>
                <tr>
                    <td>
                        <img src=":/marche/devplatypus_logo.png" />
                    </td>
                    <td style="vertical-align:middle">
                        <ul>
                            <li>Copyright (C) 2015-2016
                                <a href="mailto:alenz@dev-platypus.org">Alexander
                                Lenz</a>
                            </li>
                            <li>Copyright (C) 2015-2016
                                <a href="mailto:aschulz@dev-platypus.org">Andreas
                                Schulz</a>
                            </li>
                        </ul>
                    </td>
                </tr>
            </table>
            <p>
              Marche is published under the
              <a href="http://www.gnu.org/licenses/gpl.html">GPL
                (GNU General Public License)</a>
            </p>
            <p style="font-weight: bold">
              Version: %s
            </p>
            ''' % get_version())

    def onAboutQt(self):
        QMessageBox.aboutQt(self, 'About Qt')

    def onScanningHost(self, host):
        self.statusBar().showMessage('Scan: %s' % host)

    def onSrvTreeItemChanged(self, newItem, oldItem):
        del self._displayedHosts[:]  # clear list

        if isinstance(newItem, HostTreeItem):
            self._displayedHosts.append(newItem.host)
            self._displaySingleHost(newItem.host, newItem.host.serviceList)

    def updatejobTree(self, host, serviceList):
        if self._displayedHosts == [host]:
            self._displaySingleHost(host, serviceList)

    def updateStatus(self, host, service, instance, state, status):
        if self._displayedHosts == [host]:
            serviceItem = self.jobTree.findItems(service, Qt.MatchExactly)[0]
            instanceItem = serviceItem

            if instance:
                for i in range(serviceItem.childCount()):
                    item = serviceItem.child(i)
                    if item.text(0) == instance:
                        instanceItem = item
                        break

            instanceItem.updateStatus(state, status)

    def _displaySingleHost(self, host, serviceList):
        host = host.ip
        self.jobTree.clear()

        for service, serviceInfo in serviceList.items():
            instances = serviceInfo['instances']
            if len(instances) == 1 and '' in instances:  # service without inst
                serviceItem = JobTreeItem(self.jobTree, host, service, None, instances[''], self._model)
            else:
                serviceItem = JobTreeItem(self.jobTree, host, service, None, None, self._model)
                for instance, jobInfo in instances.items():
                    item = JobTreeItem(serviceItem, host, service, instance, jobInfo, self._model)

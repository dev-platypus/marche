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
import time

from PyQt5.QtCore import QThread, pyqtSignal, QObject


class Client(object):
    def __init__(self, ip):
        pass

    def setEventHandler(self, func):
        pass


class Host(QObject):
    def __init__(self, ip, subnet, parent=None):
        QObject.__init__(self, parent)
        self._ip = ip
        self._subnet = subnet
        self._hostname, _, _ = socket.gethostbyaddr(ip)
        self._client = Client(ip)
        self._client.setEventHandler(self._eventHandler)

    @property
    def ip(self):
        return self._ip

    @property
    def subnet(self):
        return self._subnet

    @property
    def client(self):
        return self._client

    @property
    def hostname(self):
        return self._hostname

    def _eventHandler(self, event):
        pass


class SubnetScanThread(QThread):
    hostFound = pyqtSignal(object)

    AUTOSCAN_INTERVAL = 30.0

    def __init__(self, subnet, parent=None):
        QThread.__init__(self, parent)
        self._net = ipaddress.ip_network(subnet)
        self._once = False

    def start(self, once=False):
        self._once = once
        QThread.start(self)

    def run(self):
        if self._once:
            self._scan()
        else:
            while True:
                self._scan()
                time.sleep(SubnetScanThread.AUTOSCAN_INTERVAL)

    def _scan(self):
        # TODO improve (nmap -parallel?)
        for host in self._net.hosts():
            try:
                socket.create_connection((str(host), '8124'), timeout=0.05)
                self.hostFound.emit(str(host))
            except IOError:
                pass


class Subnet(QObject):

    newHost = pyqtSignal(str)

    def __init__(self, subnet, parent=None):
        QObject.__init__(self, parent)
        self.subnet = subnet
        self._hosts = []

        self._scanThread = SubnetScanThread(subnet)
        self._scanThread.hostFound.connect(self.handleHostFound)

    def handleHostFound(self, host):
        if host not in self._hosts:
            self._hosts.append(host)
            self.newHost.emit(host)

    def startScan(self, once=True):
        self._scanThread.start(once)

    def stopScan(self):
        self._scanThread.stop()


class Model(QObject):

    newHost = pyqtSignal(str, object)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._subnets = {} # {subnetid/prefix : Subnet}
        self._hosts = []
        self._autoscan = False

    def addSubnet(self, subnet):
        if subnet not in self._subnets:
            net =  Subnet(subnet)
            net.newHost.connect(self._subnetHostFound)
            net.startScan(not self._autoscan)

            self._subnets[subnet] = net

    def removeSubnet(self, subnet):
        if subnet in self._subnets:
            self._subnets[subnet].stopScan()
            del self._subnets[subnet]

    def addHost(self, host):
        pass

    def removeHost(self, host):
        pass

    def startPollSubnet(self, subnet):
        pass

    def stopPollSubnet(self, subnet):
        pass

    def startPollHost(self, host):
        pass

    def stopPollHost(self, host):
        pass

    def _subnetHostFound(self, host):
        hostObj = Host(host, self.sender())
        self._hosts.append(hostObj)
        self.newHost.emit(str(self.sender().subnet), hostObj)

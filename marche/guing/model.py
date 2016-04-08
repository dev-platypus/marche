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
import time
import threading
import ipaddress
import logging

from PyQt5.QtCore import QThread, pyqtSignal, QObject

from marche.protocol import ServiceListEvent, StatusEvent, ErrorEvent, \
    ConffileEvent, LogfileEvent, ControlOutputEvent
from marche.client import Client


class Host(QObject):
    newServiceList = pyqtSignal(object, dict)  # service dict
    newState = pyqtSignal(object, str, str, int, str)  # self, service, instance, state, status
    errorOccured = pyqtSignal(object, str, str, int, str)  # self, service, instance, code, str
    conffilesReceived = pyqtSignal(object, str, str, dict)  # self, service, instance, files
    logfilesReceived = pyqtSignal(object, str, str, dict)  # self, service, instance, files
    ctrlOutputReceived = pyqtSignal(object, str, str, list)  # self, service, instance, lines

    def __init__(self, ip, port, subnet, parent=None):
        QObject.__init__(self, parent)
        self._ip = ip
        self._subnet = subnet
        self._hostname, _, _ = socket.gethostbyaddr(ip)
        self._serviceList = {}
        self._client = Client(ip, port, logging)
        self._client.setEventHandler(self._eventHandler)
        self._client.requestServiceList()

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

    @property
    def serviceList(self):
        if not self._serviceList:
            self._client.requestServiceList()
        return self._serviceList

    def _eventHandler(self, ev):
        if isinstance(ev, ServiceListEvent):
            self._serviceList = ev.services
            self.newServiceList.emit(self, ev.services)
        elif isinstance(ev, StatusEvent):
            self.newState.emit(self, ev.service, ev.instance, ev.state, ev.ext_status)
        elif isinstance(ev, ErrorEvent):
            self.errorOccured.emit(self, ev.service, ev.instance, ev.code, ev.string)
        elif isinstance(ev, ConffileEvent):
            self.conffilesReceived.emit(self, ev.service, ev.instance, ev.files)
        elif isinstance(ev, LogfileEvent):
            self.logfilesReceived.emit(self, ev.service, ev.instance, ev.files)
        elif isinstance(ev, ControlOutputEvent):
            self.ctrlOutputReceived.emit(self, ev.service, ev.instance, ev.content)


class SubnetScanThread(QThread):
    hostFound = pyqtSignal(object)
    scanningHost = pyqtSignal(str)

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
                self.scanningHost.emit(str(host))
                s = socket.create_connection((str(host), '12132'), timeout=0.05)
                s.close()
                self.hostFound.emit(str(host))
            except IOError:
                pass


class Subnet(QObject):

    newHost = pyqtSignal(str)
    scanningHost = pyqtSignal(str)

    def __init__(self, subnet, parent=None):
        QObject.__init__(self, parent)
        self.subnet = subnet
        self._hosts = []

        self._scanThread = SubnetScanThread(subnet)
        self._scanThread.scanningHost.connect(self.scanningHost)
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
    scanningHost = pyqtSignal(str)
    newServiceList = pyqtSignal(object, dict) # service dict
    newState = pyqtSignal(object, str, str, int, str) # service, instance, state, status
    errorOccured = pyqtSignal(object, str, str, int, str) # service, instance, code, str
    conffilesReceived = pyqtSignal(object, str, str, dict) # service, instance, files
    logfilesReceived = pyqtSignal(object, str, str, dict) # service, instance, files
    ctrlOutputReceived = pyqtSignal(object, str, str, list) # service, instance, lines

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._subnets = {} # {subnetid/prefix : Subnet}
        self._hosts = []
        self._autoscan = False

    @property
    def autoscan(self):
        return self._autoscan

    @autoscan.setter
    def autoscan(self, value):
        if value and not self._autoscan:
            for _, subnet in self._subnets.items():
                subnet.stopScan()
                subnet.startScan(self._autoscan, False)
        elif not value:
            for _, subnet in self._subnets.items():
                subnet.stopScan()
                subnet.startScan(self._autoscan, True)

        self._autoscan = value

    def addSubnet(self, subnet):
        if subnet not in self._subnets:
            net = Subnet(subnet)
            net.scanningHost.connect(self.scanningHost)
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
        hostObj = Host(host, 12132, self.sender())

        hostObj.newServiceList.connect(self.newServiceList)
        hostObj.newState.connect(self.newState)
        hostObj.errorOccured.connect(self.errorOccured)
        hostObj.conffilesReceived.connect(self.conffilesReceived)
        hostObj.logfilesReceived.connect(self.logfilesReceived)
        hostObj.ctrlOutputReceived.connect(self.ctrlOutputReceived)

        self._hosts.append(hostObj)
        self.newHost.emit(str(self.sender().subnet), hostObj)

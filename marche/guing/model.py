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

import time
import socket
import ipaddress
import logging

from PyQt5.QtCore import QThread, pyqtSignal, QObject

from marche.protocol import ServiceListEvent, StatusEvent, ErrorEvent, \
    ConffileEvent, LogfileEvent, ControlOutputEvent, RequestServiceListCommand
from marche.client import Client


class Host(QObject):
    newServiceList = pyqtSignal(object, dict)  # service dict
    newState = pyqtSignal(object, str, str, int, str)  # self, service, instance, state, status
    errorOccured = pyqtSignal(object, str, str, int, str)  # self, service, instance, code, str
    conffilesReceived = pyqtSignal(object, str, str, dict)  # self, service, instance, files
    logfilesReceived = pyqtSignal(object, str, str, dict)  # self, service, instance, files
    ctrlOutputReceived = pyqtSignal(object, str, str, list)  # self, service, instance, lines

    def __init__(self, ip, port, subnet=None, parent=None):
        QObject.__init__(self, parent)
        self._ip = ip
        self._subnet = subnet
        self._hostname, _, _ = socket.gethostbyaddr(ip)
        self._serviceList = {}
        self._client = Client(ip, port, self._eventHandler, logging)
        self._client.send(RequestServiceListCommand())

    @property
    def ip(self):
        return self._ip

    @property
    def subnet(self):
        return self._subnet

    @subnet.setter
    def subnet(self, value):
        self._subnet = value

    @property
    def client(self):
        return self._client

    @property
    def hostname(self):
        return self._hostname

    @property
    def serviceList(self):
        if not self._serviceList:
            self._client.send(RequestServiceListCommand())
        return self._serviceList

    @property
    def serverInfo(self):
        return self._client.getServerInfo()

    def _eventHandler(self, ev):
        if isinstance(ev, ServiceListEvent):
            self._serviceList = ev.services
            self.newServiceList.emit(self, ev.services)
        elif isinstance(ev, StatusEvent):
            if self._serviceList:
                self._serviceList[ev.service]['instances'][ev.instance]['state'] = ev.state
                self._serviceList[ev.service]['instances'][ev.instance]['ext_status'] = ev.ext_status
            self.newState.emit(self, ev.service, ev.instance, ev.state, ev.ext_status)
        elif isinstance(ev, ErrorEvent):
            self.errorOccured.emit(self, ev.service, ev.instance, ev.code, ev.string)
        elif isinstance(ev, ConffileEvent):
            self.conffilesReceived.emit(self, ev.service, ev.instance, ev.files)
        elif isinstance(ev, LogfileEvent):
            self.logfilesReceived.emit(self, ev.service, ev.instance, ev.files)
        elif isinstance(ev, ControlOutputEvent):
            self.ctrlOutputReceived.emit(self, ev.service, ev.instance, ev.content)

    def disconnect(self):
        self._client.close()


class SubnetScanThread(QThread):
    hostFound = pyqtSignal(object)
    scanningHost = pyqtSignal(str)

    def __init__(self, subnet, parent=None):
        QThread.__init__(self, parent)
        self._net = ipaddress.ip_network(subnet)

    def run(self):
        self._scan()

    def _scan(self):
        # TODO improve (nmap -parallel?)
        for host in self._net.hosts():
            try:
                self.scanningHost.emit(str(host))
                c = Client(str(host), 12132, print, logging)
                c.close()
                self.hostFound.emit(str(host))
            except RuntimeError:
                pass


class Subnet(QObject):

    newHost = pyqtSignal(object)
    scanningHost = pyqtSignal(str)
    scanDone = pyqtSignal()

    def __init__(self, subnet, parent=None):
        QObject.__init__(self, parent)
        self.subnet = subnet
        self._hosts = []

        self._scanThread = SubnetScanThread(subnet)
        self._scanThread.scanningHost.connect(self.scanningHost)
        self._scanThread.hostFound.connect(self.handleHostFound)
        self._scanThread.finished.connect(self.scanDone)

    def addHost(self, host):
        if host not in self._hosts:
            self._hosts.append(host)

    def hasHost(self, hostadr):
        for host in self._hosts:
            if hostadr in [host.ip, host.hostname]:
                return True
        return False

    def handleHostFound(self, hostadr):
        host =  Host(hostadr, 12132, self)
        if host not in self._hosts:
            self._hosts.append(host)
            self.newHost.emit(host)

    def startScan(self):
        self._scanThread.start()

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

    def addSubnet(self, subnet, scan=True):
        if subnet not in self._subnets:
            net = Subnet(subnet)
            net.scanningHost.connect(self.scanningHost)
            net.newHost.connect(self._subnetHostFound)
            if scan:
                net.startScan()

            self._subnets[subnet] = net

    def removeSubnet(self, subnet):
        if subnet in self._subnets:
            self._subnets[subnet].stopScan()
            del self._subnets[subnet]

    def addHost(self, hostadr):
        if self.findSubnetForHost(hostadr):
            return

        hostObj = Host(hostadr, 12132)
        self._connectHostSignals(hostObj)
        subnet = hostObj.serverInfo.subnet

        if subnet not in self._subnets:
            self.addSubnet(subnet)

        self._subnets[subnet].addHost(hostObj)
        self.newHost.emit(subnet, hostObj)

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

    def findSubnetForHost(self, hostadr):
        for net in self._subnets.values():
            if net.hasHost(hostadr):
                return net

        return None

    def _subnetHostFound(self, host):
        self._connectHostSignals(host)

        self.newHost.emit(str(self.sender().subnet), host)

    def disconnect(self):
        for host in self._hosts:
            host.disconnect()

    def _connectHostSignals(self, host):
        host.newServiceList.connect(self.newServiceList)
        host.newState.connect(self.newState)
        host.errorOccured.connect(self.errorOccured)
        host.conffilesReceived.connect(self.conffilesReceived)
        host.logfilesReceived.connect(self.logfilesReceived)
        host.ctrlOutputReceived.connect(self.ctrlOutputReceived)

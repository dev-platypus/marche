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
import threading

from PyQt5.QtCore import QThread, pyqtSignal, QObject

from marche.protocol import ServiceListEvent, StatusEvent, ErrorEvent, \
    ConffileEvent, LogfileEvent, ControlOutputEvent


class Client(object):
    def __init__(self, ip):
        self._evHandler = None
        self._th = threading.Thread(target=self._dummyEvGenerator, args=(self,))

    def start(self):
        self._th.start()

    def setEventHandler(self, func):
        self._evHandler = func

    def _dummyEvGenerator(*args):
        while True:
            inst = args[0]

            ev = ServiceListEvent()
            ev.services = {
                'taco-server-network' : {
                    'type' : 'taco',
                    'instances' : {
                        'abc' : {
                            'desc' : 'some desc',
                            'state' : 0,  # DEAD
                            'extStatus' : 'ext status str',
                            'permissions' : ('control', 'display', 'admin')
                        }
                    }
                }
            }

            if inst._evHandler:
                inst._evHandler(ev)
            time.sleep(5)


class Host(QObject):
    newServiceList = pyqtSignal(object, dict) # service dict
    newState = pyqtSignal(object, str, str, int, str) # self, service, instance, state, status
    errorOccured = pyqtSignal(object, str, str, int, str) # self, service, instance, code, str
    conffilesReceived = pyqtSignal(object, str, str, dict) # self, service, instance, files
    logfilesReceived = pyqtSignal(object, str, str, dict) # self, service, instance, files
    ctrlOutputReceived = pyqtSignal(object, str, str, list) # self, service, instance, lines

    def __init__(self, ip, subnet, parent=None):
        QObject.__init__(self, parent)
        self._ip = ip
        self._subnet = subnet
        self._hostname, _, _ = socket.gethostbyaddr(ip)
        self._serviceList = {}
        self._client = Client(ip)
        self._client.setEventHandler(self._eventHandler)
        self._client.start()

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
            self.newState.emit(self, ev.service, ev.instance, ev.state, ev.extStatus)
        elif isinstance(ev, Errorevent):
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
                socket.create_connection((str(host), '8124'), timeout=0.05)
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
            net =  Subnet(subnet)
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
        hostObj = Host(host, self.sender())

        hostObj.newServiceList.connect(self.newServiceList)
        hostObj.newState.connect(self.newState)
        hostObj.errorOccured.connect(self.errorOccured)
        hostObj.conffilesReceived.connect(self.conffilesReceived)
        hostObj.logfilesReceived.connect(self.logfilesReceived)
        hostObj.ctrlOutputReceived.connect(self.ctrlOutputReceived)

        self._hosts.append(hostObj)
        self.newHost.emit(str(self.sender().subnet), hostObj)

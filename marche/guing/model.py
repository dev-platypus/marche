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

    def __init__(self, address, port, parent=None):
        QObject.__init__(self, parent)

        try:
            self._address = ipaddress.ip_address(address)
        except ValueError:
            # seems to be a host name
            ip = socket.gethostbyname(address)
            self._address = ipaddress.ip_address(ip)

        # new lookup for fqdn
        self._hostname, _, _ = socket.gethostbyaddr(str(self._address))
        self._serviceList = {}
        self._client = Client(str(self._address), port, self._eventHandler, logging)
        self._client.send(RequestServiceListCommand())

    @property
    def ip(self):
        return str(self._address)

    @property
    def subnet(self):
        return self.serverInfo.subnet

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

    def disconnect(self):
        self._client.close()

    def startService(self, service, instance):
        self._client.startService(service, instance)

    def stopService(self, service, instance):
        self._client.stopService(service, instance)

    def restartService(self, service, instance):
        self._client.restartService(service, instance)

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


class Subnet(QThread):
    hostFound = pyqtSignal(str) # hostadr

    def __init__(self, subnetid, parent=None):
        QThread.__init__(self, parent)

        self._net = ipaddress.ip_network(subnetid)

    @property
    def address(self):
        return self._net.network_address

    def triggerScan(self):
        self.start()

    def run(self):
        self._scan()

    def _scan(self):
        # TODO improve (nmap -parallel?)
        for host in self._net.hosts():
            try:
                s = socket.create_connection((str(host), '12132'), timeout=0.05)
                s.close()

                self.hostFound.emit(str(host))
            except IOError:
                pass


class Model(QObject):
    newHost = pyqtSignal(object) # host

    newServiceList = pyqtSignal(object, dict)  # host, service dict
    newState = pyqtSignal(object, str, str, int,
                          str)  # host, service, instance, state, status
    errorOccured = pyqtSignal(object, str, str, int,
                              str)  # host, service, instance, code, str
    conffilesReceived = pyqtSignal(object, str, str,
                                   dict)  # host, service, instance, files
    logfilesReceived = pyqtSignal(object, str, str,
                                  dict)  # host, service, instance, files
    ctrlOutputReceived = pyqtSignal(object, str, str,
                                    list)  # host, service, instance, lines

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._hosts = {}
        self._subnetCache = {} # cache for running scans

    def addHost(self, hostAdr, port=12132):
        host = Host(hostAdr, port)

        if host.ip in self._hosts:
            host.disconnect()
            return

        self._hosts[host.ip] = host

        host.newServiceList.connect(self.newServiceList)
        host.newState.connect(self.newState)
        host.errorOccured.connect(self.errorOccured)
        host.conffilesReceived.connect(self.conffilesReceived)
        host.logfilesReceived.connect(self.logfilesReceived)
        host.ctrlOutputReceived.connect(self.ctrlOutputReceived)

        self.newHost.emit(host)

    def scanSubnet(self, subnetid):
        if subnetid in self._subnetCache:
            self._subnetCache

        self._subnetCache[subnetid] = Subnet(subnetid)
        self._subnetCache[subnetid].hostFound.connect(self.addHost)
        self._subnetCache[subnetid].finished.connect(self.subnetScanFinished)
        self._subnetCache[subnetid].triggerScan()

    def startService(self, hostadr, service, instance):
        self._hosts[hostadr].startService(service, instance)

    def stopService(self, hostadr, service, instance):
        self._hosts[hostadr].stopService(service, instance)

    def restartService(self, hostadr, service, instance):
        self._hosts[hostadr].restartService(service, instance)

    ## slots ##
    def subnetScanFinished(self):
        subnetid = self.sender().address
        del self._subnetCache[subnetid]

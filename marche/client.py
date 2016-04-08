#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2016 by the authors, see LICENSE
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
#   Andreas Schulz <aschulz@dev-platypus.org>
#
# *****************************************************************************

from __future__ import print_function

import json
import threading

from autobahn.asyncio.websocket import asyncio, WebSocketClientProtocol, \
    WebSocketClientFactory

from marche.protocol import Event, ConnectedEvent


class WSClient(WebSocketClientProtocol):
    def onConnect(self, response):
        self.factory.client = self
        self.factory.connected.set()
        print("Connected to Server: {}".format(response.peer))

    def onClose(self, wasClean, code, reason):
        self.factory.client = None
        self.factory.loop.stop()

    def onMessage(self, payload, isBinary):
        event = Event.unserialize(json.loads(payload.decode('utf-8')))
        if isinstance(event, ConnectedEvent):
            self.factory.serverInfo = event
            self.factory.gotServerInfo.set()
        else:
            self.factory.eventHandler(event)


class WSClientFactory(WebSocketClientFactory):
    def __init__(self, url, connected, got_info):
        WebSocketClientFactory.__init__(self, url=url)
        self.protocol = WSClient
        self.connected = connected
        self.gotServerInfo = got_info
        self.client = None
        self.eventHandler = None
        self.serverInfo = None


class Client(object):
    def __init__(self, host, port, log):
        self._evHandler = None
        self.log = log
        self.connected = threading.Event()
        self.gotServerInfo = threading.Event()
        self.thd = threading.Thread(target=self.start, args=(host, port))
        self.thd.setDaemon(True)
        self.thd.start()
        self.connected.wait()
        if self.factory.client is None:
            raise RuntimeError('Connection refused')

    def start(self, host, port):
        addr = 'ws://%s:%d' % (host, port)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.factory = WSClientFactory(addr, self.connected,
                                           self.gotServerInfo)

            coro = loop.create_connection(self.factory, host, port)
            loop.run_until_complete(coro)
            loop.run_forever()
        except Exception as err:
            self.connected.set()
            self.log.exception('could not connect to %s', addr)

    def getServerInfo(self):
        if not self.gotServerInfo.wait(1):
            raise RuntimeError('server info not received')
        return self.factory.serverInfo

    def setEventHandler(self, func):
        self.factory.eventHandler = func

    def close(self):
        self.factory.client.sendClose()

    def _sendRequest(self, request, **kwds):
        kwds['request'] = request
        self.factory.client.sendMessage(json.dumps(kwds).encode('utf-8'))

    def requestServiceList(self):
        self._sendRequest('request_service_list')

    def requestServiceStatus(self, service, instance):
        self._sendRequest('request_service_status', service=service, instance=instance)

    def startService(self, service, instance):
        self._sendRequest('start_service', service=service, instance=instance)

    def stopService(self, service, instance):
        self._sendRequest('stop_service', service=service, instance=instance)

    def restartService(self, service, instance):
        self._sendRequest('restart_service', service=service, instance=instance)


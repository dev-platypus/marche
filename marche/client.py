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
            self.factory.unlockWhenReceivedServerInfo()
            self.factory.serverInfo = event
        else:
            self.factory.eventHandler(event)


class WSClientFactory(WebSocketClientFactory):
    def __init__(self, url):
        WebSocketClientFactory.__init__(self, url=url)
        self.client = None
        self.connected = None
        self.unlockWhenReceivedServerInfo = None
        self.eventHandler = None
        self.serverInfo = None


class Client(object):
    def __init__(self, host, port):
        self._evHandler = None
        self.connected = threading.Event()
        self.thd = threading.Thread(target=self.start, args=(host, port))
        self.thd.setDaemon(True)
        self.thd.start()
        self.connected.wait()
        if self.factory.client is None:
            raise RuntimeError('Connection refused')

    def start(self, host, port):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.factory = WSClientFactory('ws://%s:%d' % (host, port))
            self.factory.protocol = WSClient
            self.factory.connected = self.connected

            coro = loop.create_connection(self.factory, host, port)
            loop.run_until_complete(coro)
            loop.run_forever()
        finally:
            self.connected.set()

    def getServerInfo(self):
        serverInfoLock = threading.Lock()
        serverInfoLock.acquire()
        self.factory.client.sendMessage('getServerInfo()'.encode('utf-8'))
        self.factory.unlockWhenReceivedServerInfo = serverInfoLock.release
        serverInfoLock.acquire()
        return self.factory.serverInfo

    def setEventHandler(self, func):
        self.factory.eventHandler = func

    def close(self):
        self.factory.client.sendClose()

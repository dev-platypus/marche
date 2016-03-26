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

import json
import threading

from autobahn.asyncio.websocket import asyncio, WebSocketClientProtocol, \
    WebSocketClientFactory

from marche.protocol import Event, ConnectedEvent


class WSClient(WebSocketClientProtocol):
    def onConnect(self, response):
        self.factory.client = self
        self.factory.unlockWhenConnected.release()
        print("Connected to Server: {}".format(response.peer))

    def onClose(self, wasClean, code, reason):
        self.factory.client = None
        print('closed!')
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
        self.unlockWhenConnected = None
        self.unlockWhenReceivedServerInfo = None
        self.eventHandler = None


class Client(object):
    def __init__(self, ip):
        self._evHandler = None
        self.unlockWhenConnected = threading.Lock()
        self.thd = threading.Thread(target=self.start, args=(ip,))
        self.thd.setDaemon(True)
        self.thd.start()
        # thd instantly acquires lock. By trying to acquire it here,
        # we make sure to only return from __init__ when successfully
        # connected. Any other case will throw an exception.
        self.unlockWhenConnected.acquire()
        if self.factory.client is None:
            raise RuntimeError('Connection refused')
        self.unlockWhenConnected.release()

    def start(self, ip):
        self.unlockWhenConnected.acquire()
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.factory = WSClientFactory('ws://' + ip)
            self.factory.protocol = WSClient
            self.factory.unlockWhenConnected = self.unlockWhenConnected

            coro = loop.create_connection(self.factory, ip, 12132)
            loop.run_until_complete(coro)
            loop.run_forever()
        except Exception:
            self.unlockWhenConnected.release()

    def getServerInfo(self):
        serverInfoLock = threading.Lock()
        serverInfoLock.acquire()
        self.factory.client.sendMessage('getServerInfo()'.encode('utf-8'))
        self.factory.unlockWhenReceivedServerInfo = serverInfoLock.release
        serverInfoLock.acquire()
        return self.factory.serverInfo

    def setEventHandler(self, func):
        self.factory.eventHandler = func

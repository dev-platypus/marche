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

from autobahn.asyncio.websocket import asyncio, WebSocketServerProtocol, \
    WebSocketServerFactory

from marche.iface.base import Interface as BaseInterface
from marche.protocol import ConnectedEvent, PROTO_VERSION
from marche import __version__ as DAEMON_VERSION


class WSServer(WebSocketServerProtocol):
    log = None

    def onConnect(self, request):
        self.log.info('Client connecting: {}'.format(request.peer))
        self.factory.clients.append(self)

    def onMessage(self, payload, isBinary):
        if payload.decode('utf-8') == 'getServerInfo()':
            connectedEvent = ConnectedEvent(PROTO_VERSION,
                                            DAEMON_VERSION,
                                            [])  # TODO: implement permissions
            self.sendMessage(
                json.dumps(connectedEvent.serialize()).encode('utf-8'),
                isBinary=False)

    def onClose(self, wasClean, code, reason):
        self.log.info('Client disconnected, reason: {}'.format(reason))
        self.factory.clients.remove(self)


class WSServerFactory(WebSocketServerFactory):
    log = None

    def __init__(self, url=None):
        WebSocketServerFactory.__init__(self, url)
        self.clients = []


class Interface(BaseInterface):
    iface_name = 'wsserver'
    needs_events = True

    def init(self):
        pass

    def run(self):
        port = int(self.config['port'])
        host = self.config['host']

        WSServer.log = self.log
        WSServerFactory.log = self.log

        thd = threading.Thread(target=self._thread, args=(host, port))
        thd.setDaemon(True)
        thd.start()
        self.log.info('WebSocket server listening on %s:%s' % (host, port))

    def _thread(self, host, port):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.factory = WSServerFactory(url='ws://' + host)
        self.factory.protocol = WSServer

        coro = loop.create_server(self.factory, host, port)
        server = loop.run_until_complete(coro)
        try:
            loop.run_forever()
        except Exception:
            server.close()
            loop.close()

    def emit_event(self, event):
        for client in self.factory.clients:
            client.sendMessage(json.dumps(event.serialize()).encode('utf-8'),
                               isBinary=False)

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

""".. index:: wsserver; interface

WebSocket interface
-------------------

This interface allows controlling services via remote procedure calls over a
protocol based on WebSocket, which is ultimately an upgraded HTTP connection.

The WebSocket interface supports asynchronous message delivery, which means
that clients need not poll for status updates continuously.

.. describe:: [interfaces.wsserver]

   The configuration settings that can be set within the
   **interfaces.wsserver** section are:

   .. describe:: port

      **Default:** 12132

      The port to listen for WebSocket clients.

   .. describe:: host

      **Default:** 0.0.0.0

      The host to bind to.
"""

import json
import threading

from autobahn.asyncio.websocket import asyncio, WebSocketServerProtocol, \
    WebSocketServerFactory

from marche.iface.base import Interface as BaseInterface
from marche.protocol import ConnectedEvent, PROTO_VERSION
from marche.permission import ClientInfo, ADMIN
from marche.auth import AuthFailed
from marche import __version__ as DAEMON_VERSION


class WSServer(WebSocketServerProtocol):
    log = None

    def onConnect(self, request):
        self.log.info('Client connecting: {}'.format(request.peer))
        self.client_info = ClientInfo(ADMIN)  # TODO
        self.factory.clients.add(self)

    def onOpen(self):
        connectedEvent = ConnectedEvent(PROTO_VERSION,
                                        DAEMON_VERSION,
                                        [])  # TODO: implement permissions
        self.sendMessage(json.dumps(connectedEvent.serialize()).encode('utf-8'))

    def onMessage(self, payload, isBinary):
        try:
            payload = json.loads(payload.decode('utf-8'))
            request = payload['request']
            if request == 'authenticate':
                try:
                    self.client_info = self.factory.authhandler.authenticate(request['user'], request['password'])
                except AuthFailed:
                    pass  # XXX
            if request == 'request_service_list':
                svclist = self.factory.jobhandler.request_service_list(self.client_info)
                self.sendMessage(json.dumps(svclist.serialize()).encode('utf-8'))
            else:
                raise RuntimeError('no such request')
        except Exception:
            self.log.warning('unrecognized message: %r', payload)
            return

    def onClose(self, wasClean, code, reason):
        self.log.info('Client disconnected, reason: {}'.format(reason))
        self.factory.clients.discard(self)


class WSServerFactory(WebSocketServerFactory):
    log = None

    def __init__(self, url, log, jobhandler, authhandler):
        WebSocketServerFactory.__init__(self, url)
        self.protocol = WSServer
        self.jobhandler = jobhandler
        self.authhandler = authhandler
        WSServer.log = self.log = log
        self.clients = set()


class Interface(BaseInterface):
    iface_name = 'wsserver'
    needs_events = True

    def init(self):
        self.server = None
        self.started = threading.Event()

    def run(self):
        port = int(self.config.get('port', 12132))
        host = self.config.get('host', '0.0.0.0')

        thd = threading.Thread(target=self._thread, args=(host, port))
        thd.setDaemon(True)
        thd.start()
        if not self.started.wait(1.0):
            raise RuntimeError('failed to start server within 1 second')

        self.log.info('WebSocket server listening on %s:%s' % (host, port))

    def _thread(self, host, port):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.factory = WSServerFactory('ws://%s:%d' % (host, port), self.log,
                                       self.jobhandler, self.authhandler)

        coro = loop.create_server(self.factory, host, port)
        self.server = loop.run_until_complete(coro)
        self.started.set()

        try:
            loop.run_forever()
        except Exception:  # pragma: no cover
            self.server.close()
            loop.close()

    def shutdown(self):
        if self.server:
            self.server.close()

    def emit_event(self, event):
        serialized = json.dumps(event.serialize()).encode('utf-8')
        for client in list(self.factory.clients):
            client.sendMessage(serialized)

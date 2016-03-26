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


import threading
import asyncio
from autobahn.asyncio.websocket import WebSocketServerProtocol, \
    WebSocketServerFactory
from marche.iface.base import Interface as BaseInterface


class snzl_server(WebSocketServerProtocol):
    log = None

    def onConnect(self, request):
        self.i = 0
        self.log.info('Client connecting: {}'.format(request.peer))

    def onOpen(self):
        pass

    def onMessage(self, payload, isBinary):
        self.i += 1
        if self.i == 5:
            self.sendMessage(u'Halftime!'.encode('utf-8'))
        self.sendMessage(payload, isBinary)

    def onClose(self, wasClean, code, reason):
        self.log.info('Client disconnected, reason: {}'.format(reason))


class Interface(BaseInterface):
    iface_name = 'snzl'

    def init(self):
        pass

    def run(self):
        port = int(self.config['port'])
        host = self.config['host']

        snzl_server.log = self.log

        thd = threading.Thread(target=self._thread, args=(host, port))
        thd.setDaemon(True)
        thd.start()
        self.log.info('snzl listening on %s:%s' % (host, port))

    def _thread(self, host, port):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        factory = WebSocketServerFactory()
        factory.protocol = snzl_server

        coro = loop.create_server(factory, host, port)
        server = loop.run_until_complete(coro)
        try:
            loop.run_forever()
        except:
            server.close()
            loop.close()

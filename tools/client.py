#!/usr/bin/env python3
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


import asyncio
from autobahn.asyncio.websocket import WebSocketClientProtocol, \
    WebSocketClientFactory


class snzl_client(WebSocketClientProtocol):
    def onConnect(self, response):
        print("Connected to Server: {}".format(response.peer))

    def onClose(self, wasClean, code, reason):
        print('closed!')
        self.factory.loop.stop()

    def onMessage(self, payload, isBinary):
        print('Received: ' + payload.decode('utf8'))


factory = WebSocketClientFactory('ws://127.0.0.1', 12132)
factory.protocol = snzl_client

loop = asyncio.get_event_loop()
coro = loop.create_connection(factory, '127.0.0.1', 12132)
loop.run_until_complete(coro)
loop.run_forever()
loop.stop()

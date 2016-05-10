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

import threading

from autobahn.asyncio.websocket import asyncio, WebSocketClientProtocol, \
    WebSocketClientFactory

from marche.protocol import Event, ConnectedEvent, RequestServiceListCommand, \
    RequestServiceStatusCommand, RequestControlOutputCommand, StartCommand, \
    StopCommand, RestartCommand


class WSClient(WebSocketClientProtocol):
    def onConnect(self, response):
        self.factory.client = self
        self.factory.connected.set()

    def onClose(self, wasClean, code, reason):
        self.factory.client = None
        self.factory.loop.stop()

    def onMessage(self, payload, isBinary):
        event = Event.unserialize(payload)
        if isinstance(event, ConnectedEvent):
            self.factory.serverInfo = event
            self.factory.gotServerInfo.set()
        else:
            if self.factory.eventHandler is not None:
                self.factory.eventHandler(event)


class WSClientFactory(WebSocketClientFactory):
    def __init__(self, url, connected, got_info):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
        WebSocketClientFactory.__init__(self, url=url)
        self.protocol = WSClient
        self.connected = connected
        self.gotServerInfo = got_info
        self.client = None
        self.eventHandler = None
        self.serverInfo = None


class Client(object):
    def __init__(self, host, port, event_handler, log):
        self.log = log
        self.addr = 'ws://%s:%d' % (host, port)
        self.connected = threading.Event()
        self.gotServerInfo = threading.Event()
        self.factory = WSClientFactory(self.addr, self.connected,
                                       self.gotServerInfo)
        self.factory.eventHandler = event_handler
        self.thd = threading.Thread(target=self._thread, args=(host, port))
        self.thd.setDaemon(True)
        self.thd.start()
        if not self.connected.wait(2) or self.factory.client is None:
            raise RuntimeError('connection failed')

    def _thread(self, host, port):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            coro = loop.create_connection(self.factory, host, port)
            loop.run_until_complete(coro)
            loop.run_forever()
        except Exception:
            self.connected.set()
            self.log.exception('could not connect to %s', self.addr)

    def getServerInfo(self):
        if not self.gotServerInfo.wait(1):  # pragma: no cover
            raise RuntimeError('server info not received')
        return self.factory.serverInfo

    def requestServiceList(self):
        self.send(RequestServiceListCommand())

    def requestStatus(self, service, instance):
        self.sendServiceCommand(RequestServiceStatusCommand, service, instance)

    def requestOutput(self, service, instance):
        self.sendServiceCommand(RequestControlOutputCommand, service, instance)

    def startService(self, service, instance):
        self.sendServiceCommand(StartCommand, service, instance)

    def stopService(self, service, instance):
        self.sendServiceCommand(StopCommand, service, instance)

    def restartService(self, service, instance):
        self.sendServiceCommand(RestartCommand, service, instance)

    def close(self):
        if self.factory.client is None:
            return
        self.factory.client.sendClose()

    def send(self, cmd):
        if self.factory.client is None:
            raise RuntimeError('client is disconnected')
        self.factory.client.sendMessage(cmd.serialize())

    def sendServiceCommand(self, cmdClass, service, instance):
        self.send(cmdClass(service, instance))


@asyncio.coroutine
def tryConnect(loop, factory, host, port, callback, timeout=1):
    ''' INTERNAL COROUTINE. Tries to connect to a marche daemon.
    :param loop: The BaseEventLoop to use.
    :param factory: Instance of a WebSocketClientFactory (or subclass).
    :param host: The host to connect to.
    :param port: int from 0-65535.
    :param callback: A function which takes a string. Is called when connecting successfully. Argument is the hostname.
    :param timeout: How long to wait in seconds for each host until connecting is cancelled. Default 1s.
    :return: The WebSocketClientProtocol (or subclass) instance, provided by the factory, is returned.
    '''
    try:
        future = loop.create_connection(factory, host, port)
        transport, protocol = yield from asyncio.wait_for(future, timeout=timeout)
        callback(host)
        return protocol
    except Exception:
        pass


def testConnections(hosts, port=12132, callback=print):
    ''' Test whether hosts run the marche daemon.
    :param hosts: List of hostnames/IP addresses.
    :param port: The port to use.
    :param callback: The function which is passed to tryConnect.
    :return: None
    '''
    # We use a fresh event loop so this function can be called from any thread.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    coros = []

    for host in hosts:
        host = str(host)
        addr = 'ws://%s:%d' % (host, port)
        factory = WSClientFactory(addr, threading.Event(), threading.Event())
        coros.append(tryConnect(loop, factory, host, port, callback))

    future = asyncio.gather(*coros)
    loop.run_until_complete(future)
    loop.stop()
    connections = future.result()
    for connection in connections:
        if connection is not None:
            # See https://www.iana.org/assignments/websocket/websocket.xml#close-code-number-rules for codes.
            # 1000 means normal closure.
            connection.sendClose(code=1000, reason="Server discovery succeeded.")

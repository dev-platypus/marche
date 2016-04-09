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

import threading

from autobahn.asyncio.websocket import asyncio, WebSocketServerProtocol, \
    WebSocketServerFactory

from marche.iface.base import Interface as BaseInterface
from marche.protocol import Errors, Command, ServiceCommand, Commands, \
    ConnectedEvent, ErrorEvent, AuthEvent, ServiceListEvent, StatusEvent, \
    PROTO_VERSION
from marche.permission import ClientInfo
from marche.auth import AuthFailed
from marche.jobs import Busy, Fault, Unauthorized
from marche import __version__ as DAEMON_VERSION


COMMAND_HANDLERS = {}


def command(cmdtype):
    def deco(func):
        def new_method(self, cmd):
            try:
                func(self, cmd)
            except Exception as err:
                if isinstance(cmd, ServiceCommand):
                    svc, inst = cmd.service, cmd.instance
                else:
                    svc, inst = '', ''
                desc = str(err)
                if isinstance(err, Busy):
                    code = Errors.BUSY
                elif isinstance(err, Unauthorized):
                    code = Errors.UNAUTH
                elif isinstance(err, Fault):
                    code = Errors.FAULT
                else:
                    code = Errors.EXCEPTION
                    desc = 'Unexpected exception: %s' % err
                self.sendMessage(ErrorEvent(svc, inst, code, desc).serialize())
                self.log.exception('error in request: %r', cmd)
        COMMAND_HANDLERS[cmdtype] = new_method
        return new_method
    return deco


class WSServer(WebSocketServerProtocol):
    log = None

    def onConnect(self, request):
        self.log.info('Client connecting: {}'.format(request.peer))
        self.client_info = ClientInfo(self.factory.jobhandler.unauth_level)
        self.factory.clients.add(self)

    def onOpen(self):
        connectedEvent = ConnectedEvent(
            PROTO_VERSION, DAEMON_VERSION,
            self.factory.jobhandler.unauth_level)
        self.sendMessage(connectedEvent.serialize())

    def onMessage(self, payload, isBinary):
        try:
            cmd = Command.unserialize(payload)
        except Exception:
            self.log.warning('invalid message payload, ignoring: %r', payload)
            return
        try:
            handler = COMMAND_HANDLERS[cmd.type]
        except Exception:
            self.log.warning('invalid command, ignoring: %r', cmd)
            return
        handler(self, cmd)

    def onClose(self, wasClean, code, reason):
        self.log.info('Client disconnected, reason: {}'.format(reason))
        self.factory.clients.discard(self)

    @command(Commands.AUTHENTICATE)
    def authenticate(self, cmd):
        try:
            self.client_info = self.factory.authhandler.authenticate(
                cmd.user, cmd.passwd)
        except AuthFailed:
            self.sendMessage(AuthEvent(False).serialize())
        else:
            self.sendMessage(AuthEvent(True).serialize())

    @command(Commands.TRIGGER_RELOAD)
    def triggerReload(self, cmd):
        self.factory.jobhandler.trigger_reload()

    @command(Commands.REQUEST_SERVICE_LIST)
    def requestServiceList(self, cmd):
        svclist = self.factory.jobhandler.request_service_list(
            self.client_info)
        self.sendMessage(svclist.serialize())

    @command(Commands.REQUEST_SERVICE_STATUS)
    def requestServiceStatus(self, cmd):
        status = self.factory.jobhandler.request_service_status(
            self.client_info, cmd.service, cmd.instance)
        self.sendMessage(status.serialize())

    @command(Commands.REQUEST_CONTROL_OUTPUT)
    def requestControlOutput(self, cmd):
        output = self.factory.jobhandler.request_control_output(
            self.client_info, cmd.service, cmd.instance)
        self.sendMessage(output.serialize())

    @command(Commands.REQUEST_LOG_FILES)
    def requestLogFiles(self, cmd):
        logfiles = self.factory.jobhandler.request_logfiles(
            self.client_info, cmd.service, cmd.instance)
        self.sendMessage(logfiles.serialize())

    @command(Commands.REQUEST_CONF_FILES)
    def requestConfFiles(self, cmd):
        conffiles = self.factory.jobhandler.request_conffiles(
            self.client_info, cmd.service, cmd.instance)
        self.sendMessage(conffiles.serialize())

    @command(Commands.START_SERVICE)
    def startService(self, cmd):
        self.factory.jobhandler.start_service(self.client_info,
                                              cmd.service, cmd.instance)

    @command(Commands.STOP_SERVICE)
    def stopService(self, cmd):
        self.factory.jobhandler.stop_service(self.client_info,
                                             cmd.service, cmd.instance)

    @command(Commands.RESTART_SERVICE)
    def restartService(self, cmd):
        self.factory.jobhandler.restart_service(self.client_info,
                                                cmd.service, cmd.instance)

    @command(Commands.SEND_CONF_FILE)
    def sendConfFile(self, cmd):
        self.factory.jobhandler.send_conffile(self.client_info,
                                              cmd.service, cmd.instance,
                                              cmd.filename, cmd.contents)


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
        if not self.started.wait(1.0):  # pragma: no cover
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
            try:
                self.server.close()
            except TypeError:  # pragma: no cover
                # Trollius sometimes raises this...
                pass

    def emit_event(self, event):
        handler = self.factory.jobhandler
        if isinstance(event, StatusEvent):
            serialized = event.serialize()
            for client in list(self.factory.clients):
                if handler.can_see_status(client.client_info, event):
                    client.sendMessage(serialized)
        elif isinstance(event, ServiceListEvent):
            for client in list(self.factory.clients):
                filtered = handler.filter_services(client.client_info, event)
                client.sendMessage(filtered.serialize())
        else:
            serialized = event.serialize()
            for client in list(self.factory.clients):
                client.sendMessage(serialized)

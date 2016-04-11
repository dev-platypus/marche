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
#   Georg Brandl <g.brandl@fz-juelich.de>
#
# *****************************************************************************

"""Test for the WebSocket interface and client."""

import os
import logging

from pytest import raises, yield_fixture

from marche import protocol as proto
from marche.config import Config
from marche.client import Client
from marche.iface.wsserver import Interface

from test.utils import MockJobHandler, MockAuthHandler, LogHandler, wait

jobhandler = MockJobHandler()
authhandler = MockAuthHandler()
logger = logging.getLogger('testwsserver')
logger.addHandler(LogHandler())


@yield_fixture(scope='module')
def wsserver_iface(request):
    """Create a Marche WebSocket server interface."""
    config = Config()
    config.iface_config['wsserver'] = {'host': '127.0.0.1', 'port': '0'}
    iface = Interface(config, jobhandler, authhandler, logger)
    jobhandler.test_interface = iface
    iface.run()
    yield iface
    iface.shutdown()


class Events(object):
    def __init__(self):
        self.events = []

    def event_handler(self, event):
        self.events.append(event)

    def expect_event(self, cls):
        wait(100, lambda: self.events)
        event = self.events[-1]
        del self.events[:]
        assert isinstance(event, cls)
        return event


@yield_fixture()
def client(wsserver_iface):
    """Create a WebSocket client."""
    port = wsserver_iface.server.sockets[0].getsockname()[1]
    events = Events()
    client = Client('127.0.0.1', port, events.event_handler, logger)
    client.events = events
    yield client
    client.close()


def test_client_errors(wsserver_iface):
    port = wsserver_iface.server.sockets[0].getsockname()[1]
    assert raises(RuntimeError, Client, '127.0.0.1', port + 1,
                  lambda event: None, logger)


def test_basic(client):
    serverinfo = client.getServerInfo()
    assert serverinfo.proto_version == proto.PROTO_VERSION

    event = proto.ErrorEvent('svc', 'inst', 42, 'an error!')
    jobhandler.emit_event(event)
    evt = client.events.expect_event(proto.ErrorEvent)
    assert evt == event

    client.send(proto.AuthenticateCommand('wrong', 'pass'))
    evt = client.events.expect_event(proto.AuthEvent)
    assert not evt.success

    client.send(proto.AuthenticateCommand('test', 'test'))
    evt = client.events.expect_event(proto.AuthEvent)
    assert evt.success

    client.send(proto.TriggerReloadCommand())
    wait(100, lambda: jobhandler.test_reloaded)

    # server should ignore invalid requests
    client.factory.client.sendMessage(b'some garbage')
    client.factory.client.sendMessage(b'{"type": "garbage"}')

    event = proto.ServiceListEvent(services={'svc': {
        'jobtype': '', 'permissions': [], 'instances': {'inst': {}}
    }})
    jobhandler.emit_event(event)
    evt = client.events.expect_event(proto.ServiceListEvent)
    assert evt.services == {}

    event = proto.StatusEvent('svc', 'inst', 0, '')
    jobhandler.emit_event(event)
    evt = client.events.expect_event(proto.StatusEvent)
    assert evt == event

    client.close()

    wait(100, lambda: not client.factory.client)
    client.close()  # should be a no-op
    assert raises(RuntimeError, client.send, proto.RequestServiceListCommand())


def test_requests(client):
    client.send(proto.RequestServiceListCommand())
    evt = client.events.expect_event(proto.ServiceListEvent)
    assert 'svc' in evt.services

    jobhandler.test_svc_list_error = True
    client.send(proto.RequestServiceListCommand())
    evt = client.events.expect_event(proto.ErrorEvent)
    assert evt.service == evt.instance == ''
    assert 'uh oh' in evt.desc
    jobhandler.test_svc_list_error = False

    client.send(proto.RequestServiceStatusCommand('non', 'existing'))
    evt = client.events.expect_event(proto.ErrorEvent)
    assert evt.code == proto.Errors.FAULT
    assert 'no such service' in evt.desc

    client.send(proto.RequestServiceStatusCommand('svc', 'inst'))
    evt = client.events.expect_event(proto.StatusEvent)
    assert evt.instance == 'inst'
    assert evt.state == 0

    client.send(proto.RequestControlOutputCommand('svc', 'inst'))
    evt = client.events.expect_event(proto.ControlOutputEvent)
    assert evt.content == ['line1', 'line2']

    client.send(proto.RequestLogFilesCommand('svc', 'inst'))
    evt = client.events.expect_event(proto.LogfileEvent)
    assert evt.files['file1'] == 'line1\nline2\n'

    client.send(proto.RequestConfFilesCommand('svc', 'inst'))
    evt = client.events.expect_event(proto.ConffileEvent)
    assert evt.files['file1'] == 'line1\nline2\n'


def test_actions(client):
    client.send(proto.StartCommand('svc', 'inst'))  # passes

    client.send(proto.StopCommand('svc', 'inst'))
    evt = client.events.expect_event(proto.ErrorEvent)
    assert evt.code == proto.Errors.BUSY

    client.send(proto.StopCommand('svc', ''))
    evt = client.events.expect_event(proto.ErrorEvent)
    assert evt.code == proto.Errors.UNAUTH

    client.send(proto.RestartCommand('svc', 'inst'))
    evt = client.events.expect_event(proto.ErrorEvent)
    assert evt.code == proto.Errors.FAULT
    assert 'cannot do this' in evt.desc

    client.send(proto.SendConfFileCommand('svc', 'inst', 'fn', ''))
    evt = client.events.expect_event(proto.ErrorEvent)
    assert evt.code == proto.Errors.EXCEPTION
    assert 'no conf files' in evt.desc

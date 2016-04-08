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

from pytest import raises, fixture, mark

from marche.config import Config
from marche.client import Client
from marche.protocol import ErrorEvent
from marche.iface.wsserver import Interface
from marche.protocol import PROTO_VERSION

from test.utils import MockJobHandler, MockAuthHandler, LogHandler, wait

jobhandler = MockJobHandler()
authhandler = MockAuthHandler()
logger = logging.getLogger('testwsserver')
logger.addHandler(LogHandler())


@fixture(scope='module')
def wsserver_iface(request):
    """Create a Marche WebSocket server interface."""
    config = Config()
    config.iface_config['wsserver'] = {'host': '127.0.0.1', 'port': '0'}
    iface = Interface(config, jobhandler, authhandler, logger)
    jobhandler.test_interface = iface
    iface.run()
    request.addfinalizer(iface.shutdown)
    return iface


@fixture()
def client(wsserver_iface):
    """Create a WebSocket client."""
    port = wsserver_iface.server.sockets[0].getsockname()[1]
    return Client('127.0.0.1', port, logger)


def test_client_errors(wsserver_iface):
    port = wsserver_iface.server.sockets[0].getsockname()[1]
    assert raises(RuntimeError, Client, '127.0.0.1', port + 1, logger)


@mark.skipif(os.name == 'nt', reason='hangs on Windows')
def test_very_basic(client):
    def event_handler(event):
        events.append(event)

    events = []
    client.setEventHandler(event_handler)

    serverinfo = client.getServerInfo()
    assert serverinfo.proto_version == PROTO_VERSION

    event = ErrorEvent('svc', 'inst', 42, 'an error!')
    jobhandler.emit_event(event)
    wait(100, lambda: events)
    assert events[0] == event
    del events[:]

    client.requestServiceList()
    wait(100, lambda: events)
    assert 'svc' in events[0].services

    client.close()

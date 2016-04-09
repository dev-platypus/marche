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

"""Test for the CLI client."""

import logging

from pytest import yield_fixture
from marche.six.moves import StringIO

from marche.cli import Console
from marche.config import Config
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


def test_cli(wsserver_iface):
    io = StringIO()
    port = wsserver_iface.server.sockets[0].getsockname()[1]
    console = Console(['127.0.0.1:%d' % port], stdout=io)
    out = []
    console.write = lambda string: out.append(string)

    def assert_message(string):
        wait(100, lambda: any(string in x for x in out))
        del out[:]

    console.onecmd('auth')
    assert_message('Usage:')
    console.onecmd('auth test wrong')
    assert_message('failed')
    console.onecmd('auth test test')
    assert_message('succeeded')

    console.onecmd('reload')
    wait(100, lambda: jobhandler.test_reloaded)

    console.onecmd('scan')
    assert_message('testhost')

    console.onecmd('list')
    assert_message('svc.inst')

    console.onecmd('start svc.inst')
    console.onecmd('stop svc.inst')
    assert_message('busy')
    console.onecmd('restart svc.inst')
    assert_message('cannot do this')

    console.onecmd('status svc.inst')
    assert_message('DEAD')

    console.onecmd('output svc.inst')
    assert_message('line1')

    console.emptyline()

    assert console.do_EOF('')
    wait(100, lambda: not console.client.factory.client)

    console.onecmd('list')
    assert_message('Error')

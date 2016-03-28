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

"""Test for the authentication and permission classes."""

import sys
import logging

from pytest import raises

from marche.config import Config
from marche.auth.base import Authenticator as BaseAuthenticator
from marche.auth import AuthFailed, AuthHandler
from marche.permission import DISPLAY, CONTROL, ADMIN, parse_permissions

from test.utils import LogHandler

# Pretend that we are an auth module.
sys.modules['marche.auth.test'] = sys.modules[__name__]

logger = logging.getLogger('testauth')
testhandler = LogHandler()
logger.addHandler(testhandler)


class Authenticator(BaseAuthenticator):
    def init(self):
        raise RuntimeError


def test_errors():
    config = Config()
    # No such module.
    config.auth_config = {'nonexisting': {}}
    testhandler.assert_error(AuthHandler, config, logger)
    # Error on init.
    config.auth_config = {'test': {}}
    testhandler.assert_error(AuthHandler, config, logger)


def test_simple():
    config = Config()
    config.auth_config = {'simple': {'user': 'user', 'passwd': 'passwd',
                                     'level': 'control'}}

    handler = AuthHandler(config, logger)
    assert handler.needs_authentication()
    assert handler.authenticate('user', 'passwd').level == CONTROL
    assert raises(AuthFailed, handler.authenticate, 'user', 'wrong')

    config.auth_config = {'simple': {'user': 'user', 'passwd': '',
                                     'level': 'display'}}
    handler = AuthHandler(config, logger)
    assert handler.authenticate('user', 'anypass').level == DISPLAY


def test_parse_permissions():
    pdict = {DISPLAY: DISPLAY, CONTROL: CONTROL, ADMIN: ADMIN}
    parse_permissions(pdict, 'display=control, control=admin, admin=display')
    assert pdict == {DISPLAY: CONTROL, CONTROL: ADMIN, ADMIN: DISPLAY}

    assert raises(ValueError, parse_permissions, pdict, 'foo')
    assert raises(ValueError, parse_permissions, pdict, 'display')
    assert raises(ValueError, parse_permissions, pdict, 'display=foo')
    assert raises(ValueError, parse_permissions, pdict, 'foo=display')
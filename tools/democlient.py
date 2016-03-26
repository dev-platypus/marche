#!/usr/bin/env python
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

import sys
import time
from os import path
from pprint import pprint

sys.path.insert(0, path.abspath(path.join(path.dirname(__file__), '..')))

from marche.client import Client


def printEvent(event):
    pprint(vars(event))

c = Client(str(sys.argv[1]) if len(sys.argv) > 1 else 'server.as-schulz.de')
connectedEvent = c.getServerInfo()

printEvent(connectedEvent)

c.setEventHandler(printEvent)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

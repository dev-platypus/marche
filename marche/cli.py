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
#   Georg Brandl <g.brandl@fz-juelich.de>
#
# *****************************************************************************

from __future__ import print_function

import cmd
import sys
import ctypes
import getpass
import logging

from marche import protocol as proto
from marche.client import Client
from marche.jobs import STATE_STR, DEAD, RUNNING, WARNING, STARTING, \
    STOPPING, INITIALIZING, NOT_RUNNING, NOT_AVAILABLE
from marche.colors import colorize
from marche.utils import normalize_addr

try:  # pragma: no cover
    librl = ctypes.cdll[ctypes.util.find_library('readline')]
except Exception:  # pragma: no cover
    librl = None


class Console(cmd.Cmd):
    prompt = colorize('bold', 'marche->') + ' '
    coloring = {
        DEAD: 'darkred',
        NOT_RUNNING: 'darkgray',
        RUNNING: 'darkgreen',
        WARNING: 'brown',
        STARTING: 'darkblue',
        STOPPING: 'darkblue',
        INITIALIZING: 'darkblue',
        NOT_AVAILABLE: 'darkgray',
    }

    def __init__(self, args, stdout=None):
        cmd.Cmd.__init__(self, stdout=stdout)
        host, port = normalize_addr(args[0] if args else '127.0.0.1', 12132,
                                    lookup_host=False)
        self.client = Client(host, int(port), self.printEvent, logging)
        connectedEvent = self.client.getServerInfo()
        self.write = self.stdout.write
        self.printEvent(connectedEvent)
        self.client.send(proto.RequestServiceListCommand())

    def _svcname(self, svc, inst):
        return '%s.%s' % (svc, inst) if inst else svc

    def _svcinst(self, name):
        return name.split('.', 1) if '.' in name else (name, '')

    def _fmt_state(self, state):
        return colorize(self.coloring[state], STATE_STR[state])

    def printEvent(self, event):
        if isinstance(event, proto.ConnectedEvent):
            self.write('\r%s: daemon version %s, protocol version %s\n' %
                       (colorize('bold', 'Connected'),
                        event.daemon_version, event.proto_version))
        elif isinstance(event, proto.ErrorEvent):
            self.write('\r--> %s: %s\n' %
                       (colorize('red', 'Error'), event.desc))
        elif isinstance(event, proto.ServiceListEvent):
            self.write('\rList of services:\n')
            self.write('%-25s Current state\n' % 'Service')
            self.write('-' * 40 + '\n')
            for svc, info in event.services.items():
                for inst, info in info['instances'].items():
                    self.write('%-25s %s\n' % (self._svcname(svc, inst),
                                               self._fmt_state(info['state'])))
            self.write('-' * 40 + '\n')
            if not event.services:  # pragma: no cover
                self.write('You might need to authenticate to see services.\n')
        elif isinstance(event, proto.StatusEvent):
            self.write('\r--> %s is now %s\n' %
                       (self._svcname(event.service, event.instance),
                        self._fmt_state(event.state)))
        elif isinstance(event, proto.ControlOutputEvent):
            self.write('\rStart/stop output of %s:\n' %
                       self._svcname(event.service, event.instance))
            self.write(''.join(event.content))
        elif isinstance(event, proto.AuthEvent):
            if event.success:
                self.write('\r%s\n' % colorize('green',
                                               'Authentication succeeded.'))
                self.client.send(proto.RequestServiceListCommand())
            else:
                self.write('\r%s\n' % colorize('red',
                                               'Authentication failed.'))
        elif isinstance(event, proto.FoundHostEvent):
            self.write('\rFound host: %s\n' % colorize('bold', event.host))
        else:  # pragma: no cover
            self.write('\r\n')
        if librl:  # pragma: no cover
            # Display a new prompt right now (unfortunately not exported by
            # the readline module.)
            librl.rl_forced_update_display()

    def emptyline(self):
        pass

    def onecmd(self, line):
        try:
            return cmd.Cmd.onecmd(self, line)
        except Exception as err:
            self.write('%s: %s\n' % (colorize('red', 'Error'), err))

    def do_EOF(self, arg):
        self.client.close()
        return True
    do_q = do_quit = do_EOF

    def do_auth(self, arg):
        if not arg:
            self.write('Usage: auth <username> [<password>]\n')
            return
        args = arg.split()
        user = args[0]
        if len(args) == 1:  # pragma: no cover
            passwd = getpass.getpass()
        else:
            passwd = args[1]
        self.client.send(proto.AuthenticateCommand(user, passwd))

    def do_reload(self, arg):
        self.client.send(proto.TriggerReloadCommand())

    def do_scan(self, arg):
        self.client.send(proto.ScanNetworkCommand())

    def do_list(self, arg):
        self.client.send(proto.RequestServiceListCommand())
    do_l = do_list

    def do_status(self, arg):
        self.client.send(
            proto.RequestServiceStatusCommand(*self._svcinst(arg)))

    def do_output(self, arg):
        self.client.send(
            proto.RequestControlOutputCommand(*self._svcinst(arg)))

    def do_start(self, arg):
        self.client.send(proto.StartCommand(*self._svcinst(arg)))

    def do_stop(self, arg):
        self.client.send(proto.StopCommand(*self._svcinst(arg)))

    def do_restart(self, arg):
        self.client.send(proto.RestartCommand(*self._svcinst(arg)))


def main():  # pragma: no cover
    try:
        Console(sys.argv[1:]).cmdloop()
    except KeyboardInterrupt:
        pass

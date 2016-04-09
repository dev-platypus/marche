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
import readline

from marche.six.moves import input

from marche import protocol as proto
from marche.client import Client
from marche.jobs import STATE_STR, DEAD, RUNNING, WARNING, STARTING, \
    STOPPING, INITIALIZING, NOT_RUNNING, NOT_AVAILABLE
from marche.colors import colorize

try:
    librl = ctypes.cdll[ctypes.util.find_library('readline')]
except Exception:
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

    def __init__(self):
        cmd.Cmd.__init__(self)
        host = str(sys.argv[1]) if len(sys.argv) > 1 else '127.0.0.1'
        self.client = Client(host, 12132, self.printEvent, logging)
        connectedEvent = self.client.getServerInfo()
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
            print('\rConnected: daemon version %s, protocol version %s' %
                  (event.daemon_version, event.proto_version))
        elif isinstance(event, proto.ErrorEvent):
            print('\r--> Error: %s' % event.desc)
        elif isinstance(event, proto.ServiceListEvent):
            print('\rList of services:')
            print('%-25s Current state' % 'Service')
            print('-' * 40)
            for svc, info in event.services.items():
                for inst, info in info['instances'].items():
                    print('%-25s %s' % (self._svcname(svc, inst),
                                        self._fmt_state(info['state'])))
            print('-' * 40)
            if not event.services:
                print('You might need to authenticate to see services.')
        elif isinstance(event, proto.StatusEvent):
            print('\r--> %s is now %s' %
                  (self._svcname(event.service, event.instance),
                   self._fmt_state(event.state)))
        elif isinstance(event, proto.ControlOutputEvent):
            print('\rStart/stop output of %s:' % self._svcname(event.service,
                                                               event.instance))
            print(''.join(event.content), end='')
        elif isinstance(event, proto.AuthEvent):
            if event.success:
                print(colorize('green', '\rAuthentication succeeded.'))
                self.client.send(proto.RequestServiceListCommand())
            else:
                print(colorize('red', '\rAuthentication failed.'))
        elif isinstance(event, proto.FoundHostEvent):
            print('\rFound host: %s' % colorize('bold', event.host))
        else:
            print('\r')
        if librl:
            # Display a new prompt right now (unfortunately not exported by
            # the readline module.)
            librl.rl_forced_update_display()

    def emptyline(self):
        pass

    def onecmd(self, line):
        try:
            return cmd.Cmd.onecmd(self, line)
        except Exception as err:
            print('Error: %s' % err)

    def do_EOF(self, arg):
        self.client.close()
        return True
    do_q = do_quit = do_EOF

    def do_auth(self, arg):
        if not arg:
            print('Usage: auth username')
        passwd = getpass.getpass()
        self.client.send(proto.AuthenticateCommand(arg, passwd))

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


def main():
    try:
        Console().cmdloop()
    except KeyboardInterrupt:
        pass

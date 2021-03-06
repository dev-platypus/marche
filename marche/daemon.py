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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

from __future__ import print_function

import os
import sys
import time
import signal
import logging
import argparse
from os import path

from marche import __version__
from marche.config import Config
from marche.utils import daemonize, setuser, write_pidfile, remove_pidfile, \
    get_default_cfgdir
from marche.loggers import ColoredConsoleHandler, LogfileHandler
from marche.handler import JobHandler
from marche.auth import AuthHandler
from marche.colors import nocolor

# configure logging library: we don't need process/thread ids and callers
logging.logMultiprocessing = False
logging.logProcesses = False
logging.logThreads = False
logging._srcfile = None  # pylint: disable=protected-access


class Daemon(object):
    def __init__(self):
        self.stop = False
        self.log = logging.getLogger('marche')
        if os.name == 'nt':  # pragma: no cover
            nocolor()

    def parse_args(self, args):
        rootdir = path.join(path.dirname(__file__), '..')
        if path.exists(path.join(rootdir, '.git')):
            default_cfgdir = path.abspath(path.join(rootdir, 'etc'))
        else:  # pragma: no cover
            default_cfgdir = get_default_cfgdir()

        parser = argparse.ArgumentParser()
        parser.add_argument('--version', action='version',
                            version='Marche daemon version %s' % __version__)
        parser.add_argument('-c', dest='configdir', action='store',
                            default=default_cfgdir, help='configuration '
                            'directory (default %s)' % default_cfgdir)
        parser.add_argument('-d', dest='daemonize', action='store_true',
                            help='daemonize the process')
        parser.add_argument('-v', dest='verbose', action='store_true',
                            help='verbose (debug) output')
        return parser.parse_args(args)

    def apply_config(self):
        self.config = Config(self.args.configdir)

        if self.args.daemonize:  # pragma: no cover
            daemonize(self.config.user, self.config.group)
        else:
            setuser(self.config.user, self.config.group)

        self.log.setLevel(logging.DEBUG if self.args.verbose else logging.INFO)
        del self.log.handlers[:]
        if not self.args.daemonize:
            self.log.addHandler(ColoredConsoleHandler())
        try:
            self.log.addHandler(LogfileHandler(self.config.logdir, 'marche'))
        except Exception as err:  # pragma: no cover
            if self.args.daemonize:
                print('cannot open logfile:', err, file=sys.stderr)
            else:
                self.log.exception('cannot open logfile: %s', err)
            return False

        if not self.config.interfaces:
            self.log.error('no interfaces configured, the daemon will not do '
                           'anything useful!')
            return False

        if not self.config.job_config:
            self.log.error('no jobs configured, the daemon will not do '
                           'anything useful!')
            return False

        if not self.config.auth_config:
            self.log.warning('no authenticators configured, everyone will be '
                             'able to execute any action!')

        if self.args.daemonize:  # pragma: no cover
            write_pidfile(self.config.piddir)

        return True

    def run(self, args=None):
        self.args = self.parse_args(args)
        if not self.apply_config():
            return 1

        self.log.info('Starting marche %s ...', __version__)

        jobhandler = JobHandler(self.config, self.log)
        authhandler = AuthHandler(self.config, self.log)

        for interface in self.config.interfaces:
            try:
                mod = __import__('marche.iface.%s' % interface, {}, {},
                                 ['Interface'])
            except Exception as err:
                self.log.exception('could not import interface %r: %s',
                                   interface, err)
                continue
            self.log.info('starting interface: %s', interface)
            try:
                iface = mod.Interface(self.config, jobhandler, authhandler,
                                      self.log)
                if iface.needs_events:
                    jobhandler.add_interface(iface)
                iface.run()
            except Exception as err:
                self.log.exception('could not start interface %r: %s',
                                   interface, err)
                continue

        signal.signal(signal.SIGTERM, lambda *a: setattr(self, 'stop', True))
        signal.signal(signal.SIGUSR1, lambda *a: jobhandler.trigger_reload())

        self.log.info('startup successful')
        self.wait()

        jobhandler.shutdown()

        if self.args.daemonize:  # pragma: no cover
            remove_pidfile(self.config.piddir)
        return 0

    def wait(self):  # pragma: no cover
        try:
            while not self.stop:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

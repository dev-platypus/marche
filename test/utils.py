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

"""Utilities for the tests."""

import time
import logging

from marche.jobs import Fault, Busy, Unauthorized, DEAD, RUNNING
from marche.jobs.base import Job as BaseJob
from marche.protocol import ServiceListEvent, StatusEvent, LogfileEvent, \
    ConffileEvent, ControlOutputEvent, FoundHostEvent
from marche.auth import AuthFailed
from marche.permission import ClientInfo, DISPLAY, ADMIN, NONE


def wait(nmax, callback):
    n = 0
    while not callback():
        time.sleep(0.01)
        n += 1
        if n > nmax:
            raise RuntimeError('wait timeout reached')


def job_call_check(job, service, instance, cmdlinesuffix, output):
    for action in ('start', 'stop', 'restart'):
        if action == 'start':
            job.start_service(service, instance)
        elif action == 'stop':
            job.stop_service(service, instance)
        elif action == 'restart':
            job.restart_service(service, instance)
        wait(100, lambda: job.service_status(service, instance)[0] == RUNNING)
        out = job.service_output(service, instance)
        outlen = len(output)
        assert out[-outlen-1].startswith('$ ')
        assert out[-outlen-1].endswith(' %s\n' %
                                       cmdlinesuffix.replace('action', action))
        assert out[-outlen:] == [l.replace('action', action) + '\n'
                                 for l in output]


class LogHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.errors = []
        self.warnings = []
        self.messages = 0

    def assert_error(self, func, *args):
        nerrors = len(self.errors)
        func(*args)
        assert len(self.errors) > nerrors

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            self.errors.append(record)
        elif record.levelno >= logging.WARNING:
            self.warnings.append(record)
        else:
            self.messages += 1


class MockAsyncProcess(object):
    def __init__(self, status, log, cmd, sh, stdout=None, stderr=None):
        self.status = status
        self.log = log
        self.cmd = cmd
        self.use_sh = sh
        self.stdout = stdout if stdout is not None else []
        self.stderr = stderr if stderr is not None else []
        self.done = False
        self.retcode = None

    def start(self):
        time.sleep(0.01)
        self.stdout.append('output\n')
        self.stderr.append('error\n')
        self.retcode = 1 if self.cmd == 'fail' else 0
        self.done = True

    def join(self):
        pass


class MockJobHandler(object):

    test_interface = None
    test_reloaded = False
    test_svc_list_error = False
    unauth_level = NONE
    uid = 'deadcafe'

    def emit_event(self, event):
        if self.test_interface:
            self.test_interface.emit_event(event)

    def trigger_reload(self):
        self.test_reloaded = True

    def scan_network(self):
        self.emit_event(FoundHostEvent('testhost', 2))

    def request_service_list(self, client):
        if self.test_svc_list_error:
            raise Fault('uh oh')
        svcs = {'svc': {
            'jobtype': '',
            'permissions': [],
            'instances': {
                '': {'desc': '', 'state': DEAD, 'ext_status': ''},
                'inst': {'desc': '', 'state': DEAD, 'ext_status': ''}}}}
        return ServiceListEvent(services=svcs)

    def filter_services(self, client, event):
        return ServiceListEvent(services={})

    def can_see_status(self, client, event):
        return True

    def get_service_description(self, client, service, instance):
        return 'desc'

    def request_service_status(self, client, service, instance):
        if service != 'svc':
            raise Fault('no such service')
        return StatusEvent(service=service, instance=instance,
                           state=DEAD, ext_status='ext_status')

    def request_control_output(self, client, service, instance):
        return ControlOutputEvent(service=service, instance=instance,
                                  content=['line1', 'line2'])

    def request_logfiles(self, client, service, instance):
        return LogfileEvent(service=service, instance=instance,
                            files={'file1': 'line1\nline2\n',
                                   'file2': 'line3\nline4\n'})

    def request_conffiles(self, client, service, instance):
        return ConffileEvent(service=service, instance=instance,
                             files={'file1': 'line1\nline2\n',
                                    'file2': 'line3\nline4\n'})

    def start_service(self, client, service, instance):
        if client.level < ADMIN:
            raise Fault('no permission')

    def stop_service(self, client, service, instance):
        if instance == 'inst':
            raise Busy
        raise Unauthorized

    def restart_service(self, client, service, instance):
        raise Fault('cannot do this')

    def send_conffile(self, client, service, instance, filename, contents):
        raise ValueError('no conf files')


class MockAuthHandler(object):

    def needs_authentication(self):
        return True

    def authenticate(self, user, passwd):
        if user == passwd == 'test':
            return ClientInfo(ADMIN)
        if user == passwd == 'guest':
            return ClientInfo(DISPLAY)
        raise AuthFailed


class MockIface(object):
    """Standin for an interface from the handler side."""

    def __init__(self, events):
        self.test_events = events

    def emit_event(self, event):
        self.test_events.append(event)


class MockJob(BaseJob):
    """Job for testing the handler class."""

    def init(self):
        # Does not call the base class init() to not start the poller thread
        # (avoids async events to conflict with expected events).
        self.test_started = []
        self.test_stopped = []
        self.test_restarted = []
        self.test_configs = {}

    def check(self):
        return not self.config.get('fail')

    def get_services(self):
        return [
            ('svc1', ''),       # A service without instances
            ('svc2', 'inst1'),  # A service with only subinstances
            ('svc3', ''),       # A service with a main and sub instance
            ('svc3', 'inst2'),
        ]

    def service_description(self, service, instance):
        return 'desc:' + instance

    def service_status(self, service, instance):
        if service == 'svc1':
            return DEAD, 'ext:' + instance
        return RUNNING, 'ext:' + instance

    def service_output(self, service, instance):
        return ['out:' + instance]

    def service_logs(self, service, instance):
        return {'log:' + instance: service}

    def start_service(self, service, instance):
        if service == 'svc1':
            raise Busy
        elif service == 'svc2':
            raise Fault
        self.test_started.append((service, instance))

    def stop_service(self, service, instance):
        self.test_stopped.append((service, instance))

    def restart_service(self, service, instance):
        if service == 'svc1':
            raise ValueError
        self.test_restarted.append((service, instance))

    def receive_config(self, service, instance):
        return {'conf:' + instance: service}

    def send_config(self, service, instance, filename, contents):
        self.test_configs[filename] = contents

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

"""Constants for use with the new Marche protocol."""

import json

from marche.six import add_metaclass

# Increment this when making changes to the protocol.
PROTO_VERSION = 2


class Commands(object):
    AUTHENTICATE = 'auth'
    TRIGGER_RELOAD = 'reload'
    SCAN_NETWORK = 'scan'
    START_SERVICE = 'start'
    STOP_SERVICE = 'stop'
    RESTART_SERVICE = 'restart'
    REQUEST_SERVICE_LIST = 'services?'
    REQUEST_SERVICE_STATUS = 'status?'
    REQUEST_CONTROL_OUTPUT = 'output?'
    REQUEST_LOG_FILES = 'logfiles?'
    REQUEST_CONF_FILES = 'conffiles?'
    SEND_CONF_FILE = 'sendconfig'


class Events(object):
    CONNECTED = 'connected'
    AUTH_RESULT = 'authresult'
    SERVICE_LIST = 'services'
    ERROR = 'error'
    STATUS = 'status'
    CONTROL_OUTPUT = 'output'
    CONF_FILES = 'conffiles'
    LOG_FILES = 'logfiles'
    FOUND_HOST = 'host'


class Errors(object):
    BUSY = 1
    FAULT = 2
    UNAUTH = 3
    EXCEPTION = 9


class RegistryMeta(type):
    def __new__(mcs, name, bases, attrs):
        newtype = type.__new__(mcs, name, bases, attrs)
        if newtype.type:
            newtype.registry[newtype.type] = newtype
        return newtype


@add_metaclass(RegistryMeta)
class SerializableMessage(object):
    registry = {}

    #: Designation of the type of message.
    type = None

    def serialize(self):
        if not self.type:
            raise RuntimeError('base class cannot be serialized')
        ret = {'type': self.type}
        ret.update(vars(self))
        return json.dumps(ret).encode('utf-8')

    @classmethod
    def unserialize(cls, data):
        data = json.loads(data.decode('utf-8'))
        if 'type' not in data:
            raise RuntimeError('type not given in data')
        if data['type'] not in cls.registry:
            # command is not recognized; ignore it for compatibility
            return None
        cls = cls.registry[data.pop('type')]
        return cls(**data)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and \
            vars(self) == vars(other)

    def __repr__(self):
        return '<%s: %r>' % (self.__class__.__name__, vars(self))


# -----------------------------------------------------------------------------

class Command(SerializableMessage):
    registry = {}


class AuthenticateCommand(Command):
    type = Commands.AUTHENTICATE

    def __init__(self, user, passwd):
        self.user = user
        self.passwd = passwd


class ScanNetworkCommand(Command):
    type = Commands.SCAN_NETWORK


class TriggerReloadCommand(Command):
    type = Commands.TRIGGER_RELOAD


class RequestServiceListCommand(Command):
    type = Commands.REQUEST_SERVICE_LIST


class ServiceCommand(Command):
    def __init__(self, service, instance):
        self.service = service
        self.instance = instance


class StartCommand(ServiceCommand):
    type = Commands.START_SERVICE


class StopCommand(ServiceCommand):
    type = Commands.STOP_SERVICE


class RestartCommand(ServiceCommand):
    type = Commands.RESTART_SERVICE


class RequestServiceStatusCommand(ServiceCommand):
    type = Commands.REQUEST_SERVICE_STATUS


class RequestControlOutputCommand(ServiceCommand):
    type = Commands.REQUEST_CONTROL_OUTPUT


class RequestLogFilesCommand(ServiceCommand):
    type = Commands.REQUEST_LOG_FILES


class RequestConfFilesCommand(ServiceCommand):
    type = Commands.REQUEST_CONF_FILES


class SendConfFileCommand(ServiceCommand):
    type = Commands.SEND_CONF_FILE

    def __init__(self, service, instance, filename, contents):
        ServiceCommand.__init__(self, service, instance)
        self.filename = filename
        self.contents = contents


# -----------------------------------------------------------------------------

class Event(SerializableMessage):
    registry = {}


class ConnectedEvent(Event):
    type = Events.CONNECTED

    def __init__(self, proto_version, daemon_version, unauth_level, subnet):
        self.proto_version = proto_version
        self.daemon_version = daemon_version
        self.unauth_level = unauth_level
        self.subnet = subnet


class ServiceListEvent(Event):
    type = Events.SERVICE_LIST

    def __init__(self, services):
        self.services = services


class AuthEvent(Event):
    type = Events.AUTH_RESULT

    def __init__(self, success):
        self.success = success


class ServiceEvent(Event):
    def __init__(self, service, instance):
        self.service = service
        self.instance = instance


class StatusEvent(ServiceEvent):
    type = Events.STATUS

    def __init__(self, service, instance, state, ext_status):
        ServiceEvent.__init__(self, service, instance)
        self.state = state
        self.ext_status = ext_status


class ErrorEvent(ServiceEvent):
    type = Events.ERROR

    def __init__(self, service, instance, code, desc):
        ServiceEvent.__init__(self, service, instance)
        self.code = code
        self.desc = desc


class ControlOutputEvent(ServiceEvent):
    type = Events.CONTROL_OUTPUT

    def __init__(self, service, instance, content):
        ServiceEvent.__init__(self, service, instance)
        self.content = content


class FileEvent(ServiceEvent):
    def __init__(self, service, instance, files):
        ServiceEvent.__init__(self, service, instance)
        self.files = files


class ConffileEvent(FileEvent):
    type = Events.CONF_FILES


class LogfileEvent(FileEvent):
    type = Events.LOG_FILES


class FoundHostEvent(Event):
    type = Events.FOUND_HOST

    def __init__(self, host, version):
        self.host = host
        self.version = version

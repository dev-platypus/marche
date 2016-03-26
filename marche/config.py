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

"""Config file handling."""

import os
from os import path

from marche.six.moves import configparser

from marche.permission import DISPLAY, STRING_LEVELS


class CasePreservingConfigParser(configparser.SafeConfigParser):
    def optionxform(self, key):
        return key


class Config(object):
    """An object that represents all merged Marche configuration files."""

    user = None
    group = None
    piddir = '/var/run'
    logdir = '/var/log'

    job_config = {}
    auth_config = {}
    iface_config = {}
    interfaces = ['xmlrpc', 'udp', 'snzl']
    unauth_level = DISPLAY

    def __init__(self, confdir=None):
        self.confdir = confdir
        self.reload()

    def reload(self):
        confdir = self.confdir
        self.__dict__.clear()
        self.confdir = confdir
        self.job_config = {}
        self.auth_config = {}
        self.iface_config = {}
        if confdir is None or not path.isdir(self.confdir):
            return

        for fn in os.listdir(self.confdir):
            if fn.endswith('.conf'):
                self._read_one(path.join(self.confdir, fn))

    def _read_one(self, fname):
        parser = CasePreservingConfigParser()
        parser.read(fname)

        for section in parser.sections():
            if section == 'general':
                if parser.has_option('general', 'user'):
                    self.user = parser.get('general', 'user')
                if parser.has_option('general', 'group'):
                    self.group = parser.get('general', 'group')
                if parser.has_option('general', 'piddir'):
                    self.piddir = parser.get('general', 'piddir')
                if parser.has_option('general', 'logdir'):
                    self.logdir = parser.get('general', 'logdir')
                if parser.has_option('general', 'interfaces'):
                    self.interfaces = [
                        i.strip() for i in
                        parser.get('general', 'interfaces').split(',') if i]
                if parser.has_option('general', 'unauth_level'):
                    perm = parser.get('general', 'unauth_level')
                    self.unauth_level = STRING_LEVELS.get(perm.lower().strip(),
                                                          DISPLAY)
            elif section.startswith('job.'):
                self.job_config[section[4:]] = dict(parser.items(section))
            elif section.startswith('auth.'):
                self.auth_config[section[5:]] = dict(parser.items(section))
            elif section.startswith('interface.'):
                if section[10:] == 'xmlrpc':
                    # Legacy support for user/passwd in xmlrpc section
                    if parser.has_option(section, 'user'):
                        self.auth_config.setdefault('simple', {})['user'] = \
                            parser.get(section, 'user')
                    if parser.has_option(section, 'passwd'):
                        self.auth_config.setdefault('simple', {})['passwd'] = \
                            parser.get(section, 'passwd')
                self.iface_config[section[10:]] = dict(parser.items(section))

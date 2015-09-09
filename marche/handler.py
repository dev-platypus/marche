#  -*- coding: utf-8 -*-
# *****************************************************************************
# MLZ server control daemon
# Copyright (c) 2015 by the authors, see LICENSE
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

"""Job control dispatcher."""

from threading import Lock


class JobHandler(object):

    def __init__(self, config, log):
        self.config = config
        self.log = log
        self._lock = Lock()
        self.jobs = {}
        self.service2job = {}
        self._add_jobs()

    def _add_jobs(self):
        self.log.info('adding jobs...')
        for (name, config) in self.config.job_config.items():
            if 'type' not in config:
                self.log.warning('job %r has no type assigned, ignoring' % name)
                continue
            try:
                mod = __import__('marche.jobs.%s' % config['type'], {}, {}, 'Job')
            except Exception as err:
                self.log.exception('could not import module %r for job %s: %s' %
                                   (config['type'], name, err))
                continue
            try:
                job = mod.Job(name, config, self.log)
                if not job.check():
                    raise RuntimeError('feasibility check failed')
                for service in job.get_services():
                    if service in self.service2job:
                        raise RuntimeError('duplicate service name %r, provided by jobs '
                                           '%s and %s' % (service, name,
                                                          self.service2job[service].name))
                    self.service2job[service] = job
                    self.log.info('found service: %s' % service)
            except Exception as err:
                self.log.exception('could not initialize job %s: %s' % (name, err))
            else:
                self.jobs[name] = job
                self.log.info('job %s initialized' % name)

    def reload_jobs(self):
        """Reload the jobs and list of their services."""
        with self._lock:
            self.config.reload()
            self.jobs = {}
            self.service2job = {}
            self._add_jobs()

    def get_services(self):
        """Get a list of all services provided by jobs."""
        with self._lock:
            return self.service2job.keys()

    def start_service(self, name):
        """Start a single service."""
        with self._lock:
            self.service2job[name].start_service(name)

    def stop_service(self, name):
        """Stop a single service."""
        with self._lock:
            self.service2job[name].stop_service(name)

    def restart_service(self, name):
        """Restart a single service."""
        with self._lock:
            self.service2job[name].restart_service(name)

    def service_status(self, name):
        """Return the status of a single service."""
        with self._lock:
            return self.service2job[name].service_status(name)

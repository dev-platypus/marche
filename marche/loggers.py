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

import os
import sys
import time
import linecache
import traceback
from os import path
from logging import Formatter, Handler, DEBUG, INFO, WARNING, ERROR

from marche.six import iteritems

from marche import colors

LOGFMT = '%(asctime)s : %(levelname)-7s : %(name)-25s: %(message)s'
DATEFMT = '%H:%M:%S'
DATESTAMP_FMT = '%Y-%m-%d'
SECONDS_PER_DAY = 60 * 60 * 24

LOGLEVELS = {'debug': DEBUG, 'info': INFO, 'warning': WARNING, 'error': ERROR}


class ConsoleFormatter(Formatter):
    """
    A lightweight formatter for the interactive console, with optional
    colored output.
    """

    def __init__(self, fmt=None, datefmt=None, colorize=None):
        Formatter.__init__(self, fmt, datefmt)
        self.colorize = colorize if colorize else lambda c, s: s

    def formatTime(self, record, datefmt=None):
        return time.strftime(datefmt or DATEFMT,
                             self.converter(record.created))

    def format(self, record):
        record.message = record.getMessage()
        levelno = record.levelno
        datefmt = self.colorize('lightgray', '[%(asctime)s] ')
        namefmt = '%(name)-25s: '
        if levelno <= DEBUG:
            fmtstr = self.colorize('darkgray', '%s%%(message)s' % namefmt)
        elif levelno <= INFO:
            fmtstr = '%s%%(message)s' % namefmt
        elif levelno <= WARNING:
            fmtstr = self.colorize('fuchsia', '%s%%(levelname)s: %%(message)s'
                                   % namefmt)
        else:
            fmtstr = self.colorize('red', '%s%%(levelname)s: %%(message)s'
                                   % namefmt)
        fmtstr = datefmt + fmtstr
        if not getattr(record, 'nonl', False):
            fmtstr += '\n'
        record.asctime = self.formatTime(record, self.datefmt)
        # Note: no exception info, it only goes to the logfile.
        return fmtstr % record.__dict__


def format_extended_frame(frame):
    ret = []
    for key, value in iteritems(frame.f_locals):
        try:
            valstr = repr(value)[:256]
        except Exception:
            valstr = '<cannot be displayed>'
        ret.append('        %-20s = %s\n' % (key, valstr))
    ret.append('\n')
    return ret


def format_extended_traceback(etype, value, tb):
    ret = ['Traceback (most recent call last):\n']
    while tb is not None:
        frame = tb.tb_frame
        filename = frame.f_code.co_filename
        item = '  File "%s", line %d, in %s\n' % (filename, tb.tb_lineno,
                                                  frame.f_code.co_name)
        linecache.checkcache(filename)
        line = linecache.getline(filename, tb.tb_lineno, frame.f_globals)
        if line:
            item = item + '    %s\n' % line.strip()
        ret.append(item)
        if filename != '<script>':
            ret += format_extended_frame(tb.tb_frame)
        tb = tb.tb_next
    ret += traceback.format_exception_only(etype, value)
    return ''.join(ret).rstrip('\n')


class LogfileFormatter(Formatter):
    """
    The standard Formatter does not support milliseconds with an explicit
    datestamp format.  It also doesn't show the full traceback for exceptions.
    """

    extended_traceback = True

    def formatException(self, ei):
        if self.extended_traceback:
            s = format_extended_traceback(*ei)
        else:
            s = ''.join(traceback.format_exception(ei[0], ei[1], ei[2],
                                                   sys.maxsize))
            if s.endswith('\n'):
                s = s[:-1]
        return s

    def formatTime(self, record, datefmt=None):
        res = time.strftime(DATEFMT, self.converter(record.created))
        res += ',%03d' % record.msecs
        return res


class StreamHandler(Handler):
    """Reimplemented from logging: remove cruft, remove bare excepts."""

    def __init__(self, stream):
        Handler.__init__(self)
        self.stream = stream

    def flush(self):
        self.acquire()
        try:
            if self.stream and hasattr(self.stream, 'flush'):
                self.stream.flush()
        finally:
            self.release()

    def emit(self, record):
        try:
            msg = self.format(record)
            try:
                self.stream.write('%s\n' % msg)
            except UnicodeEncodeError:  # pragma: no cover
                self.stream.write('%s\n' % msg.encode('utf-8'))
            self.flush()
        except Exception:  # pragma: no cover
            self.handleError(record)


class LogfileHandler(StreamHandler):
    """
    Logs to log files with a date stamp appended, and rollover on midnight.
    """

    def __init__(self, directory, filenameprefix, dayfmt=DATESTAMP_FMT):
        directory = path.join(directory, filenameprefix)
        if not path.isdir(directory):
            os.makedirs(directory)
        self._currentsymlink = path.join(directory, 'current')
        self._filenameprefix = filenameprefix
        self._pathnameprefix = path.join(directory, filenameprefix)
        self._dayfmt = dayfmt
        # today's logfile name
        basefn = self._pathnameprefix + '-' + time.strftime(dayfmt) + '.log'
        self.base_filename = path.abspath(basefn)
        self.mode = 'a'
        StreamHandler.__init__(self, self._open())
        # determine time of first midnight from now on
        t = time.localtime()
        self.rollover_at = time.mktime((t[0], t[1], t[2], 0, 0, 0,
                                        t[6], t[7], t[8])) + SECONDS_PER_DAY
        self.setFormatter(LogfileFormatter(LOGFMT, DATEFMT))

    def _open(self):
        # update 'current' symlink upon open
        try:
            os.remove(self._currentsymlink)
        except OSError:
            # if the symlink does not (yet) exist, OSError is raised.
            # should happen at most once per installation....
            pass
        if hasattr(os, 'symlink'):
            os.symlink(path.basename(self.base_filename), self._currentsymlink)
        # finally open the new logfile....
        return open(self.base_filename, self.mode)

    def emit(self, record):
        try:
            t = int(time.time())
            if t >= self.rollover_at:
                self.do_rollover()
            if self.stream is None:
                self.stream = self._open()
            StreamHandler.emit(self, record)
        except Exception:  # pragma: no cover
            self.handleError(record)

    def close(self):
        self.acquire()
        try:
            if self.stream:
                self.flush()
                if hasattr(self.stream, 'close'):
                    self.stream.close()
                StreamHandler.close(self)
                self.stream = None
        finally:
            self.release()

    def do_rollover(self):
        self.stream.close()
        self.base_filename = self._pathnameprefix + '-' + \
            time.strftime(self._dayfmt) + '.log'
        self.stream = self._open()
        self.rollover_at += SECONDS_PER_DAY


class ColoredConsoleHandler(StreamHandler):
    """
    A handler class that writes colorized records to standard output.
    """

    def __init__(self, stream=None):
        StreamHandler.__init__(self, stream or sys.stdout)
        self.setFormatter(ConsoleFormatter(datefmt=DATEFMT,
                                           colorize=colors.colorize))

    def emit(self, record):
        msg = self.format(record)
        try:
            self.stream.write(msg)
        except UnicodeEncodeError:  # pragma: no cover
            self.stream.write(msg.encode('utf-8'))
        self.stream.flush()

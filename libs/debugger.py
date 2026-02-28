# -*- coding: UTF-8 -*-
#
# Universal Movie Scraper (Python) - metadata.universal.python
# Based on metadata.universal XML scraper by Olympia
# Python structure inspired by metadata.themoviedb.org.python by Team Kodi
#
# SPDX-License-Identifier: GPL-2.0-or-later
# See LICENSE.txt for more information.

"""
Provides a context manager that writes extended debugging info
in the Kodi log on unhandled exceptions
"""
from __future__ import absolute_import, unicode_literals

import inspect
from contextlib import contextmanager
from platform import uname
from pprint import pformat

import xbmc

from .utils import logger

try:
    from typing import Text, Generator, Callable, Dict, Any
except ImportError:
    pass


def _format_vars(variables):
    # type: (Dict[Text, Any]) -> Text
    """
    Format variables dictionary

    :param variables: variables dict
    :return: formatted string with sorted var = val pairs
    """
    var_list = [(var, val) for var, val in variables.items()
                if not (var.startswith('__') or var.endswith('__'))]
    var_list.sort(key=lambda i: i[0])
    lines = []
    for var, val in var_list:
        lines.append('{0} = {1}'.format(var, pformat(val)))
    return '\n'.join(lines)


@contextmanager
def debug_exception(logger_func=logger.error):
    # type: (Callable[[Text], None]) -> Generator[None]
    """
    Diagnostic helper context manager

    It controls execution within its context and writes extended
    diagnostic info to the Kodi log if an unhandled exception
    happens within the context.

    :param logger_func: logger function which must accept a single argument
        which is a log message.
    """
    try:
        yield
    except Exception as exc:
        frame_info = inspect.trace(5)[-1]
        logger_func(
            '*** Unhandled exception detected: {} {} ***'.format(type(exc), exc))
        logger_func('*** Start diagnostic info ***')
        logger_func('System info: {0}'.format(uname()))
        logger_func('OS info: {0}'.format(
            xbmc.getInfoLabel('System.OSVersionInfo')))
        logger_func('Kodi version: {0}'.format(
            xbmc.getInfoLabel('System.BuildVersion')))
        logger_func('Module: {0}'.format(frame_info[1]))
        logger_func('Code fragment:\n{0}'.format(
            ''.join(frame_info[4])))
        logger_func('Local variables:\n{0}'.format(
            _format_vars(frame_info[0].f_locals)))
        logger_func('*** End diagnostic info ***')
        raise

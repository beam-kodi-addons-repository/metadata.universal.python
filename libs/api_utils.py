# -*- coding: UTF-8 -*-
#
# Universal Movie Scraper (Python) - metadata.universal.python
# Based on metadata.universal XML scraper by Olympia
# Python structure inspired by metadata.themoviedb.org.python by Team Kodi
#
# SPDX-License-Identifier: GPL-2.0-or-later
# See LICENSE.txt for more information.

"""Functions to interact with various web site APIs"""

from __future__ import absolute_import, unicode_literals

import json
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import URLError
from urllib.parse import urlencode
from .utils import logger


class _RedirectHandler(HTTPRedirectHandler):
    """Extended redirect handler that also follows HTTP 308 Permanent Redirect"""
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)


_opener = build_opener(_RedirectHandler)

try:
    from typing import Text, Optional, Union, List, Dict, Any
    InfoType = Dict[Text, Any]
except ImportError:
    pass

HEADERS = {}


def set_headers(headers):
    # type: (Dict) -> None
    HEADERS.clear()
    HEADERS.update(headers)


def load_info(url, params=None, default=None, resp_type='json'):
    # type: (Text, Dict, Text, Text) -> Optional[Text]
    """
    Load info from external api

    :param url: API endpoint URL
    :param params: URL query params
    :default: object to return if there is an error
    :resp_type: what to return to the calling function
    :return: API response or default on error
    """
    theerror = ''
    if params:
        url = url + '?' + urlencode(params)
    logger.debug('Calling URL "{}"'.format(url))
    if HEADERS:
        logger.debug(str(HEADERS))
    req = Request(url, headers=HEADERS)
    try:
        response = _opener.open(req)
    except URLError as e:
        if hasattr(e, 'reason'):
            theerror = {'error': 'failed to reach the remote site\nReason: {}'.format(e.reason)}
            logger.debug(
                'failed to reach the remote site\nReason: {}'.format(e.reason))
        elif hasattr(e, 'code'):
            theerror = {'error': 'remote site unable to fulfill the request\nError code: {}'.format(e.code)}
            logger.debug(
                'remote site unable to fulfill the request\nError code: {}'.format(e.code))
        if default is not None:
            return default
        else:
            return theerror
    if response is None:
        resp = default
    elif resp_type.lower() == 'json':
        try:
            resp = json.loads(response.read().decode('utf-8'))
        except json.decoder.JSONDecodeError:
            logger.debug('remote site sent back bad JSON')
            resp = default
    else:
        resp = response.read().decode('utf-8')
    return resp

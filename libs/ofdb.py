# -*- coding: UTF-8 -*-
#
# Universal Movie Scraper (Python) - metadata.universal.python
# Based on metadata.universal XML scraper by Olympia
# Python structure inspired by metadata.themoviedb.org.python by Team Kodi
#
# SPDX-License-Identifier: GPL-2.0-or-later
# See LICENSE.txt for more information.

"""Functions to get plot from OFDb.de (Online Film Datenbank)"""

from __future__ import absolute_import, unicode_literals

import re
from . import api_utils
from .utils import logger

try:
    from typing import Optional, Text
except ImportError:
    pass

OFDB_SEARCH_URL = 'https://ssl.ofdb.de/view.php'
OFDB_BASE_URL = 'https://ssl.ofdb.de/'


def get_ofdb_plot(imdb_id):
    # type: (Text) -> Optional[Text]
    """
    Get German-language plot from OFDb.de using IMDb ID

    :param imdb_id: IMDb ID (e.g. tt1234567)
    :return: plot text or None
    """
    if not imdb_id:
        return None
    logger.debug('Searching OFDb.de for {}'.format(imdb_id))

    # Search for the movie by IMDb ID
    response = api_utils.load_info(
        OFDB_SEARCH_URL,
        params={'page': 'suchergebnis', 'SText': imdb_id, 'Ession': 'cinema'},
        default='', resp_type='text'
    )
    if not response:
        return None

    # Find the OFDb movie page link
    match = re.search(r'href="(film/[^"]*)"', response)
    if not match:
        logger.debug('OFDb: no movie page found for {}'.format(imdb_id))
        return None

    film_url = OFDB_BASE_URL + match.group(1)
    logger.debug('Found OFDb film page: {}'.format(film_url))

    # Fetch the film page
    film_response = api_utils.load_info(film_url, default='', resp_type='text')
    if not film_response:
        return None

    # Find the plot link
    plot_match = re.search(r'href="(plot/[^"]*)"', film_response)
    if not plot_match:
        logger.debug('OFDb: no plot link found on film page')
        return None

    plot_url = OFDB_BASE_URL + plot_match.group(1)
    logger.debug('Found OFDb plot page: {}'.format(plot_url))

    # Fetch the plot page
    plot_response = api_utils.load_info(plot_url, default='', resp_type='text')
    if not plot_response:
        return None

    # Extract the plot text - OFDb uses "Inhalt:" label
    plot_text_match = re.search(
        r'<b>Inhalt:</b>\s*<br\s*/?>\s*(.*?)(?:</p>|<br\s*/?>\s*<br)',
        plot_response, re.DOTALL)
    if plot_text_match:
        plot = plot_text_match.group(1).strip()
        # Clean HTML tags
        plot = re.sub(r'<[^>]+>', '', plot).strip()
        if plot:
            return plot

    # Fallback pattern for plot extraction
    plot_text_match = re.search(
        r'class="Inhalt"[^>]*>(.*?)</(?:div|td)',
        plot_response, re.DOTALL)
    if plot_text_match:
        plot = plot_text_match.group(1).strip()
        plot = re.sub(r'<[^>]+>', '', plot).strip()
        if plot:
            return plot

    return None

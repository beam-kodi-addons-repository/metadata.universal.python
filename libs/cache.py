# -*- coding: UTF-8 -*-
#
# Universal Movie Scraper (Python) - metadata.universal.python
# Based on metadata.universal XML scraper by Olympia
# Python structure inspired by metadata.themoviedb.org.python by Team Kodi
#
# SPDX-License-Identifier: GPL-2.0-or-later
# See LICENSE.txt for more information.

"""Cache-related functionality"""

from __future__ import absolute_import, unicode_literals

import os
import pickle
import xbmcvfs

from .utils import ADDON, logger

try:
    from typing import Optional, Text, Dict, Any
except ImportError:
    pass


def _get_cache_directory():
    # type: () -> Text
    temp_dir = xbmcvfs.translatePath('special://temp')
    cache_dir = os.path.join(temp_dir, 'scrapers', ADDON.getAddonInfo('id'))
    if not xbmcvfs.exists(cache_dir):
        xbmcvfs.mkdir(cache_dir)
    logger.debug('the cache dir is ' + cache_dir)
    return cache_dir


CACHE_DIR = _get_cache_directory()  # type: Text


def cache_movie_info(movie_info):
    # type: (Dict[Text, Any]) -> None
    """
    Save movie_info dict to cache
    """
    movie_id = movie_info.get('id') or movie_info.get('uniqueids', {}).get('tmdb', '')
    file_name = str(movie_id) + '.pickle'
    cache = {
        'movie_info': movie_info
    }
    try:
        with open(os.path.join(CACHE_DIR, file_name), 'wb') as fo:
            pickle.dump(cache, fo, protocol=2)
    except (IOError, pickle.PickleError) as exc:
        logger.debug('Cache write error: {} {}'.format(type(exc), exc))


def load_movie_info_from_cache(movie_id):
    # type: (Text) -> Optional[Dict[Text, Any]]
    """
    Load movie info from a local cache

    :param movie_id: movie ID (tmdb or imdb)
    :return: movie_info dict or None
    """
    file_name = str(movie_id) + '.pickle'
    try:
        with open(os.path.join(CACHE_DIR, file_name), 'rb') as fo:
            load_kwargs = {'encoding': 'bytes'}
            cache = pickle.load(fo, **load_kwargs)
        return cache['movie_info']
    except (IOError, pickle.PickleError) as exc:
        logger.debug('Cache message: {} {}'.format(type(exc), exc))
        return None

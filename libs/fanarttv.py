# -*- coding: UTF-8 -*-
#
# Universal Movie Scraper (Python) - metadata.universal.python
# Based on metadata.universal XML scraper by Olympia
# Python structure inspired by metadata.themoviedb.org.python by Team Kodi
#
# SPDX-License-Identifier: GPL-2.0-or-later
# See LICENSE.txt for more information.

"""Functions to interact with fanart.tv API for movie artwork"""

from __future__ import absolute_import, unicode_literals

from urllib.parse import quote
from . import api_utils, settings
from .utils import logger

try:
    from typing import Optional, Text, Dict, List, Any
except ImportError:
    pass

API_URL = 'https://webservice.fanart.tv/v3/movies/{}'

ARTMAP = {
    'movielogo': 'clearlogo',
    'hdmovielogo': 'clearlogo',
    'hdmovieclearart': 'clearart',
    'movieart': 'clearart',
    'moviedisc': 'discart',
    'moviebanner': 'banner',
    'moviethumb': 'landscape',
    'moviebackground': 'fanart',
    'movieposter': 'poster',
}

SET_ARTMAP = {
    'movielogo': 'set.clearlogo',
    'hdmovielogo': 'set.clearlogo',
    'hdmovieclearart': 'set.clearart',
    'movieart': 'set.clearart',
    'moviedisc': 'set.discart',
    'moviebanner': 'set.banner',
    'moviethumb': 'set.landscape',
    'moviebackground': 'set.fanart',
    'movieposter': 'set.poster',
}

HEADERS = (
    ('User-Agent', 'Kodi Universal Movie scraper by Team Kodi'),
    ('api-key', settings.FANARTTV_CLOWNCAR),
)


def get_movie_artwork(media_id, source_settings):
    # type: (Text, Dict) -> Dict
    """
    Get movie artwork from fanart.tv

    :param media_id: TMDb or IMDb ID
    :param source_settings: addon settings dict
    :return: dict with available_art
    """
    if not media_id:
        return {}

    language = source_settings.get('FANARTTV_POSTER_LANG', 'en')
    clientkey = source_settings.get('FANARTTV_CLIENTKEY', '')

    logger.debug('Getting fanart.tv movie artwork for {}'.format(media_id))
    data = _get_data(media_id, clientkey)
    if not data:
        return {}

    art = _parse_data(data, language, ARTMAP, source_settings)
    return {'available_art': art}


def get_set_artwork(collection_tmdb_id, source_settings):
    # type: (Text, Dict) -> Dict
    """
    Get collection/set artwork from fanart.tv

    :param collection_tmdb_id: TMDb collection ID
    :param source_settings: addon settings dict
    :return: dict with available_art for set
    """
    if not collection_tmdb_id:
        return {}

    language = source_settings.get('FANARTTV_POSTER_LANG', 'en')
    clientkey = source_settings.get('FANARTTV_CLIENTKEY', '')

    logger.debug('Getting fanart.tv set artwork for collection {}'.format(collection_tmdb_id))
    data = _get_data(collection_tmdb_id, clientkey)
    if not data:
        return {}

    art = _parse_data(data, language, SET_ARTMAP, source_settings, is_set=True)
    return {'available_art': art}


def _get_data(media_id, clientkey=''):
    # type: (Text, Text) -> Dict
    """Fetch data from fanart.tv API"""
    headers = dict(HEADERS)
    if clientkey:
        headers['client-key'] = clientkey
    api_utils.set_headers(headers)
    fanarttv_url = API_URL.format(media_id)
    result = api_utils.load_info(fanarttv_url, default={})
    api_utils.set_headers({})
    return result


def _parse_data(data, language, artmap, source_settings, is_set=False):
    # type: (Dict, Text, Dict, Dict, bool) -> Dict
    """
    Parse fanart.tv response data into artwork dict

    :param data: raw fanart.tv API response
    :param language: preferred language
    :param artmap: mapping of fanart.tv types to Kodi types
    :param source_settings: settings dict to check enabled art types
    :param is_set: whether this is set/collection artwork
    :return: artwork dict
    """
    result = {}
    language_fallback = 'en'

    for arttype, artlist in data.items():
        if arttype not in artmap:
            continue
        if not isinstance(artlist, list):
            continue

        generaltype = artmap[arttype]

        # Check if this art type is enabled in settings
        if not _is_art_type_enabled(generaltype, source_settings, is_set):
            continue

        for image in artlist:
            image_lang = _get_image_language(arttype, image)
            if image_lang and image_lang != language and image_lang != language_fallback:
                continue

            if generaltype not in result:
                result[generaltype] = []

            url = quote(image.get('url', ''), safe="%/:=&?~#+!$,;'@()*[]")
            preview = url.replace('.fanart.tv/fanart/', '.fanart.tv/preview/')
            result[generaltype].append({
                'url': url,
                'preview': preview,
                'lang': image_lang or ''
            })

    return result


def _is_art_type_enabled(generaltype, source_settings, is_set):
    # type: (Text, Dict, bool) -> bool
    """Check if a specific art type is enabled in settings"""
    if is_set:
        mapping = {
            'set.poster': 'FANARTTV_SET_POSTER',
            'set.fanart': 'FANARTTV_SET_FANART',
            'set.clearlogo': 'FANARTTV_SET_CLEARLOGO',
            'set.clearart': 'FANARTTV_SET_CLEARART',
            'set.banner': 'FANARTTV_SET_BANNER',
            'set.landscape': 'FANARTTV_SET_LANDSCAPE',
            'set.discart': 'FANARTTV_SET_DISCART',
        }
    else:
        mapping = {
            'poster': 'FANARTTV_POSTER',
            'fanart': 'FANARTTV_FANART',
            'clearlogo': 'FANARTTV_CLEARLOGO',
            'clearart': 'FANARTTV_CLEARART',
            'banner': 'FANARTTV_BANNER',
            'landscape': 'FANARTTV_LANDSCAPE',
            'discart': 'FANARTTV_DISCART',
        }
    setting_key = mapping.get(generaltype)
    if setting_key:
        return source_settings.get(setting_key, True)
    return True


def _get_image_language(arttype, image):
    # type: (Text, Dict) -> Optional[Text]
    """Get image language, handling fanart.tv's conventions"""
    if 'lang' not in image or arttype == 'moviebackground':
        return None
    if arttype in ('movielogo', 'hdmovielogo', 'hdmovieclearart', 'movieart',
                   'moviebanner', 'moviethumb', 'moviedisc'):
        return image['lang'] if image['lang'] not in ('', '00') else 'en'
    # movieposter may or may not have a title
    return image['lang'] if image['lang'] not in ('', '00') else None

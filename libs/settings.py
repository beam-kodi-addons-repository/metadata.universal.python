# -*- coding: UTF-8 -*-
#
# Universal Movie Scraper (Python) - metadata.universal.python
# Based on metadata.universal XML scraper by Olympia
# Python structure inspired by metadata.themoviedb.org.python by Team Kodi
#
# SPDX-License-Identifier: GPL-2.0-or-later
# See LICENSE.txt for more information.

"""Settings management for Universal Movie Scraper"""

from __future__ import absolute_import, unicode_literals

import json
import sys
import urllib.parse
from datetime import datetime, timedelta
from .utils import logger
from . import api_utils
from xbmcaddon import Addon

# API Keys
TMDB_CLOWNCAR = 'f090bb54758cabf231fb605d3e3e0468'
FANARTTV_CLOWNCAR = '384afe262ee0962545a752ff340e3ce4'
TRAKT_CLOWNCAR = '5f2dc73b6b11c2ac212f5d8b4ec8f3dc4b727bb3f026cd254d89eda997fe64ae'

MAXIMAGES = 200

TMDB_HEADERS = (
    ('User-Agent', 'Kodi Universal Movie scraper by Team Kodi'),
    ('Accept', 'application/json'),
)

FANARTTV_MAPPING = {
    'movieposter': 'poster',
    'moviebackground': 'fanart',
    'movielogo': 'clearlogo',
    'hdmovielogo': 'clearlogo',
    'hdmovieclearart': 'clearart',
    'movieart': 'clearart',
    'moviedisc': 'discart',
    'moviebanner': 'banner',
    'moviethumb': 'landscape',
}

FANARTTV_SET_MAPPING = {
    'movieposter': 'set.poster',
    'moviebackground': 'set.fanart',
    'movielogo': 'set.clearlogo',
    'hdmovielogo': 'set.clearlogo',
    'hdmovieclearart': 'set.clearart',
    'movieart': 'set.clearart',
    'moviedisc': 'set.discart',
    'moviebanner': 'set.banner',
    'moviethumb': 'set.landscape',
}


def _get_date_numeric(datetime_):
    return (datetime_ - datetime(1970, 1, 1)).total_seconds()


def _get_configuration():
    addon = Addon()
    logger.debug('getting TMDb configuration details')
    api_utils.set_headers(dict(TMDB_HEADERS))
    result = api_utils.load_info(
        'https://api.themoviedb.org/3/configuration',
        params={'api_key': TMDB_CLOWNCAR}
    )
    api_utils.set_headers({})
    return result


def load_base_urls():
    """Load and cache TMDb image base URLs"""
    addon = Addon()
    image_root_url = addon.getSettingString('originalUrl')
    preview_root_url = addon.getSettingString('previewUrl')
    last_updated = addon.getSettingString('lastUpdated')
    if not image_root_url or not preview_root_url or not last_updated or \
            float(last_updated) < _get_date_numeric(datetime.now() - timedelta(days=30)):
        conf = _get_configuration()
        if conf and not conf.get('error'):
            image_root_url = conf['images']['secure_base_url'] + 'original'
            preview_root_url = conf['images']['secure_base_url'] + 'w780'
            addon.setSetting('originalUrl', image_root_url)
            addon.setSetting('previewUrl', preview_root_url)
            addon.setSetting('lastUpdated', str(
                _get_date_numeric(datetime.now())))
    return image_root_url, preview_root_url


def get_settings():
    """Get all addon settings, supporting both path-specific and global settings"""
    addon = Addon()
    settings = {}
    logger.debug('Getting settings')
    try:
        source_params = dict(urllib.parse.parse_qsl(sys.argv[2] if len(sys.argv) > 2 else ''))
    except (IndexError, ValueError):
        source_params = {}
    source_settings = json.loads(source_params.get('pathSettings', '{}'))

    # Search settings
    settings['SEARCH_SERVICE'] = source_settings.get(
        'searchservice', addon.getSettingString('searchservice')) or 'themoviedb.org'
    settings['SEARCH_LANGUAGE'] = source_settings.get(
        'tmdbsearchlanguage', addon.getSettingString('tmdbsearchlanguage')) or 'en-US'
    settings['IMDB_SEARCH_LANGUAGE'] = source_settings.get(
        'imdbsearchlanguage', addon.getSettingString('imdbsearchlanguage')) or 'None'
    settings['FULL_IMDB_SEARCH'] = source_settings.get(
        'fullimdbsearch', _get_bool_setting(addon, 'fullimdbsearch', False))

    # Title settings
    settings['TITLE_SOURCE'] = source_settings.get(
        'titlesource', addon.getSettingString('titlesource')) or 'themoviedb.org'
    settings['TITLE_LANGUAGE'] = source_settings.get(
        'tmdbtitlelanguage', addon.getSettingString('tmdbtitlelanguage')) or 'en-US'

    # Genre settings
    settings['GENRES_SOURCE'] = source_settings.get(
        'genressource', addon.getSettingString('genressource')) or 'themoviedb.org'
    settings['GENRES_LANGUAGE'] = source_settings.get(
        'tmdbgenreslanguage', addon.getSettingString('tmdbgenreslanguage')) or 'en-US'

    # Plot settings
    settings['PLOT_SOURCE'] = source_settings.get(
        'plotsource', addon.getSettingString('plotsource')) or 'themoviedb.org'
    settings['PLOT_LANGUAGE'] = source_settings.get(
        'tmdbplotlanguage', addon.getSettingString('tmdbplotlanguage')) or 'en-US'

    # Tagline settings
    settings['TAGLINE_SOURCE'] = source_settings.get(
        'taglinesource', addon.getSettingString('taglinesource')) or 'themoviedb.org'
    settings['TAGLINE_LANGUAGE'] = source_settings.get(
        'tmdbtaglinelanguage', addon.getSettingString('tmdbtaglinelanguage')) or 'en-US'

    # Outline settings
    settings['OUTLINE_SOURCE'] = source_settings.get(
        'outlinesource', addon.getSettingString('outlinesource')) or 'IMDb'
    settings['OMDB_API_KEY'] = source_settings.get(
        'omdbapikey', addon.getSettingString('omdbapikey')) or ''

    # Credits settings
    settings['CREDITS_SOURCE'] = source_settings.get(
        'creditssource', addon.getSettingString('creditssource')) or 'themoviedb.org'

    # Studio settings
    settings['STUDIO_SOURCE'] = source_settings.get(
        'studiosource', addon.getSettingString('studiosource')) or 'themoviedb.org'

    # Country settings
    settings['COUNTRY_SOURCE'] = source_settings.get(
        'countrysource', addon.getSettingString('countrysource')) or 'themoviedb.org'

    # Set/Collection settings
    settings['TMDB_SET'] = source_settings.get(
        'tmdbset', _get_bool_setting(addon, 'tmdbset', True))
    settings['SET_LANGUAGE'] = source_settings.get(
        'tmdbsetlanguage', addon.getSettingString('tmdbsetlanguage')) or 'en-US'

    # Tags/Keywords settings
    settings['TMDB_TAGS'] = source_settings.get(
        'tmdbtags', addon.getSettingString('tmdbtags')) or 'None'

    # Rating settings
    settings['RATING_SOURCE'] = source_settings.get(
        'mratingsource', addon.getSettingString('mratingsource')) or 'IMDb'
    settings['ALSO_ROTTEN'] = source_settings.get(
        'alsorotten', _get_bool_setting(addon, 'alsorotten', False))
    settings['TOMATO_TYPE'] = source_settings.get(
        'tomato', addon.getSettingString('tomato')) or 'TomatoMeter All Critics'
    settings['OMDB_API_KEY2'] = source_settings.get(
        'omdbapikey2', addon.getSettingString('omdbapikey2')) or ''
    settings['ALSO_OTHER_ROTTEN'] = source_settings.get(
        'alsootherrotten', _get_bool_setting(addon, 'alsootherrotten', False))
    settings['ALSO_IMDB'] = source_settings.get(
        'alsoimdb', _get_bool_setting(addon, 'alsoimdb', False))
    settings['ALSO_META'] = source_settings.get(
        'alsometa', _get_bool_setting(addon, 'alsometa', False))
    settings['ALSO_TMDB'] = source_settings.get(
        'alsotmdb', _get_bool_setting(addon, 'alsotmdb', False))
    settings['IMDB_TOP250'] = source_settings.get(
        'imdbtop250', _get_bool_setting(addon, 'imdbtop250', True))

    # Certification settings
    settings['CERT_SOURCE'] = source_settings.get(
        'certificationssource', addon.getSettingString('certificationssource')) or 'themoviedb.org'
    settings['IMDB_CERT_COUNTRY'] = source_settings.get(
        'imdbcertcountry', addon.getSettingString('imdbcertcountry')) or 'United States'
    settings['TMDB_CERT_COUNTRY'] = source_settings.get(
        'tmdbcertcountry', addon.getSettingString('tmdbcertcountry')) or 'us'
    settings['CERT_PREFIX'] = source_settings.get(
        'certprefix', addon.getSettingString('certprefix')) or 'Rated '

    # Trailer settings
    settings['TMDB_TRAILER'] = source_settings.get(
        'tmdbtrailer', _get_bool_setting(addon, 'tmdbtrailer', True))
    settings['TRAILER_LANGUAGE'] = source_settings.get(
        'tmdbtrailerlanguage', addon.getSettingString('tmdbtrailerlanguage')) or 'en-US'

    # Poster/Artwork settings - fanart.tv
    settings['FANARTTV_POSTER'] = source_settings.get(
        'fanarttvposter', _get_bool_setting(addon, 'fanarttvposter', True))
    settings['FANARTTV_POSTER_LANG'] = source_settings.get(
        'fanarttvposterlanguage', addon.getSettingString('fanarttvposterlanguage')) or 'en'
    settings['FANARTTV_FANART'] = source_settings.get(
        'fanarttvfanart', _get_bool_setting(addon, 'fanarttvfanart', True))
    settings['FANARTTV_CLEARLOGO'] = source_settings.get(
        'fanarttvclearlogo', _get_bool_setting(addon, 'fanarttvclearlogo', True))
    settings['FANARTTV_CLEARART'] = source_settings.get(
        'fanarttvclearart', _get_bool_setting(addon, 'fanarttvclearart', True))
    settings['FANARTTV_BANNER'] = source_settings.get(
        'fanarttvmoviebanner', _get_bool_setting(addon, 'fanarttvmoviebanner', True))
    settings['FANARTTV_LANDSCAPE'] = source_settings.get(
        'fanarttvmovielandscape', _get_bool_setting(addon, 'fanarttvmovielandscape', True))
    settings['FANARTTV_DISCART'] = source_settings.get(
        'fanarttvmoviediscart', _get_bool_setting(addon, 'fanarttvmoviediscart', True))
    settings['FANARTTV_CLIENTKEY'] = source_settings.get(
        'fanarttv_clientkey', addon.getSettingString('fanarttv_clientkey')) or ''

    # Poster/Artwork settings - TMDb
    settings['TMDB_POSTERS'] = source_settings.get(
        'tmdbthumbs', _get_bool_setting(addon, 'tmdbthumbs', True))
    settings['TMDB_POSTER_LANG'] = source_settings.get(
        'tmdbthumblanguage', addon.getSettingString('tmdbthumblanguage')) or 'en'
    settings['TMDB_FANART'] = source_settings.get(
        'fanart', _get_bool_setting(addon, 'fanart', True))
    settings['TMDB_LANDSCAPE'] = source_settings.get(
        'tmdbmovielandscape', _get_bool_setting(addon, 'tmdbmovielandscape', True))

    # Collection artwork - fanart.tv
    settings['FANARTTV_SET_POSTER'] = source_settings.get(
        'fanarttvsetposter', _get_bool_setting(addon, 'fanarttvsetposter', True))
    settings['FANARTTV_SET_FANART'] = source_settings.get(
        'fanarttvsetfanart', _get_bool_setting(addon, 'fanarttvsetfanart', True))
    settings['FANARTTV_SET_CLEARLOGO'] = source_settings.get(
        'fanarttvsetclearlogo', _get_bool_setting(addon, 'fanarttvsetclearlogo', True))
    settings['FANARTTV_SET_CLEARART'] = source_settings.get(
        'fanarttvsetclearart', _get_bool_setting(addon, 'fanarttvsetclearart', True))
    settings['FANARTTV_SET_BANNER'] = source_settings.get(
        'fanarttvsetmoviebanner', _get_bool_setting(addon, 'fanarttvsetmoviebanner', True))
    settings['FANARTTV_SET_LANDSCAPE'] = source_settings.get(
        'fanarttvsetmovielandscape', _get_bool_setting(addon, 'fanarttvsetmovielandscape', True))
    settings['FANARTTV_SET_DISCART'] = source_settings.get(
        'fanarttvsetmoviediscart', _get_bool_setting(addon, 'fanarttvsetmoviediscart', True))

    logger.debug('Settings loaded: {}'.format(settings))
    return settings


def _get_bool_setting(addon, setting_id, default=False):
    """Safely get a bool setting"""
    try:
        return addon.getSettingBool(setting_id)
    except Exception:
        return default

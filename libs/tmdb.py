# -*- coding: UTF-8 -*-
#
# Universal Movie Scraper (Python) - metadata.universal.python
# Based on metadata.universal XML scraper by Olympia
# Python structure inspired by metadata.themoviedb.org.python by Team Kodi
#
# SPDX-License-Identifier: GPL-2.0-or-later
# See LICENSE.txt for more information.

"""Functions to interact with TMDb API for movies"""

from __future__ import absolute_import, unicode_literals

import unicodedata
from . import api_utils, settings
from .utils import logger, safe_get

try:
    from typing import Text, Optional, Union, List, Dict, Any
    InfoType = Dict[Text, Any]
except ImportError:
    pass

HEADERS = (
    ('User-Agent', 'Kodi Universal Movie scraper by Team Kodi'),
    ('Accept', 'application/json'),
)

TMDB_PARAMS = {'api_key': settings.TMDB_CLOWNCAR}
BASE_URL = 'https://api.themoviedb.org/3/{}'
SEARCH_URL = BASE_URL.format('search/movie')
FIND_URL = BASE_URL.format('find/{}')
MOVIE_URL = BASE_URL.format('movie/{}')
COLLECTION_URL = BASE_URL.format('collection/{}')
CONFIG_URL = BASE_URL.format('configuration')


def _set_params(language=None, append_to_response=None):
    """Build params dict with API key and optional language/append"""
    params = TMDB_PARAMS.copy()
    if language:
        params['language'] = language
    if append_to_response:
        params['append_to_response'] = append_to_response
    return params


def search_movie(title, year=None):
    # type: (Text, Optional[Text]) -> List[InfoType]
    """
    Search for a movie by title and optional year

    :param title: movie title to search
    :param year: optional release year
    :return: list of search results
    """
    source_settings = settings.get_settings()
    api_utils.set_headers(dict(HEADERS))

    # Check if title is actually a direct ID
    search_media_id = _parse_media_id(title)
    if search_media_id:
        logger.debug('using {} of {} to find movie'.format(
            search_media_id['type'], search_media_id['id']))
        if search_media_id['type'] == 'tmdb':
            result = get_movie_details(search_media_id['id'],
                                       source_settings['SEARCH_LANGUAGE'])
            if result and not result.get('error'):
                return [result]
            return []
        else:
            result = find_movie_by_external_id(
                search_media_id['id'], source_settings['SEARCH_LANGUAGE'])
            if result and not result.get('error'):
                return result.get('movie_results', [])
            return []

    # Normal title search
    params = _set_params(language=source_settings['SEARCH_LANGUAGE'])
    params['query'] = unicodedata.normalize('NFKC', title)
    if year:
        params['year'] = str(year)

    resp = api_utils.load_info(SEARCH_URL, params=params)

    api_utils.set_headers({})
    if resp and not resp.get('error'):
        results = resp.get('results', [])
        # Try without year if no results found
        if not results and year:
            params_no_year = _set_params(language=source_settings['SEARCH_LANGUAGE'])
            params_no_year['query'] = unicodedata.normalize('NFKC', title)
            resp2 = api_utils.load_info(SEARCH_URL, params=params_no_year)
            if resp2 and not resp2.get('error'):
                results = resp2.get('results', [])
        return results
    return []


def find_movie_by_external_id(external_id, language=None):
    # type: (Text, Optional[Text]) -> InfoType
    """
    Find a movie by external ID (e.g. IMDb)

    :param external_id: external ID string
    :param language: language filter
    :return: find results
    """
    theurl = FIND_URL.format(external_id)
    params = _set_params(language=language)
    params['external_source'] = 'imdb_id'
    api_utils.set_headers(dict(HEADERS))
    result = api_utils.load_info(theurl, params=params)
    api_utils.set_headers({})
    return result


def get_movie_details(movie_id, language=None, append=None):
    # type: (Text, Optional[Text], Optional[Text]) -> InfoType
    """
    Get full movie details from TMDb

    :param movie_id: TMDb movie ID
    :param language: language filter
    :param append: append_to_response value
    :return: movie details dict
    """
    if append is None:
        append = 'trailers,images,releases,casts,keywords'
    theurl = MOVIE_URL.format(movie_id)
    api_utils.set_headers(dict(HEADERS))
    result = api_utils.load_info(
        theurl, params=_set_params(language=language, append_to_response=append))
    api_utils.set_headers({})
    return result


def get_movie_details_fallback(movie_id):
    # type: (Text) -> InfoType
    """
    Get movie details without language filter (for fallback English data + images)

    :param movie_id: TMDb movie ID
    :return: movie details dict
    """
    theurl = MOVIE_URL.format(movie_id)
    api_utils.set_headers(dict(HEADERS))
    result = api_utils.load_info(
        theurl, params=_set_params(append_to_response='trailers,images'))
    api_utils.set_headers({})
    return result


def get_collection_details(collection_id, language=None):
    # type: (Text, Optional[Text]) -> InfoType
    """
    Get collection/set details

    :param collection_id: TMDb collection ID
    :param language: language filter
    :return: collection details dict
    """
    if not collection_id:
        return None
    theurl = COLLECTION_URL.format(collection_id)
    api_utils.set_headers(dict(HEADERS))
    result = api_utils.load_info(
        theurl, params=_set_params(language=language, append_to_response='images'))
    api_utils.set_headers({})
    return result


def get_tmdb_id_from_imdb(imdb_id):
    # type: (Text) -> Optional[Text]
    """
    Resolve IMDb ID to TMDb ID

    :param imdb_id: IMDb ID (e.g. tt1234567)
    :return: TMDb ID string or None
    """
    result = find_movie_by_external_id(imdb_id)
    if result and not result.get('error'):
        movies = result.get('movie_results', [])
        if movies:
            return str(movies[0]['id'])
    return None


def load_movie_info(movie_id):
    # type: (Text) -> Optional[InfoType]
    """
    Load complete movie info - main entry point for detail gathering

    :param movie_id: TMDb or IMDb movie ID
    :return: assembled movie details or None
    """
    source_settings = settings.get_settings()

    # Resolve IMDb ID to TMDb ID if needed
    tmdb_id = movie_id
    if str(movie_id).startswith('tt'):
        tmdb_id = get_tmdb_id_from_imdb(movie_id)
        if not tmdb_id:
            logger.error('Could not find TMDb ID for IMDb ID: {}'.format(movie_id))
            return None

    # Get movie details with configured language
    movie = get_movie_details(tmdb_id, source_settings['SEARCH_LANGUAGE'])
    if not movie or movie.get('error'):
        logger.error('Failed to get movie details for ID: {}'.format(tmdb_id))
        return None

    # Get fallback details (no language - English + images)
    movie_fallback = get_movie_details_fallback(tmdb_id)
    if movie_fallback and not movie_fallback.get('error'):
        # Use fallback images (they include all languages)
        movie['images'] = movie_fallback.get('images', {})
    else:
        movie_fallback = {}

    # Get collection/set details if present
    collection = None
    collection_fallback = None
    if movie.get('belongs_to_collection'):
        collection_id = movie['belongs_to_collection'].get('id')
        if collection_id and source_settings['TMDB_SET']:
            collection = get_collection_details(
                collection_id, source_settings['SET_LANGUAGE'])
            collection_fallback = get_collection_details(collection_id)
            if collection and collection_fallback and not collection_fallback.get('error'):
                if 'images' in collection_fallback:
                    collection['images'] = collection_fallback['images']

    # Get details in specific language for title if needed
    title_data = None
    if source_settings['TITLE_SOURCE'] == 'themoviedb.org' and \
       source_settings['TITLE_LANGUAGE'] != source_settings['SEARCH_LANGUAGE']:
        title_data = get_movie_details(tmdb_id, source_settings['TITLE_LANGUAGE'],
                                       append='')

    # Get details in specific language for genres if needed
    genres_data = None
    if source_settings['GENRES_SOURCE'] == 'themoviedb.org' and \
       source_settings['GENRES_LANGUAGE'] != source_settings['SEARCH_LANGUAGE']:
        genres_data = get_movie_details(tmdb_id, source_settings['GENRES_LANGUAGE'],
                                        append='')

    # Get details in specific language for plot if needed
    plot_data = None
    if source_settings['PLOT_SOURCE'] == 'themoviedb.org' and \
       source_settings['PLOT_LANGUAGE'] != source_settings['SEARCH_LANGUAGE']:
        plot_data = get_movie_details(tmdb_id, source_settings['PLOT_LANGUAGE'],
                                      append='')

    # Get details in specific language for tagline if needed
    tagline_data = None
    if source_settings['TAGLINE_SOURCE'] == 'themoviedb.org' and \
       source_settings['TAGLINE_LANGUAGE'] != source_settings['SEARCH_LANGUAGE']:
        tagline_data = get_movie_details(tmdb_id, source_settings['TAGLINE_LANGUAGE'],
                                         append='')

    # Get trailer in specific language if needed
    trailer_data = None
    if source_settings['TMDB_TRAILER'] and \
       source_settings['TRAILER_LANGUAGE'] != source_settings['SEARCH_LANGUAGE']:
        trailer_data = get_movie_details(tmdb_id, source_settings['TRAILER_LANGUAGE'],
                                         append='trailers')

    return {
        'movie': movie,
        'movie_fallback': movie_fallback,
        'collection': collection,
        'collection_fallback': collection_fallback,
        'title_data': title_data,
        'genres_data': genres_data,
        'plot_data': plot_data,
        'tagline_data': tagline_data,
        'trailer_data': trailer_data,
        'settings': source_settings,
    }


def _parse_media_id(title):
    # type: (Text) -> Optional[Dict]
    """
    Parse a direct media ID from the search title

    :param title: title that might contain an ID
    :return: dict with type and id, or None
    """
    if not isinstance(title, str):
        title = str(title)
    if title.startswith('tt') and title[2:].isdigit():
        return {'type': 'imdb', 'id': title}
    title_lower = title.lower()
    if title_lower.startswith('tmdb/') and title_lower[5:].isdigit():
        return {'type': 'tmdb', 'id': title[5:]}
    if title_lower.startswith('imdb/tt') and title_lower[7:].isdigit():
        return {'type': 'imdb', 'id': title[5:]}
    return None

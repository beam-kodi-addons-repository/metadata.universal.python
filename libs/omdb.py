# -*- coding: UTF-8 -*-
#
# Universal Movie Scraper (Python) - metadata.universal.python
# Based on metadata.universal XML scraper by Olympia
# Python structure inspired by metadata.themoviedb.org.python by Team Kodi
#
# SPDX-License-Identifier: GPL-2.0-or-later
# See LICENSE.txt for more information.

"""Functions to interact with OMDB API for Rotten Tomatoes and MetaCritic data"""

from __future__ import absolute_import, unicode_literals

from . import api_utils
from .utils import logger

try:
    from typing import Optional, Text, Dict, Any
except ImportError:
    pass

OMDB_URL = 'https://www.omdbapi.com/'


def get_omdb_data(imdb_id, api_key):
    # type: (Text, Text) -> Dict
    """
    Fetch movie data from OMDB API

    :param imdb_id: IMDb ID (e.g. tt1234567)
    :param api_key: OMDB API key
    :return: dict with OMDB data
    """
    if not imdb_id or not api_key:
        return {}
    logger.debug('Getting OMDB data for {}'.format(imdb_id))
    params = {
        'i': imdb_id,
        'apikey': api_key,
        'tomatoes': 'true',
        'r': 'json'
    }
    result = api_utils.load_info(OMDB_URL, params=params)
    if not result or isinstance(result, str):
        return {}
    if result.get('Response') == 'False':
        logger.debug('OMDB error: {}'.format(result.get('Error', 'Unknown')))
        return {}
    return result


def get_rt_rating(omdb_data, tomato_type='TomatoMeter All Critics'):
    # type: (Dict, Text) -> Optional[Dict]
    """
    Extract Rotten Tomatoes rating based on type setting

    :param omdb_data: OMDB API response
    :param tomato_type: one of 'TomatoMeter All Critics', 'TomatoMeter Audience Score',
                        'Average Rating All Critics', 'Average Rating Audience Score'
    :return: dict with rating and votes or None
    """
    if not omdb_data:
        return None

    if tomato_type == 'TomatoMeter All Critics':
        meter = omdb_data.get('tomatoMeter')
        if not meter or meter == 'N/A':
            # Fallback to Ratings array
            for r in omdb_data.get('Ratings', []):
                if r.get('Source') == 'Rotten Tomatoes':
                    meter = r['Value'].rstrip('%')
                    break
        if meter and meter != 'N/A':
            try:
                return {
                    'rating': float(meter),
                    'votes': _safe_int(omdb_data.get('tomatoReviews', '0'))
                }
            except (ValueError, TypeError):
                pass

    elif tomato_type == 'TomatoMeter Audience Score':
        meter = omdb_data.get('tomatoUserMeter')
        if meter and meter != 'N/A':
            try:
                return {
                    'rating': float(meter),
                    'votes': _safe_int(omdb_data.get('tomatoUserReviews', '0'))
                }
            except (ValueError, TypeError):
                pass

    elif tomato_type == 'Average Rating All Critics':
        rating = omdb_data.get('tomatoRating')
        if rating and rating != 'N/A':
            try:
                return {
                    'rating': float(rating),
                    'votes': _safe_int(omdb_data.get('tomatoReviews', '0'))
                }
            except (ValueError, TypeError):
                pass

    elif tomato_type == 'Average Rating Audience Score':
        rating = omdb_data.get('tomatoUserRating')
        if rating and rating != 'N/A':
            try:
                return {
                    'rating': float(rating),
                    'votes': _safe_int(omdb_data.get('tomatoUserReviews', '0'))
                }
            except (ValueError, TypeError):
                pass

    # Final fallback: try Ratings array for any RT data
    for r in omdb_data.get('Ratings', []):
        if r.get('Source') == 'Rotten Tomatoes':
            value = r['Value'].rstrip('%')
            try:
                return {'rating': float(value), 'votes': 0}
            except (ValueError, TypeError):
                pass
    return None


def get_metacritic_rating(omdb_data):
    # type: (Dict) -> Optional[Dict]
    """
    Extract MetaCritic rating from OMDB data

    :param omdb_data: OMDB API response
    :return: dict with rating and votes or None
    """
    if not omdb_data:
        return None

    metascore = omdb_data.get('Metascore')
    if metascore and metascore != 'N/A':
        try:
            return {'rating': float(metascore), 'votes': 0}
        except (ValueError, TypeError):
            pass

    for r in omdb_data.get('Ratings', []):
        if r.get('Source') == 'Metacritic':
            value = r['Value'].split('/')[0]
            try:
                return {'rating': float(value), 'votes': 0}
            except (ValueError, TypeError):
                pass
    return None


def get_rt_consensus(omdb_data):
    # type: (Dict) -> Optional[Text]
    """
    Get Rotten Tomatoes Critics' Consensus

    :param omdb_data: OMDB API response
    :return: consensus text or None
    """
    if not omdb_data:
        return None
    consensus = omdb_data.get('tomatoConsensus')
    if consensus and consensus != 'N/A':
        return consensus
    return None


def _safe_int(value):
    # type: (Any) -> int
    """Safely convert string to int, stripping commas"""
    try:
        return int(str(value).replace(',', ''))
    except (ValueError, TypeError):
        return 0

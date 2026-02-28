# -*- coding: UTF-8 -*-
#
# Universal Movie Scraper (Python) - metadata.universal.python
# Based on metadata.universal XML scraper by Olympia
# Python structure inspired by metadata.themoviedb.org.python by Team Kodi
#
# SPDX-License-Identifier: GPL-2.0-or-later
# See LICENSE.txt for more information.

"""Plugin route actions for Universal Movie Scraper"""

from __future__ import absolute_import, unicode_literals

import json
import sys
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin

from . import tmdb, imdb, data_utils, settings
from .utils import logger, safe_get

try:
    from typing import Optional, Text, Union, Dict, List
except ImportError:
    pass


def _get_params(argv):
    # type: (List) -> Dict
    """Parse addon call parameters from argv"""
    result = {'handle': int(argv[0])}
    if len(argv) < 2 or not argv[1]:
        return result
    result.update(urllib.parse.parse_qsl(argv[1].lstrip('?')))
    return result


def _strip_trailing_article(title):
    # type: (Text) -> Text
    """Strip trailing articles from title for better matching"""
    articles = [prefix + article
                for prefix in (', ', ' ')
                for article in ('the', 'a', 'an')]
    title_lower = title.lower()
    for article in articles:
        if title_lower.endswith(article):
            return title[:len(title) - len(article)]
    return title


def search_for_movie(title, year, handle, source_settings):
    # type: (Text, Optional[Text], int, Dict) -> None
    """
    Search for a movie by title and year

    :param title: movie title to search
    :param year: optional year
    :param handle: plugin handle
    :param source_settings: settings dict
    """
    logger.info("Find movie with title '{}' from year '{}'".format(title, year))
    title = _strip_trailing_article(title)

    search_service = source_settings.get('SEARCH_SERVICE', 'themoviedb.org')

    if search_service == 'IMDb':
        _search_imdb(title, year, handle, source_settings)
    else:
        _search_tmdb(title, year, handle)


def _search_tmdb(title, year, handle):
    # type: (Text, Optional[Text], int) -> None
    """Search for a movie using TMDb"""
    search_results = tmdb.search_movie(title, year)

    # If year was provided and no results, try adjacent years and without year
    if year and not search_results:
        search_results = tmdb.search_movie(title, str(int(year) - 1))
    if year and not search_results:
        search_results = tmdb.search_movie(title, str(int(year) + 1))
    if year and not search_results:
        search_results = tmdb.search_movie(title)

    if not search_results:
        return

    if isinstance(search_results, dict) and 'error' in search_results:
        header = "Universal Movie Scraper error searching with TMDb"
        xbmcgui.Dialog().notification(
            header, search_results['error'],
            xbmcgui.NOTIFICATION_WARNING)
        logger.error(header + ': ' + search_results['error'])
        return

    image_root_url, preview_root_url = settings.load_base_urls()

    for movie in search_results:
        movie_label = movie.get('title', '')
        movie_year = ''
        if movie.get('release_date'):
            movie_year = movie['release_date'].split('-')[0]
            movie_label += ' ({})'.format(movie_year)

        listitem = xbmcgui.ListItem(movie_label, offscreen=True)

        infotag = listitem.getVideoInfoTag()
        infotag.setTitle(movie.get('title', ''))
        if movie_year:
            try:
                infotag.setYear(int(movie_year))
            except (ValueError, TypeError):
                pass

        # Set poster thumbnail
        if movie.get('poster_path') and preview_root_url:
            listitem.setArt({'thumb': preview_root_url + movie['poster_path']})

        uniqueids = {'tmdb': str(movie['id'])}
        if movie.get('imdb_id'):
            uniqueids['imdb'] = movie['imdb_id']

        xbmcplugin.addDirectoryItem(
            handle=handle,
            url=json.dumps(uniqueids),
            listitem=listitem,
            isFolder=True
        )


def _search_imdb(title, year, handle, source_settings):
    # type: (Text, Optional[Text], int, Dict) -> None
    """Search for a movie using IMDb"""
    language = source_settings.get('IMDB_SEARCH_LANGUAGE', '')
    full_search = source_settings.get('FULL_IMDB_SEARCH', False)

    search_results = imdb.search_imdb(title, year, language, full_search)

    if not search_results:
        return

    for result in search_results:
        movie_label = result.get('title', '')
        movie_year = result.get('year', '')
        if movie_year:
            movie_label += ' ({})'.format(movie_year)

        listitem = xbmcgui.ListItem(movie_label, offscreen=True)

        infotag = listitem.getVideoInfoTag()
        infotag.setTitle(result.get('title', ''))
        if movie_year:
            try:
                infotag.setYear(int(movie_year))
            except (ValueError, TypeError):
                pass

        uniqueids = {}
        imdb_id = result.get('imdb_id', '')
        if imdb_id:
            uniqueids['imdb'] = imdb_id

        xbmcplugin.addDirectoryItem(
            handle=handle,
            url=json.dumps(uniqueids),
            listitem=listitem,
            isFolder=True
        )


def find_uniqueids_in_nfo(nfo, handle):
    # type: (Text, int) -> None
    """
    Find movie IDs in NFO file content

    :param nfo: NFO file contents
    :param handle: plugin handle
    """
    if isinstance(nfo, bytes):
        nfo = nfo.decode('utf-8', 'replace')
    logger.debug('Parsing NFO file:\n{}'.format(nfo))

    uniqueids = data_utils.find_uniqueids_in_text(nfo)
    if uniqueids:
        listitem = xbmcgui.ListItem(offscreen=True)
        xbmcplugin.addDirectoryItem(
            handle=handle,
            url=json.dumps(uniqueids),
            listitem=listitem,
            isFolder=True
        )


def get_details(input_uniqueids, handle, source_settings,
                fail_silently=False):
    # type: (Dict, int, Dict, bool) -> bool
    """
    Get full movie details and set to ListItem

    :param input_uniqueids: dict with unique IDs
    :param handle: plugin handle
    :param source_settings: settings dict
    :param fail_silently: if True, don't show error notifications
    :return: True if successful
    """
    if not input_uniqueids:
        return False

    # Determine the movie ID to use
    movie_id = input_uniqueids.get('tmdb') or input_uniqueids.get('imdb')
    if not movie_id:
        logger.error('No valid movie ID found in: {}'.format(input_uniqueids))
        return False

    logger.info('Getting details for movie ID: {}'.format(movie_id))

    # Load movie info from all sources
    movie_data = tmdb.load_movie_info(movie_id)
    if not movie_data:
        if not fail_silently:
            header = "Universal Movie Scraper error"
            msg = "Could not get movie information for ID: {}".format(movie_id)
            xbmcgui.Dialog().notification(
                header, msg, xbmcgui.NOTIFICATION_WARNING)
            logger.error(msg)
        return False

    # Assemble details from multiple sources
    details = data_utils.assemble_movie_details(movie_data)
    if not details:
        if not fail_silently:
            logger.error('Failed to assemble movie details')
        return False

    # Build the ListItem
    listitem = xbmcgui.ListItem(details['info']['title'], offscreen=True)
    infotag = listitem.getVideoInfoTag()

    # Set info
    _set_info(infotag, details['info'])

    # Set cast
    cast_list = _build_cast(details.get('cast', []))
    infotag.setCast(cast_list)

    # Set unique IDs
    infotag.setUniqueIDs(details['uniqueids'], 'tmdb')

    # Set ratings
    ratings_dict = _build_ratings(details.get('ratings', {}))
    default_rating = _find_default_rating(details.get('ratings', {}))
    infotag.setRatings(ratings_dict, default_rating)

    # Set artwork
    _add_artworks(listitem, details.get('available_art', {}))

    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=listitem)
    return True


def get_artwork(input_uniqueids, handle, source_settings):
    # type: (Dict, int, Dict) -> None
    """
    Get available artwork for a movie

    :param input_uniqueids: dict with unique IDs
    :param handle: plugin handle
    :param source_settings: settings dict
    """
    if not input_uniqueids:
        return

    movie_id = input_uniqueids.get('tmdb') or input_uniqueids.get('imdb')
    if not movie_id:
        return

    logger.debug('Getting artwork for movie ID {}'.format(movie_id))

    movie_data = tmdb.load_movie_info(movie_id)
    if not movie_data:
        xbmcplugin.setResolvedUrl(
            handle, False, xbmcgui.ListItem(offscreen=True))
        return

    details = data_utils.assemble_movie_details(movie_data)
    if not details:
        xbmcplugin.setResolvedUrl(
            handle, False, xbmcgui.ListItem(offscreen=True))
        return

    listitem = xbmcgui.ListItem(
        details['info'].get('title', ''), offscreen=True)
    _add_artworks(listitem, details.get('available_art', {}))
    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=listitem)


def _set_info(infotag, info_dict):
    # type: (xbmc.InfoTagVideo, Dict) -> None
    """Set movie info on InfoTagVideo"""
    infotag.setTitle(info_dict.get('title', ''))
    infotag.setOriginalTitle(info_dict.get('originaltitle', ''))
    infotag.setPlot(info_dict.get('plot', ''))
    infotag.setPlotOutline(info_dict.get('plotoutline', ''))
    infotag.setTagLine(info_dict.get('tagline', ''))
    infotag.setStudios(info_dict.get('studio', []))
    infotag.setGenres(info_dict.get('genre', []))
    infotag.setCountries(info_dict.get('country', []))
    infotag.setWriters(info_dict.get('credits', []))
    infotag.setDirectors(info_dict.get('director', []))
    infotag.setPremiered(info_dict.get('premiered', ''))
    if 'tag' in info_dict:
        infotag.setTags(info_dict['tag'])
    if 'mpaa' in info_dict:
        infotag.setMpaa(info_dict['mpaa'])
    if 'trailer' in info_dict:
        infotag.setTrailer(info_dict['trailer'])
    if 'set' in info_dict:
        infotag.setSet(info_dict['set'])
        infotag.setSetOverview(info_dict.get('setoverview', ''))
    if 'duration' in info_dict:
        infotag.setDuration(info_dict['duration'])
    if 'top250' in info_dict:
        infotag.setTop250(info_dict['top250'])


def _build_cast(cast_list):
    # type: (List[Dict]) -> List[xbmc.Actor]
    """Build Actor objects from cast list"""
    return [
        xbmc.Actor(
            cast['name'],
            cast.get('role', ''),
            cast.get('order', 0),
            cast.get('thumbnail', '')
        )
        for cast in cast_list
    ]


def _build_ratings(rating_dict):
    # type: (Dict) -> Dict
    """Build ratings dict for setRatings"""
    return {
        key: (value['rating'], value.get('votes', 0))
        for key, value in rating_dict.items()
        if 'rating' in value
    }


def _find_default_rating(rating_dict):
    # type: (Dict) -> Optional[Text]
    """Find the default rating key"""
    for key, value in rating_dict.items():
        if value.get('default'):
            return key
    return None


def _add_artworks(listitem, artworks):
    # type: (xbmcgui.ListItem, Dict) -> None
    """Add artworks to ListItem"""
    infotag = listitem.getVideoInfoTag()
    for arttype, artlist in artworks.items():
        if arttype == 'fanart':
            continue
        for image in artlist[:settings.MAXIMAGES]:
            infotag.addAvailableArtwork(image['url'], arttype,
                                        preview=image.get('preview', ''))

    # Fanart
    fanart_to_set = [
        {'image': image['url'], 'preview': image.get('preview', '')}
        for image in artworks.get('fanart', [])[:settings.MAXIMAGES]
    ]
    if fanart_to_set:
        listitem.setAvailableFanart(fanart_to_set)


def run():
    """Main entry point - route addon calls"""
    params = _get_params(sys.argv[1:])
    handle = params['handle']
    enddir = True
    source_settings = settings.get_settings()

    if 'action' in params:
        action = params['action']
        logger.debug('Called with action: {} params: {}'.format(action, params))

        if action == 'find' and 'title' in params:
            search_for_movie(
                params['title'], params.get('year'),
                handle, source_settings)

        elif action.lower() == 'nfourl' and 'nfo' in params:
            find_uniqueids_in_nfo(params['nfo'], handle)

        elif action == 'getdetails':
            unique_ids = None
            if 'url' in params:
                try:
                    unique_ids = json.loads(params['url'])
                except (ValueError, TypeError):
                    logger.error("Can't parse lookup string: {}".format(params['url']))
            elif 'uniqueIDs' in params:
                try:
                    unique_ids = json.loads(params['uniqueIDs'])
                except (ValueError, TypeError):
                    logger.error("Can't parse uniqueIDs: {}".format(params['uniqueIDs']))

            if unique_ids:
                enddir = not get_details(
                    unique_ids, handle, source_settings,
                    fail_silently='uniqueIDs' in params)

        elif action == 'getartwork':
            unique_ids = None
            if 'id' in params:
                try:
                    unique_ids = json.loads(params['id'])
                except (ValueError, TypeError):
                    unique_ids = {'tmdb': params['id']}
            if unique_ids:
                get_artwork(unique_ids, handle, source_settings)

        else:
            logger.error('Unhandled action: {}'.format(action))
    else:
        logger.error('No action in params to act on')

    if enddir:
        xbmcplugin.endOfDirectory(handle)

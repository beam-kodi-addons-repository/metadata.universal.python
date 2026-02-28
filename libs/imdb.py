# -*- coding: UTF-8 -*-
#
# Universal Movie Scraper (Python) - metadata.universal.python
# Based on metadata.universal XML scraper by Olympia
# Python structure inspired by metadata.themoviedb.org.python by Team Kodi
#
# SPDX-License-Identifier: GPL-2.0-or-later
# See LICENSE.txt for more information.

"""Functions to interact with IMDb for ratings, search, and supplemental data"""

from __future__ import absolute_import, unicode_literals

import re
import json
from urllib.parse import quote_plus
from . import api_utils
from .utils import logger

try:
    from typing import Optional, Text, Dict, List, Any
except ImportError:
    pass

IMDB_BASE_URL = 'https://www.imdb.com'
IMDB_TITLE_URL = IMDB_BASE_URL + '/title/{}/'
IMDB_FULLCREDITS_URL = IMDB_BASE_URL + '/title/{}/fullcredits/'
IMDB_RELEASEINFO_URL = IMDB_BASE_URL + '/title/{}/releaseinfo/'
IMDB_TAGLINE_URL = IMDB_BASE_URL + '/title/{}/taglines/'
IMDB_FIND_URL = IMDB_BASE_URL + '/find/'

IMDB_LDJSON_REGEX = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)
IMDB_NEXT_DATA_REGEX = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
IMDB_TOP250_REGEX = re.compile(r'Top rated movie #(\d+)')
IMDB_TOP250_REGEX_ALT = re.compile(r'Top Rated Movies #(\d+)')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml',
}

# Map full country names (from settings) to IMDb ISO country codes
IMDB_CERT_COUNTRY_MAP = {
    'Argentina': 'AR', 'Australia': 'AU', 'Austria': 'AT',
    'Belgium': 'BE', 'Brazil': 'BR', 'Bulgaria': 'BG',
    'Canada': 'CA', 'China': 'CN', 'Colombia': 'CO',
    'Chile': 'CL', 'Croatia': 'HR', 'Czech Republic': 'CZ',
    'Denmark': 'DK', 'Finland': 'FI', 'France': 'FR',
    'Germany': 'DE', 'Greece': 'GR', 'Hong Kong': 'HK',
    'Hungary': 'HU', 'Iceland': 'IS', 'India': 'IN',
    'Israel': 'IL', 'Italy': 'IT', 'Japan': 'JP',
    'Mexico': 'MX', 'Netherlands': 'NL', 'Norway': 'NO',
    'Pakistan': 'PK', 'Poland': 'PL', 'Portugal': 'PT',
    'Romania': 'RO', 'Russia': 'RU', 'Serbia': 'RS',
    'Singapore': 'SG', 'Slovenia': 'SI', 'Spain': 'ES',
    'Sweden': 'SE', 'Switzerland': 'CH', 'Thailand': 'TH',
    'Turkey': 'TR', 'United Kingdom': 'GB', 'Uruguay': 'UY',
    'United States': 'US', 'Venezuela': 'VE',
}


def _fetch_imdb_page(url, language='en-US,en;q=0.9'):
    # type: (Text, Text) -> Text
    """Fetch an IMDb page with proper headers"""
    headers = dict(HEADERS)
    headers['Accept-Language'] = language
    api_utils.set_headers(headers)
    response = api_utils.load_info(url, default='', resp_type='text')
    api_utils.set_headers({})
    return response


# =============================================================================
# Main page data extraction (comprehensive)
# =============================================================================

def get_imdb_details(imdb_id):
    # type: (Text) -> Dict
    """
    Get comprehensive data from IMDb main page.
    Extracts: ratings, top250, outline, genres, certification,
    directors, writers, actors, studios, countries, tagline.

    :param imdb_id: IMDb ID (e.g. tt1234567)
    :return: dict with all extracted data
    """
    if not imdb_id:
        return {}
    logger.debug('Getting IMDb details for {}'.format(imdb_id))
    response = _fetch_imdb_page(IMDB_TITLE_URL.format(imdb_id))
    return _parse_imdb_page(response)


def _parse_imdb_page(html):
    # type: (Text) -> Dict
    """Parse IMDb page HTML to extract ALL available data"""
    result = {}
    if not html:
        return result

    # === Parse LD+JSON data ===
    match = re.search(IMDB_LDJSON_REGEX, html)
    if match:
        try:
            ldjson = json.loads(match.group(1).replace('\n', ''))

            # Ratings
            aggregate_rating = ldjson.get('aggregateRating', {})
            rating = aggregate_rating.get('ratingValue')
            votes = aggregate_rating.get('ratingCount')
            if rating is not None and votes is not None:
                result['ratings'] = {
                    'imdb': {
                        'rating': float(rating),
                        'votes': int(votes)
                    }
                }

            # Outline / description
            description = ldjson.get('description')
            if description:
                result['outline'] = description

            # Genres
            genres = ldjson.get('genre', [])
            if isinstance(genres, str):
                genres = [genres]
            if genres:
                result['genres'] = genres

            # Content Rating (certification - typically US)
            content_rating = ldjson.get('contentRating')
            if content_rating:
                result['certification'] = content_rating

            # Directors
            directors_data = ldjson.get('director', [])
            if isinstance(directors_data, dict):
                directors_data = [directors_data]
            directors = [d['name'] for d in directors_data
                         if isinstance(d, dict) and d.get('name')]
            if directors:
                result['directors'] = directors

            # Writers (from creator, Person types only)
            creators = ldjson.get('creator', [])
            if isinstance(creators, dict):
                creators = [creators]
            writers = [c['name'] for c in creators
                       if isinstance(c, dict) and
                       c.get('@type') == 'Person' and c.get('name')]
            if writers:
                result['writers'] = writers

            # Actors (basic - no roles from LD+JSON)
            actors_data = ldjson.get('actor', [])
            if isinstance(actors_data, dict):
                actors_data = [actors_data]
            actors = []
            for i, a in enumerate(actors_data):
                if isinstance(a, dict) and a.get('name'):
                    actors.append({
                        'name': a['name'],
                        'role': '',
                        'thumbnail': '',
                        'order': i,
                    })
            if actors:
                result['actors'] = actors

        except (json.decoder.JSONDecodeError, AttributeError, ValueError,
                KeyError, TypeError):
            logger.debug('Failed to parse IMDb LD+JSON')

    # === Parse top250 ===
    top250 = _parse_imdb_top250(html)
    if top250:
        result['top250'] = top250

    # === Parse studios (production companies) from HTML ===
    studios = _parse_imdb_studios(html)
    if studios:
        result['studios'] = studios

    # === Parse countries from HTML ===
    countries = _parse_imdb_countries(html)
    if countries:
        result['countries'] = countries

    # === Parse tagline from HTML / __NEXT_DATA__ ===
    tagline = _parse_imdb_tagline(html)
    if tagline:
        result['tagline'] = tagline

    return result


def _parse_imdb_top250(html):
    # type: (Text) -> Optional[int]
    """Parse IMDb top250 ranking from page"""
    match = re.search(IMDB_TOP250_REGEX, html)
    if match:
        return int(match.group(1))
    match = re.search(IMDB_TOP250_REGEX_ALT, html)
    if match:
        return int(match.group(1))
    return None


def _parse_imdb_studios(html):
    # type: (Text) -> List[Text]
    """Parse production companies from IMDb page HTML"""
    # Modern IMDb: data-testid="title-details-companies"
    section_match = re.search(
        r'data-testid="title-details-companies"(.*?)(?:</li>|</section>)',
        html, re.DOTALL)
    if not section_match:
        section_match = re.search(
            r'Production compan(?:y|ies)(.*?)(?:</li>|</section>)',
            html, re.DOTALL | re.IGNORECASE)
    if section_match:
        section = section_match.group(1)
        studios = re.findall(r'href="/company/[^"]*"[^>]*>([^<]+)</a>', section)
        if studios:
            return [s.strip() for s in studios]

    # Try __NEXT_DATA__ for production companies
    next_data = _extract_next_data(html)
    if next_data:
        try:
            edges = (next_data.get('props', {}).get('pageProps', {})
                     .get('mainColumnData', {}).get('production', {})
                     .get('edges', []))
            companies = []
            for edge in edges:
                name = (edge.get('node', {}).get('company', {})
                        .get('companyText', {}).get('text'))
                if name:
                    companies.append(name)
            if companies:
                return companies
        except (AttributeError, KeyError, TypeError):
            pass

    return []


def _parse_imdb_countries(html):
    # type: (Text) -> List[Text]
    """Parse country of origin from IMDb page HTML"""
    # Modern IMDb: data-testid="title-details-origin"
    section_match = re.search(
        r'data-testid="title-details-origin"(.*?)(?:</li>|</section>)',
        html, re.DOTALL)
    if not section_match:
        section_match = re.search(
            r'Countr(?:y|ies) of origin(.*?)(?:</li>|</section>)',
            html, re.DOTALL | re.IGNORECASE)
    if section_match:
        section = section_match.group(1)
        countries = re.findall(
            r'href="/search/title/\?country_of_origin=[^"]*"[^>]*>([^<]+)</a>',
            section)
        if countries:
            return [c.strip() for c in countries]

    # Try __NEXT_DATA__
    next_data = _extract_next_data(html)
    if next_data:
        try:
            origins = (next_data.get('props', {}).get('pageProps', {})
                       .get('aboveTheFoldData', {})
                       .get('countriesOfOrigin', {}).get('countries', []))
            countries = []
            for c in origins:
                name = c.get('text')
                if name:
                    countries.append(name)
            if countries:
                return countries
        except (AttributeError, KeyError, TypeError):
            pass

    return []


def _parse_imdb_tagline(html):
    # type: (Text) -> Optional[Text]
    """Parse tagline from IMDb page HTML"""
    # Modern IMDb: data-testid="storyline-taglines"
    match = re.search(
        r'data-testid="storyline-taglines"[^>]*>.*?'
        r'<(?:span|li|div)[^>]*class="[^"]*"[^>]*>([^<]+)<',
        html, re.DOTALL)
    if match:
        tagline = match.group(1).strip()
        if tagline:
            return tagline

    # Try __NEXT_DATA__ for tagline
    next_data = _extract_next_data(html)
    if next_data:
        try:
            above = (next_data.get('props', {}).get('pageProps', {})
                     .get('aboveTheFoldData', {}))
            tagline_obj = above.get('tagline', {})
            text = tagline_obj.get('text')
            if text:
                return text
        except (AttributeError, KeyError, TypeError):
            pass

    return None


def _extract_next_data(html):
    # type: (Text) -> Optional[Dict]
    """Extract __NEXT_DATA__ JSON from IMDb page"""
    match = re.search(IMDB_NEXT_DATA_REGEX, html)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.decoder.JSONDecodeError, ValueError):
            pass
    return None


# =============================================================================
# IMDb Search
# =============================================================================

def search_imdb(query, year=None, language=None, full_search=False):
    # type: (Text, Optional[Text], Optional[Text], bool) -> List[Dict]
    """
    Search IMDb for movies

    :param query: search query
    :param year: optional year filter
    :param language: secondary search language for AKA titles
    :param full_search: include all movie categories (not just features)
    :return: list of search results with imdb_id, title, year
    """
    if not query:
        return []

    logger.debug('Searching IMDb for "{}" year={}'.format(query, year))

    search_query = query
    if year:
        search_query += ' ({})'.format(year)

    response = _fetch_imdb_page(
        IMDB_FIND_URL + '?q={}&s=tt'.format(quote_plus(search_query)),
        language='en-US,en;q=0.9')

    if not response:
        return []

    # Check if IMDb redirected to a single title page
    single_result = _check_single_title_redirect(response)
    if single_result:
        return [single_result]

    results = _parse_imdb_search_results(response, full_search)

    # If secondary language is set, do AKA search for localized titles
    if language and language not in ('None', ''):
        response_lang = _fetch_imdb_page(
            IMDB_FIND_URL + '?q={}&s=tt'.format(quote_plus(search_query)),
            language=language)
        if response_lang:
            lang_results = _parse_imdb_search_results(response_lang, full_search)
            if lang_results:
                id_to_result = {r['imdb_id']: r for r in results}
                for lr in lang_results:
                    if lr['imdb_id'] in id_to_result:
                        # Update with localized title
                        id_to_result[lr['imdb_id']]['title'] = lr['title']
                    else:
                        results.append(lr)

    return results


def _check_single_title_redirect(html):
    # type: (Text) -> Optional[Dict]
    """Check if IMDb search redirected to a single title page"""
    match = re.search(
        r'<meta property="og:url" content="https://www.imdb.com/title/(tt\d+)/',
        html)
    if not match:
        return None

    imdb_id = match.group(1)
    result = {'imdb_id': imdb_id, 'title': '', 'year': ''}

    ldjson_match = re.search(IMDB_LDJSON_REGEX, html)
    if ldjson_match:
        try:
            ldjson = json.loads(ldjson_match.group(1).replace('\n', ''))
            result['title'] = ldjson.get('name', '')
            date_published = ldjson.get('datePublished', '')
            if date_published:
                result['year'] = date_published.split('-')[0]
        except (json.decoder.JSONDecodeError, ValueError):
            pass

    if not result['title']:
        title_match = re.search(
            r'<meta\s+(?:name|property)="(?:og:)?title"\s+content="([^"]*?)'
            r'\s*\((?:[^)]*?(\d{4}))',
            html)
        if title_match:
            result['title'] = title_match.group(1).strip()
            result['year'] = title_match.group(2) or ''

    return result if result['title'] else None


def _parse_imdb_search_results(html, full_search=False):
    # type: (Text, bool) -> List[Dict]
    """Parse IMDb search/find results page"""
    results = []
    seen_ids = set()

    # Try __NEXT_DATA__ JSON first (most reliable on modern IMDb)
    next_data = _extract_next_data(html)
    if next_data:
        try:
            title_results = (next_data.get('props', {}).get('pageProps', {})
                             .get('titleResults', {}).get('results', []))
            for item in title_results:
                # Modern IMDb uses 'index' for the tt ID at top level,
                # and nests details under 'listItem'
                imdb_id = item.get('index', '') or item.get('id', '')
                list_item = item.get('listItem', {})
                if not imdb_id:
                    imdb_id = list_item.get('titleId', '')
                if not imdb_id or imdb_id in seen_ids:
                    continue

                # Filter non-movie types unless full_search
                if not full_search:
                    title_type = list_item.get('titleType', {})
                    type_id = title_type.get('id', '') if isinstance(title_type, dict) else ''
                    if type_id in ('tvSeries', 'tvMiniSeries', 'tvEpisode',
                                   'videoGame', 'podcastSeries', 'podcastEpisode'):
                        continue

                seen_ids.add(imdb_id)
                title = (list_item.get('titleText', '') or
                         list_item.get('originalTitleText', '') or
                         item.get('titleNameText', ''))
                year = (list_item.get('releaseYear', '') or
                        item.get('titleReleaseText', ''))
                results.append({
                    'imdb_id': imdb_id,
                    'title': title,
                    'year': str(year) if year else '',
                })
        except (AttributeError, KeyError, TypeError):
            pass

    # Fallback: regex on inline JSON data
    if not results:
        # Try modern format with "index" key
        pattern = re.compile(
            r'"index"\s*:\s*"(tt\d+)".*?"titleText"\s*:\s*"([^"]*?)".*?'
            r'"releaseYear"\s*:\s*(\d{4})?',
            re.DOTALL)
        for match in pattern.finditer(html):
            imdb_id = match.group(1)
            title = match.group(2)
            year = match.group(3) or ''
            if imdb_id in seen_ids:
                continue
            seen_ids.add(imdb_id)
            title = title.replace('\\u0026', '&').replace('\\u0027', "'")
            title = title.replace('\\"', '"').replace('\\/', '/')
            results.append({
                'imdb_id': imdb_id,
                'title': title,
                'year': year,
            })

    # Fallback: HTML parsing for ipc-title structure
    if not results:
        html_pattern = re.compile(
            r'href="/title/(tt\d+)/[^"]*"[^>]*class="ipc-title-link[^"]*"[^>]*>'
            r'\s*<h3[^>]*>([^<]*)</h3>',
            re.DOTALL)
        for match in html_pattern.finditer(html):
            imdb_id = match.group(1)
            if imdb_id in seen_ids:
                continue
            seen_ids.add(imdb_id)
            title = match.group(2).strip()
            # Try to find the year in metadata span after title
            year_match = re.search(
                r'/title/' + re.escape(imdb_id) + r'/.*?'
                r'cli-title-metadata-item["\s>]*(\d{4})',
                html, re.DOTALL)
            year = year_match.group(1) if year_match else ''
            results.append({
                'imdb_id': imdb_id,
                'title': title,
                'year': year,
            })

    # Legacy fallback: old-style search result HTML
    if not results:
        legacy_pattern = re.compile(
            r'href="/title/(tt\d+)/[^"]*"[^>]*>(?:&#x22;)?([^<]*?)(?:&#x22;)?'
            r'</a>\s*(?:\([IV]+\)\s*)?\([^(]*?(\d{4})',
            re.DOTALL)
        for match in legacy_pattern.finditer(html):
            imdb_id = match.group(1)
            if imdb_id in seen_ids:
                continue
            seen_ids.add(imdb_id)
            title = match.group(2).strip()
            year = match.group(3)
            results.append({
                'imdb_id': imdb_id,
                'title': title,
                'year': year,
            })

    return results


# =============================================================================
# Outline and Plot (standalone fetchers)
# =============================================================================

def get_imdb_outline(imdb_id):
    # type: (Text) -> Optional[Text]
    """
    Get plot outline from IMDb (standalone fetch)

    :param imdb_id: IMDb ID
    :return: outline text or None
    """
    if not imdb_id:
        return None
    logger.debug('Getting IMDb outline for {}'.format(imdb_id))
    response = _fetch_imdb_page(IMDB_TITLE_URL.format(imdb_id))
    if not response:
        return None

    match = re.search(IMDB_LDJSON_REGEX, response)
    if match:
        try:
            ldjson = json.loads(match.group(1).replace('\n', ''))
            description = ldjson.get('description')
            if description:
                return description
        except (json.decoder.JSONDecodeError, AttributeError):
            pass
    return None


def get_imdb_plot(imdb_id):
    # type: (Text) -> Optional[Text]
    """
    Get full plot from IMDb plotsummary page

    :param imdb_id: IMDb ID
    :return: plot text or None
    """
    if not imdb_id:
        return None
    logger.debug('Getting IMDb plot for {}'.format(imdb_id))
    plot_url = IMDB_BASE_URL + '/title/{}/plotsummary/'.format(imdb_id)
    response = _fetch_imdb_page(plot_url)
    if not response:
        return None

    # Try ipc-html-content-inner-div (modern IMDb)
    plot_match = re.search(
        r'<div[^>]*class="[^"]*ipc-html-content-inner-div[^"]*"[^>]*>(.*?)</div>',
        response, re.DOTALL)
    if plot_match:
        plot = plot_match.group(1).strip()
        plot = re.sub(r'<[^>]+>', '', plot)
        if plot:
            return plot

    # Try __NEXT_DATA__ for plot summaries
    next_data = _extract_next_data(response)
    if next_data:
        try:
            summaries = (next_data.get('props', {}).get('pageProps', {})
                         .get('contentData', {}).get('categories', []))
            for cat in summaries:
                for item in cat.get('section', {}).get('items', []):
                    text = item.get('htmlContent')
                    if text:
                        text = re.sub(r'<[^>]+>', '', text).strip()
                        if text:
                            return text
        except (AttributeError, KeyError, TypeError):
            pass

    return None


# =============================================================================
# Full Credits (IMDbFull)
# =============================================================================

def get_imdb_full_credits(imdb_id):
    # type: (Text) -> Dict
    """
    Get full credits from IMDb fullcredits page.
    Returns directors, writers, and cast with roles.

    :param imdb_id: IMDb ID
    :return: dict with directors, writers, cast lists
    """
    if not imdb_id:
        return {}
    logger.debug('Getting IMDb full credits for {}'.format(imdb_id))
    response = _fetch_imdb_page(IMDB_FULLCREDITS_URL.format(imdb_id))
    if not response:
        return {}

    result = {}

    # Try __NEXT_DATA__ first (most reliable on modern IMDb)
    next_data = _extract_next_data(response)
    if next_data:
        try:
            categories = (next_data.get('props', {}).get('pageProps', {})
                          .get('contentData', {}).get('categories', []))
            for cat in categories:
                cat_id = cat.get('id', '')
                if cat_id == 'director':
                    directors = []
                    for item in cat.get('credits', []):
                        name = (item.get('name', {}).get('nameText', {})
                                .get('text', ''))
                        if name and name not in directors:
                            directors.append(name)
                    if directors:
                        result['directors'] = directors
                elif cat_id == 'writer':
                    writers = []
                    for item in cat.get('credits', []):
                        name = (item.get('name', {}).get('nameText', {})
                                .get('text', ''))
                        if name and name not in writers:
                            writers.append(name)
                    if writers:
                        result['writers'] = writers
                elif cat_id == 'cast':
                    cast = []
                    for item in cat.get('credits', []):
                        name = (item.get('name', {}).get('nameText', {})
                                .get('text', ''))
                        characters = item.get('characters', [])
                        role = characters[0] if characters else ''
                        thumb = (item.get('name', {}).get('primaryImage', {})
                                 .get('url', '') if item.get('name', {})
                                 .get('primaryImage') else '')
                        if name:
                            cast.append({
                                'name': name,
                                'role': role,
                                'thumbnail': thumb,
                                'order': len(cast),
                            })
                    if cast:
                        result['cast'] = cast
        except (AttributeError, KeyError, TypeError, IndexError):
            logger.debug('Failed to parse __NEXT_DATA__ credits')

    # HTML fallback for cast table
    if 'cast' not in result:
        cast = _parse_cast_table(response)
        if cast:
            result['cast'] = cast

    # HTML fallback for directors
    if 'directors' not in result:
        directors = _parse_crew_section(response, 'Directed by')
        if directors:
            result['directors'] = directors

    # HTML fallback for writers
    if 'writers' not in result:
        writers = _parse_crew_section(response, 'Writing Credits')
        if not writers:
            writers = _parse_crew_section(response, 'Series Writing Credits')
        if writers:
            result['writers'] = writers

    return result


def _parse_cast_table(html):
    # type: (Text) -> List[Dict]
    """Parse cast from HTML cast_list table"""
    cast = []
    table_match = re.search(
        r'<table[^>]*class="cast_list"[^>]*>(.*?)</table>',
        html, re.DOTALL)
    if not table_match:
        return cast

    row_pattern = re.compile(
        r'<td[^>]*>\s*<a\s+href="/name/[^"]*"[^>]*>([^<]+)</a>'
        r'.*?'
        r'(?:<td\s+class="character"[^>]*>(.*?)</td>)?',
        re.DOTALL)
    for match in row_pattern.finditer(table_match.group(1)):
        name = match.group(1).strip()
        role_html = match.group(2) or ''
        role = re.sub(r'<[^>]+>', '', role_html).strip()
        role = re.sub(r'\s+', ' ', role)
        if name:
            cast.append({
                'name': name,
                'role': role,
                'thumbnail': '',
                'order': len(cast),
            })
    return cast


def _parse_crew_section(html, section_name):
    # type: (Text, Text) -> List[Text]
    """Parse crew names from a specific section header"""
    pattern = re.compile(
        r'<h4[^>]*id="[^"]*"[^>]*>\s*' + re.escape(section_name) +
        r'.*?</h4>(.*?)(?:<h4|<script)',
        re.DOTALL | re.IGNORECASE)
    match = pattern.search(html)
    if not match:
        return []

    section = match.group(1)
    names = re.findall(r'<a\s+href="/name/[^"]*"[^>]*>([^<]+)</a>', section)
    seen = set()
    result = []
    for name in names:
        name = name.strip()
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


# =============================================================================
# Certifications by country
# =============================================================================

def get_imdb_certification_by_country(imdb_id, country_name):
    # type: (Text, Text) -> Optional[Text]
    """
    Get certification for a specific country from IMDb

    :param imdb_id: IMDb ID
    :param country_name: full country name (e.g. 'United States')
    :return: certification string or None
    """
    if not imdb_id or not country_name:
        return None

    country_code = IMDB_CERT_COUNTRY_MAP.get(country_name, '')
    if not country_code:
        logger.debug('Unknown country for IMDb cert: {}'.format(country_name))
        return None

    logger.debug('Getting IMDb certification for {} in {}'.format(
        imdb_id, country_name))

    # Try the parentalguide page first
    url = IMDB_BASE_URL + '/title/{}/parentalguide/'.format(imdb_id)
    response = _fetch_imdb_page(url)
    if response:
        cert = _parse_certification_page(response, country_code, country_name)
        if cert:
            return cert

    # Fallback: releaseinfo page
    response = _fetch_imdb_page(IMDB_RELEASEINFO_URL.format(imdb_id))
    if response:
        cert = _parse_certification_page(response, country_code, country_name)
        if cert:
            return cert

    return None


def _parse_certification_page(html, country_code, country_name):
    # type: (Text, Text, Text) -> Optional[Text]
    """Parse certification from IMDb page HTML"""
    # Pattern: certificates=CC:CERT or certificates=CC%3ACERT
    pattern = re.compile(
        r'certificates=' + re.escape(country_code) +
        r'(?:%3A|:)([^"&\s<]+)',
        re.IGNORECASE)
    match = pattern.search(html)
    if match:
        return match.group(1)

    # Fallback: look for country name followed by cert
    pattern2 = re.compile(
        re.escape(country_name) + r'\s*:\s*([A-Za-z0-9+/\-]+)',
        re.IGNORECASE)
    match2 = pattern2.search(html)
    if match2:
        return match2.group(1)

    # Try __NEXT_DATA__
    next_data = _extract_next_data(html)
    if next_data:
        try:
            certs = (next_data.get('props', {}).get('pageProps', {})
                     .get('contentData', {}).get('section', {})
                     .get('items', []))
            for item in certs:
                cc = item.get('country', {}).get('id', '')
                if cc.upper() == country_code.upper():
                    cert_val = item.get('certification')
                    if cert_val:
                        return cert_val
        except (AttributeError, KeyError, TypeError):
            pass

    return None


# =============================================================================
# IMDb Tagline (standalone fetcher)
# =============================================================================

def get_imdb_tagline(imdb_id):
    # type: (Text) -> Optional[Text]
    """
    Get tagline from IMDb taglines page (fallback when main page
    doesn't have it)

    :param imdb_id: IMDb ID
    :return: tagline text or None
    """
    if not imdb_id:
        return None
    logger.debug('Getting IMDb tagline for {}'.format(imdb_id))
    response = _fetch_imdb_page(IMDB_TAGLINE_URL.format(imdb_id))
    if not response:
        return None

    # Try __NEXT_DATA__
    next_data = _extract_next_data(response)
    if next_data:
        try:
            edges = (next_data.get('props', {}).get('pageProps', {})
                     .get('contentData', {}).get('section', {})
                     .get('items', []))
            if edges:
                text = edges[0].get('text') or edges[0].get('plainText')
                if text:
                    return text
        except (AttributeError, KeyError, TypeError, IndexError):
            pass

    # HTML fallback
    match = re.search(
        r'<div[^>]*class="[^"]*ipc-html-content-inner-div[^"]*"[^>]*>(.*?)</div>',
        response, re.DOTALL)
    if match:
        tagline = re.sub(r'<[^>]+>', '', match.group(1)).strip()
        if tagline:
            return tagline

    return None

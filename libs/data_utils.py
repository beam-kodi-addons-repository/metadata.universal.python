# -*- coding: UTF-8 -*-
#
# Universal Movie Scraper (Python) - metadata.universal.python
# Based on metadata.universal XML scraper by Olympia
# Python structure inspired by metadata.themoviedb.org.python by Team Kodi
#
# SPDX-License-Identifier: GPL-2.0-or-later
# See LICENSE.txt for more information.

"""Functions to process and assemble movie data from multiple sources"""

from __future__ import absolute_import, unicode_literals

import re
from .utils import safe_get, logger
from . import settings, imdb, fanarttv, omdb, ofdb

try:
    from typing import Optional, Tuple, Text, Dict, List, Any
    from xbmcgui import ListItem
    InfoType = Dict[Text, Any]
except ImportError:
    pass

TAG_RE = re.compile(r'<[^>]+>')

# NFO URL patterns for parsing movie IDs
MOVIE_ID_REGEXPS = (
    r'(themoviedb)\.org/movie/(\d+)',           # TMDb http link
    r'(themoviedb)\.org/./movie/(\d+)',          # TMDb http link with lang
    r'(imdb)\.com/.+/(tt\d+)',                   # IMDb http link
    r'(imdb)\.com/Title\?t{0,2}(\d+)',           # IMDb old format
)


def find_uniqueids_in_text(text):
    # type: (Text) -> Dict
    """
    Find movie unique IDs in NFO text

    :param text: NFO file contents
    :return: dict of unique IDs found
    """
    result = {}
    res = re.search(r'(themoviedb\.org/movie/)(\d+)', text)
    if res:
        result['tmdb'] = res.group(2)
    res = re.search(r'imdb\....?/title/tt(\d+)', text)
    if res:
        result['imdb'] = 'tt' + res.group(1)
    else:
        res = re.search(r'imdb\....?/Title\?t{0,2}(\d+)', text)
        if res:
            result['imdb'] = 'tt' + res.group(1)
    return result


def assemble_movie_details(movie_data):
    # type: (InfoType) -> Optional[InfoType]
    """
    Assemble complete movie details from multiple sources based on settings

    :param movie_data: dict containing movie, movie_fallback, collection, etc.
    :return: assembled details dict with info, ratings, uniqueids, cast, available_art
    """
    movie = movie_data['movie']
    movie_fallback = movie_data.get('movie_fallback', {})
    collection = movie_data.get('collection')
    collection_fallback = movie_data.get('collection_fallback')
    title_data = movie_data.get('title_data')
    genres_data = movie_data.get('genres_data')
    plot_data = movie_data.get('plot_data')
    tagline_data = movie_data.get('tagline_data')
    trailer_data = movie_data.get('trailer_data')
    source_settings = movie_data['settings']

    if not movie:
        return None

    imdb_id = movie.get('imdb_id', '')
    tmdb_id = str(movie.get('id', ''))

    # === Fetch IMDb details once (all data from main page) ===
    imdb_details = {}
    need_imdb = (
        source_settings['RATING_SOURCE'] == 'IMDb' or
        source_settings['ALSO_IMDB'] or
        source_settings['IMDB_TOP250'] or
        source_settings['OUTLINE_SOURCE'] == 'IMDb' or
        source_settings['PLOT_SOURCE'] == 'IMDb Outline' or
        source_settings['PLOT_SOURCE'] == 'IMDb' or
        source_settings['GENRES_SOURCE'] == 'IMDb' or
        source_settings['STUDIO_SOURCE'] == 'IMDb' or
        source_settings['COUNTRY_SOURCE'] == 'IMDb' or
        source_settings['TAGLINE_SOURCE'] == 'IMDb' or
        source_settings['CREDITS_SOURCE'] in ('IMDb', 'IMDbFull') or
        (source_settings['CERT_SOURCE'] == 'IMDb' and
         source_settings['IMDB_CERT_COUNTRY'] == 'United States')
    )
    if need_imdb and imdb_id:
        imdb_details = imdb.get_imdb_details(imdb_id)

    # === Fetch IMDb full credits if needed ===
    imdb_full_credits = {}
    if source_settings['CREDITS_SOURCE'] == 'IMDbFull' and imdb_id:
        imdb_full_credits = imdb.get_imdb_full_credits(imdb_id)

    # === Fetch OMDB data if needed (for RT/MC ratings, RT consensus) ===
    omdb_data = {}
    need_omdb = (
        source_settings['RATING_SOURCE'] == 'Rotten Tomatoes' or
        source_settings['RATING_SOURCE'] == 'MetaCritic' or
        source_settings['ALSO_ROTTEN'] or
        source_settings['ALSO_OTHER_ROTTEN'] or
        source_settings['ALSO_META'] or
        source_settings['OUTLINE_SOURCE'] == "Rotten Tomatoes / Critics' Consensus" or
        source_settings['PLOT_SOURCE'] == "Rotten Tomatoes / Critics' Consensus"
    )
    if need_omdb and imdb_id:
        api_key = (source_settings.get('OMDB_API_KEY2') or
                   source_settings.get('OMDB_API_KEY'))
        if api_key:
            omdb_data = omdb.get_omdb_data(imdb_id, api_key)

    # === Title ===
    title = movie.get('title', '')
    originaltitle = movie.get('original_title', '')
    if source_settings['TITLE_SOURCE'] == 'themoviedb.org':
        if title_data and title_data.get('title'):
            title = title_data['title']
        elif movie.get('title'):
            title = movie['title']

    # === Genres ===
    genres = _get_names(movie.get('genres', []))
    if source_settings['GENRES_SOURCE'] == 'themoviedb.org' and genres_data:
        tmdb_genres = _get_names(genres_data.get('genres', []))
        if tmdb_genres:
            genres = tmdb_genres
    elif source_settings['GENRES_SOURCE'] == 'IMDb':
        imdb_genres = imdb_details.get('genres', [])
        if imdb_genres:
            genres = imdb_genres

    # === Plot ===
    plot = ''
    if source_settings['PLOT_SOURCE'] == 'themoviedb.org':
        if plot_data and plot_data.get('overview'):
            plot = plot_data['overview']
        elif movie.get('overview'):
            plot = movie['overview']
        elif movie_fallback.get('overview'):
            plot = movie_fallback['overview']
    elif source_settings['PLOT_SOURCE'] == 'IMDb':
        imdb_plot = imdb.get_imdb_plot(imdb_id)
        if imdb_plot:
            plot = imdb_plot
        elif movie.get('overview'):
            plot = movie['overview']
    elif source_settings['PLOT_SOURCE'] == 'IMDb Outline':
        imdb_outline = imdb_details.get('outline', '')
        if not imdb_outline and imdb_id:
            imdb_outline = imdb.get_imdb_outline(imdb_id) or ''
        if imdb_outline:
            plot = imdb_outline
        elif movie.get('overview'):
            plot = movie['overview']
    elif source_settings['PLOT_SOURCE'] == "Rotten Tomatoes / Critics' Consensus":
        consensus = omdb.get_rt_consensus(omdb_data) if omdb_data else ''
        if consensus:
            plot = consensus
        elif movie.get('overview'):
            plot = movie['overview']
    elif source_settings['PLOT_SOURCE'] == 'OFDb.de':
        ofdb_plot = ofdb.get_ofdb_plot(imdb_id) if imdb_id else ''
        if ofdb_plot:
            plot = ofdb_plot
        elif movie.get('overview'):
            plot = movie['overview']
    else:
        plot = movie.get('overview') or movie_fallback.get('overview', '')

    # === Tagline ===
    tagline = ''
    if source_settings['TAGLINE_SOURCE'] == 'themoviedb.org':
        if tagline_data and tagline_data.get('tagline'):
            tagline = tagline_data['tagline']
        elif movie.get('tagline'):
            tagline = movie['tagline']
        elif movie_fallback.get('tagline'):
            tagline = movie_fallback['tagline']
    elif source_settings['TAGLINE_SOURCE'] == 'IMDb':
        tagline = imdb_details.get('tagline', '')
        if not tagline and imdb_id:
            tagline = imdb.get_imdb_tagline(imdb_id) or ''
        if not tagline:
            tagline = movie.get('tagline') or movie_fallback.get('tagline', '')
    elif source_settings['TAGLINE_SOURCE'] != 'None':
        tagline = movie.get('tagline') or movie_fallback.get('tagline', '')

    # === Outline ===
    outline = ''
    if source_settings['OUTLINE_SOURCE'] == 'IMDb':
        outline = imdb_details.get('outline', '')
        if not outline and imdb_id:
            outline = imdb.get_imdb_outline(imdb_id) or ''
    elif source_settings['OUTLINE_SOURCE'] == "Rotten Tomatoes / Critics' Consensus":
        outline = omdb.get_rt_consensus(omdb_data) if omdb_data else ''

    # === Studio ===
    studio = _get_names(movie.get('production_companies', []))
    if source_settings['STUDIO_SOURCE'] == 'IMDb':
        imdb_studios = imdb_details.get('studios', [])
        if imdb_studios:
            studio = imdb_studios

    # === Country ===
    country = _get_names(movie.get('production_countries', []))
    if source_settings['COUNTRY_SOURCE'] == 'IMDb':
        imdb_countries = imdb_details.get('countries', [])
        if imdb_countries:
            country = imdb_countries

    # === Credits (Cast, Directors, Writers) ===
    credits_list = []
    directors = []
    cast = []
    casts = movie.get('casts', {})

    if source_settings['CREDITS_SOURCE'] == 'themoviedb.org':
        # Writers
        credits_list = _get_cast_members(
            casts, 'crew', 'Writing', ['Screenplay', 'Writer', 'Author'])
        # Directors
        directors = _get_cast_members(
            casts, 'crew', 'Directing', ['Director'])
        # Cast
        image_root_url, _ = settings.load_base_urls()
        cast = _build_cast_list(casts.get('cast', []), image_root_url)
    elif source_settings['CREDITS_SOURCE'] == 'IMDb':
        # Basic IMDb credits from LD+JSON on main page
        directors = imdb_details.get('directors', [])
        credits_list = imdb_details.get('writers', [])
        imdb_actors = imdb_details.get('actors', [])
        cast = [{'name': a.get('name', ''), 'role': a.get('role', ''),
                 'thumbnail': a.get('thumbnail', ''), 'order': a.get('order', i)}
                for i, a in enumerate(imdb_actors)]
    elif source_settings['CREDITS_SOURCE'] == 'IMDbFull':
        # Full credits from dedicated IMDb page
        if imdb_full_credits:
            directors = imdb_full_credits.get('directors', [])
            credits_list = imdb_full_credits.get('writers', [])
            full_cast = imdb_full_credits.get('cast', [])
            cast = [{'name': c.get('name', ''), 'role': c.get('role', ''),
                     'thumbnail': '', 'order': i}
                    for i, c in enumerate(full_cast)]
        else:
            # Fallback to TMDb
            credits_list = _get_cast_members(
                casts, 'crew', 'Writing', ['Screenplay', 'Writer', 'Author'])
            directors = _get_cast_members(
                casts, 'crew', 'Directing', ['Director'])
            image_root_url, _ = settings.load_base_urls()
            cast = _build_cast_list(casts.get('cast', []), image_root_url)

    # === Premiered date ===
    premiered = movie.get('release_date', '')

    # === Tags/Keywords ===
    tags = []
    if source_settings['TMDB_TAGS'] == 'themoviedb.org':
        keywords = movie.get('keywords', {}).get('keywords', [])
        tags = _get_names(keywords)

    # === Certification / MPAA ===
    mpaa = ''
    if source_settings['CERT_SOURCE'] == 'IMDb' and imdb_id:
        imdb_cert_country = source_settings.get('IMDB_CERT_COUNTRY', 'United States')
        if imdb_cert_country == 'United States' and imdb_details.get('certification'):
            # Use certification from main page LD+JSON
            mpaa = source_settings['CERT_PREFIX'] + imdb_details['certification']
        else:
            cert_val = imdb.get_imdb_certification_by_country(
                imdb_id, imdb_cert_country)
            if cert_val:
                mpaa = source_settings['CERT_PREFIX'] + cert_val
    else:
        cert_country = source_settings['TMDB_CERT_COUNTRY'].upper()
        releases = movie.get('releases', {})
        if 'countries' in releases:
            for cert in releases['countries']:
                if cert.get('iso_3166_1') == cert_country and cert.get('certification'):
                    mpaa = source_settings['CERT_PREFIX'] + cert['certification']
                    break

    # === Runtime ===
    duration = 0
    if movie.get('runtime'):
        duration = movie['runtime'] * 60  # Convert to seconds

    # === Trailer ===
    trailer = ''
    if source_settings['TMDB_TRAILER']:
        trailer = _parse_trailer(
            movie.get('trailers', {}),
            movie_fallback.get('trailers', {}))
        # Check language-specific trailer
        if trailer_data and not trailer:
            trailer = _parse_trailer(trailer_data.get('trailers', {}), {})

    # === Set/Collection ===
    set_name = ''
    set_overview = ''
    set_tmdbid = None
    if collection and source_settings['TMDB_SET']:
        set_name = collection.get('name') or ''
        if collection_fallback and not set_name:
            set_name = collection_fallback.get('name', '')
        set_overview = collection.get('overview') or ''
        if collection_fallback and not set_overview:
            set_overview = collection_fallback.get('overview', '')
        set_tmdbid = movie.get('belongs_to_collection', {}).get('id')

    # === Ratings ===
    ratings = {}
    # TMDb rating
    tmdb_rating = float(movie.get('vote_average', 0))
    tmdb_votes = int(movie.get('vote_count', 0))
    if tmdb_rating > 0 and (
            source_settings['RATING_SOURCE'] == 'themoviedb.org' or
            source_settings['ALSO_TMDB']):
        ratings['themoviedb'] = {
            'rating': tmdb_rating,
            'votes': tmdb_votes
        }

    # IMDb rating
    if source_settings['RATING_SOURCE'] == 'IMDb' or source_settings['ALSO_IMDB']:
        if imdb_details.get('ratings', {}).get('imdb'):
            ratings['imdb'] = imdb_details['ratings']['imdb']

    # Rotten Tomatoes rating
    if source_settings['ALSO_ROTTEN'] or \
            source_settings['RATING_SOURCE'] == 'Rotten Tomatoes':
        tomato_type = source_settings.get('TOMATO_TYPE', 'TomatoMeter All Critics')
        rt_rating = omdb.get_rt_rating(omdb_data, tomato_type) if omdb_data else None
        if rt_rating:
            ratings['tomatometerallcritics'] = rt_rating
        # Also get non-default RT ratings
        if source_settings['ALSO_OTHER_ROTTEN'] and omdb_data:
            all_rt_types = [
                'TomatoMeter All Critics',
                'TomatoMeter Audience Score',
                'Average Rating All Critics',
                'Average Rating Audience Score',
            ]
            for rt_type in all_rt_types:
                if rt_type == tomato_type:
                    continue
                other_rt = omdb.get_rt_rating(omdb_data, rt_type)
                if other_rt:
                    key = rt_type.lower().replace(' ', '')
                    ratings[key] = other_rt

    # MetaCritic rating
    if source_settings['ALSO_META'] or \
            source_settings['RATING_SOURCE'] == 'MetaCritic':
        mc_rating = omdb.get_metacritic_rating(omdb_data) if omdb_data else None
        if mc_rating:
            ratings['metacritic'] = mc_rating

    # === IMDb Top250 ===
    top250 = 0
    if source_settings['IMDB_TOP250'] and imdb_details.get('top250'):
        top250 = imdb_details['top250']

    # === Determine default rating ===
    default_rating = _determine_default_rating(ratings, source_settings)
    for rating_type in ratings:
        ratings[rating_type]['default'] = (rating_type == default_rating)

    # === Unique IDs ===
    uniqueids = {}
    if tmdb_id:
        uniqueids['tmdb'] = tmdb_id
    if imdb_id:
        uniqueids['imdb'] = imdb_id

    # === Artwork ===
    available_art = _parse_tmdb_artwork(
        movie, collection, source_settings)

    # Merge fanart.tv artwork
    _merge_fanarttv_artwork(available_art, tmdb_id, imdb_id,
                            set_tmdbid, source_settings)

    # === Build final info dict ===
    info = {
        'title': title,
        'originaltitle': originaltitle,
        'plot': plot,
        'plotoutline': outline,
        'tagline': tagline,
        'studio': studio,
        'genre': genres,
        'country': country,
        'credits': credits_list,
        'director': directors,
        'premiered': premiered,
        'tag': tags,
    }
    if mpaa:
        info['mpaa'] = mpaa
    if trailer:
        info['trailer'] = trailer
    if set_name:
        info['set'] = set_name
        info['setoverview'] = set_overview
    if duration:
        info['duration'] = duration
    if top250:
        info['top250'] = top250

    return {
        'info': info,
        'ratings': ratings,
        'uniqueids': uniqueids,
        'cast': cast,
        'available_art': available_art,
    }


def _get_names(items):
    # type: (List) -> List[Text]
    """Get names from a list of dicts"""
    return [item['name'] for item in items] if items else []


def _get_cast_members(casts, casttype, department, jobs):
    # type: (Dict, Text, Text, List[Text]) -> List[Text]
    """Extract cast members by department and job"""
    result = []
    if casttype in casts:
        for cast in casts[casttype]:
            if cast.get('department') == department and \
               cast.get('job') in jobs and \
               cast.get('name') not in result:
                result.append(cast['name'])
    return result


def _build_cast_list(cast_entries, image_root_url):
    # type: (List, Text) -> List[Dict]
    """Build cast list with thumbnails"""
    cast = []
    for actor in cast_entries:
        thumb = ''
        if actor.get('profile_path'):
            thumb = image_root_url + actor['profile_path']
        cast.append({
            'name': actor.get('name', ''),
            'role': actor.get('character', ''),
            'thumbnail': thumb,
            'order': actor.get('order', 0),
        })
    return cast


def _parse_trailer(trailers, fallback):
    # type: (Dict, Dict) -> Text
    """Parse YouTube trailer from TMDb trailers data"""
    if trailers.get('youtube'):
        return 'plugin://plugin.video.youtube/play/?video_id=' + \
               trailers['youtube'][0]['source']
    if fallback.get('youtube'):
        return 'plugin://plugin.video.youtube/play/?video_id=' + \
               fallback['youtube'][0]['source']
    return ''


def _determine_default_rating(ratings, source_settings):
    # type: (Dict, Dict) -> Text
    """Determine which rating should be the default"""
    rating_source = source_settings['RATING_SOURCE']
    if rating_source == 'IMDb' and 'imdb' in ratings:
        return 'imdb'
    elif rating_source == 'themoviedb.org' and 'themoviedb' in ratings:
        return 'themoviedb'
    elif rating_source == 'Rotten Tomatoes' and 'tomatometerallcritics' in ratings:
        return 'tomatometerallcritics'
    elif rating_source == 'MetaCritic' and 'metacritic' in ratings:
        return 'metacritic'
    # Fallback to first available
    if ratings:
        return list(ratings.keys())[0]
    return 'themoviedb'


def _parse_tmdb_artwork(movie, collection, source_settings):
    # type: (Dict, Optional[Dict], Dict) -> Dict
    """Parse TMDb artwork into Kodi artwork format"""
    language = source_settings.get('TMDB_POSTER_LANG', 'en')
    available_art = {}
    image_root_url, preview_root_url = settings.load_base_urls()

    if not image_root_url:
        return available_art

    images = movie.get('images', {})

    # Posters
    if source_settings.get('TMDB_POSTERS', True) and 'posters' in images:
        posters = _build_image_list_with_fallback(
            images['posters'], image_root_url, preview_root_url, language)
        if posters:
            available_art['poster'] = posters

    # Fanart/Backdrops
    if source_settings.get('TMDB_FANART', True) and 'backdrops' in images:
        fanart = _build_fanart_list(
            images['backdrops'], image_root_url, preview_root_url)
        if fanart:
            available_art['fanart'] = fanart

    # Landscape
    if source_settings.get('TMDB_LANDSCAPE', True) and 'backdrops' in images:
        landscape = _build_image_list_with_fallback(
            images['backdrops'], image_root_url, preview_root_url, language)
        if landscape:
            available_art['landscape'] = landscape

    # Logos
    if 'logos' in images:
        logos = _build_image_list_with_fallback(
            images['logos'], image_root_url, preview_root_url, language)
        if logos:
            available_art['clearlogo'] = logos

    # Collection/Set artwork from TMDb
    if collection and source_settings.get('TMDB_SET', True):
        coll_images = collection.get('images', {})
        if 'posters' in coll_images:
            set_posters = _build_image_list_with_fallback(
                coll_images['posters'], image_root_url, preview_root_url, language)
            if set_posters:
                available_art['set.poster'] = set_posters
        if 'backdrops' in coll_images:
            set_fanart = _build_fanart_list(
                coll_images['backdrops'], image_root_url, preview_root_url)
            if set_fanart:
                available_art['set.fanart'] = set_fanart
            set_landscape = _build_image_list_with_fallback(
                coll_images['backdrops'], image_root_url, preview_root_url, language)
            if set_landscape:
                available_art['set.landscape'] = set_landscape

    return available_art


def _build_image_list_with_fallback(imagelist, image_root_url, preview_root_url,
                                     language, language_fallback='en'):
    # type: (List, Text, Text, Text, Text) -> List[Dict]
    """Build image list with language fallback"""
    images = _build_image_list(imagelist, image_root_url, preview_root_url, [language])
    if language != language_fallback:
        images.extend(_build_image_list(
            imagelist, image_root_url, preview_root_url, [language_fallback]))
    if not images:
        images = _build_image_list(imagelist, image_root_url, preview_root_url)
    return images


def _build_fanart_list(imagelist, image_root_url, preview_root_url):
    # type: (List, Text, Text) -> List[Dict]
    """Build fanart list (no language, or null language)"""
    return _build_image_list(imagelist, image_root_url, preview_root_url, ['xx', None])


def _build_image_list(imagelist, image_root_url, preview_root_url, languages=None):
    # type: (List, Text, Text, Optional[List]) -> List[Dict]
    """Build image list, optionally filtering by language"""
    result = []
    for img in imagelist:
        if languages and img.get('iso_639_1') not in languages:
            continue
        file_path = img.get('file_path', '')
        if file_path.endswith('.svg'):
            continue
        result.append({
            'url': image_root_url + file_path,
            'preview': preview_root_url + file_path,
            'lang': img.get('iso_639_1', '')
        })
    return result


def _merge_fanarttv_artwork(available_art, tmdb_id, imdb_id, set_tmdbid, source_settings):
    # type: (Dict, Text, Text, Optional[int], Dict) -> None
    """Merge fanart.tv artwork into available_art dict"""
    # Movie artwork
    media_id = tmdb_id or imdb_id
    if media_id:
        fanarttv_movie = fanarttv.get_movie_artwork(media_id, source_settings)
        fanarttv_art = fanarttv_movie.get('available_art', {})
        for arttype, artlist in fanarttv_art.items():
            if arttype in available_art:
                available_art[arttype] = artlist + available_art[arttype]
            else:
                available_art[arttype] = artlist

    # Set artwork
    if set_tmdbid:
        fanarttv_set = fanarttv.get_set_artwork(str(set_tmdbid), source_settings)
        fanarttv_set_art = fanarttv_set.get('available_art', {})
        for arttype, artlist in fanarttv_set_art.items():
            if arttype in available_art:
                available_art[arttype] = artlist + available_art[arttype]
            else:
                available_art[arttype] = artlist

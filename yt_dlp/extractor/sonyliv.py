# coding: utf-8
from __future__ import unicode_literals

import time
import uuid

from .common import InfoExtractor
from ..compat import compat_HTTPError
from ..utils import (
    ExtractorError,
    int_or_none,
    try_get,
)


class SonyLIVIE(InfoExtractor):
    _VALID_URL = r'''(?x)
                     (?:
                        sonyliv:|
                        https?://(?:www\.)?sonyliv\.com/(?:s(?:how|port)s/[^/]+|movies|clip|trailer|music-videos)/[^/?#&]+-
                    )
                    (?P<id>\d+)
                  '''
    _TESTS = [{
        'url': 'https://www.sonyliv.com/shows/bachelors-delight-1700000113/achaari-cheese-toast-1000022678?watch=true',
        'info_dict': {
            'title': 'Achaari Cheese Toast',
            'id': '1000022678',
            'ext': 'mp4',
            'upload_date': '20200411',
            'description': 'md5:3957fa31d9309bf336ceb3f37ad5b7cb',
            'timestamp': 1586632091,
            'duration': 185,
            'season_number': 1,
            'series': 'Bachelors Delight',
            'episode_number': 1,
            'release_year': 2016,
        },
        'params': {
            'skip_download': True,
        },
    }, {
        'url': 'https://www.sonyliv.com/movies/tahalka-1000050121?watch=true',
        'only_matching': True,
    }, {
        'url': 'https://www.sonyliv.com/clip/jigarbaaz-1000098925',
        'only_matching': True,
    }, {
        'url': 'https://www.sonyliv.com/trailer/sandwiched-forever-1000100286?watch=true',
        'only_matching': True,
    }, {
        'url': 'https://www.sonyliv.com/sports/india-tour-of-australia-2020-21-1700000286/cricket-hls-day-3-1st-test-aus-vs-ind-19-dec-2020-1000100959?watch=true',
        'only_matching': True,
    }, {
        'url': 'https://www.sonyliv.com/music-videos/yeh-un-dinon-ki-baat-hai-1000018779',
        'only_matching': True,
    }]
    _GEO_COUNTRIES = ['IN']
    _TOKEN = None

    def _call_api(self, version, path, video_id):
        headers = {}
        if self._TOKEN:
            headers['security_token'] = self._TOKEN
        try:
            return self._download_json(
                'https://apiv2.sonyliv.com/AGL/%s/A/ENG/WEB/%s' % (version, path),
                video_id, headers=headers)['resultObj']
        except ExtractorError as e:
            if isinstance(e.cause, compat_HTTPError) and e.cause.code == 403:
                message = self._parse_json(
                    e.cause.read().decode(), video_id)['message']
                if message == 'Geoblocked Country':
                    self.raise_geo_restricted(countries=self._GEO_COUNTRIES)
                raise ExtractorError(message)
            raise

    def _real_initialize(self):
        self._TOKEN = self._call_api('1.4', 'ALL/GETTOKEN', None)

    def _real_extract(self, url):
        video_id = self._match_id(url)
        try:
            content = self._call_api(
                '1.5', 'IN/CONTENT/VIDEOURL/VOD/' + video_id, video_id)
        except:
            content = self._call_api(
                '1.5', 'IN/CONTENT/VIDEOURL/VOD/' + video_id + '/freepreview', video_id)
        if not self.get_param('allow_unplayable_formats') and content.get('isEncrypted'):
            raise ExtractorError('This video is DRM protected.', expected=True)
        dash_url = content['videoURL']
        headers = {
            'x-playback-session-id': '%s-%d' % (uuid.uuid4().hex, time.time() * 1000)
        }
        formats = self._extract_mpd_formats(
            dash_url, video_id, mpd_id='dash', headers=headers, fatal=False)
        formats.extend(self._extract_m3u8_formats(
            dash_url.replace('.mpd', '.m3u8').replace('/DASH/', '/HLS/'),
            video_id, 'mp4', m3u8_id='hls', headers=headers, fatal=False))
        for f in formats:
            f.setdefault('http_headers', {}).update(headers)
        self._sort_formats(formats)

        metadata = self._call_api(
            '1.6', 'IN/DETAIL/' + video_id, video_id)['containers'][0]['metadata']
        title = metadata['episodeTitle']
        subtitles = {}
        for sub in content.get('subtitle', []):
            sub_url = sub.get('subtitleUrl')
            if not sub_url:
                continue
            subtitles.setdefault(sub.get('subtitleLanguageName', 'ENG'), []).append({
                'url': sub_url,
            })
        return {
            'id': video_id,
            'title': title,
            'formats': formats,
            'thumbnail': content.get('posterURL'),
            'description': metadata.get('longDescription') or metadata.get('shortDescription'),
            'timestamp': int_or_none(metadata.get('creationDate'), 1000),
            'duration': int_or_none(metadata.get('duration')),
            'season_number': int_or_none(metadata.get('season')),
            'series': metadata.get('title'),
            'episode_number': int_or_none(metadata.get('episodeNumber')),
            'release_year': int_or_none(metadata.get('year')),
            'subtitles': subtitles,
        }


class SonyLIVSeriesIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?sonyliv\.com/shows/[^/?#&]+-(?P<id>\d{10})$'
    _TESTS = [{
        'url': 'https://www.sonyliv.com/shows/adaalat-1700000091',
        'playlist_mincount': 456,
        'info_dict': {
            'id': '1700000091',
        },
    }]
    _API_SHOW_URL = "https://apiv2.sonyliv.com/AGL/1.9/R/ENG/WEB/IN/DL/DETAIL/{}?kids_safe=false&from=0&to=49"
    _API_EPISODES_URL = "https://apiv2.sonyliv.com/AGL/1.4/R/ENG/WEB/IN/CONTENT/DETAIL/BUNDLE/{}?from=0&to=1000&orderBy=episodeNumber&sortOrder=asc"
    _API_SECURITY_URL = 'https://apiv2.sonyliv.com/AGL/1.4/A/ENG/WEB/ALL/GETTOKEN'

    def _entries(self, show_id):
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.sonyliv.com',
        }
        headers['security_token'] = self._download_json(
            self._API_SECURITY_URL, video_id=show_id, headers=headers,
            note='Downloading security token')['resultObj']
        seasons = try_get(
            self._download_json(self._API_SHOW_URL.format(show_id), video_id=show_id, headers=headers),
            lambda x: x['resultObj']['containers'][0]['containers'], list)
        for season in seasons or []:
            season_id = season['id']
            episodes = try_get(
                self._download_json(self._API_EPISODES_URL.format(season_id), video_id=season_id, headers=headers),
                lambda x: x['resultObj']['containers'][0]['containers'], list)
            for episode in episodes or []:
                video_id = episode.get('id')
                yield self.url_result('sonyliv:%s' % video_id, ie=SonyLIVIE.ie_key(), video_id=video_id)

    def _real_extract(self, url):
        show_id = self._match_id(url)
        return self.playlist_result(self._entries(show_id), playlist_id=show_id)

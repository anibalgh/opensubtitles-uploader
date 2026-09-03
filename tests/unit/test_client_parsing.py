"""Parsing tests for the OpenSubtitles REST adapter helpers (no network)."""

from __future__ import annotations

import gzip
import zlib
from pathlib import Path

import pytest

from opensubtitles_uploader.adapters.osapi.client import (
    OpenSubtitlesClient,
    _content_md5,
    _kind_from,
    _normalize_imdb,
    _parse_feature,
)
from opensubtitles_uploader.adapters.osapi.keys import ApiKeySource
from opensubtitles_uploader.domain.errors import AuthError
from opensubtitles_uploader.domain.model import MediaKind


def test_normalize_imdb():
    assert _normalize_imdb(1375666) == "tt1375666"
    assert _normalize_imdb("1375666") == "tt1375666"


def test_kind_from():
    assert _kind_from("Movie") == MediaKind.MOVIE
    assert _kind_from("Episode") == MediaKind.EPISODE
    assert _kind_from("Tvshow") == MediaKind.SHOW


def test_parse_feature_movie():
    attributes = {
        "feature_type": "Movie",
        "title": "Inception",
        "year": "2010",
        "imdb_id": 1375666,
        "img_url": "https://example.org/poster.jpg",
    }
    movie = _parse_feature(attributes)
    assert movie is not None
    assert movie.imdb_id == "tt1375666"
    assert movie.title == "Inception"
    assert movie.year == 2010
    assert movie.kind == MediaKind.MOVIE
    assert movie.backdrop_url == "https://example.org/poster.jpg"


def test_parse_feature_episode_uses_parent_title():
    attributes = {
        "feature_type": "Episode",
        "title": "Pilot",
        "parent_title": "Breaking Bad",
        "year": "2008",
        "imdb_id": 9126,
        "season_number": 1,
        "episode_number": 1,
    }
    movie = _parse_feature(attributes)
    assert movie is not None
    assert movie.kind == MediaKind.EPISODE
    assert movie.title == "Breaking Bad"
    assert movie.season == 1 and movie.episode == 1


def test_osu_gzip_no_header_matches_raw_deflate():
    payload = b"1\n00:00:01,000 --> 00:00:02,000\nHello!\n" * 50
    encoded = OpenSubtitlesClient._osu_gzip(payload)
    import base64

    raw = base64.b64decode(encoded)
    # gzip.compress without its 10-byte header == zlib raw deflate stream
    assert zlib.decompress(raw, -zlib.MAX_WBITS) == payload
    # ...and equals gzip.compress()[10:]
    assert raw == gzip.compress(payload, compresslevel=9, mtime=0)[10:]


def test_content_md5(tmp_path):
    file = Path(tmp_path) / "sub.srt"
    file.write_bytes(b"subtitle content")
    import hashlib

    assert _content_md5(file) == hashlib.md5(b"subtitle content").hexdigest()


def test_client_upload_requires_login():
    client = OpenSubtitlesClient(api_key=ApiKeySource(None))
    with pytest.raises(AuthError):
        client.upload(
            moviehash="ab" * 8,
            moviebytesize=1234,
            language="eng",
            subtitle_path=Path("x.srt"),
        )

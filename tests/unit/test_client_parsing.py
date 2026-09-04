"""Parsing tests for the OpenSubtitles REST adapter helpers (no network)."""

from __future__ import annotations

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


def test_normalize_imdb_zero_pads():
    # tt0294448 (Chôjin Locke, 1983): the REST API returns the bare number.
    assert _normalize_imdb(294448) == "tt0294448"
    assert _normalize_imdb("294448") == "tt0294448"
    assert _normalize_imdb("tt0294448") == "tt0294448"


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


def test_osu_gzip_is_zlib_rfc1950():
    import base64

    payload = b"1\n00:00:01,000 --> 00:00:02,000\nHola mundo\n" * 50
    encoded = OpenSubtitlesClient._osu_gzip(payload)
    raw = base64.b64decode(encoded)
    # Matches Node.js zlib.deflate() used by the original opensubtitles-api
    assert zlib.decompress(raw) == payload
    assert raw == zlib.compress(payload)


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


def test_gui_login_is_upload_only(monkeypatch):
    """GUI login must only use XML-RPC; REST/metadata stays untouched."""
    from opensubtitles_uploader.adapters.osapi.client import OpenSubtitlesClient

    client = OpenSubtitlesClient(api_key=ApiKeySource(None))

    def fake_xml_login(username, password, language="en"):
        return "xml-token-123"

    def fail_rest(*args, **kwargs):  # pragma: no cover
        raise AssertionError("REST must not be called by the GUI upload login")

    monkeypatch.setattr(client._xmlrpc, "login", fake_xml_login)
    monkeypatch.setattr(client, "_rest", fail_rest)

    session = client.login("upload_user", "secret")
    assert session.token == "xml-token-123"
    assert session.user.upload_capable is True
    assert client._xml_token == "xml-token-123"
    assert client._rest_token is None  # metadata session untouched


def test_metadata_session_needs_env_creds_and_key(monkeypatch):
    """Without API key, ensure_metadata_session must be a safe no-op."""
    from opensubtitles_uploader.adapters.osapi.client import OpenSubtitlesClient

    client = OpenSubtitlesClient(api_key=ApiKeySource(None))
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", "someone")
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "secret")
    monkeypatch.delenv("OPENSUBTITLES_API_KEY", raising=False)  # repo .env may set it

    def fail_rest(*args, **kwargs):  # pragma: no cover
        raise AssertionError("no REST call without an API key")

    monkeypatch.setattr(client, "_rest", fail_rest)
    assert client.ensure_metadata_session() is None
    assert client.metadata_user() is None


class _FakeXmlRpc:
    """Records calls; lets tests script try/upload responses."""

    def __init__(self, try_response, upload_response=None):
        self.try_response = try_response
        self.upload_response = upload_response
        self.tried = None
        self.uploaded = None

    def try_upload_subtitles(self, token, cd1):
        self.tried = (token, cd1)
        return self.try_response

    def upload_subtitles(self, token, baseinfo, cd1):
        self.uploaded = (token, baseinfo, cd1)
        return self.upload_response


def _client_with_session(tmp_path, fake):
    client = OpenSubtitlesClient(api_key=ApiKeySource(None))
    client._xml_token = "upload-token"
    client._xmlrpc = fake  # type: ignore[assignment]
    sub = Path(tmp_path) / "movie.spa.srt"
    sub.write_bytes(b"1\n00:00:01,000 --> 00:00:02,000\nHola\n")
    return client, sub


def test_upload_stops_when_already_in_db(tmp_path):
    fake = _FakeXmlRpc(
        {
            "status": "200 OK",
            "alreadyindb": 1,
            "data": [{"IDSubtitle": 42, "HashWasAlreadyInDb": 1, "MovieName": "The Terror"}],
        }
    )
    client, sub = _client_with_session(tmp_path, fake)
    outcome = client.upload(moviehash="ab" * 8, moviebytesize=1, language="spa", subtitle_path=sub)
    assert outcome.state == "already_exists"
    assert outcome.existing and outcome.existing[0].subtitle_id == 42
    assert fake.uploaded is None  # never reached the real upload


def test_upload_uses_server_authoritative_imdb(tmp_path):
    fake = _FakeXmlRpc(
        {"status": "200 OK", "alreadyindb": 0, "data": [{"IDMovieImdb": "9876543"}]},
        {"status": "200 OK", "data": "https://www.opensubtitles.org/subtitles/1"},
    )
    client, sub = _client_with_session(tmp_path, fake)
    outcome = client.upload(
        moviehash="ab" * 8,
        moviebytesize=1,
        language="spa",
        subtitle_path=sub,
        imdb_id="tt2708480",  # generic (show) id — must be overridden
    )
    assert outcome.succeeded and outcome.url
    _token, baseinfo, cd1 = fake.uploaded
    assert baseinfo["idmovieimdb"] == "9876543"
    assert baseinfo["sublanguageid"] == "spa"
    assert "subcontent" in cd1

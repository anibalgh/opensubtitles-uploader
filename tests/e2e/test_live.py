"""Live end-to-end tests against the real OpenSubtitles services.

These are **disabled by default**: they need a real account and an API key.

Run with:

    export OPENSUBTITLES_API_KEY=…            # application API key
    export OPENSUBTITLES_USERNAME=…           # metadata/catalogue account (.env)
    export OPENSUBTITLES_PASSWORD=…
    export OPENSUBTITLES_UPLOAD_USERNAME=…    # optional: GUI upload account
    export OPENSUBTITLES_UPLOAD_PASSWORD=…
    poetry run pytest -m e2e
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.e2e

API_KEY = os.environ.get("OPENSUBTITLES_API_KEY", "")
META_USER = os.environ.get("OPENSUBTITLES_USERNAME", "")
META_PASS = os.environ.get("OPENSUBTITLES_PASSWORD", "")
UPLOAD_USER = os.environ.get("OPENSUBTITLES_UPLOAD_USERNAME", "")
UPLOAD_PASS = os.environ.get("OPENSUBTITLES_UPLOAD_PASSWORD", "")

needs_catalogue = pytest.mark.skipif(
    not (API_KEY and META_USER and META_PASS),
    reason="OPENSUBTITLES_API_KEY/USERNAME/PASSWORD not set",
)
needs_upload = pytest.mark.skipif(
    not (UPLOAD_USER and UPLOAD_PASS),
    reason="OPENSUBTITLES_UPLOAD_USERNAME/PASSWORD not set",
)


def _client(tmp_path_factory):
    from opensubtitles_uploader.adapters.osapi.client import OpenSubtitlesClient
    from opensubtitles_uploader.adapters.osapi.keys import ApiKeySource
    from opensubtitles_uploader.adapters.storage.secret_store import FernetSecretStore

    vault = FernetSecretStore(tmp_path_factory.mktemp("e2e"))
    vault.set_secret("opensubtitles-uploader", "__api_key__", API_KEY)
    return OpenSubtitlesClient(api_key=ApiKeySource(vault))


@needs_catalogue
def test_live_metadata_catalogue(tmp_path_factory, monkeypatch):
    """The .env (metadata) account must drive search and REST login."""
    monkeypatch.setenv("OPENSUBTITLES_USERNAME", META_USER)
    monkeypatch.setenv("OPENSUBTITLES_PASSWORD", META_PASS)
    client = _client(tmp_path_factory)

    user = client.ensure_metadata_session()
    assert user is not None and user.username
    assert user.upload_capable is False  # metadata account never uploads

    languages = client.languages()
    assert any(lang.iso639_1 == "en" for lang in languages)

    results = client.search_features("Inception")
    assert results and any(m.imdb_id == "tt1375666" for m in results)

    client.logout()


@needs_upload
def test_live_upload_login(tmp_path_factory):
    """The GUI (upload) account must authenticate on XML-RPC."""
    client = _client(tmp_path_factory)
    session = client.login(UPLOAD_USER, UPLOAD_PASS)
    assert session.token
    assert session.user.upload_capable is True
    client.logout()

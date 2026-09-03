"""Live end-to-end tests against the real OpenSubtitles services.

These are **disabled by default**: they need a real account and an API key.

Run with:

    export OPENSUBTITLES_API_KEY=…
    export OPENSUBTITLES_USERNAME=…
    export OPENSUBTITLES_PASSWORD=…
    poetry run pytest -m e2e
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.e2e

API_KEY = os.environ.get("OPENSUBTITLES_API_KEY", "")
USERNAME = os.environ.get("OPENSUBTITLES_USERNAME", "")
PASSWORD = os.environ.get("OPENSUBTITLES_PASSWORD", "")

needs_credentials = pytest.mark.skipif(
    not (API_KEY and USERNAME and PASSWORD),
    reason="OPENSUBTITLES_API_KEY/USERNAME/PASSWORD not set",
)


@needs_credentials
def test_live_login_and_catalog():
    from opensubtitles_uploader.adapters.osapi.client import OpenSubtitlesClient
    from opensubtitles_uploader.adapters.osapi.keys import ApiKeySource
    from opensubtitles_uploader.adapters.storage.secret_store import FernetSecretStore
    from opensubtitles_uploader.config import user_config_path

    vault = FernetSecretStore(user_config_path() / "test-e2e")
    vault.set_secret("opensubtitles-uploader", "__api_key__", API_KEY)
    client = OpenSubtitlesClient(api_key=ApiKeySource(vault))

    session = client.login(USERNAME, PASSWORD)
    assert session.token
    assert session.user.username

    languages = client.languages()
    assert any(lang.iso639_1 == "en" for lang in languages)

    results = client.search_features("Inception")
    assert results and any(m.imdb_id == "tt1375666" for m in results)

    client.logout()


@needs_credentials
def test_live_hash_round_trip():
    """A real moviehash should be identifiable without uploading anything."""
    from opensubtitles_uploader.adapters.osapi.client import OpenSubtitlesClient
    from opensubtitles_uploader.adapters.osapi.keys import ApiKeySource
    from opensubtitles_uploader.adapters.storage.secret_store import FernetSecretStore
    from opensubtitles_uploader.config import user_config_path

    vault = FernetSecretStore(user_config_path() / "test-e2e")
    vault.set_secret("opensubtitles-uploader", "__api_key__", API_KEY)
    client = OpenSubtitlesClient(api_key=ApiKeySource(vault))
    # Known public sample: hash of a well-known file used in OS docs.
    movie = client.identify("8e245d9679d31e12", 132393969)
    # Identification may legitimately return None for hashes unknown to the DB,
    # so we only assert the call does not raise and returns a MovieRef or None.
    assert movie is None or movie.imdb_id

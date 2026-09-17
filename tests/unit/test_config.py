"""Tests for environment/``.env`` configuration resolution.

Regression guard: the base URL and HTTP timeout used to be module-level
constants evaluated *before* ``load_dotenv()`` ran, so a local ``.env``
silently lost those two values.  They are now resolved lazily.
"""

from __future__ import annotations

from opensubtitles_uploader import config
from opensubtitles_uploader.adapters.osapi.client import OpenSubtitlesClient
from opensubtitles_uploader.adapters.osapi.keys import ApiKeySource

_DEFAULT_BASE_URL = "https://api.opensubtitles.com/api/v1"
_DEFAULT_TIMEOUT = 30.0


def test_api_base_url_default(monkeypatch):
    monkeypatch.delenv("OPENSUBTITLES_BASE_URL", raising=False)
    assert config.api_base_url() == _DEFAULT_BASE_URL


def test_api_base_url_reads_environment(monkeypatch):
    monkeypatch.setenv("OPENSUBTITLES_BASE_URL", "https://mirror.invalid/api/v1")
    assert config.api_base_url() == "https://mirror.invalid/api/v1"


def test_http_timeout_default(monkeypatch):
    monkeypatch.delenv("OPENSUBTITLES_HTTP_TIMEOUT", raising=False)
    assert config.http_timeout() == _DEFAULT_TIMEOUT


def test_http_timeout_reads_environment(monkeypatch):
    monkeypatch.setenv("OPENSUBTITLES_HTTP_TIMEOUT", "7.5")
    assert config.http_timeout() == 7.5


def test_http_timeout_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("OPENSUBTITLES_HTTP_TIMEOUT", "not-a-number")
    assert config.http_timeout() == _DEFAULT_TIMEOUT
    monkeypatch.setenv("OPENSUBTITLES_HTTP_TIMEOUT", "0")
    assert config.http_timeout() == _DEFAULT_TIMEOUT


def test_dotenv_values_are_honoured(tmp_path, monkeypatch):
    """A value loaded from a local ``.env`` must reach the accessors."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENSUBTITLES_BASE_URL=https://from-dotenv.invalid/api/v1\nOPENSUBTITLES_HTTP_TIMEOUT=7\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENSUBTITLES_BASE_URL", raising=False)
    monkeypatch.delenv("OPENSUBTITLES_HTTP_TIMEOUT", raising=False)
    monkeypatch.setattr(config, "dotenv_candidates", lambda: [env_file])

    config.load_dotenv()

    assert config.api_base_url() == "https://from-dotenv.invalid/api/v1"
    assert config.http_timeout() == 7.0


def test_client_resolves_configuration_at_runtime(monkeypatch):
    """The client must not freeze environment values at import time."""
    monkeypatch.setenv("OPENSUBTITLES_BASE_URL", "https://runtime.invalid/api/v1")
    client = OpenSubtitlesClient(api_key=ApiKeySource(None))
    assert client._rest_base == "https://runtime.invalid/api/v1"


def test_client_explicit_arguments_win(monkeypatch):
    monkeypatch.setenv("OPENSUBTITLES_BASE_URL", "https://runtime.invalid/api/v1")
    client = OpenSubtitlesClient(
        api_key=ApiKeySource(None), rest_base_url="https://explicit.invalid/api/v1"
    )
    assert client._rest_base == "https://explicit.invalid/api/v1"

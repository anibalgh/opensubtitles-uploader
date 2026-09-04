"""Tests for the CLI adapter helpers (no network)."""

from __future__ import annotations

import pytest

import opensubtitles_uploader.adapters.cli.main as cli_main
from opensubtitles_uploader.domain.errors import AuthError


class _FakeClient:
    def __init__(self) -> None:
        self.logins: list[tuple[str, str]] = []

    def login(self, username: str, password: str) -> None:
        self.logins.append((username, password))


class _FakeAuth:
    def __init__(self, restored: object = None) -> None:
        self._restored = restored

    def restore(self) -> object:
        return self._restored


class _FakeCtx:
    def __init__(self, client: _FakeClient, auth: _FakeAuth) -> None:
        self.client = client
        self.auth = auth


def test_ensure_upload_session_uses_env_credentials(monkeypatch):
    client = _FakeClient()
    ctx = _FakeCtx(client, _FakeAuth())
    monkeypatch.setattr(
        cli_main, "environment_upload_credentials", lambda: ("org_user", "org_pass")
    )
    cli_main._ensure_upload_session(ctx)
    assert client.logins == [("org_user", "org_pass")]


def test_ensure_upload_session_falls_back_to_keychain(monkeypatch):
    client = _FakeClient()
    ctx = _FakeCtx(client, _FakeAuth(restored="a-user"))
    monkeypatch.setattr(cli_main, "environment_upload_credentials", lambda: None)
    cli_main._ensure_upload_session(ctx)
    assert client.logins == []  # restore() established the session


def test_ensure_upload_session_raises_without_credentials(monkeypatch):
    client = _FakeClient()
    ctx = _FakeCtx(client, _FakeAuth(restored=None))
    monkeypatch.setattr(cli_main, "environment_upload_credentials", lambda: None)
    with pytest.raises(AuthError):
        cli_main._ensure_upload_session(ctx)

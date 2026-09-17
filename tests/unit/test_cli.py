"""Tests for the CLI adapter helpers (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import opensubtitles_uploader.adapters.cli.main as cli_main
from opensubtitles_uploader.domain.errors import AuthError
from opensubtitles_uploader.domain.model import (
    Language,
    MovieRef,
    SubtitleFile,
    UploadOutcome,
    VideoFile,
)

ENGLISH = Language(code="eng", iso639_1="en", name="English", native="English")


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


class _FakeVideos:
    def __init__(self) -> None:
        self.identify_calls: list[dict[str, str | None]] = []

    def analyze(self, path: Path) -> VideoFile:
        return VideoFile(path=Path(path), name=Path(path).name, size_bytes=10, os_hash="ab" * 8)

    def identify(
        self, video: VideoFile, *, title: str | None = None, imdb_id: str | None = None
    ) -> VideoFile:
        self.identify_calls.append({"title": title, "imdb_id": imdb_id})
        movie = MovieRef(imdb_id=imdb_id or "tt42969298", title=title or "KAMUI Hes Behind You")
        return VideoFile(
            path=video.path,
            name=video.name,
            size_bytes=video.size_bytes,
            os_hash=video.os_hash,
            movie=movie,
        )


class _FakeSubtitles:
    def analyze(self, path: Path) -> SubtitleFile:
        return SubtitleFile(
            path=Path(path), name=Path(path).name, size_bytes=10, md5="cd" * 16, language=ENGLISH
        )


class _FakeUploads:
    def __init__(self) -> None:
        self.requests: list = []

    def upload(self, request):
        self.requests.append(request)
        return UploadOutcome(state="created", url="https://example.invalid/1")


class _LoginClient:
    def __init__(self) -> None:
        self.logins: list[tuple[str, str]] = []

    def login(self, username: str, password: str) -> None:
        self.logins.append((username, password))


class _UploadCtx:
    def __init__(self) -> None:
        self.videos = _FakeVideos()
        self.subtitles = _FakeSubtitles()
        self.uploads = _FakeUploads()
        self.client = _LoginClient()
        self.auth = _FakeAuth()


def test_upload_command_forwards_title_and_imdb(monkeypatch, tmp_path):
    video = tmp_path / "KAMUI.Hes.Behind.You.s01e09.mkv"
    video.write_bytes(b"\x00" * 10)
    subtitle = tmp_path / "KAMUI.Hes.Behind.You.s01e09.eng.srt"
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    ctx = _UploadCtx()
    monkeypatch.setattr(cli_main, "_context", lambda: ctx)
    monkeypatch.setattr(cli_main, "environment_upload_credentials", lambda: ("org_user", "pw"))

    result = CliRunner().invoke(
        cli_main.app,
        ["upload", str(video), str(subtitle), "--title", "My Title", "--imdb-id", "tt42969298"],
    )

    assert result.exit_code == 0, result.output
    assert ctx.videos.identify_calls == [{"title": "My Title", "imdb_id": "tt42969298"}]
    assert ctx.uploads.requests[0].video.movie.imdb_id == "tt42969298"

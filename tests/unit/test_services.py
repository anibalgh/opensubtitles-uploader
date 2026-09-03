"""Tests for application services using in-memory fakes of the ports."""

from __future__ import annotations

from pathlib import Path

import pytest

from opensubtitles_uploader.application.services import (
    AuthService,
    CatalogService,
    SubtitleService,
    UploadService,
    VideoService,
    build_upload_request,
    normalize_imdb_id,
)
from opensubtitles_uploader.domain.errors import FileNotSupportedError, ValidationError
from opensubtitles_uploader.domain.model import (
    Language,
    MediaInfo,
    MediaKind,
    MovieRef,
    SubtitleFile,
    UploadOutcome,
    UserInfo,
    VideoFile,
)

ENGLISH = Language(code="eng", iso639_1="en", name="English", native="English")


class FakeHasher:
    def movie_hash(self, path: Path) -> tuple[str, int]:
        return "ab" * 8, 1_234_567

    def md5(self, path: Path) -> str:
        return "cd" * 16


class FakeProbe:
    def probe(self, path: Path) -> MediaInfo:
        return MediaInfo(
            duration_ms=1_500_000, frame_rate=23.976, frame_count=35964, width=1920, height=1080
        )


class FakeCatalog:
    def __init__(self) -> None:
        self.movie = MovieRef(
            imdb_id="tt1375666", title="Inception", year=2010, kind=MediaKind.MOVIE
        )
        self.identified: MovieRef | None = None
        self.guesses: MovieRef | None = None
        self.searches: list[MovieRef] = []

    def identify(self, moviehash: str, moviebytesize: int) -> MovieRef | None:
        return self.identified

    def guess_movie(self, filename: str) -> MovieRef | None:
        return self.guesses

    def search_features(self, query: str) -> list[MovieRef]:
        return self.searches

    def feature_details(self, imdb_id: str) -> MovieRef | None:
        return self.movie if imdb_id == self.movie.imdb_id else None


class FakeDetector:
    def __init__(self, language: Language | None = None) -> None:
        self.language = language

    def detect(self, subtitle_path: Path) -> Language | None:
        return self.language


class FakeVault:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def set_secret(self, service: str, username: str, secret: str) -> None:
        self.data[f"{service}:{username}"] = secret

    def get_secret(self, service: str, username: str) -> str | None:
        return self.data.get(f"{service}:{username}")

    def delete_secret(self, service: str, username: str) -> None:
        self.data.pop(f"{service}:{username}", None)


class FakeSettings:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}

    def get(self, key: str, default: object = None) -> object:
        return self.data.get(key, default)

    def set(self, key: str, value: object) -> None:
        self.data[key] = value

    def delete(self, key: str) -> None:
        self.data.pop(key, None)


class FakeAuth:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.logins: list[tuple[str, str]] = []

    def login(self, username: str, password: str):
        self.logins.append((username, password))
        if not self.ok:
            from opensubtitles_uploader.domain.errors import AuthError

            raise AuthError("Wrong username or password")
        return type("S", (), {"user": UserInfo(user_id=1, username=username)})()  # type: ignore[return-value]

    def whoami(self) -> UserInfo:
        return UserInfo(user_id=1, username="alice")

    def logout(self) -> None:
        return None


class FakeUploader:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.outcome = UploadOutcome(
            state="created", url="https://www.opensubtitles.org/subtitles/1"
        )

    def upload(self, **kwargs):
        self.calls.append(kwargs)
        return self.outcome


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _video_path(tmp_path: Path) -> Path:
    video = tmp_path / "Inception.2010.1080p.mkv"
    video.write_bytes(b"\x00" * 1024)
    return video


def _make_video(**overrides) -> VideoFile:
    data = dict(
        path=Path("/tmp/movie.mkv"),
        name="movie.mkv",
        size_bytes=1_234_567,
        os_hash="ab" * 8,
    )
    data.update(overrides)
    return VideoFile(**data)  # type: ignore[arg-type]


def _make_subtitle(**overrides) -> SubtitleFile:
    data = dict(
        path=Path("/tmp/movie.eng.srt"),
        name="movie.eng.srt",
        size_bytes=10_000,
        md5="cd" * 16,
        language=ENGLISH,
    )
    data.update(overrides)
    return SubtitleFile(**data)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_normalize_imdb_id():
    assert normalize_imdb_id("1375666") == "tt1375666"
    assert normalize_imdb_id("tt1375666") == "tt1375666"
    assert normalize_imdb_id("https://www.imdb.com/title/tt1375666/") == "tt1375666"
    with pytest.raises(ValidationError):
        normalize_imdb_id("")  # type: ignore[arg-type]


def test_auth_service_login_and_restore():
    vault, settings = FakeVault(), FakeSettings()
    service = AuthService(FakeAuth(), vault, settings)
    user = service.login("alice", "secret", remember=True)
    assert user.username == "alice"
    assert settings.get("os_user") == "alice"
    assert vault.get_secret("opensubtitles-uploader", "alice") == "secret"
    assert service.restore() is not None


def test_auth_service_validation():
    service = AuthService(FakeAuth(), FakeVault(), FakeSettings())
    with pytest.raises(ValidationError):
        service.login("", "secret")
    with pytest.raises(ValidationError):
        service.login("alice", "")


def test_auth_logout_clears_credentials():
    vault, settings = FakeVault(), FakeSettings()
    service = AuthService(FakeAuth(), vault, settings)
    service.login("alice", "secret")
    service.logout()
    assert settings.get("os_user") is None
    assert vault.get_secret("opensubtitles-uploader", "alice") is None


def test_video_analyze_fills_fields(tmp_path):
    path = _video_path(tmp_path)
    catalog = FakeCatalog()
    catalog.identified = MovieRef(imdb_id="tt1375666", title="Inception", year=2010)
    service = VideoService(FakeHasher(), FakeProbe(), catalog)
    video = service.analyze(path)
    assert video.name == path.name
    assert video.size_bytes == 1_234_567
    assert video.os_hash == "ab" * 8
    assert video.media.height == 1080
    assert video.movie is not None and video.movie.imdb_id == "tt1375666"
    assert video.hd is True


def test_video_analyze_rejects_unsupported(tmp_path):
    bad = tmp_path / "video.exe"
    bad.write_bytes(b"x" * 100)
    service = VideoService(FakeHasher(), FakeProbe(), FakeCatalog())
    with pytest.raises(FileNotSupportedError):
        service.analyze(bad)


def test_video_identify_falls_back_to_search(tmp_path):
    path = _video_path(tmp_path)
    catalog = FakeCatalog()
    catalog.searches = [MovieRef(imdb_id="tt1375666", title="Inception", year=2010)]
    service = VideoService(FakeHasher(), FakeProbe(), catalog)
    video = service.analyze(path)  # no direct identification
    assert video.movie is None
    identified = service.identify(video)
    assert identified.movie is not None and identified.movie.imdb_id == "tt1375666"


def test_subtitle_analyze_detects_flags(tmp_path):
    sub = tmp_path / "movie.eng.srt"
    sub.write_text(
        "(sound) (laugh) (music) (rain) (door) (steps) (wind) (phone) (cry) (bang) (whisper) "
        "hello world this is fine",
        encoding="utf-8",
    )
    service = SubtitleService(FakeHasher(), FakeDetector(ENGLISH))
    analysed = service.analyze(sub)
    assert analysed.md5 == "cd" * 16
    assert analysed.language == ENGLISH
    assert analysed.hearing_impaired is True
    assert analysed.machine_translated is False


def test_upload_service_maps_fields():
    video = _make_video()
    subtitle = _make_subtitle()
    request = build_upload_request(
        video,
        subtitle,
        language=ENGLISH,
        release_name="My.Release",
        comment="hi",
        hearing_impaired=True,
    )
    uploader = FakeUploader()
    service = UploadService(uploader, FakeCatalog())
    outcome = service.upload(request)
    assert outcome.succeeded
    call = uploader.calls[0]
    assert call["moviehash"] == video.os_hash
    assert call["moviebytesize"] == video.size_bytes
    assert call["language"] == "eng"
    assert call["subtitle_path"] == subtitle.path
    assert call["hearing_impaired"] is True
    assert call["comment"] == "hi"
    assert call["movie_filename"] == video.name
    assert call["subhash"] == subtitle.md5
    # video has no movie: imdb_id must be None
    assert call["imdb_id"] is None


def test_upload_service_requires_language():
    subtitle = _make_subtitle(language=None)
    request = build_upload_request(_make_video(), subtitle)
    service = UploadService(FakeUploader(), FakeCatalog())
    with pytest.raises(ValidationError):
        service.upload(request)


def test_catalog_service_search_and_details():
    catalog = FakeCatalog()
    service = CatalogService(catalog)
    with pytest.raises(ValidationError):
        service.search("   ")
    assert service.details("tt1375666") is not None  # type: ignore[arg-type]

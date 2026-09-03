"""Application ports.

The ports are the contracts the core depends on.  They are declared as
``typing.Protocol`` so any adapter implementing the same shape (the real
OpenSubtitles REST client, in-memory fakes in tests, a mock media probe…)
can be injected at the composition root.  Nothing here imports adapters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from opensubtitles_uploader.domain.model import (
    ExistingMatch,
    Language,
    MediaInfo,
    MovieRef,
    Session,
    UploadOutcome,
    UserInfo,
)

# --------------------------------------------------------------------------
# Driven ports — the core calls *out* through these
# --------------------------------------------------------------------------


class OpenSubtitlesAuth(Protocol):
    """Authentication with the OpenSubtitles service."""

    def login(self, username: str, password: str) -> Session: ...

    def whoami(self) -> UserInfo: ...

    def logout(self) -> None: ...


class OpenSubtitlesCatalog(Protocol):
    """Movie identification and search capabilities."""

    def identify(self, moviehash: str, moviebytesize: int) -> MovieRef | None:
        """Map an OpenSubtitles movie hash to a movie reference (if known)."""

    def guess_movie(self, filename: str) -> MovieRef | None:
        """Best-effort identification from a file name alone."""

    def search_features(self, query: str) -> list[MovieRef]:
        """Full-text search of movies / shows / episodes."""

    def feature_details(self, imdb_id: str) -> MovieRef | None:
        """Fetch detailed metadata (title/year/kind/season/episode)."""


class OpenSubtitlesUploader(Protocol):
    """Upload-side operations."""

    def check_existing(
        self, moviehash: str, moviebytesize: int, subhash: str | None = None
    ) -> list[ExistingMatch]:
        """Ask the service whether this video/subtitle is already known."""

    def upload(
        self,
        *,
        moviehash: str,
        moviebytesize: int,
        language: str,
        subtitle_path: Path,
        imdb_id: str | None = None,
        movie_filename: str | None = None,
        release_name: str | None = None,
        fps: float | None = None,
        duration_ms: int | None = None,
        frames: int | None = None,
        hearing_impaired: bool | None = None,
        machine_translation: bool | None = None,
        foreign_parts_only: bool | None = None,
        high_definition: bool | None = None,
        translator: str | None = None,
        comment: str | None = None,
        subhash: str | None = None,
    ) -> UploadOutcome: ...


class OpenSubtitlesInfo(Protocol):
    """Reference data (subtitle languages)."""

    def languages(self) -> list[Language]: ...


class FileHasher(Protocol):
    """Compute hashes over local files."""

    def movie_hash(self, path: Path) -> tuple[str, int]:
        """Return (OpenSubtitles movie hash, size in bytes)."""

    def md5(self, path: Path) -> str:
        """Return the MD5 digest of a file (used for subtitle content)."""


class MediaProbe(Protocol):
    """Extract technical metadata from a media file (best effort)."""

    def probe(self, path: Path) -> MediaInfo: ...


class LanguageDetector(Protocol):
    """Detect the language of a subtitle from content and file name."""

    def detect(self, subtitle_path: Path) -> Language | None: ...


class BackdropProvider(Protocol):
    """Find decorative artwork for a movie reference (best effort)."""

    def get_backdrop(self, movie: MovieRef) -> str | None: ...


class SettingsStore(Protocol):
    """Persistent non-secret application settings."""

    def get(self, key: str, default: object = None) -> object: ...

    def set(self, key: str, value: object) -> None: ...

    def delete(self, key: str) -> None: ...


class SecretStore(Protocol):
    """Secure storage for credentials (OS keyring when available)."""

    def set_secret(self, service: str, username: str, secret: str) -> None: ...

    def get_secret(self, service: str, username: str) -> str | None: ...

    def delete_secret(self, service: str, username: str) -> None: ...


# --------------------------------------------------------------------------
# Convenience composite used by driving adapters (UI/CLI)
# --------------------------------------------------------------------------


class OpenSubtitlesGateway(
    OpenSubtitlesAuth,
    OpenSubtitlesCatalog,
    OpenSubtitlesUploader,
    OpenSubtitlesInfo,
    Protocol,
):  # pragma: no cover - structural composite
    """A single client implementing every OpenSubtitles capability."""

"""Domain model: entities and value objects.

Pure Python — only ``dataclasses``, ``enum`` and ``pathlib``.  No web
frameworks, no ORM, no I/O beyond representing paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path


class MediaKind(StrEnum):
    MOVIE = "movie"
    SHOW = "show"
    EPISODE = "episode"


@dataclass(frozen=True)
class MediaInfo:
    """Technical media characteristics extracted from a video file."""

    duration_ms: int | None = None
    frame_rate: float | None = None
    frame_count: int | None = None
    width: int | None = None
    height: int | None = None

    @property
    def hd(self) -> bool | None:
        """Best-effort high-definition inference (mirrors the original app)."""
        if self.height is None and self.width is None:
            return None
        height = self.height or 0
        width = self.width or 0
        # Letterboxed/cropped 1080p can go as low as 536px of height.
        return height >= 720 or (width >= 1280 and height >= 536)


@dataclass(frozen=True)
class MovieRef:
    """A movie / show / episode reference (typically from OpenSubtitles)."""

    imdb_id: str
    title: str
    year: int | None = None
    kind: MediaKind | None = None
    season: int | None = None
    episode: int | None = None
    # Optional decorative backdrop used by the UI as placeholder art.
    backdrop_url: str | None = None

    def display_title(self) -> str:
        if self.kind == MediaKind.EPISODE and self.season is not None and self.episode is not None:
            return f"{self.title} S{self.season:02d}E{self.episode:02d}"
        base = self.title
        if self.year:
            base = f"{base} ({self.year})"
        return base


@dataclass(frozen=True)
class Language:
    """A subtitle language.

    ``code`` is the 3-letter OpenSubtitles legacy code (e.g. ``eng``),
    ``iso639_1`` is the two letter code (e.g. ``en``), used by the
    current REST API, and ``name``/``native`` are display strings.
    """

    code: str
    iso639_1: str
    name: str
    native: str | None = None

    def display(self) -> str:
        return self.native if self.native and self.native != self.name else self.name


@dataclass(frozen=True)
class UserInfo:
    """Public profile information for a logged-in user."""

    user_id: int
    username: str
    level: str = ""
    vip: bool = False
    upload_capable: bool = False


@dataclass(frozen=True)
class Session:
    """An authenticated OpenSubtitles session."""

    token: str
    user: UserInfo
    base_url: str = "https://api.opensubtitles.com/api/v1"


@dataclass(frozen=True)
class VideoFile:
    """A local video file, analysed and ready to be paired with subtitles."""

    path: Path
    name: str
    size_bytes: int
    os_hash: str
    media: MediaInfo = field(default_factory=MediaInfo)
    movie: MovieRef | None = None

    @property
    def hd(self) -> bool:
        """Name-based fallback (like the original) or media-based truth."""
        if self.media.hd is not None:
            return self.media.hd
        return _name_suggests_hd(self.name)


@dataclass(frozen=True)
class SubtitleFile:
    """A local subtitle file with its detected properties."""

    path: Path
    name: str
    size_bytes: int
    md5: str
    language: Language | None = None
    hearing_impaired: bool = False
    machine_translated: bool = False
    foreign_parts_only: bool = False


@dataclass(frozen=True)
class SubtitleFlags:
    """Optional flags a user can force on the subtitle being uploaded."""

    hearing_impaired: bool | None = None
    machine_translated: bool | None = None
    foreign_parts_only: bool | None = None


@dataclass(frozen=True)
class UploadRequest:
    """Everything required (and optional) to upload one subtitle.

    ``video`` provides moviehash/size/name/technical metadata; the rest are
    user-editable fields mirrored from the original application.
    """

    video: VideoFile
    subtitle: SubtitleFile
    language: Language | None = None
    movie_aka: str | None = None
    release_name: str | None = None
    high_definition: bool | None = None
    translator: str | None = None
    comment: str | None = None
    flags: SubtitleFlags = field(default_factory=SubtitleFlags)

    @property
    def effective_language(self) -> Language | None:
        return self.language or self.subtitle.language

    def with_flags(
        self,
        *,
        hearing_impaired: bool | None = None,
        machine_translated: bool | None = None,
        foreign_parts_only: bool | None = None,
    ) -> UploadRequest:
        return replace(
            self,
            flags=SubtitleFlags(
                hearing_impaired=(
                    hearing_impaired
                    if hearing_impaired is not None
                    else self.flags.hearing_impaired
                ),
                machine_translated=(
                    machine_translated
                    if machine_translated is not None
                    else self.flags.machine_translated
                ),
                foreign_parts_only=(
                    foreign_parts_only
                    if foreign_parts_only is not None
                    else self.flags.foreign_parts_only
                ),
            ),
        )


@dataclass(frozen=True)
class ExistingMatch:
    """One already-existing subtitle reported by the service."""

    subtitle_id: int
    url: str | None = None
    file_id: int | None = None
    lang_code: str | None = None
    movie_name: str | None = None
    # Which identifier matched (movie hash, file name, subtitle md5...).
    matched_by: tuple[str, ...] = ()


@dataclass(frozen=True)
class UploadOutcome:
    """Result of an upload attempt."""

    state: str  # "created" | "already_exists" | "failed"
    url: str | None = None
    message_code: str = "upload_ok"
    existing: list[ExistingMatch] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.state == "created"


def _name_suggests_hd(filename: str) -> bool:
    lowered = filename.lower()
    if "720p" in lowered or "1080p" in lowered or "1080i" in lowered:
        return True
    has_rip = "dvdrip" in lowered or "dvd.rip" in lowered
    if has_rip and "1080" not in lowered and "720" not in lowered:
        return False
    return False

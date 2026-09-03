"""Media probing adapter.

Best-effort extraction of technical metadata (duration, frame rate, frame
count, resolution) from a video file.  Tries, in order:

1. the ``mediainfo`` CLI (``--Output=JSON``);
2. the ``ffprobe`` CLI (from FFmpeg);

and gracefully returns an empty :class:`MediaInfo` when neither is
installed or the file cannot be probed — mirroring the original
application, for which mediainfo data was optional.
"""

from __future__ import annotations

import json
import shutil
import subprocess  # nosec B404
from fractions import Fraction
from pathlib import Path
from typing import Any

from opensubtitles_uploader.domain.model import MediaInfo

_TIMEOUT = 25  # seconds


def _parse_duration_clock(value: str) -> int | None:
    """Parse ``HH:MM:SS.mmm`` (or ``MM:SS.mmm``) into milliseconds."""
    parts = value.strip().split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
        elif len(parts) == 2:
            hours, minutes, seconds = 0, int(parts[0]), float(parts[1])
        else:
            return round(float(parts[0]) * 1000)
        return round((hours * 3600 + minutes * 60 + seconds) * 1000)
    except (ValueError, IndexError):
        return None


def _as_float(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _as_int(value: object) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _parse_fraction(value: str) -> float | None:
    try:
        return float(Fraction(value.strip()))
    except (ZeroDivisionError, ValueError):
        return _as_float(value)


class CommandLineMediaProbe:
    """Default :class:`MediaProbe` implementation (mediainfo/ffprobe)."""

    def __init__(self, mediainfo_bin: str | None = None, ffprobe_bin: str | None = None) -> None:
        self._mediainfo = mediainfo_bin or shutil.which("mediainfo")
        self._ffprobe = ffprobe_bin or shutil.which("ffprobe")

    # -- public API --------------------------------------------------------
    def probe(self, path: Path) -> MediaInfo:
        if self._mediainfo:
            info = self._probe_mediainfo(path)
            if info.duration_ms or info.frame_rate or info.frame_count:
                return info
        if self._ffprobe:
            return self._probe_ffprobe(path)
        return MediaInfo()

    # -- mediainfo ---------------------------------------------------------
    def _probe_mediainfo(self, path: Path) -> MediaInfo:
        binary = self._mediainfo
        if not binary:
            return MediaInfo()
        try:
            result = subprocess.run(  # nosec B603
                [binary, "--Output=JSON", str(path)],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                check=False,
            )
            if result.returncode != 0:
                return MediaInfo()
            payload = json.loads(result.stdout)
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return MediaInfo()

        tracks = payload.get("media", {}).get("track", [])
        general: dict[str, Any] = next(
            (t for t in tracks if str(t.get("@type", "")).lower() == "general"), {}
        )
        video: dict[str, Any] = next(
            (t for t in tracks if str(t.get("@type", "")).lower() == "video"), {}
        )

        raw_duration = general.get("Duration")
        duration_ms = _parse_duration_clock(raw_duration) if raw_duration else None
        if duration_ms is None and video.get("Duration"):
            duration_ms = _parse_duration_clock(str(video["Duration"]))

        frame_rate = _as_float(video.get("FrameRate")) or _as_float(video.get("OriginalFrameRate"))
        if frame_rate is None and video.get("FrameRate_Num") and video.get("FrameRate_Den"):
            try:
                frame_rate = float(video["FrameRate_Num"]) / float(video["FrameRate_Den"])
            except (TypeError, ValueError, ZeroDivisionError):
                frame_rate = None

        frame_count = _as_int(video.get("FrameCount"))
        if frame_count is None and video.get("FrameCount_Num"):
            frame_count = _as_int(video.get("FrameCount_Num"))
        if frame_count is None and duration_ms and frame_rate:
            frame_count = round(duration_ms / 1000 * frame_rate)

        return MediaInfo(
            duration_ms=duration_ms,
            frame_rate=round(frame_rate, 3) if frame_rate else None,
            frame_count=frame_count,
            width=_as_int(video.get("Width")),
            height=_as_int(video.get("Height")),
        )

    # -- ffprobe ------------------------------------------------------------
    def _probe_ffprobe(self, path: Path) -> MediaInfo:
        binary = self._ffprobe
        if not binary:
            return MediaInfo()
        try:
            result = subprocess.run(  # nosec B603
                [
                    binary,
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                check=False,
            )
            if result.returncode != 0:
                return MediaInfo()
            payload = json.loads(result.stdout)
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return MediaInfo()

        streams = payload.get("streams", [])
        video: dict[str, Any] = next((s for s in streams if s.get("codec_type") == "video"), {})
        duration_s = _as_float(video.get("duration")) or _as_float(
            payload.get("format", {}).get("duration")
        )
        duration_ms = round(duration_s * 1000) if duration_s else None

        frame_rate = None
        if video.get("r_frame_rate"):
            frame_rate = _parse_fraction(str(video["r_frame_rate"]))
        frame_count = _as_int(video.get("nb_frames"))
        if frame_count is None and duration_ms and frame_rate:
            frame_count = round(duration_ms / 1000 * frame_rate)

        return MediaInfo(
            duration_ms=duration_ms,
            frame_rate=round(frame_rate, 3) if frame_rate else None,
            frame_count=frame_count,
            width=_as_int(video.get("width")),
            height=_as_int(video.get("height")),
        )


def has_any_probe() -> bool:
    return shutil.which("mediainfo") is not None or shutil.which("ffprobe") is not None

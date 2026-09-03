"""Rules for pairing a video file with its subtitle.

Used to auto-discover a sibling subtitle when a video is dropped, and the
reverse — replicating the auto-detection of the original application with
saner token semantics.

Rule: after removing the extension (and, for subtitles, an optional
trailing language tag such as ``.eng``), the token lists of both names
are compared case-insensitively.  They pair when one list is a prefix of
the other — which covers ``Movie.eng.srt`` ⇄ ``Movie.2000.1080p.mkv`` —
and, when both names carry ``SxxEyy`` markers, the episode must match.
"""

from __future__ import annotations

import re
from pathlib import Path

from opensubtitles_uploader.domain.naming import episode_tag

# A trailing language tag such as ``.eng`` or ``.en`` between the base
# name and the extension of a subtitle ("Movie.eng.srt").
_LANG_TAG_RE = re.compile(r"\.(?P<tag>[a-z]{2,3})(?:[-_][a-z0-9]{2,8})?$", re.IGNORECASE)

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokens(value: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(value)]


def _subtitle_tokens(name: str) -> list[str]:
    stem = Path(name).stem
    match = _LANG_TAG_RE.search(stem)
    if match:
        stem = stem[: match.start()]
    return _tokens(stem)


def _video_tokens(name: str) -> list[str]:
    return _tokens(Path(name).stem)


def _is_prefix(shorter: list[str], longer: list[str]) -> bool:
    if not shorter or len(shorter) > len(longer):
        return False
    return longer[: len(shorter)] == shorter


def subtitle_matches_video(subtitle_name: str, video_name: str) -> bool:
    """Whether a subtitle file plausibly belongs to a video file."""
    sub = _subtitle_tokens(subtitle_name)
    vid = _video_tokens(video_name)
    if not sub or not vid:
        return False
    if not (_is_prefix(sub, vid) or _is_prefix(vid, sub)):
        return False
    sub_ep = episode_tag(subtitle_name)
    vid_ep = episode_tag(video_name)
    return sub_ep is None or vid_ep is None or sub_ep == vid_ep


def video_matches_subtitle(video_name: str, subtitle_name: str) -> bool:
    """Symmetrical convenience wrapper."""
    return subtitle_matches_video(subtitle_name, video_name)

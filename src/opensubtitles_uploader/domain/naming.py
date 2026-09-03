"""Movie-name heuristics: cleaning and episode matching.

These pure functions replicate the filename analysis of the original
NW.js application (clearing codecs/sources/quality tokens, extracting
``SxxEyy`` episode tags, computing IMDB-search queries).
"""

from __future__ import annotations

import re
from pathlib import Path

# Tokens that add no value to a human movie title.
_QUALITY_RE = re.compile(r"(400|480|720|1080)[pix]", re.IGNORECASE)
_CODEC_RE = re.compile(r"[xh]26\d|hevc|xvid|divx", re.IGNORECASE)
_SOURCE_RE = re.compile(
    r"bluray|bdrip|brrip|dsr|dvdrip|dvd.rip|hdtv|\Wts\W|telesync|\Wcam\W|web-?dl|webrip",
    re.IGNORECASE,
)
_SPECIAL_RE = re.compile(r"\Wextended\W|\Wproper", re.IGNORECASE)

_IGNORED_WORDS = frozenset({"the", "an", "a", "of", "in", "and"})
_YEAR_RE = re.compile(r"(19|20)\d{2}")


def episode_tag(name: str) -> tuple[int, int] | None:
    """Extract ``(season, episode)`` from a name.

    Understands both ``S01E02`` and ``1x02`` spellings; returns ``None``
    when the name carries no episode marker.
    """
    sxe = re.search(r"\bS(\d{1,2})E(\d{1,3})\b", name, re.IGNORECASE)
    if sxe:
        return int(sxe.group(1)), int(sxe.group(2))
    num = re.search(r"\b(\d{1,2})x(\d{1,3})\b", name, re.IGNORECASE)
    if num:
        return int(num.group(1)), int(num.group(2))
    return None


def clean_movie_name(filename: str) -> str:
    """Return a human-readable title candidate from a release file name."""
    stem = Path(filename).stem
    title = stem
    title = _QUALITY_RE.sub("", title)
    title = _CODEC_RE.sub("", title)
    title = _SOURCE_RE.sub("", title)
    title = _SPECIAL_RE.sub("", title)
    title = re.sub(r"[._\-]+", " ", title)
    title = re.sub(r"\[[^]]*\]", "", title)
    title = re.sub(r"\([^)]*\)", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def significant_words(title: str, limit: int = 4) -> list[str]:
    """Most informative words of a title, for pre-filling a search box."""
    words: list[str] = []
    for word in title.split():
        low = word.lower()
        if low in _IGNORED_WORDS:
            continue
        if _YEAR_RE.fullmatch(word):
            continue
        words.append(low)
        if len(words) == limit:
            break
    return words

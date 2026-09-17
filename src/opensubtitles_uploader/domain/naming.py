"""Movie-name heuristics: cleaning and episode matching.

These pure functions replicate the filename analysis of the original
NW.js application (clearing codecs/sources/quality tokens, extracting
``SxxEyy`` episode tags, computing IMDB-search queries).
"""

from __future__ import annotations

import re
from pathlib import Path

# Tokens that add no value to a human movie title.
_QUALITY_RE = re.compile(r"(400|480|720|1080|2160)[pix]|\b4k\b", re.IGNORECASE)
_CODEC_RE = re.compile(r"[xh]26\d|hevc|xvid|divx", re.IGNORECASE)
_SOURCE_RE = re.compile(
    r"bluray|bdrip|brrip|dsr|dvdrip|dvd.rip|hdtv|\Wts\W|telesync|\Wcam\W|web-?dl|webrip",
    re.IGNORECASE,
)
_SPECIAL_RE = re.compile(r"\Wextended\W|\Wproper", re.IGNORECASE)

_IGNORED_WORDS = frozenset({"the", "an", "a", "of", "in", "and"})
_YEAR_RE = re.compile(r"(19|20)\d{2}")

# Identifiers embedded in release names and folders:
#   [imdbid-tt42969298]   {imdb-tt42969298}   imdbid=tt42969298   tt42969298
_IMDB_MARKER_RE = re.compile(r"imdb(?:id)?[\s._\-=:]*?tt(\d{5,9})", re.IGNORECASE)
_IMDB_BARE_RE = re.compile(r"(?<![0-9A-Za-z])tt(\d{5,9})(?![0-9A-Za-z])", re.IGNORECASE)

# Media extensions stripped when reading a title from a file name.
_MEDIA_EXT_RE = re.compile(
    r"\.(?:mkv|mp4|m4v|avi|mov|m2ts|ts|webm|flv|wmv|mpg|mpeg|mp2|vob|srt|sub|ass|ssa|smi|txt)$",
    re.IGNORECASE,
)

# Episode markers removed from a title (``S01E02`` / ``1x02``).
_EPISODE_TAG_RE = re.compile(r"\bS\d{1,2}E\d{1,3}\b|\b\d{1,2}x\d{1,3}\b", re.IGNORECASE)


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


def _strip_release_tokens(text: str) -> str:
    """Remove quality/codec/source/identifier noise from a release string."""
    text = _QUALITY_RE.sub("", text)
    text = _CODEC_RE.sub("", text)
    text = _SOURCE_RE.sub("", text)
    text = _SPECIAL_RE.sub("", text)
    text = re.sub(r"[._\-]+", " ", text)
    text = re.sub(r"\[[^]]*\]", "", text)
    text = re.sub(r"\{[^}]*\}", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_movie_name(filename: str) -> str:
    """Return a human-readable title candidate from a release file name."""
    return _strip_release_tokens(Path(filename).stem)


def extract_imdb_id(text: str) -> str | None:
    """Return the IMDb id embedded in a file or folder name, if any.

    Prefers an explicit ``imdb``/``imdbid`` marker, then a bare ``tt`` id, so
    it understands ``[imdbid-tt42969298]``, ``{imdb-tt42969298}``,
    ``imdbid=tt…`` and plain ``tt…`` spellings.  Returns ``None`` when the
    text carries no id.
    """
    if not text:
        return None
    marker = _IMDB_MARKER_RE.search(text)
    if marker:
        return f"tt{marker.group(1)}"
    bare = _IMDB_BARE_RE.search(text)
    if bare:
        return f"tt{bare.group(1)}"
    return None


def release_title(name: str) -> str:
    """Human-readable title/release name from a file **or** folder name.

    Unlike :func:`clean_movie_name` it never relies on ``Path.stem``, which
    would truncate a folder name at its last dot.  It strips
    ``{tvdb-…}``/``[imdbid-…]`` tokens and episode tags, so
    ``KAMUI.Hes.Behind.You.s01e09.mkv`` becomes ``KAMUI Hes Behind You``.
    """
    text = _MEDIA_EXT_RE.sub("", Path(name).name)
    text = _strip_release_tokens(text)
    text = _IMDB_BARE_RE.sub(" ", text)
    text = _EPISODE_TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip(" -_.")


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

"""Bundled language catalogue.

The authoritative language list is fetched from the service
(:meth:`~.osapi.client.OpenSubtitlesClient.languages`); this module
provides the offline fallback and the static tag lookup used by the
filename-based language detection.  Data comes from the original
application's ``os-lang.json`` (OSDb 3-letter codes + ISO 639-1).
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path

from opensubtitles_uploader.domain.model import Language

_DATA_RESOURCE = Path("data") / "os_languages.json"


@lru_cache(maxsize=1)
def bundled_languages() -> tuple[Language, ...]:
    """All languages shipped with the application (offline safe)."""
    text = (
        resources.files("opensubtitles_uploader")
        .joinpath(str(_DATA_RESOURCE))
        .read_text(encoding="utf-8")
    )
    entries = json.loads(text)
    return tuple(
        Language(
            code=str(entry["code"]),
            iso639_1=str(entry["iso6391"]),
            name=str(entry["name"]),
            native=str(entry.get("native") or entry["name"]),
        )
        for entry in entries
    )


@lru_cache(maxsize=1)
def bundled_language_index() -> dict[str, Language]:
    """Index by 3-letter code and by ISO 639-1 code (lowercase)."""
    index: dict[str, Language] = {}
    for language in bundled_languages():
        index[language.code.lower()] = language
        if language.iso639_1:
            index[language.iso639_1.lower()] = language
    return index


def language_by_tag(tag: str) -> Language | None:
    """Resolve a file-name tag (``eng``, ``en``, ``spa``…) to a language."""
    normalized = tag.strip().lower().lstrip(".")
    if not normalized:
        return None
    index = bundled_language_index()
    if normalized in index:
        return index[normalized]
    # Tolerate suffixes like ``en-US``, ``pt-br``.
    base = normalized.split("-")[0].split("_")[0]
    return index.get(base)

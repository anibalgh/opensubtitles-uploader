"""File hashing: the OpenSubtitles movie hash and content MD5.

The movie hash algorithm only reads the first and last 64 KiB of the file,
so hashing multi-gigabyte videos is instant.  Reference:
https://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from opensubtitles_uploader.domain.errors import FileNotSupportedError

CHUNK_SIZE = 65536  # 64 KiB
_UINT64_MASK = (1 << 64) - 1


def compute_movie_hash(path: str | Path) -> tuple[str, int]:
    """Return ``(movie_hash, size_bytes)`` for a video file."""
    file = Path(path)
    size = file.stat().st_size
    if size < CHUNK_SIZE * 2:
        raise FileNotSupportedError(
            "The file is too small to compute an OpenSubtitles movie hash.",
            code="file_too_small",
        )

    total = size  # file size is part of the hash

    def _sum_chunk(data: bytes) -> int:
        # Sum consecutive little-endian unsigned 64-bit words.
        total = 0
        for offset in range(0, len(data) - 7, 8):
            total = (total + int.from_bytes(data[offset : offset + 8], "little")) & _UINT64_MASK
        return total

    with file.open("rb") as handle:
        total = (total + _sum_chunk(handle.read(CHUNK_SIZE))) & _UINT64_MASK
        handle.seek(-CHUNK_SIZE, 2)  # relative to end
        total = (total + _sum_chunk(handle.read(CHUNK_SIZE))) & _UINT64_MASK

    return f"{total:016x}", size


def compute_md5(path: str | Path) -> str:
    """Return the hex MD5 digest of a file's content.

    MD5 is a content fingerprint required by the OpenSubtitles service;
    it is *not* used for security purposes.
    """
    digest = hashlib.md5(usedforsecurity=False)
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class LocalFileHasher:
    """Default :class:`FileHasher` implementation."""

    def movie_hash(self, path: Path) -> tuple[str, int]:
        return compute_movie_hash(path)

    def md5(self, path: Path) -> str:
        return compute_md5(path)

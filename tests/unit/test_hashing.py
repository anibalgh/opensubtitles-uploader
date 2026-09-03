"""Tests for the OpenSubtitles movie-hash and MD5 implementations."""

from __future__ import annotations

import hashlib
import os
import struct

import pytest

from opensubtitles_uploader.adapters.media.hashing import LocalFileHasher, compute_movie_hash
from opensubtitles_uploader.domain.errors import FileNotSupportedError

CHUNK = 65536
MASK = (1 << 64) - 1


def _make_file(path, size: int, head_word: int = 0, tail_word: int = 0) -> None:
    """Build a file of ``size`` zero bytes, optionally with non-zero first
    words in the head and tail 64 KiB chunks."""
    with open(path, "wb") as handle:
        handle.write(b"\x00" * size)
    if head_word:
        with open(path, "r+b") as handle:
            handle.seek(0)
            handle.write(struct.pack("<Q", head_word))
    if tail_word:
        with open(path, "r+b") as handle:
            handle.seek(size - CHUNK)
            handle.write(struct.pack("<Q", tail_word))


def test_movie_hash_of_zeros_is_filesize(tmp_path):
    size = CHUNK * 2
    file = tmp_path / "video.mkv"
    _make_file(file, size)
    digest, bytesize = compute_movie_hash(file)
    assert bytesize == size
    assert digest == f"{size & MASK:016x}"


def test_movie_hash_known_combination(tmp_path):
    size = 1024 * 1024
    head, tail = 0x1122334455667788, 0xDEADBEEFCAFEBABE
    file = tmp_path / "video.mp4"
    _make_file(file, size, head_word=head, tail_word=tail)
    digest, _ = compute_movie_hash(file)
    assert digest == f"{(size + head + tail) & MASK:016x}"


def test_movie_hash_randomized_matches_reference_algorithm(tmp_path):
    """Compare against a straightforward reference implementation."""
    size = CHUNK * 3 + 1234
    file = tmp_path / "video.avi"
    data = os.urandom(size)
    file.write_bytes(data)

    def reference() -> int:
        total = size
        for offset in (0, size - CHUNK):
            chunk = data[offset : offset + CHUNK]
            words = struct.unpack(f"<{len(chunk) // 8}Q", chunk)
            total = (total + sum(words)) & MASK
        return total

    digest, _ = compute_movie_hash(file)
    assert digest == f"{reference():016x}"


def test_movie_hash_rejects_too_small_files(tmp_path):
    file = tmp_path / "tiny.mkv"
    file.write_bytes(b"\x00" * (CHUNK * 2 - 1))
    with pytest.raises(FileNotSupportedError):
        compute_movie_hash(file)


def test_md5(tmp_path):
    file = tmp_path / "sub.srt"
    file.write_bytes(b"hello")
    hasher = LocalFileHasher()
    assert hasher.md5(file) == hashlib.md5(b"hello").hexdigest()

"""Tests for the pure domain rules (files / naming / pairing)."""

from __future__ import annotations

from opensubtitles_uploader.domain.files import (
    classify_file,
    has_foreign_only_markers,
    has_machine_translation_markers,
    likely_hearing_impaired,
)
from opensubtitles_uploader.domain.naming import clean_movie_name, episode_tag, significant_words
from opensubtitles_uploader.domain.pairing import subtitle_matches_video


def test_classify_file():
    assert classify_file("Movie.2020.1080p.mkv") == "video"
    assert classify_file("movie.eng.srt") == "subtitle"
    assert classify_file("notes.txt") == "subtitle"  # txt counts as subtitle
    assert classify_file("archive.zip") is None
    assert classify_file("") is None


def test_machine_translation_markers():
    assert has_machine_translation_markers("Movie auto translated by Google.srt")
    assert has_machine_translation_markers("babel fish translation")
    assert not has_machine_translation_markers("A completely normal subtitle")


def test_foreign_only_markers():
    assert has_foreign_only_markers("Movie.forced.srt")
    assert has_foreign_only_markers("Movie (foreign parts).srt")
    assert not has_foreign_only_markers("Movie.srt")


def test_hearing_impaired_heuristic():
    content = " ".join("(sound of rain)" for _ in range(12))
    assert likely_hearing_impaired(content)
    assert not likely_hearing_impaired("Hello world, how are you today?")


def test_episode_tag():
    assert episode_tag("Show.S01E02.mkv") == (1, 2)
    assert episode_tag("Show 1x03.mkv") == (1, 3)
    assert episode_tag("Movie 2020.mkv") is None


def test_clean_movie_name():
    cleaned = clean_movie_name("The.Movie.Title.2020.1080p.BluRay.x264-GROUP.mkv")
    assert "1080p" not in cleaned
    assert "BluRay" not in cleaned
    assert "x264" not in cleaned
    assert cleaned.lower().startswith("the movie title")


def test_significant_words():
    words = significant_words("The Great Movie of 1999 and Beyond")
    assert "the" not in words
    assert "1999" not in words
    assert "beyond" in words


def test_subtitle_video_pairing():
    assert subtitle_matches_video("Movie.Title.2020.eng.srt", "Movie.Title.2020.1080p.mkv")
    assert subtitle_matches_video("Movie.2000.eng.srt", "Movie.2000.mkv")
    assert subtitle_matches_video("show.s01e02.eng.srt", "show.s01e02.720p.mkv")
    # Same show but different episode must NOT pair.
    assert not subtitle_matches_video("show.s01e02.eng.srt", "show.s01e03.mkv")
    assert not subtitle_matches_video("other.movie.srt", "Movie.mkv")

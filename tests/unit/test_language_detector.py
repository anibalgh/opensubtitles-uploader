"""Tests for the heuristic subtitle language detector."""

from __future__ import annotations

from opensubtitles_uploader.adapters.media.dataset import bundled_language_index, language_by_tag
from opensubtitles_uploader.adapters.media.language_detector import HeuristicLanguageDetector

detector = HeuristicLanguageDetector()

ES_TEXT = (
    "el la los las de que y en un una es por con no a su al lo como más pero sus le ya o este sí "
    "porque esta entre cuando muy sin sobre también me hasta hay donde quien desde todo nos durante "
    "todos uno les ni contra otros ese eso ante ellos e esto mí antes algunos qué unos yo otro otra "
    "él tanto esa estos mucho quienes nada muchos cual poco ella estar estas algunas algo nosotros "
) * 3

EN_TEXT = (
    "the and of to in is that it you he was for on are with as his they at be this have from or one "
    "had by but not what all were we when your can said there use an each which she do how their if "
    "will up other about out many then them these so some her would make like him into time has look "
    "two more write go see number no way could people than water been call who oil its now find long "
    "down day did get come made may part over new sound take only little work know place year live "
    "me back give most very after thing our just name good sentence man think say great where help "
    "through much before line right too mean old any same tell boy follow came want show also around "
) * 3

JA_TEXT = "こんにちは、これは日本語の字幕です。私はあなたを愛しています。" * 20


def test_spanish_content(tmp_path):
    sub = tmp_path / "pelicula.srt"
    sub.write_text(ES_TEXT, encoding="utf-8")
    language = detector.detect(sub)
    assert language is not None
    assert language.iso639_1 == "es"


def test_english_content(tmp_path):
    sub = tmp_path / "movie.srt"
    sub.write_text(EN_TEXT, encoding="utf-8")
    language = detector.detect(sub)
    assert language is not None
    assert language.iso639_1 == "en"


def test_japanese_script(tmp_path):
    sub = tmp_path / "movie.srt"
    sub.write_text(JA_TEXT, encoding="utf-8")
    language = detector.detect(sub)
    assert language is not None
    assert language.iso639_1 == "ja"


def test_filename_tag_fallback(tmp_path):
    sub = tmp_path / "movie.eng.srt"
    sub.write_text("blah blah gibberish content without real words zzz", encoding="utf-8")
    language = detector.detect(sub)
    assert language is not None
    assert language.code == "eng"
    assert language.iso639_1 == "en"


def test_no_language_detected(tmp_path):
    sub = tmp_path / "movie.srt"
    sub.write_text("1234567890 !!! ??? ...", encoding="utf-8")
    assert detector.detect(sub) is None


def test_dataset_lookup():
    index = bundled_language_index()
    assert index["eng"].name == "English"
    assert language_by_tag("en") is not None
    assert language_by_tag("es") is not None
    assert language_by_tag("pt-BR") is not None
    assert language_by_tag("zzz") is None

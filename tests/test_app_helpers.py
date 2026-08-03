import os

import pytest
from fastapi import HTTPException

import app


def test_normalize_lang_maps_common_variants():
    assert app._normalize_lang("en-US") == "en"
    assert app._normalize_lang("fr-fr") == "fr"
    assert app._normalize_lang("pt-BR") == "pt"
    assert app._normalize_lang("de") == "de"
    assert app._normalize_lang(None) == ""


def test_segment_to_text_prefers_words_over_text():
    segment = {
        "text": "fallback",
        "words": [{"word": " hello "}, {"word": "world"}, {"word": "   "}],
    }
    assert app._segment_to_text(segment) == "hello world"


def test_load_clip_segments_from_metadata_filters_and_relativizes():
    data = {
        "shorts": [{"start": 10, "end": 20}],
        "transcript": {
            "segments": [
                {"start": 8, "end": 11, "text": "ignored-left-overlap-only-text"},
                {"start": 10, "end": 12, "words": [{"word": "one"}]},
                {"start": 15, "end": 17, "words": [{"word": "two"}, {"word": "three"}]},
                {"start": 19.5, "end": 21, "text": "tail"},
                {"start": 30, "end": 31, "text": "out"},
            ]
        },
    }

    segments = app._load_clip_segments_from_metadata(data, 0)

    assert segments == [
        {"start": 0.0, "end": 1.0, "text": "ignored-left-overlap-only-text"},
        {"start": 0.0, "end": 2.0, "text": "one"},
        {"start": 5.0, "end": 7.0, "text": "two three"},
        {"start": 9.5, "end": 11.0, "text": "tail"},
    ]


def test_load_clip_segments_from_metadata_raises_for_missing_clip():
    with pytest.raises(HTTPException) as exc:
        app._load_clip_segments_from_metadata({"shorts": []}, 0)
    assert exc.value.status_code == 404


def test_resolve_social_platforms_uses_env_and_deduplicates(monkeypatch):
    monkeypatch.setenv("UPLOAD_POST_DEFAULT_PLATFORMS", "instagram, youtube,instagram,invalid")
    assert app._resolve_social_platforms(None) == ["instagram", "youtube"]


def test_resolve_social_platforms_rejects_when_none_valid():
    with pytest.raises(HTTPException) as exc:
        app._resolve_social_platforms(["invalid", "also-invalid"])
    assert exc.value.status_code == 400


def test_sweep_output_directory_skips_active_and_thumbnails(tmp_path, monkeypatch):
    old_ts = 1000
    now_ts = 5000

    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(app, "OUTPUT_SWEEP_MIN_AGE_SECONDS", 100)

    keep_active = tmp_path / "job-active"
    keep_active.mkdir()
    keep_thumb = tmp_path / "thumbnails"
    keep_thumb.mkdir()
    delete_dir = tmp_path / "old-dir"
    delete_dir.mkdir()
    delete_file = tmp_path / "old-file.txt"
    delete_file.write_text("x", encoding="utf-8")

    os.utime(keep_active, (old_ts, old_ts))
    os.utime(keep_thumb, (old_ts, old_ts))
    os.utime(delete_dir, (old_ts, old_ts))
    os.utime(delete_file, (old_ts, old_ts))

    original_jobs = app.jobs
    try:
        app.jobs = {
            "j1": {
                "status": "processing",
                "output_dir": str(keep_active),
            }
        }
        removed = app._sweep_output_directory(now_ts)
    finally:
        app.jobs = original_jobs

    assert removed == 2
    assert keep_active.exists()
    assert keep_thumb.exists()
    assert not delete_dir.exists()
    assert not delete_file.exists()


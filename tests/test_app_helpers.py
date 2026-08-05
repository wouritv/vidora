import asyncio
import json
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


def test_sanitize_input_filename_strips_signed_url_query_params():
    assert app._sanitize_input_filename(
        "output/job/clip.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=abc"
    ) == "clip.mp4"


def test_sanitize_input_filename_accepts_plain_filename_and_rejects_empty():
    assert app._sanitize_input_filename("  clip.mp4  ") == "clip.mp4"
    assert app._sanitize_input_filename("") is None
    assert app._sanitize_input_filename(None) is None


def test_translate_clip_works_without_in_memory_job(tmp_path, monkeypatch):
    job_id = "job-translate"
    output_dir = tmp_path / job_id
    output_dir.mkdir(parents=True)

    metadata_path = output_dir / "sample_metadata.json"
    clip_path = output_dir / "clip_1.mp4"
    clip_path.write_bytes(b"video")

    metadata = {
        "transcript": {
            "language": "en",
            "segments": [
                {
                    "start": 0,
                    "end": 2,
                    "words": [
                        {"word": "Hello", "start": 0, "end": 1},
                        {"word": "world", "start": 1, "end": 2},
                    ],
                }
            ],
        },
        "shorts": [
            {
                "start": 0,
                "end": 2,
                "video_url": f"/videos/{job_id}/clip_1.mp4",
            }
        ],
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(app, "jobs", {})
    monkeypatch.setattr(
        app,
        "_translate_segments_with_fallback",
        lambda segments, _source_lang, _target_lang: [
            {**segment, "text": f"FR: {segment['text']}"} for segment in segments
        ],
    )

    def fake_burn_subtitles(_video_path, _srt_path, output_path, **_kwargs):
        with open(output_path, "wb") as handle:
            handle.write(b"translated-video")
        return True

    monkeypatch.setattr(app, "burn_subtitles", fake_burn_subtitles)

    req = app.TranslateRequest(
        job_id=job_id,
        clip_index=0,
        target_language="fr",
        input_filename="clip_1.mp4",
    )

    result = asyncio.run(app.translate_clip(req))

    assert result["success"] is True
    assert result["mode"] == "subtitles_only"
    assert result["target_language"] == "fr"
    assert result["new_video_url"].endswith("translated_fr_clip_1.mp4")

    updated = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert updated["shorts"][0]["translated_subtitles_language"] == "fr"
    assert updated["shorts"][0]["video_url"].endswith("translated_fr_clip_1.mp4")
    assert len(updated.get("translation_cache", {})) == 1


def test_translate_segments_with_cache_reuses_cached_entries(monkeypatch):
    segments = [
        {"start": 0.0, "end": 1.0, "text": "hello"},
        {"start": 1.0, "end": 2.0, "text": "world"},
    ]
    translation_cache = {
        app._build_translation_cache_key("en", "fr", "hello"): {
            "text": "bonjour",
            "provider": "openai",
        }
    }
    calls = []

    def fake_translate_with_fallback(items, _source_lang, _target_lang):
        calls.append([item["text"] for item in items])
        return [{**items[0], "text": f"FR: {items[0]['text']}", "provider": "gemini"}]

    monkeypatch.setattr(app, "_translate_segments_with_fallback", fake_translate_with_fallback)

    translated, cache_stats = app._translate_segments_with_cache(segments, "en", "fr", translation_cache)

    assert translated == [
        {"start": 0.0, "end": 1.0, "text": "bonjour", "provider": "openai"},
        {"start": 1.0, "end": 2.0, "text": "FR: world", "provider": "gemini"},
    ]
    assert cache_stats == {"hits": 1, "misses": 1}
    assert calls == [["world"]]
    assert len(translation_cache) == 2


def test_translate_captions_persists_and_reuses_translation_cache(tmp_path, monkeypatch):
    job_id = "job-caption-cache"
    output_dir = tmp_path / job_id
    output_dir.mkdir(parents=True)

    metadata_path = output_dir / "sample_metadata.json"
    metadata = {
        "transcript": {
            "language": "en",
            "segments": [
                {
                    "start": 0,
                    "end": 2,
                    "words": [
                        {"word": "Hello", "start": 0, "end": 1},
                        {"word": "world", "start": 1, "end": 2},
                    ],
                }
            ],
        },
        "shorts": [
            {
                "start": 0,
                "end": 2,
                "video_url": f"/videos/{job_id}/clip_1.mp4",
            }
        ],
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))

    call_count = {"value": 0}

    def fake_translate_with_fallback(segments, _source_lang, _target_lang):
        call_count["value"] += 1
        return [{**segment, "text": f"FR: {segment['text']}", "provider": "openai"} for segment in segments]

    monkeypatch.setattr(app, "_translate_segments_with_fallback", fake_translate_with_fallback)

    req = app.TranslateRequest(job_id=job_id, clip_index=0, target_language="fr")

    first_result = asyncio.run(app.translate_captions(req))
    second_result = asyncio.run(app.translate_captions(req))

    assert first_result["success"] is True
    assert first_result["cache"] == {"hits": 0, "misses": 1}
    assert second_result["cache"] == {"hits": 1, "misses": 0}
    assert call_count["value"] == 1

    updated = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert len(updated.get("translation_cache", {})) == 1


def test_translated_segments_to_caption_words_distributes_word_timing():
    captions = app._translated_segments_to_caption_words([
        {"start": 0.0, "end": 1.2, "text": "bonjour le monde"},
        {"start": 1.2, "end": 2.0, "text": "salut"},
    ])

    assert captions == [
        {"text": "bonjour", "startMs": 0, "endMs": 400},
        {"text": "le", "startMs": 400, "endMs": 800},
        {"text": "monde", "startMs": 800, "endMs": 1200},
        {"text": "salut", "startMs": 1200, "endMs": 2000},
    ]



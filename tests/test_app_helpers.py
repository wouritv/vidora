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
    monkeypatch.setenv("SOCIAL_DEFAULT_PLATFORMS", "instagram, youtube,instagram,invalid")
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


def test_encrypt_then_decrypt_token_roundtrip(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "unit-test-key")
    original = "abc.123.token"
    encrypted = app._encrypt_token(original)
    assert encrypted
    assert encrypted != original
    assert app._decrypt_token(encrypted) == original


def test_extract_token_data_handles_tiktok_nested_shape():
    token_data = {
        "data": {
            "access_token": "tk_access",
            "refresh_token": "tk_refresh",
            "expires_in": 7200,
            "scope": "video.publish user.info.basic",
        }
    }
    parsed = app._extract_token_data("tiktok", token_data)
    assert parsed["access_token"] == "tk_access"
    assert parsed["refresh_token"] == "tk_refresh"
    assert parsed["expires_in"] == 7200


def test_is_token_expiring_for_missing_or_invalid_expires_at():
    assert app._is_token_expiring({}) is True
    assert app._is_token_expiring({"expires_at": "not-a-date"}) is True


def test_enforce_subscription_retention_policy_resets_balances_after_deadline(monkeypatch):
    user_id = "user-retention"
    old_end = (app.datetime.now(app.timezone.utc) - app.timedelta(days=10)).isoformat()
    latest = {"id": "sub-1", "payment_end_date": old_end, "account_disabled_at": None}
    calls = {"set": 0, "history": 0, "update": 0}

    monkeypatch.setattr(app, "STORAGE_RETENTION_PERIODE_DAYS", 7)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)

    async def fake_get_user_abonnement(_user_id):
        return None

    async def fake_get_latest(_user_id):
        return latest

    async def fake_get_user_data(_user_id):
        return {"credit": 120.0, "stockage": 4.5}

    async def fake_set_balance(**_kwargs):
        calls["set"] += 1
        return {}

    async def fake_insert_history(**kwargs):
        calls["history"] += 1
        assert kwargs["operation_type"] == "subscription_expiration"
        assert kwargs["credit"] == 120.0
        assert kwargs["storage"] == 4.5
        return {}

    async def fake_update_row(_sub_id, updates):
        calls["update"] += 1
        assert "retention_deadline_at" in updates
        return {**latest, **updates}

    monkeypatch.setattr(app, "get_user_abonnement", fake_get_user_abonnement)
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", fake_get_latest)
    monkeypatch.setattr(app, "supabase_get_user_data", fake_get_user_data)
    monkeypatch.setattr(app, "supabase_set_user_data_balance", fake_set_balance)
    monkeypatch.setattr(app, "supabase_insert_user_data_history", fake_insert_history)
    monkeypatch.setattr(app, "supabase_update_souscription_row", fake_update_row)

    result = asyncio.run(app._enforce_subscription_retention_policy(user_id))

    assert result["state"] == "disabled"
    assert calls == {"set": 1, "history": 1, "update": 1}


def test_buy_credits_checkout_requires_active_subscription(monkeypatch):
    class DummyRequest:
        headers = {"X-User-Id": "user-1"}

    async def fake_policy(_user_id):
        return {"state": "no_subscription"}

    monkeypatch.setattr(app, "_require_stripe_ready", lambda: None)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_enforce_subscription_retention_policy", fake_policy)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(app.buy_credits_checkout(DummyRequest(), app.BuyCreditsRequest(amount_usd=5)))

    assert exc.value.status_code == 403
    assert "abonnement actif" in exc.value.detail.lower()



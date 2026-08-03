import pytest

import translate
from translate import SUPPORTED_LANGUAGES, get_supported_languages


def test_get_supported_languages_returns_copy():
    langs = get_supported_languages()
    assert langs == SUPPORTED_LANGUAGES
    assert langs is not SUPPORTED_LANGUAGES


def test_get_supported_languages_contains_common_entries():
    langs = get_supported_languages()
    assert langs["en"] == "English"
    assert langs["es"] == "Spanish"
    assert langs["fr"] == "French"


def test_translate_video_polls_until_dubbed(monkeypatch):
    monkeypatch.setattr(
        translate,
        "create_dubbing_project",
        lambda **_kwargs: {"dubbing_id": "dub-1", "expected_duration_sec": 10},
    )

    statuses = iter([
        {"status": "dubbing"},
        {"status": "dubbed"},
    ])
    monkeypatch.setattr(translate, "get_dubbing_status", lambda *_args, **_kwargs: next(statuses))
    monkeypatch.setattr(
        translate,
        "download_dubbed_video",
        lambda **_kwargs: "/tmp/final.mp4",
    )
    monkeypatch.setattr(translate.time, "sleep", lambda *_args, **_kwargs: None)

    out = translate.translate_video(
        video_path="in.mp4",
        output_path="out.mp4",
        target_language="fr",
        api_key="k",
        max_wait_seconds=10,
        poll_interval=0,
    )
    assert out == "/tmp/final.mp4"


def test_translate_video_raises_on_failed_status(monkeypatch):
    monkeypatch.setattr(
        translate,
        "create_dubbing_project",
        lambda **_kwargs: {"dubbing_id": "dub-2", "expected_duration_sec": 10},
    )
    monkeypatch.setattr(translate, "get_dubbing_status", lambda *_args, **_kwargs: {"status": "failed", "error": "quota"})
    monkeypatch.setattr(translate.time, "sleep", lambda *_args, **_kwargs: None)

    with pytest.raises(Exception, match="Dubbing failed: quota"):
        translate.translate_video(
            video_path="in.mp4",
            output_path="out.mp4",
            target_language="fr",
            api_key="k",
            max_wait_seconds=10,
            poll_interval=0,
        )


def test_translate_video_times_out(monkeypatch):
    monkeypatch.setattr(
        translate,
        "create_dubbing_project",
        lambda **_kwargs: {"dubbing_id": "dub-3", "expected_duration_sec": 10},
    )
    monkeypatch.setattr(translate, "get_dubbing_status", lambda *_args, **_kwargs: {"status": "dubbing"})
    monkeypatch.setattr(translate.time, "sleep", lambda *_args, **_kwargs: None)

    ticks = iter([0, 1, 3])
    monkeypatch.setattr(translate.time, "time", lambda: next(ticks))

    with pytest.raises(Exception, match="timed out"):
        translate.translate_video(
            video_path="in.mp4",
            output_path="out.mp4",
            target_language="fr",
            api_key="k",
            max_wait_seconds=2,
            poll_interval=0,
        )

import os

os.environ.setdefault("SECRET_KEY", "test-secret")

import app


def test_detect_bad_take_candidates_falls_back_to_heuristic_when_ai_disabled(monkeypatch):
    monkeypatch.setenv("AUTO_EDIT_BAD_TAKE_AI", "false")
    transcript = {
        "segments": [
            {"start": 1.0, "end": 2.0, "text": "um um we should restart"},
        ]
    }

    candidates = app._detect_bad_take_candidates(transcript)

    assert len(candidates) == 1
    assert candidates[0]["reason"] == "filler hesitation"
    assert candidates[0]["start"] < 1.0
    assert candidates[0]["end"] > 2.0


def test_parse_bad_take_candidates_response_accepts_fenced_json():
    raw = """```json
    {"candidates": [{"start": 1.2, "end": 2.4, "reason": "false start", "confidence": 0.87}]}
    ```"""

    parsed = app._parse_bad_take_candidates_response(raw)

    assert parsed == [{"start": 1.2, "end": 2.4, "reason": "false start", "confidence": 0.87}]


def test_sanitize_bad_take_candidates_clamps_and_merges_ranges():
    raw_candidates = [
        {"start": -1, "end": 2.0, "reason": "false start", "confidence": 1.2},
        {"start": 1.8, "end": 3.0, "reason": "false start", "confidence": 0.7},
        {"start": 4.0, "end": 3.9, "reason": "bad", "confidence": 0.3},
    ]

    sanitized = app._sanitize_bad_take_candidates(raw_candidates, max_end=2.5)

    assert sanitized == [
        {"start": 0.0, "end": 2.5, "reason": "false start", "confidence": 1.0}
    ]


def test_detect_bad_take_candidates_prefers_ai_when_available(monkeypatch):
    transcript = {"segments": [{"start": 0.0, "end": 1.0, "text": "text"}]}
    expected = [{"start": 0.1, "end": 0.8, "reason": "restart", "confidence": 0.78}]

    monkeypatch.setattr(app, "_detect_bad_take_candidates_ai", lambda _t: expected)
    monkeypatch.setattr(app, "_detect_bad_take_candidates_heuristic", lambda _t: [])

    candidates = app._detect_bad_take_candidates(transcript)

    assert candidates == expected


from ia_captions import _clean_json, _normalize_segments, _srt_timestamp


def test_srt_timestamp_rounds_to_milliseconds():
    assert _srt_timestamp(0) == "00:00:00,000"
    assert _srt_timestamp(1.2344) == "00:00:01,234"
    assert _srt_timestamp(3661.9) == "01:01:01,900"


def test_normalize_segments_filters_empty_and_invalid_segments():
    transcript = {
        "segments": [
            {"start": 0, "end": 1.5, "text": "  hello  "},
            {"start": 2, "end": 2, "text": "skip"},
            {"start": 3, "end": 4, "text": "   "},
            {"start": 5, "end": 6, "text": "world"},
        ]
    }
    assert _normalize_segments(transcript) == [
        {"start": 0.0, "end": 1.5, "text": "hello"},
        {"start": 5.0, "end": 6.0, "text": "world"},
    ]


def test_clean_json_strips_code_fences():
    raw = "```json\n{\"hello\": true}\n```"
    assert _clean_json(raw) == '{"hello": true}'


def test_clean_json_returns_trimmed_text_when_not_fenced():
    assert _clean_json("  plain text  ") == "plain text"



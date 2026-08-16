from ia_captions import (
    _clean_json,
    _generate_caption_texts,
    _normalize_segments,
    _srt_timestamp,
    _upload_post_payload,
)


class _FakeOpenAIResponse:
    def __init__(self, content):
        self.choices = [type("Choice", (), {"message": type("Msg", (), {"content": content})()})()]


class _FakeOpenAIClient:
    def __init__(self, *_args, **_kwargs):
        pass

    @property
    def chat(self):
        class _Chat:
            class completions:
                @staticmethod
                def create(**_kwargs):
                    return _FakeOpenAIResponse(
                        "```json\n{\"captions\":[{\"index\":1,\"text\":\"Hook line\"}]}\n```"
                    )

        return _Chat()


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


def test_upload_post_payload_sets_platform_specific_fields():
    payload = _upload_post_payload(
        final_title="My Reel",
        final_description="Description",
        platforms=["tiktok", "youtube", "linkedin", "facebook"],
        user_id="u123",
        scheduled_date="2026-08-04T10:00:00Z",
        timezone_name="Europe/Paris",
    )

    assert payload["user"] == "u123"
    assert payload["platform[]"] == ["tiktok", "youtube", "linkedin", "facebook"]
    assert payload["scheduled_date"] == "2026-08-04T10:00:00Z"
    assert payload["timezone"] == "Europe/Paris"
    assert payload["tiktok_title"] == "Description"
    assert payload["youtube_title"] == "My Reel"
    assert payload["youtube_description"] == "Description"
    assert payload["privacyStatus"] == "public"
    assert payload["linkedin_title"] == "My Reel"
    assert payload["facebook_description"] == "Description"


def test_generate_caption_texts_returns_original_when_no_keys():
    segments = [{"text": "Line 1"}, {"text": "Line 2"}]
    assert _generate_caption_texts(segments, "tiktok", gemini_key=None, openai_key=None) == ["Line 1", "Line 2"]


def test_generate_caption_texts_uses_openai_json_response(monkeypatch):
    import openai

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAIClient)
    segments = [{"text": "First"}, {"text": "Second"}]

    # Only index 1 is returned by the fake model; index 2 must fallback to source text.
    out = _generate_caption_texts(segments, "tiktok", gemini_key=None, openai_key="k")
    assert out == ["Hook line", "Second"]


def test_generate_caption_texts_falls_back_to_source_when_openai_fails(monkeypatch):
    import openai

    class _BrokenOpenAI:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(openai, "OpenAI", _BrokenOpenAI)
    segments = [{"text": "a"}, {"text": "b"}]
    assert _generate_caption_texts(segments, "tiktok", gemini_key=None, openai_key="k") == ["a", "b"]

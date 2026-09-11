import asyncio
import types
from unittest.mock import MagicMock

import pytest

import anonymous_stories as stories


# ---------------------------------------------------------------------------
# build_final_text
# ---------------------------------------------------------------------------

def test_build_final_text_joins_blocks_with_blank_lines():
    content = {
        "hook": "Hook line",
        "introduction": "Intro line",
        "story": "Story body",
        "questions": ["Question one?", "Question two?"],
    }
    text = stories.build_final_text(content)
    assert text == "Hook line\n\nIntro line\n\nStory body\n\nQuestion one?\nQuestion two?"


def test_build_final_text_skips_empty_blocks():
    content = {"hook": "", "introduction": "  ", "story": "Story only", "questions": []}
    assert stories.build_final_text(content) == "Story only"


def test_build_final_text_handles_completely_empty_content():
    assert stories.build_final_text({}) == ""


# ---------------------------------------------------------------------------
# validate_generated_story_payload
# ---------------------------------------------------------------------------

def _valid_payload(**overrides):
    payload = {
        "is_story": True,
        "confidence": 0.9,
        "has_personal_experience": True,
        "hook": "Hook",
        "introduction": "Intro",
        "story": "A real story",
        "questions": ["What would you do?"],
    }
    payload.update(overrides)
    return payload


def test_validate_generated_story_payload_accepts_well_formed_output():
    normalized = stories.validate_generated_story_payload(_valid_payload())
    assert normalized["is_story"] is True
    assert normalized["story"] == "A real story"
    assert normalized["full_text"] == stories.build_final_text(normalized)


def test_validate_generated_story_payload_rejects_non_dict():
    with pytest.raises(stories.StoryValidationError) as exc_info:
        stories.validate_generated_story_payload("not a dict")
    assert exc_info.value.code == stories.AnonymousStoryErrorCode.GENERATION_INVALID


def test_validate_generated_story_payload_rejects_missing_field():
    payload = _valid_payload()
    del payload["hook"]
    with pytest.raises(stories.StoryValidationError) as exc_info:
        stories.validate_generated_story_payload(payload)
    assert exc_info.value.code == stories.AnonymousStoryErrorCode.GENERATION_INVALID


def test_validate_generated_story_payload_flags_not_a_story():
    payload = _valid_payload(is_story=False, reason="No personal experience found")
    with pytest.raises(stories.StoryValidationError) as exc_info:
        stories.validate_generated_story_payload(payload)
    assert exc_info.value.code == stories.AnonymousStoryErrorCode.NOT_A_STORY
    assert "No personal experience found" in str(exc_info.value)


def test_validate_generated_story_payload_rejects_empty_questions():
    payload = _valid_payload(questions=[])
    with pytest.raises(stories.StoryValidationError) as exc_info:
        stories.validate_generated_story_payload(payload)
    assert exc_info.value.code == stories.AnonymousStoryErrorCode.GENERATION_INVALID


def test_validate_generated_story_payload_rejects_empty_story_body():
    payload = _valid_payload(story="   ")
    with pytest.raises(stories.StoryValidationError):
        stories.validate_generated_story_payload(payload)


def test_validate_generated_story_payload_strips_and_filters_questions():
    payload = _valid_payload(questions=["  Real question?  ", "   ", ""])
    normalized = stories.validate_generated_story_payload(payload)
    assert normalized["questions"] == ["Real question?"]


def test_validate_generated_story_payload_keeps_model_provided_title():
    payload = _valid_payload(title="  Mon mari veut que je demissionne  ")
    normalized = stories.validate_generated_story_payload(payload)
    assert normalized["title"] == "Mon mari veut que je demissionne"


def test_validate_generated_story_payload_derives_title_when_missing():
    payload = _valid_payload(hook="Il m'a annonce qu'il voulait divorcer devant toute la famille")
    normalized = stories.validate_generated_story_payload(payload)
    assert normalized["title"]
    assert normalized["title"] == stories.derive_fallback_title({"hook": payload["hook"]})


# ---------------------------------------------------------------------------
# derive_fallback_title
# ---------------------------------------------------------------------------

def test_derive_fallback_title_truncates_long_hook_with_ellipsis():
    content = {"hook": "Un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze"}
    title = stories.derive_fallback_title(content)
    assert title.endswith("…")
    assert len(title.split()) <= 13  # 12 words + possible trailing punctuation stripped


def test_derive_fallback_title_uses_story_when_hook_missing():
    content = {"hook": "", "story": "Elle a decouvert la verite trop tard"}
    title = stories.derive_fallback_title(content)
    assert title == "Elle a decouvert la verite trop tard"


def test_derive_fallback_title_returns_empty_for_empty_content():
    assert stories.derive_fallback_title({}) == ""


# ---------------------------------------------------------------------------
# validate_edited_story_content
# ---------------------------------------------------------------------------

def test_validate_edited_story_content_accepts_partial_edit():
    normalized = stories.validate_edited_story_content({
        "hook": "",
        "introduction": "",
        "story": "Edited story text",
        "questions": ["One question?"],
    })
    assert normalized["story"] == "Edited story text"
    assert normalized["full_text"] == "Edited story text\n\nOne question?"


def test_validate_edited_story_content_rejects_empty_story():
    with pytest.raises(stories.StoryValidationError):
        stories.validate_edited_story_content({"story": "   ", "questions": []})


def test_validate_edited_story_content_rejects_non_list_questions():
    with pytest.raises(stories.StoryValidationError):
        stories.validate_edited_story_content({"story": "ok", "questions": "not a list"})


# ---------------------------------------------------------------------------
# find_possible_identifying_leftovers
# ---------------------------------------------------------------------------

def test_find_possible_identifying_leftovers_detects_email():
    leftovers = stories.find_possible_identifying_leftovers("Contact me at jane.doe@example.com please")
    assert "email" in leftovers


def test_find_possible_identifying_leftovers_detects_phone_number():
    leftovers = stories.find_possible_identifying_leftovers("Appelle moi au 06 12 34 56 78 vite")
    assert "phone_number" in leftovers


def test_find_possible_identifying_leftovers_clean_text_returns_empty():
    leftovers = stories.find_possible_identifying_leftovers("Ceci est une histoire anonyme sans coordonnees.")
    assert leftovers == []


# ---------------------------------------------------------------------------
# generate_story_from_transcript (network call mocked)
# ---------------------------------------------------------------------------

def test_generate_story_from_transcript_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        asyncio.run(stories.generate_story_from_transcript("some transcript"))


def test_generate_story_from_transcript_validates_and_attaches_usage(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    fake_message = types.SimpleNamespace(content='{"is_story": true, "confidence": 0.8, '
                                                   '"has_personal_experience": true, "hook": "H", '
                                                   '"introduction": "I", "story": "S", "questions": ["Q?"]}')
    fake_choice = types.SimpleNamespace(message=fake_message)
    fake_usage = types.SimpleNamespace(prompt_tokens=100, completion_tokens=50)
    fake_response = types.SimpleNamespace(choices=[fake_choice], usage=fake_usage)

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response
    monkeypatch.setattr(stories, "_get_openai_client", lambda: fake_client)

    result = asyncio.run(stories.generate_story_from_transcript("A transcript"))

    assert result["story"] == "S"
    assert result["usage"]["prompt_tokens"] == 100
    assert result["usage"]["completion_tokens"] == 50


def test_generate_story_from_transcript_raises_validation_error_on_bad_json(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    fake_message = types.SimpleNamespace(content="not json at all")
    fake_choice = types.SimpleNamespace(message=fake_message)
    fake_response = types.SimpleNamespace(choices=[fake_choice], usage=None)

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response
    monkeypatch.setattr(stories, "_get_openai_client", lambda: fake_client)

    with pytest.raises(stories.StoryValidationError) as exc_info:
        asyncio.run(stories.generate_story_from_transcript("A transcript"))
    assert exc_info.value.code == stories.AnonymousStoryErrorCode.GENERATION_INVALID


# ---------------------------------------------------------------------------
# transcribe_video (network call mocked out at the config level)
# ---------------------------------------------------------------------------

def test_transcribe_video_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        asyncio.run(stories.transcribe_video("/tmp/does-not-matter.mp4"))

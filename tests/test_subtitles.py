import pytest

import subtitles
from subtitles import format_srt_block, generate_srt, hex_to_ass_color


def test_format_srt_block_formats_standard_timestamp():
    block = format_srt_block(1, 1.234, 65.008, "Hello world")
    assert block == "1\n00:00:01,234 --> 00:01:05,007\nHello world\n\n"


def test_format_srt_block_pads_hours_minutes_seconds():
    block = format_srt_block(12, 3661.9, 3662.1, "Test")
    assert "01:01:01" in block


@pytest.mark.parametrize(
    "hex_color,opacity,expected",
    [
        ("#FFFFFF", 1.0, "&H00FFFFFF"),
        ("#000000", 0.0, "&HFF000000"),
        ("#123456", 0.5, "&H80563412"),
        ("bad-value", 1.0, "&H00FFFFFF"),
    ],
)
def test_hex_to_ass_color(hex_color, opacity, expected):
    assert hex_to_ass_color(hex_color, opacity) == expected


def test_generate_srt_returns_false_when_no_words_in_range(tmp_path):
    transcript = {"segments": [{"words": [{"word": "hello", "start": 0.0, "end": 0.5}]}]}
    out = tmp_path / "empty.srt"

    ok = generate_srt(transcript, clip_start=10, clip_end=12, output_path=str(out))

    assert ok is False
    assert not out.exists()


def test_generate_srt_groups_words_by_limits(tmp_path):
    transcript = {
        "segments": [
            {
                "words": [
                    {"word": "hello", "start": 1.0, "end": 1.4},
                    {"word": "world", "start": 1.5, "end": 1.9},
                    {"word": "again", "start": 2.1, "end": 2.5},
                ]
            }
        ]
    }
    out = tmp_path / "clip.srt"

    ok = generate_srt(
        transcript,
        clip_start=1.0,
        clip_end=3.0,
        output_path=str(out),
        max_chars=11,  # forces a split before adding "again"
        max_duration=3.0,
    )

    assert ok is True
    content = out.read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:00,899\nhello world\n\n" in content
    assert "2\n00:00:01,100 --> 00:00:01,500\nagain\n\n" in content


def test_extract_words_in_range_filters_overlap_only():
    transcript = {
        "segments": [
            {"words": [
                {"word": "before", "start": 0.0, "end": 0.5},
                {"word": "inside", "start": 1.0, "end": 1.5},
                {"word": "after", "start": 2.0, "end": 2.5},
            ]}
        ]
    }
    result = subtitles._extract_words_in_range(transcript, 0.8, 1.8)
    assert [item["word"] for item in result] == ["inside"]


def test_should_flush_block_conditions():
    block = [{"word": "one", "end": 1.0}, {"word": "two", "end": 1.2}]
    assert subtitles._should_flush_block([], 0.0, 1.0, "x", 20, 2.0, 4) is False
    assert subtitles._should_flush_block(block, 0.0, 3.5, "x", 50, 2.0, 10) is True
    assert subtitles._should_flush_block(block, 0.0, 1.5, "verylong", 5, 10.0, 10) is True
    assert subtitles._should_flush_block(block, 0.0, 1.5, "x", 50, 10.0, 2) is True


def test_flush_srt_block_handles_empty_and_non_empty():
    index, text = subtitles._flush_srt_block([], clip_start=0.0, block_start=0.0, index=1)
    assert index == 1
    assert text == ""

    block = [{"word": "hi", "end": 1.0}, {"word": "there", "end": 1.5}]
    index, text = subtitles._flush_srt_block(block, clip_start=0.5, block_start=0.2, index=1)
    assert index == 2
    assert "hi there" in text


def test_normalize_subtitle_text_case_upper_and_lower(tmp_path):
    srt_path = tmp_path / "sample.srt"
    srt_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello World\n\n", encoding="utf-8")

    subtitles._normalize_subtitle_text_case(str(srt_path), "uppercase")
    assert "HELLO WORLD" in srt_path.read_text(encoding="utf-8")

    subtitles._normalize_subtitle_text_case(str(srt_path), "lowercase")
    assert "hello world" in srt_path.read_text(encoding="utf-8")


def test_burn_subtitles_builds_command_and_returns_true(monkeypatch):
    captured = {}

    def fake_run(cmd, stdout=None, stderr=None, **kwargs):
        captured["cmd"] = cmd
        class _Result:
            returncode = 0
            stderr = b""
        return _Result()

    monkeypatch.setattr(subtitles, "_normalize_subtitle_text_case", lambda *args, **kwargs: None)
    monkeypatch.setattr(subtitles.subprocess, "run", fake_run)

    ok = subtitles.burn_subtitles("in.mp4", "/tmp/sub.srt", "out.mp4", alignment="top", fontsize=20)
    assert ok is True
    assert "ffmpeg" in captured["cmd"][0]
    assert "subtitles='" in captured["cmd"][5]


def test_burn_subtitles_raises_on_ffmpeg_error(monkeypatch):
    def fake_run(cmd, stdout=None, stderr=None, **kwargs):
        class _Result:
            returncode = 1
            stderr = b"boom"
        return _Result()

    monkeypatch.setattr(subtitles, "_normalize_subtitle_text_case", lambda *args, **kwargs: None)
    monkeypatch.setattr(subtitles.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError):
        subtitles.burn_subtitles("in.mp4", "/tmp/sub.srt", "out.mp4")



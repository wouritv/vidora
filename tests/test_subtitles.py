import pytest

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

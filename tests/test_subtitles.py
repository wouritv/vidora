import pytest

from subtitles import format_srt_block, hex_to_ass_color


def test_format_srt_block_formats_standard_timestamp():
    block = format_srt_block(1, 1.234, 65.008, "Hello world")
    assert block == "1\n00:00:01,233 --> 00:01:05,008\nHello world\n\n"


def test_format_srt_block_pads_hours_minutes_seconds():
    block = format_srt_block(12, 3661.9, 3662.1, "Test")
    assert "01:01:01" in block


@pytest.mark.parametrize(
    "hex_color,opacity,expected",
    [
        ("#FFFFFF", 1.0, "&H00FFFFFF"),
        ("#000000", 0.0, "&HFF000000"),
        ("#123456", 0.5, "&H80465412"),
        ("bad-value", 1.0, "&H00FFFFFF"),
    ],
)
def test_hex_to_ass_color(hex_color, opacity, expected):
    assert hex_to_ass_color(hex_color, opacity) == expected


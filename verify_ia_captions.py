from ia_captions import _normalize_segments, _srt_timestamp


def main() -> None:
    sample = {
        "segments": [
            {"start": 0.0, "end": 1.25, "text": " Hello world "},
            {"start": 1.25, "end": 2.5, "text": ""},
            {"start": 2.5, "end": 4.0, "text": "Next line"},
        ]
    }
    normalized = _normalize_segments(sample)

    assert len(normalized) == 2
    assert normalized[0]["text"] == "Hello world"
    assert _srt_timestamp(1.25) == "00:00:01,250"

    print("ia_captions smoke test: ok")


if __name__ == "__main__":
    main()


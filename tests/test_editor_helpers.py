from editor import VideoEditor


def test_split_filter_chain_respects_commas_inside_quotes():
    chain = "eq=contrast=1.1:enable='between(t,0,3)',hue=s=0:enable='between(t,3,5)'"
    parts = VideoEditor._split_filter_chain(chain)
    assert parts == [
        "eq=contrast=1.1:enable='between(t,0,3)'",
        "hue=s=0:enable='between(t,3,5)'",
    ]


def test_enforce_zoompan_output_size_replaces_or_adds_size():
    chain = "zoompan=z='1.1':d=1:fps=30:s=720x1280,eq=contrast=1.2"
    out = VideoEditor._enforce_zoompan_output_size(chain, 1080, 1920)
    assert "zoompan=z='1.1':d=1:fps=30:s=1080x1920" in out
    assert out.endswith(",eq=contrast=1.2")

    chain_no_size = "zoompan=z='1.2':d=1:fps=30"
    out_no_size = VideoEditor._enforce_zoompan_output_size(chain_no_size, 1080, 1920)
    assert out_no_size == "zoompan=z='1.2':d=1:fps=30:s=1080x1920"


def test_sanitize_filter_string_rewrites_comparisons():
    raw = "eq=contrast='if(t<3,1.2,1.0)':enable='on>=75',hue=s='if(on<=20,0,1)'"
    cleaned = VideoEditor._sanitize_filter_string(raw)

    assert "lt(t,3)" in cleaned
    assert "gte(on,75)" in cleaned
    assert "lte(on,20)" in cleaned
    assert "<" not in cleaned
    assert ">=" not in cleaned


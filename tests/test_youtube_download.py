import os
import types

import pytest

import youtube_download as ytdl


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------

def test_sanitize_filename_strips_invalid_characters_and_spaces():
    assert ytdl.sanitize_filename('My: Video? "Title" <2024>') == "My_Video_Title_2024"


def test_sanitize_filename_truncates_to_100_chars():
    long_name = "a" * 250
    assert len(ytdl.sanitize_filename(long_name)) == 100


# ---------------------------------------------------------------------------
# _build_ytdlp_opts -- this is the actual fix for "No supported JavaScript
# runtime could be found": mobile clients (android/ios) don't trigger
# YouTube's 'web' client JS/PO-Token challenge, and the bgutil PO-Token
# provider covers the cookie fallback path instead of needing a local JS
# runtime like deno.
# ---------------------------------------------------------------------------

def test_build_ytdlp_opts_without_cookies_uses_mobile_clients():
    opts = ytdl._build_ytdlp_opts(use_cookies=False, job_cookies_path=None, proxy_session_id=None)
    assert opts["extractor_args"]["youtube"]["player_client"] == ["android", "ios"]
    assert opts["cookiefile"] is None


def test_build_ytdlp_opts_with_cookies_uses_web_clients_and_cookiefile():
    opts = ytdl._build_ytdlp_opts(use_cookies=True, job_cookies_path="/tmp/cookies.txt", proxy_session_id=None)
    assert opts["extractor_args"]["youtube"]["player_client"] == ["mweb", "web"]
    assert opts["cookiefile"] == "/tmp/cookies.txt"


def test_build_ytdlp_opts_always_configures_the_pot_provider():
    opts = ytdl._build_ytdlp_opts(use_cookies=False, job_cookies_path=None, proxy_session_id=None)
    assert opts["extractor_args"]["youtubepot-bgutilhttp"] == {"base_url": "http://pot-provider:4416"}


def test_build_ytdlp_opts_appends_sticky_session_id_to_proxy(monkeypatch):
    monkeypatch.setenv("YOUTUBE_PROXY", "http://user:pass@proxy.example.com:8080")
    opts = ytdl._build_ytdlp_opts(use_cookies=False, job_cookies_path=None, proxy_session_id="abc123")
    assert opts["proxy"] == "http://user__sessid.abc123:pass@proxy.example.com:8080"


def test_build_ytdlp_opts_without_proxy_env_has_no_proxy(monkeypatch):
    monkeypatch.delenv("YOUTUBE_PROXY", raising=False)
    opts = ytdl._build_ytdlp_opts(use_cookies=False, job_cookies_path=None, proxy_session_id="abc123")
    assert opts["proxy"] is None


# ---------------------------------------------------------------------------
# _make_job_cookies_copy
# ---------------------------------------------------------------------------

def test_make_job_cookies_copy_returns_none_without_env(monkeypatch):
    monkeypatch.delenv("YOUTUBE_COOKIES", raising=False)
    assert ytdl._make_job_cookies_copy() is None


def test_make_job_cookies_copy_returns_none_for_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUTUBE_COOKIES", str(tmp_path / "does-not-exist.txt"))
    assert ytdl._make_job_cookies_copy() is None


def test_make_job_cookies_copy_copies_existing_file(monkeypatch, tmp_path):
    source = tmp_path / "cookies.txt"
    source.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setenv("YOUTUBE_COOKIES", str(source))

    job_copy = ytdl._make_job_cookies_copy()
    try:
        assert job_copy is not None
        assert job_copy != str(source)
        with open(job_copy, encoding="utf-8") as f:
            assert f.read() == "# Netscape HTTP Cookie File\n"
    finally:
        if job_copy:
            import os
            os.remove(job_copy)


# ---------------------------------------------------------------------------
# _locate_downloaded_file
# ---------------------------------------------------------------------------

def test_locate_downloaded_file_finds_exact_mp4(tmp_path):
    (tmp_path / "My_Title.mp4").write_bytes(b"data")
    assert ytdl._locate_downloaded_file(str(tmp_path), "My_Title") == str(tmp_path / "My_Title.mp4")


def test_locate_downloaded_file_falls_back_to_prefixed_match(tmp_path):
    (tmp_path / "My_Title.f137.mp4").write_bytes(b"data")
    found = ytdl._locate_downloaded_file(str(tmp_path), "My_Title")
    assert found == str(tmp_path / "My_Title.f137.mp4")


def test_locate_downloaded_file_returns_expected_path_when_nothing_found(tmp_path):
    found = ytdl._locate_downloaded_file(str(tmp_path), "Missing")
    assert found == str(tmp_path / "Missing.mp4")


# ---------------------------------------------------------------------------
# _looks_like_netscape_cookies
# ---------------------------------------------------------------------------

def test_looks_like_netscape_cookies_recognizes_header_and_data_rows():
    assert ytdl._looks_like_netscape_cookies("") is False
    assert ytdl._looks_like_netscape_cookies("# Netscape HTTP Cookie File\n") is True
    assert ytdl._looks_like_netscape_cookies("example.com\tTRUE\t/\tFALSE\t0\tname\tvalue") is True
    assert ytdl._looks_like_netscape_cookies("invalid line") is False
    assert ytdl._looks_like_netscape_cookies("# just comment\nsite\tTRUE\t/\tFALSE\t0\ta\tb") is True


# ---------------------------------------------------------------------------
# _resolve_cookiefile_from_env
# ---------------------------------------------------------------------------

def test_resolve_cookiefile_from_env_missing_or_placeholder(monkeypatch):
    monkeypatch.delenv("YOUTUBE_COOKIES", raising=False)
    assert ytdl._resolve_cookiefile_from_env() is None
    monkeypatch.setenv("YOUTUBE_COOKIES", "...")
    assert ytdl._resolve_cookiefile_from_env() is None


def test_resolve_cookiefile_from_env_reads_valid_path(monkeypatch, tmp_path):
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\nexample.com\tTRUE\t/\tFALSE\t0\tname\tvalue\n")
    monkeypatch.setenv("YOUTUBE_COOKIES", str(cookies_file))
    assert ytdl._resolve_cookiefile_from_env() == str(cookies_file)


def test_resolve_cookiefile_from_env_rejects_non_netscape_path(monkeypatch, tmp_path):
    bad_file = tmp_path / "cookies.txt"
    bad_file.write_text("not netscape at all")
    monkeypatch.setenv("YOUTUBE_COOKIES", str(bad_file))
    assert ytdl._resolve_cookiefile_from_env() is None


def test_resolve_cookiefile_from_env_writes_inline_content(monkeypatch, tmp_path):
    inline = "example.com\\tTRUE\\t/\\tFALSE\\t0\\tname\\tvalue"
    monkeypatch.setenv("YOUTUBE_COOKIES", inline)
    written_path = tmp_path / "cookies.txt"
    monkeypatch.setattr(ytdl, "_looks_like_netscape_cookies", lambda text: True)

    written = {}

    class _F:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, data):
            written["data"] = data

    monkeypatch.setattr("builtins.open", lambda *a, **k: _F())
    monkeypatch.setattr(os.path, "getsize", lambda p: 10)

    assert ytdl._resolve_cookiefile_from_env() == "/app/cookies.txt"
    assert "Netscape HTTP Cookie File" in written["data"]


def test_resolve_cookiefile_from_env_rejects_invalid_inline_content(monkeypatch):
    monkeypatch.setenv("YOUTUBE_COOKIES", "inline-no-tabs")
    monkeypatch.setattr(os.path, "isfile", lambda _p: False)
    assert ytdl._resolve_cookiefile_from_env() is None


def test_resolve_cookiefile_from_env_returns_none_on_read_error(monkeypatch):
    monkeypatch.setenv("YOUTUBE_COOKIES", "cookie_path")
    monkeypatch.setattr(os.path, "isfile", lambda _p: True)
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(OSError("read fail")))
    assert ytdl._resolve_cookiefile_from_env() is None


def test_resolve_cookiefile_from_env_returns_none_on_write_error(monkeypatch):
    monkeypatch.setenv("YOUTUBE_COOKIES", "a\\tb\\tc\\td\\te\\tf\\tg")
    monkeypatch.setattr(ytdl, "_looks_like_netscape_cookies", lambda _t: True)
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(OSError("no write")))
    assert ytdl._resolve_cookiefile_from_env() is None


# ---------------------------------------------------------------------------
# _extract_info_with_fallback
# ---------------------------------------------------------------------------

def test_extract_info_with_fallback_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    class _YDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download=False):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("first fail")
            return {"title": "ok"}

    monkeypatch.setattr(ytdl.yt_dlp, "YoutubeDL", _YDL, raising=False)
    info, opts = ytdl._extract_info_with_fallback("https://y.t", None, "sess")
    assert info["title"] == "ok"
    assert "extractor_args" in opts


def test_extract_info_with_fallback_raises_last_error(monkeypatch):
    class _YDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download=False):
            raise RuntimeError("blocked")

    monkeypatch.setattr(ytdl.yt_dlp, "YoutubeDL", _YDL, raising=False)
    with pytest.raises(RuntimeError, match="blocked"):
        ytdl._extract_info_with_fallback("https://y.t", None, "sess")


# ---------------------------------------------------------------------------
# _print_download_failure
# ---------------------------------------------------------------------------

def test_print_download_failure_sleeps_once(monkeypatch):
    slept = {"n": 0}
    monkeypatch.setattr(ytdl.time, "sleep", lambda _s: slept.__setitem__("n", slept["n"] + 1))
    ytdl._print_download_failure(RuntimeError("boom"))
    assert slept["n"] == 1


# ---------------------------------------------------------------------------
# download_youtube_video (full orchestration, internals mocked)
# ---------------------------------------------------------------------------

def test_download_youtube_video_success_and_cleanup(monkeypatch, tmp_path):
    cookie_file = tmp_path / "job_cookie.txt"
    cookie_file.write_text("x")

    monkeypatch.setattr(ytdl, "_make_job_cookies_copy", lambda: str(cookie_file))
    monkeypatch.setattr(ytdl, "_extract_info_with_fallback", lambda *args, **kwargs: ({"title": "My Video"}, {}))
    monkeypatch.setattr(ytdl, "_run_download", lambda *args, **kwargs: "/tmp/out.mp4")
    monkeypatch.setattr(ytdl, "sanitize_filename", lambda name: "My_Video")
    monkeypatch.setattr(ytdl, "yt_dlp", types.SimpleNamespace(version=types.SimpleNamespace(__version__="1.0")))

    removed = []
    monkeypatch.setattr(os.path, "exists", lambda p: str(p) == str(cookie_file))
    monkeypatch.setattr(os, "remove", lambda p: removed.append(p))

    file_path, title = ytdl.download_youtube_video("https://youtube.com/watch?v=abc", output_dir="/tmp")
    assert file_path == "/tmp/out.mp4"
    assert title == "My_Video"
    assert str(cookie_file) in removed


def test_download_youtube_video_prints_failure_and_raises(monkeypatch):
    monkeypatch.setattr(ytdl, "_make_job_cookies_copy", lambda: None)
    monkeypatch.setattr(ytdl, "_extract_info_with_fallback", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("blocked")))
    printer = {"called": 0}
    monkeypatch.setattr(ytdl, "_print_download_failure", lambda exc: printer.__setitem__("called", printer["called"] + 1))
    monkeypatch.setattr(ytdl, "yt_dlp", types.SimpleNamespace(version=types.SimpleNamespace(__version__="1.0")))
    with pytest.raises(RuntimeError):
        ytdl.download_youtube_video("https://youtube.com/watch?v=abc", output_dir="/tmp")
    assert printer["called"] == 1

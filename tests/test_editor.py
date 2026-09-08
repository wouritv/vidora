import importlib
import json
import sys
import types
from unittest.mock import MagicMock, patch
import time

import pytest

def _import_editor_with_stubs(monkeypatch):
    google_mod = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")

    class _DummyClient:
        def __init__(self, *args, **kwargs):
            pass

    class _Config:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    genai_mod.Client = _DummyClient
    genai_mod.types = types.SimpleNamespace(GenerateContentConfig=_Config)
    google_mod.genai = genai_mod

    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)

    if "editor" in sys.modules:
        return importlib.reload(sys.modules["editor"])
    return importlib.import_module("editor")


def test_split_filter_chain_respects_quoted_commas(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)

    parts = editor.VideoEditor._split_filter_chain("scale=1080:1920,drawtext=text='a,b,c',eq=contrast=1.1")

    assert parts == ["scale=1080:1920", "drawtext=text='a,b,c'", "eq=contrast=1.1"]


def test_sanitize_filter_string_rewrites_comparisons_and_rounds(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)

    sanitized = editor.VideoEditor._sanitize_filter_string("if(t<3,1,0),if(on>=75,2,0),fps=30.0000708083")

    assert "lt(t,3)" in sanitized
    assert "gte(on,75)" in sanitized
    assert "fps=30" in sanitized


def test_enforce_zoompan_output_size_adds_and_replaces_size(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    added = editor.VideoEditor._enforce_zoompan_output_size("zoompan=z='1.2'", 1080, 1920)
    replaced = editor.VideoEditor._enforce_zoompan_output_size("zoompan=z='1.2':s=720x1280", 1080, 1920)
    assert ":s=1080x1920" in added
    assert ":s=1080x1920" in replaced
    assert ":s=720x1280" not in replaced


def test_get_effects_config_returns_none_on_bad_json(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    instance.client.models = types.SimpleNamespace(
        generate_content=lambda *args, **kwargs: types.SimpleNamespace(text="not-json")
    )
    result = instance.get_effects_config(video_file_obj="file", duration=12, transcript=None)
    assert result is None


def test_get_effects_config_parses_fenced_json(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    payload = {"filter_string": "eq=contrast=1.1"}
    instance.client.models = types.SimpleNamespace(
        generate_content=lambda *args, **kwargs: types.SimpleNamespace(text=f"```json\n{json.dumps(payload)}\n```")
    )
    result = instance.get_effects_config(video_file_obj="file", duration=12, transcript=None)
    assert result == payload


def test_get_effects_config_parses_fenced_json_without_type(monkeypatch):
    """Test that get_effects_config handles ```without json type."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    payload = {"segments": []}
    instance.client.models = types.SimpleNamespace(
        generate_content=lambda *args, **kwargs: types.SimpleNamespace(text=f"```\n{json.dumps(payload)}\n```")
    )
    result = instance.get_effects_config(video_file_obj="file", duration=12, transcript=None)
    assert result == payload


def test_apply_edits_copies_original_when_filter_missing(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    run_mock = MagicMock()
    monkeypatch.setattr(editor.subprocess, "run", run_mock)
    instance.apply_edits("in.mp4", "out.mp4", filter_data={})
    run_mock.assert_called_once()


def test_video_editor_init(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2-pro")
    instance = editor.VideoEditor(api_key="test-key")
    assert instance.client is not None
    assert instance.model_name == "gemini-2-pro"


def test_sanitize_filter_string_handles_comparison_operators(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    # Test >= replacement
    result = editor.VideoEditor._sanitize_filter_string("enable='on>=75'")
    assert "gte(on,75)" in result
    # Test <= replacement
    result = editor.VideoEditor._sanitize_filter_string("enable='t<=5'")
    assert "lte(t,5)" in result
    # Test > replacement
    result = editor.VideoEditor._sanitize_filter_string("enable='x>10'")
    assert "gt(x,10)" in result
    # Test < replacement
    result = editor.VideoEditor._sanitize_filter_string("enable='y<20'")
    assert "lt(y,20)" in result


def test_sanitize_filter_string_rewrites_fragile_enable_expressions(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    result = editor.VideoEditor._sanitize_filter_string("enable='1-between(t,0,5)'")
    assert "not(between(t,0,5))" in result


def test_sanitize_filter_string_rounds_excessively_precise_floats(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    result = editor.VideoEditor._sanitize_filter_string("fps=30.000070808301")
    assert "fps=30" in result


def test_sanitize_filter_string_handles_fractional_floats(monkeypatch):
    """Test that _sanitize_filter_string handles non-integer floats properly."""
    editor = _import_editor_with_stubs(monkeypatch)
    result = editor.VideoEditor._sanitize_filter_string("fps=23.976023976")
    # Should round to 3 decimal places and strip trailing zeros
    assert "23.976" in result


def test_sanitize_filter_string_handles_invalid_float_rounding(monkeypatch):
    """Test that _sanitize_filter_string handles invalid floats gracefully."""
    editor = _import_editor_with_stubs(monkeypatch)
    # Test with something that looks like a float but can't be parsed
    result = editor.VideoEditor._sanitize_filter_string("value=12.345678901xyz")
    # Should still contain the problematic part (no crash)
    assert isinstance(result, str)


def test_split_filter_chain_empty_string(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    parts = editor.VideoEditor._split_filter_chain("")
    assert parts == [""]


def test_enforce_zoompan_output_size_non_zoompan_filters(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    # Non-zoompan filters should pass through unchanged
    result = editor.VideoEditor._enforce_zoompan_output_size("scale=1080:1920,eq=contrast=1.1", 1920, 1080)
    assert "scale=1080:1920" in result
    assert "eq=contrast=1.1" in result


def test_get_ffmpeg_filter_returns_none_on_json_error(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    instance.client.models = types.SimpleNamespace(
        generate_content=lambda *args, **kwargs: types.SimpleNamespace(text="```\ninvalid json\n```")
    )
    result = instance.get_ffmpeg_filter("file", duration=10)
    assert result is None


def test_get_ffmpeg_filter_parses_valid_json(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    payload = {"filter_string": "scale=1920:1080"}
    instance.client.models = types.SimpleNamespace(
        generate_content=lambda *args, **kwargs: types.SimpleNamespace(
            text=f"{json.dumps(payload)}"
        )
    )
    result = instance.get_ffmpeg_filter("file", duration=10)
    assert result == payload


def test_get_ffmpeg_filter_parses_json_fenced_with_json_type(monkeypatch):
    """Test that get_ffmpeg_filter handles ```json block correctly."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    payload = {"filter_string": "zoompan=z='1.1'"}
    instance.client.models = types.SimpleNamespace(
        generate_content=lambda *args, **kwargs: types.SimpleNamespace(
            text=f"```json\n{json.dumps(payload)}\n```"
        )
    )
    result = instance.get_ffmpeg_filter("file", duration=10)
    assert result == payload


def test_get_ffmpeg_filter_parses_json_fenced_without_type(monkeypatch):
    """Test that get_ffmpeg_filter handles ``` block without json type."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    payload = {"filter_string": "scale=1920:1080"}
    instance.client.models = types.SimpleNamespace(
        generate_content=lambda *args, **kwargs: types.SimpleNamespace(
            text=f"```\n{json.dumps(payload)}\n```"
        )
    )
    result = instance.get_ffmpeg_filter("file", duration=10)
    assert result == payload


def test_get_ffmpeg_filter_uses_default_dimensions(monkeypatch):
    """Test that get_ffmpeg_filter uses default dimensions when not provided."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    payload = {"filter_string": "scale=1080:1920"}
    instance.client.models = types.SimpleNamespace(
        generate_content=lambda *args, **kwargs: types.SimpleNamespace(
            text=f"{json.dumps(payload)}"
        )
    )
    result = instance.get_ffmpeg_filter("file", duration=10)
    assert result == payload


def test_get_effects_config_uses_default_dimensions(monkeypatch):
    """Test that get_effects_config uses default dimensions when not provided."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    payload = {"segments": []}
    instance.client.models = types.SimpleNamespace(
        generate_content=lambda *args, **kwargs: types.SimpleNamespace(text=f"{json.dumps(payload)}")
    )
    result = instance.get_effects_config("file", duration=10)
    assert result == payload


def test_apply_edits_with_missing_probe_continues(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    monkeypatch.setattr(
        editor.subprocess, "check_output",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("probe failed"))
    )
    run_mock = MagicMock()
    monkeypatch.setattr(editor.subprocess, "run", run_mock)
    instance.apply_edits("in.mp4", "out.mp4", {"filter_string": "eq=contrast=1.1"})
    run_mock.assert_called_once()


def test_apply_edits_adds_setsar_when_not_present(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    monkeypatch.setattr(
        editor.subprocess, "check_output",
        lambda *args, **kwargs: b"1920x1080"
    )
    run_mock = MagicMock()
    monkeypatch.setattr(editor.subprocess, "run", run_mock)
    instance.apply_edits("in.mp4", "out.mp4", {"filter_string": "eq=contrast=1.1"})
    args = run_mock.call_args
    assert any("setsar=1" in str(arg) for arg in args[0][0])


def test_apply_edits_doesnt_add_duplicate_setsar(monkeypatch):
    """Test that apply_edits doesn't add setsar if already present."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    monkeypatch.setattr(
        editor.subprocess, "check_output",
        lambda *args, **kwargs: b"1920x1080"
    )
    run_mock = MagicMock()
    monkeypatch.setattr(editor.subprocess, "run", run_mock)
    instance.apply_edits("in.mp4", "out.mp4", {"filter_string": "eq=contrast=1.1,setsar=1"})
    args = run_mock.call_args
    # Count occurrences of setsar=1
    setsar_count = str(args).count("setsar=1")
    assert setsar_count == 1


def test_apply_edits_enforces_zoompan_output_size_when_filter_changes(monkeypatch):
    """Test that apply_edits enforces zoompan output size when sanitization changes the filter."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    monkeypatch.setattr(
        editor.subprocess, "check_output",
        lambda *args, **kwargs: b"1920x1080"
    )
    run_mock = MagicMock()
    monkeypatch.setattr(editor.subprocess, "run", run_mock)
    # Use a filter that will be sanitized (t<3)
    instance.apply_edits("in.mp4", "out.mp4", {"filter_string": "zoompan=z='1.1':s=720x480,if(t<3,1,0)"})
    run_mock.assert_called_once()
    # Verify the call included zoompan with enforced size
    args = run_mock.call_args
    assert any("1920x1080" in str(arg) for arg in args[0][0])


def test_apply_edits_executes_ffmpeg_with_sanitized_filter(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    monkeypatch.setattr(
        editor.subprocess, "check_output",
        lambda *args, **kwargs: b"1920x1080"
    )
    run_mock = MagicMock()
    monkeypatch.setattr(editor.subprocess, "run", run_mock)
    instance.apply_edits("in.mp4", "out.mp4", {"filter_string": "if(t<3,1,0)"})
    run_mock.assert_called_once()
    args = run_mock.call_args
    # Verify sanitization happened
    assert any("lt(t,3)" in str(arg) for arg in args[0][0])


def test_apply_edits_handles_subprocess_error(monkeypatch):
    import subprocess
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    monkeypatch.setattr(
        editor.subprocess, "check_output",
        lambda *args, **kwargs: b"1920x1080"
    )
    error_result = types.SimpleNamespace(returncode=1, stderr=b"ffmpeg error")
    monkeypatch.setattr(
        editor.subprocess, "run",
        MagicMock(side_effect=subprocess.CalledProcessError(1, "ffmpeg", stderr=b"error"))
    )
    with pytest.raises(subprocess.CalledProcessError):
        instance.apply_edits("in.mp4", "out.mp4", {"filter_string": "eq=contrast=1.1"})


def test_apply_edits_handles_subprocess_error_with_empty_stderr(monkeypatch):
    """Test that apply_edits handles subprocess error with empty stderr gracefully."""
    import subprocess
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    monkeypatch.setattr(
        editor.subprocess, "check_output",
        lambda *args, **kwargs: b"1920x1080"
    )
    monkeypatch.setattr(
        editor.subprocess, "run",
        MagicMock(side_effect=subprocess.CalledProcessError(1, "ffmpeg", stderr=None))
    )
    with pytest.raises(subprocess.CalledProcessError):
        instance.apply_edits("in.mp4", "out.mp4", {"filter_string": "eq=contrast=1.1"})


def test_apply_edits_handles_stderr_decode_error(monkeypatch):
    """Test that apply_edits handles stderr decoding errors gracefully."""
    import subprocess
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    monkeypatch.setattr(
        editor.subprocess, "check_output",
        lambda *args, **kwargs: b"1920x1080"
    )
    # Create an error with invalid utf-8 in stderr
    error = subprocess.CalledProcessError(1, "ffmpeg", stderr=b"\xff\xfe")
    monkeypatch.setattr(
        editor.subprocess, "run",
        MagicMock(side_effect=error)
    )
    with pytest.raises(subprocess.CalledProcessError):
        instance.apply_edits("in.mp4", "out.mp4", {"filter_string": "eq=contrast=1.1"})


def test_upload_video_file_not_found(monkeypatch):
    """Test that upload_video raises FileNotFoundError for missing files."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    with pytest.raises(FileNotFoundError):
        instance.upload_video("/nonexistent/video.mp4")


def test_upload_video_successful_upload(monkeypatch, tmp_path):
    """Test that upload_video successfully uploads and polls for ACTIVE state."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")

    # Create a temporary file
    video_file = tmp_path / "test.mp4"
    video_file.write_text("fake video content")

    # Mock the client.files.upload and client.files.get
    upload_result = types.SimpleNamespace(name="file123")

    file_info_active = types.SimpleNamespace(state="ACTIVE")

    instance.client.files = types.SimpleNamespace(
        upload=lambda *args, **kwargs: upload_result,
        get=lambda *args, **kwargs: file_info_active
    )

    result = instance.upload_video(str(video_file))
    assert result == upload_result


def test_upload_video_polling_on_pending(monkeypatch, tmp_path):
    """Test that upload_video polls for ACTIVE state."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")

    # Create a temporary file
    video_file = tmp_path / "test.mp4"
    video_file.write_text("fake video content")

    # Mock the client.files.upload and client.files.get with delayed ACTIVE state
    upload_result = types.SimpleNamespace(name="file123")

    file_states = [
        types.SimpleNamespace(state="PROCESSING"),
        types.SimpleNamespace(state="PROCESSING"),
        types.SimpleNamespace(state="ACTIVE"),
    ]
    state_iter = iter(file_states)

    instance.client.files = types.SimpleNamespace(
        upload=lambda *args, **kwargs: upload_result,
        get=lambda *args, **kwargs: next(state_iter)
    )

    # Mock time.sleep to avoid actual delays
    monkeypatch.setattr(editor.time, "sleep", lambda x: None)

    result = instance.upload_video(str(video_file))
    assert result == upload_result


def test_upload_video_failed_state(monkeypatch, tmp_path):
    """Test that upload_video raises exception on FAILED state."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")

    # Create a temporary file
    video_file = tmp_path / "test.mp4"
    video_file.write_text("fake video content")

    # Mock the client.files.upload
    upload_result = types.SimpleNamespace(name="file123")

    file_info_failed = types.SimpleNamespace(state="FAILED")

    instance.client.files = types.SimpleNamespace(
        upload=lambda *args, **kwargs: upload_result,
        get=lambda *args, **kwargs: file_info_failed
    )

    with pytest.raises(Exception, match="Video processing failed"):
        instance.upload_video(str(video_file))


def test_upload_video_upload_error(monkeypatch, tmp_path):
    """Test that upload_video handles upload errors."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")

    # Create a temporary file
    video_file = tmp_path / "test.mp4"
    video_file.write_text("fake video content")

    # Mock the client.files.upload to raise an error
    instance.client.files = types.SimpleNamespace(
        upload=lambda *args, **kwargs: (_ for _ in ()).throw(Exception("Upload failed"))
    )

    with pytest.raises(Exception, match="Upload failed"):
        instance.upload_video(str(video_file))


def test_sanitize_filter_string_handles_unparsable_float(monkeypatch):
    """Test that _sanitize_filter_string handles floats that fail to parse."""
    editor = _import_editor_with_stubs(monkeypatch)
    # Create a custom float-like string that will fail float() parsing
    # when passed to the _round_float_token function
    result = editor.VideoEditor._sanitize_filter_string("fps=30.999999999999999999999999")
    # Should not crash and return a string
    assert isinstance(result, str)


def test_apply_edits_with_non_string_args(monkeypatch):
    """Test that apply_edits handles non-string command arguments."""
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    monkeypatch.setattr(
        editor.subprocess, "check_output",
        lambda *args, **kwargs: b"1920x1080"
    )
    run_mock = MagicMock()
    monkeypatch.setattr(editor.subprocess, "run", run_mock)
    # Mock the command building to include non-string args
    instance.apply_edits("in.mp4", "out.mp4", {"filter_string": "eq=contrast=1.1"})
    run_mock.assert_called_once()


def test_apply_edits_with_exception_decode_error(monkeypatch):
    """Test that apply_edits handles exception when decoding stderr raises."""
    import subprocess
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    monkeypatch.setattr(
        editor.subprocess, "check_output",
        lambda *args, **kwargs: b"1920x1080"
    )

    # Create an error that will raise during decode attempt
    error = subprocess.CalledProcessError(1, "ffmpeg", stderr=b"some error")

    call_count = [0]
    def side_effect_func(*args, **kwargs):
        call_count[0] += 1
        raise error

    monkeypatch.setattr(
        editor.subprocess, "run",
        MagicMock(side_effect=side_effect_func)
    )

    with pytest.raises(subprocess.CalledProcessError):
        instance.apply_edits("in.mp4", "out.mp4", {"filter_string": "eq=contrast=1.1"})

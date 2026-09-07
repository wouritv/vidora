import importlib
import json
import sys
import types
from unittest.mock import MagicMock


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


def test_apply_edits_copies_original_when_filter_missing(monkeypatch):
    editor = _import_editor_with_stubs(monkeypatch)
    instance = editor.VideoEditor(api_key="k")
    run_mock = MagicMock()
    monkeypatch.setattr(editor.subprocess, "run", run_mock)
    instance.apply_edits("in.mp4", "out.mp4", filter_data={})
    run_mock.assert_called_once()



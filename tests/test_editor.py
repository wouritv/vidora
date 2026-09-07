import importlib
import sys
import types


def _import_editor_with_stubs(monkeypatch):
    google_mod = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")

    class _DummyClient:
        def __init__(self, *args, **kwargs):
            pass

    genai_mod.Client = _DummyClient
    genai_mod.types = types.SimpleNamespace(GenerateContentConfig=object)
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


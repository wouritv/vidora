import importlib
import sys
import types


def _import_thumbnail_with_stubs(monkeypatch):
    google_mod = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")

    class _DummyClient:
        def __init__(self, *args, **kwargs):
            self.models = types.SimpleNamespace(generate_content=lambda *a, **k: types.SimpleNamespace(text='{"titles": ["A"]}'))
            self.files = types.SimpleNamespace(upload=lambda **k: types.SimpleNamespace(name="file"), get=lambda **k: types.SimpleNamespace(state="ACTIVE"))

    genai_mod.Client = _DummyClient
    genai_mod.types = types.SimpleNamespace(GenerateContentConfig=object, ImageConfig=object)
    google_mod.genai = genai_mod

    pil_mod = types.ModuleType("PIL")
    pil_image_mod = types.ModuleType("PIL.Image")
    pil_image_mod.open = lambda *args, **kwargs: object()
    pil_mod.Image = pil_image_mod

    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "PIL", pil_mod)
    monkeypatch.setitem(sys.modules, "PIL.Image", pil_image_mod)

    if "thumbnail" in sys.modules:
        return importlib.reload(sys.modules["thumbnail"])
    return importlib.import_module("thumbnail")


def test_refine_titles_returns_fallback_when_json_invalid(monkeypatch):
    thumbnail = _import_thumbnail_with_stubs(monkeypatch)

    class _BadClient:
        def __init__(self, *args, **kwargs):
            self.models = types.SimpleNamespace(generate_content=lambda *a, **k: types.SimpleNamespace(text="not-json"))

    monkeypatch.setattr(thumbnail.genai, "Client", _BadClient)

    result = thumbnail.refine_titles("k", "context", "feedback")

    assert result == {"titles": ["Could not refine titles - please try again"]}


def test_generate_youtube_description_strips_markdown_fence(monkeypatch):
    thumbnail = _import_thumbnail_with_stubs(monkeypatch)

    fenced = "```\nLine 1\nLine 2\n```"

    class _Client:
        def __init__(self, *args, **kwargs):
            self.models = types.SimpleNamespace(generate_content=lambda *a, **k: types.SimpleNamespace(text=fenced))

    monkeypatch.setattr(thumbnail.genai, "Client", _Client)

    result = thumbnail.generate_youtube_description("k", "title", [{"start": 0, "text": "Intro"}], "fr", 90)

    assert result["description"] == "Line 1\nLine 2"


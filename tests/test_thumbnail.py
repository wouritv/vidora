import importlib
import sys
import types
import pytest


def _import_thumbnail_with_stubs(monkeypatch):
    google_mod = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")

    class _DummyClient:
        def __init__(self, *args, **kwargs):
            self.models = types.SimpleNamespace(generate_content=lambda *a, **k: types.SimpleNamespace(text='{"titles": ["A"]}'))
            self.files = types.SimpleNamespace(upload=lambda **k: types.SimpleNamespace(name="file"), get=lambda **k: types.SimpleNamespace(state="ACTIVE"))

    class _Config:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    genai_mod.Client = _DummyClient
    genai_mod.types = types.SimpleNamespace(GenerateContentConfig=_Config, ImageConfig=_Config)
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


def test_generate_thumbnail_builds_prompt_and_saves_images(monkeypatch, tmp_path):
    thumbnail = _import_thumbnail_with_stubs(monkeypatch)
    monkeypatch.chdir(tmp_path)

    opened_paths = []

    def _open_image(path):
        opened_paths.append(path)
        return f"IMG:{path}"

    monkeypatch.setattr(thumbnail.Image, "open", _open_image)
    monkeypatch.setattr(thumbnail.os.path, "exists", lambda p: p in {"face.png", "bg.png"})

    class _GeneratedImage:
        def __init__(self):
            self.saved_paths = []

        def save(self, path):
            self.saved_paths.append(path)

    class _Part:
        def __init__(self, text=None, image=None):
            self.text = text
            self._image = image

        def as_image(self):
            return self._image

    class _Client:
        instances = []

        def __init__(self, *args, **kwargs):
            self.calls = []
            self.generated_images = []
            _Client.instances.append(self)

            def _generate_content(*a, **k):
                self.calls.append(k)
                img = _GeneratedImage()
                self.generated_images.append(img)
                return types.SimpleNamespace(parts=[_Part(text="note"), _Part(image=img)])

            self.models = types.SimpleNamespace(generate_content=_generate_content)

    monkeypatch.setattr(thumbnail.genai, "Client", _Client)

    result = thumbnail.generate_thumbnail(
        "k",
        "Mon titre",
        "session-a",
        face_image_path="face.png",
        bg_image_path="bg.png",
        extra_prompt="Use red tones",
        count=2,
        video_context="Video about pricing",
    )

    assert result == [
        "/thumbnails/session-a/thumb_1.jpg",
        "/thumbnails/session-a/thumb_2.jpg",
    ]
    assert opened_paths == ["face.png", "bg.png"]
    assert len(_Client.instances) == 1
    assert len(_Client.instances[0].calls) == 2

    prompt_parts = _Client.instances[0].calls[0]["contents"]
    assert prompt_parts[0] == "IMG:face.png"
    assert prompt_parts[1] == "IMG:bg.png"
    assert "VIDEO CONTEXT" in prompt_parts[2]
    assert "Video about pricing" in prompt_parts[2]
    assert "MANDATORY USER INSTRUCTIONS" in prompt_parts[2]
    assert "Include the provided face/person prominently" in prompt_parts[2]
    assert "Use the provided background image as the base/backdrop" in prompt_parts[2]

    saved_paths = [img.saved_paths[0] for img in _Client.instances[0].generated_images]
    assert saved_paths[0].endswith("output/thumbnails/session-a/thumb_1.jpg")
    assert saved_paths[1].endswith("output/thumbnails/session-a/thumb_2.jpg")


def test_generate_thumbnail_returns_empty_list_when_no_image_parts(monkeypatch, tmp_path):
    thumbnail = _import_thumbnail_with_stubs(monkeypatch)
    monkeypatch.chdir(tmp_path)

    class _Part:
        def __init__(self, text=None):
            self.text = text

        def as_image(self):
            return None

    class _Client:
        def __init__(self, *args, **kwargs):
            self.models = types.SimpleNamespace(
                generate_content=lambda *a, **k: types.SimpleNamespace(parts=[_Part(text="only text")])
            )

    monkeypatch.setattr(thumbnail.genai, "Client", _Client)

    result = thumbnail.generate_thumbnail("k", "Mon titre", "session-b", count=1)

    assert result == []


def test_generate_thumbnail_raises_when_all_generations_fail(monkeypatch, tmp_path):
    thumbnail = _import_thumbnail_with_stubs(monkeypatch)
    monkeypatch.chdir(tmp_path)

    class _Client:
        def __init__(self, *args, **kwargs):
            self.models = types.SimpleNamespace(
                generate_content=lambda *a, **k: (_ for _ in ()).throw(Exception("boom"))
            )

    monkeypatch.setattr(thumbnail.genai, "Client", _Client)

    with pytest.raises(RuntimeError, match="All thumbnail generations failed. Last error: boom"):
        thumbnail.generate_thumbnail("k", "Mon titre", "session-c", count=2)



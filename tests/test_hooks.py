import importlib
import os
import sys
import types

import pytest


def _import_hooks_with_stubs(monkeypatch):
    pil_mod = types.ModuleType("PIL")
    pil_mod.Image = object
    pil_mod.ImageDraw = object
    pil_mod.ImageFont = object
    pil_mod.ImageFilter = object
    monkeypatch.setitem(sys.modules, "PIL", pil_mod)

    if "hooks" in sys.modules:
        return importlib.reload(sys.modules["hooks"])
    return importlib.import_module("hooks")


def test_add_hook_to_video_raises_when_input_video_missing(monkeypatch):
    hooks = _import_hooks_with_stubs(monkeypatch)
    monkeypatch.setattr(os.path, "exists", lambda path: False)

    with pytest.raises(FileNotFoundError):
        hooks.add_hook_to_video("missing.mp4", "hook", "out.mp4")


def test_add_hook_to_video_runs_ffmpeg_and_cleans_temp_file(monkeypatch):
    hooks = _import_hooks_with_stubs(monkeypatch)

    removed = []

    def fake_exists(path):
        return path in {"video.mp4", "temp_hook_video.mp4.png"}

    monkeypatch.setattr(os.path, "exists", fake_exists)
    monkeypatch.setattr(hooks.subprocess, "check_output", lambda cmd: b"1080x1920")
    monkeypatch.setattr(hooks, "create_hook_image", lambda *args, **kwargs: ("temp_hook_video.mp4.png", 500, 200))
    monkeypatch.setattr(hooks.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(os, "remove", lambda path: removed.append(path))

    ok = hooks.add_hook_to_video("video.mp4", "my hook", "out.mp4", position="top")

    assert ok is True
    assert removed == ["temp_hook_video.mp4.png"]


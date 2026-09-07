import importlib
import sys
import types

import pytest


def _import_main_with_stubs(monkeypatch):
    cv2_mod = types.ModuleType("cv2")
    monkeypatch.setitem(sys.modules, "cv2", cv2_mod)

    scenedetect_mod = types.ModuleType("scenedetect")
    scenedetect_mod.open_video = lambda *args, **kwargs: None

    class _SceneManager:
        def add_detector(self, *args, **kwargs):
            return None

        def detect_scenes(self, *args, **kwargs):
            return None

        def get_scene_list(self):
            return []

    scenedetect_mod.SceneManager = _SceneManager
    monkeypatch.setitem(sys.modules, "scenedetect", scenedetect_mod)

    detectors_mod = types.ModuleType("scenedetect.detectors")
    detectors_mod.ContentDetector = object
    monkeypatch.setitem(sys.modules, "scenedetect.detectors", detectors_mod)

    ultralytics_mod = types.ModuleType("ultralytics")
    ultralytics_mod.YOLO = lambda *args, **kwargs: object()
    monkeypatch.setitem(sys.modules, "ultralytics", ultralytics_mod)

    monkeypatch.setitem(sys.modules, "torch", types.ModuleType("torch"))
    monkeypatch.setitem(sys.modules, "numpy", types.ModuleType("numpy"))

    tqdm_mod = types.ModuleType("tqdm")
    tqdm_mod.tqdm = lambda value, *args, **kwargs: value
    monkeypatch.setitem(sys.modules, "tqdm", tqdm_mod)

    monkeypatch.setitem(sys.modules, "yt_dlp", types.ModuleType("yt_dlp"))

    mp_mod = types.ModuleType("mediapipe")
    mp_mod.solutions = types.SimpleNamespace(
        face_detection=types.SimpleNamespace(FaceDetection=lambda *args, **kwargs: object()),
        face_mesh=object(),
    )
    monkeypatch.setitem(sys.modules, "mediapipe", mp_mod)

    google_mod = types.ModuleType("google")
    google_mod.genai = types.ModuleType("google.genai")
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", google_mod.genai)

    if "main" in sys.modules:
        return importlib.reload(sys.modules["main"])
    return importlib.import_module("main")


def test_sanitize_filename_removes_invalid_characters(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    assert main.sanitize_filename('My <video>: "title"?.mp4') == "My_video_title.mp4"


def test_safe_float_returns_default_on_invalid_input(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    assert main._safe_float("3.14") == 3.14
    assert main._safe_float("x", default=9.9) == 9.9


def test_iou_computes_overlap_ratio(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    assert main._iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert main._iou([0, 0, 2, 2], [10, 10, 2, 2]) == 0.0


def test_build_scene_sample_indices_respects_bounds(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setattr(main, "MIN_SAMPLES_PER_SCENE", 3)
    monkeypatch.setattr(main, "MAX_SAMPLES_PER_SCENE", 5)
    indices = main._build_scene_sample_indices(0, 100, fps=30)
    assert len(indices) <= 5
    assert indices[0] == 0


def test_build_scene_sample_indices_fallback_when_empty(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    indices = main._build_scene_sample_indices(10, 10, fps=30)
    assert indices == [10]


def test_smooth_strategies_replaces_single_flip(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    result = main._smooth_strategies(["TRACK", "GENERAL", "TRACK"])
    assert result == ["TRACK", "TRACK", "TRACK"]


def test_classify_scene_strategy_thresholds(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    assert main._classify_scene_strategy(1) == "TRACK"
    assert main._classify_scene_strategy(2) == "MULTI_SPEAKER"
    assert main._classify_scene_strategy(4) == "MULTI_SPEAKER"
    assert main._classify_scene_strategy(5) == "GENERAL"


def test_looks_like_netscape_cookies(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    assert main._looks_like_netscape_cookies("") is False
    assert main._looks_like_netscape_cookies("# Netscape HTTP Cookie File\n") is True
    assert main._looks_like_netscape_cookies("example.com\tTRUE\t/\tFALSE\t0\tname\tvalue") is True
    assert main._looks_like_netscape_cookies("invalid line") is False


def test_get_video_resolution_success_and_failure(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    class _CapOk:
        def isOpened(self):
            return True

        def get(self, prop):
            if prop == main.cv2.CAP_PROP_FRAME_WIDTH:
                return 1920
            if prop == main.cv2.CAP_PROP_FRAME_HEIGHT:
                return 1080
            return 0

        def release(self):
            return None

    main.cv2.CAP_PROP_FRAME_WIDTH = 3
    main.cv2.CAP_PROP_FRAME_HEIGHT = 4
    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _: _CapOk(), raising=False)
    assert main.get_video_resolution("video.mp4") == (1920, 1080)

    class _CapBad:
        def isOpened(self):
            return False

    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _: _CapBad(), raising=False)
    with pytest.raises(IOError):
        main.get_video_resolution("bad.mp4")



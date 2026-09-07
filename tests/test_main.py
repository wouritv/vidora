import importlib
import sys
import types


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


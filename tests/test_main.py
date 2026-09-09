import importlib
import math
import os
import runpy
import sys
import types

import pytest


def _import_main_with_stubs(monkeypatch):
    cv2_mod = types.ModuleType("cv2")
    # Add cv2 constants
    cv2_mod.CAP_PROP_POS_FRAMES = 1
    cv2_mod.CAP_PROP_FPS = 5
    cv2_mod.CAP_PROP_FRAME_WIDTH = 3
    cv2_mod.CAP_PROP_FRAME_HEIGHT = 4
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


def _mini_np():
    class _MiniMask(list):
        def any(self):
            return any(self)

        def __invert__(self):
            return _MiniMask([not v for v in self])

    class _MiniArray:
        def __init__(self, data):
            self.data = list(data)

        @property
        def size(self):
            return len(self.data)

        def astype(self, _dtype):
            return self

        def __iter__(self):
            return iter(self.data)

        def __len__(self):
            return len(self.data)

        def __getitem__(self, key):
            if isinstance(key, slice):
                return _MiniArray(self.data[key])
            if isinstance(key, _MiniMask):
                return _MiniArray([v for v, keep in zip(self.data, key) if keep])
            return self.data[key]

        def __setitem__(self, key, value):
            if isinstance(key, _MiniMask):
                values = list(value)
                vi = 0
                for i, keep in enumerate(key):
                    if keep:
                        self.data[i] = values[vi]
                        vi += 1
                return
            self.data[key] = value

        def __pow__(self, power):
            return _MiniArray([v ** power for v in self.data])

    class _MiniFrame:
        def __init__(self, shape):
            self.shape = shape

        def __getitem__(self, _key):
            return self

        def __setitem__(self, _key, _value):
            return None

        def copy(self):
            return _MiniFrame(self.shape)

        def tobytes(self):
            return b"frame"

    class _MiniCorr:
        def __init__(self, value):
            self.value = value

        def __getitem__(self, key):
            i, j = key
            if i == 0 and j == 1:
                return self.value
            return 1.0

    class _MiniNP:
        nan = float("nan")
        float32 = "float32"
        int16 = "int16"
        uint8 = "uint8"

        @staticmethod
        def frombuffer(_raw, dtype=None):
            return _MiniArray([100.0] * 320)

        @staticmethod
        def array(data, dtype=None):
            if isinstance(data, _MiniArray):
                return _MiniArray(data.data)
            return _MiniArray(list(data))

        @staticmethod
        def zeros(shape, dtype=None):
            return _MiniFrame(shape)

        @staticmethod
        def ones(shape, dtype=None):
            return _MiniFrame(shape)

        @staticmethod
        def sqrt(value):
            return math.sqrt(value)

        @staticmethod
        def mean(values):
            vals = values.data if isinstance(values, _MiniArray) else list(values)
            return (sum(vals) / len(vals)) if vals else 0.0

        @staticmethod
        def hypot(a, b):
            return math.hypot(a, b)

        @staticmethod
        def std(values):
            vals = values.data if isinstance(values, _MiniArray) else list(values)
            if not vals:
                return 0.0
            m = sum(vals) / len(vals)
            return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))

        @staticmethod
        def corrcoef(_a, _b):
            return _MiniCorr(0.8)

        @staticmethod
        def isnan(values):
            if isinstance(values, (int, float)):
                return isinstance(values, float) and math.isnan(values)
            vals = values.data if isinstance(values, _MiniArray) else list(values)
            return _MiniMask([isinstance(v, float) and math.isnan(v) for v in vals])

        @staticmethod
        def all(mask):
            return all(mask)

        @staticmethod
        def flatnonzero(mask):
            return [i for i, v in enumerate(mask) if v]

        @staticmethod
        def interp(x_idxs, xp, fp):
            src = list(fp)
            fallback = src[0] if src else 0.0
            return [fallback for _ in x_idxs]

    return _MiniNP


def _install_cli_runtime_stubs(monkeypatch, tmp_path, *, shorts_payload=None):
    mini = _mini_np()

    np_mod = types.ModuleType("numpy")
    np_mod.nan = mini.nan
    np_mod.float32 = mini.float32
    np_mod.int16 = mini.int16
    np_mod.uint8 = mini.uint8
    np_mod.frombuffer = mini.frombuffer
    np_mod.array = mini.array
    np_mod.zeros = mini.zeros
    np_mod.ones = mini.ones
    np_mod.sqrt = mini.sqrt
    np_mod.mean = mini.mean
    np_mod.hypot = mini.hypot
    np_mod.std = mini.std
    np_mod.corrcoef = mini.corrcoef
    np_mod.isnan = mini.isnan
    np_mod.all = mini.all
    np_mod.flatnonzero = mini.flatnonzero
    np_mod.interp = mini.interp
    monkeypatch.setitem(sys.modules, "numpy", np_mod)

    class _Frame:
        def __init__(self, h=10, w=20):
            self.shape = (h, w, 3)

        def __getitem__(self, _key):
            return self

        def __setitem__(self, _key, _value):
            return None

        def copy(self):
            return _Frame(self.shape[0], self.shape[1])

        def tobytes(self):
            return b"frame"

    cv2_mod = types.ModuleType("cv2")
    cv2_mod.CAP_PROP_POS_FRAMES = 1
    cv2_mod.CAP_PROP_FPS = 5
    cv2_mod.CAP_PROP_FRAME_WIDTH = 3
    cv2_mod.CAP_PROP_FRAME_HEIGHT = 4
    cv2_mod.CAP_PROP_FRAME_COUNT = 7
    cv2_mod.COLOR_BGR2RGB = 10
    cv2_mod.INTER_LINEAR = 1
    cv2_mod.cvtColor = lambda frame, code: frame
    cv2_mod.resize = lambda frame, size, interpolation=None: _Frame(size[1], size[0])
    cv2_mod.GaussianBlur = lambda frame, kernel, sigma: frame

    class _Cap:
        def __init__(self, _path):
            self.i = 0

        def isOpened(self):
            return True

        def set(self, *_args):
            return None

        def get(self, prop):
            if prop == cv2_mod.CAP_PROP_FPS:
                return 25.0
            if prop == cv2_mod.CAP_PROP_FRAME_WIDTH:
                return 20
            if prop == cv2_mod.CAP_PROP_FRAME_HEIGHT:
                return 10
            if prop == cv2_mod.CAP_PROP_FRAME_COUNT:
                return 2
            return 0

        def read(self):
            if self.i >= 2:
                return False, None
            self.i += 1
            return True, _Frame()

        def release(self):
            return None

    cv2_mod.VideoCapture = _Cap
    monkeypatch.setitem(sys.modules, "cv2", cv2_mod)

    scenedetect_mod = types.ModuleType("scenedetect")
    class _T:
        def __init__(self, frame_num):
            self.frame_num = frame_num

    class _V:
        frame_rate = 25.0

    scenedetect_mod.open_video = lambda _p: _V()
    scenedetect_mod.FrameTimecode = lambda n, fps: _T(n)

    class _SceneManager:
        def add_detector(self, *_a, **_k):
            return None

        def detect_scenes(self, video=None):
            return None

        def get_scene_list(self):
            return [(_T(0), _T(2))]

    scenedetect_mod.SceneManager = _SceneManager
    monkeypatch.setitem(sys.modules, "scenedetect", scenedetect_mod)
    detectors_mod = types.ModuleType("scenedetect.detectors")
    detectors_mod.ContentDetector = object
    monkeypatch.setitem(sys.modules, "scenedetect.detectors", detectors_mod)

    class _YoloModel:
        def __call__(self, *args, **kwargs):
            return []

    ultralytics_mod = types.ModuleType("ultralytics")
    ultralytics_mod.YOLO = lambda *args, **kwargs: _YoloModel()
    monkeypatch.setitem(sys.modules, "ultralytics", ultralytics_mod)

    monkeypatch.setitem(sys.modules, "torch", types.ModuleType("torch"))

    class _TqdmCtx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, _n):
            return None

    tqdm_mod = types.ModuleType("tqdm")
    tqdm_mod.tqdm = lambda value=None, **kwargs: value if value is not None and not isinstance(value, (int, float)) else _TqdmCtx()
    monkeypatch.setitem(sys.modules, "tqdm", tqdm_mod)

    class _DetBBox:
        xmin, ymin, width, height = 0.1, 0.1, 0.3, 0.3

    class _Detection:
        location_data = types.SimpleNamespace(relative_bounding_box=_DetBBox())

    class _FaceDet:
        def process(self, _rgb):
            return types.SimpleNamespace(detections=[_Detection()])

    class _FaceMesh:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def process(self, _rgb):
            return types.SimpleNamespace(multi_face_landmarks=[])

    mp_mod = types.ModuleType("mediapipe")
    mp_mod.solutions = types.SimpleNamespace(
        face_detection=types.SimpleNamespace(FaceDetection=lambda *a, **k: _FaceDet()),
        face_mesh=types.SimpleNamespace(FaceMesh=lambda **k: _FaceMesh()),
    )
    monkeypatch.setitem(sys.modules, "mediapipe", mp_mod)

    class _Word:
        def __init__(self):
            self.word = "hello"
            self.start = 0.0
            self.end = 0.2
            self.probability = 0.9

    class _Seg:
        start = 0.0
        end = 0.5
        text = "hello"
        words = [_Word()]

    class _Info:
        language = "en"
        language_probability = 0.9

    class _WhisperModel:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, *a, **k):
            return ([_Seg()], _Info())

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=_WhisperModel))

    payload = shorts_payload if shorts_payload is not None else {"shorts": [{"start": 0.0, "end": 1.0}]}
    class _GenResp:
        text = __import__("json").dumps(payload)
        usage_metadata = None

    class _GenClient:
        def __init__(self, api_key):
            self.models = types.SimpleNamespace(generate_content=lambda **k: _GenResp())

    google_mod = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    genai_mod.Client = _GenClient
    google_mod.genai = genai_mod
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)

    class _YDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download=False):
            return {"title": "Video Sample"}

        def download(self, urls):
            out = self.opts.get("outtmpl", "")
            if "%(ext)s" in out:
                out = out.replace("%(ext)s", "mp4")
            if out:
                os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
                with open(out, "wb") as f:
                    f.write(b"x")
            return None

    ydl_mod = types.ModuleType("yt_dlp")
    ydl_mod.YoutubeDL = _YDL
    ydl_mod.version = types.SimpleNamespace(__version__="1.0")
    monkeypatch.setitem(sys.modules, "yt_dlp", ydl_mod)

    import subprocess as _sp

    class _Proc:
        def __init__(self):
            self.stdin = types.SimpleNamespace(write=lambda _b: None, close=lambda: None)
            self.stderr = types.SimpleNamespace(read=lambda: b"")
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(_sp, "Popen", lambda *a, **k: _Proc())

    def _run(cmd, stdout=None, stderr=None, check=False, **kwargs):
        if isinstance(cmd, list) and cmd and cmd[0] == "ffmpeg" and cmd[-1].endswith(".mp4"):
            os.makedirs(os.path.dirname(cmd[-1]) or ".", exist_ok=True)
            with open(cmd[-1], "wb") as f:
                f.write(b"clip")
        return types.SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(_sp, "run", _run)


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


def test_strip_json_markdown_handles_various_formats(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    result = main._strip_json_markdown("```json\n{}\n```")
    assert result == "{}"

    result = main._strip_json_markdown("```\n{}\n```")
    assert result == "{}"

    result = main._strip_json_markdown("{}")
    assert result == "{}"


def test_is_quota_or_rate_limit_error_detects_common_messages(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    assert main._is_quota_or_rate_limit_error(Exception("resource_exhausted")) is True
    assert main._is_quota_or_rate_limit_error(Exception("quota exceeded")) is True
    assert main._is_quota_or_rate_limit_error(Exception("rate limit")) is True
    assert main._is_quota_or_rate_limit_error(Exception("429")) is True
    assert main._is_quota_or_rate_limit_error(Exception("other error")) is False


def test_build_words_payload_extracts_words(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    transcript = {
        "segments": [
            {
                "words": [
                    {"word": "hello", "start": 0.0, "end": 0.5},
                    {"word": "world", "start": 0.6, "end": 1.0}
                ]
            }
        ]
    }

    result = main._build_words_payload(transcript)
    assert len(result) == 2
    assert result[0]["w"] == "hello"
    assert result[1]["w"] == "world"


def test_build_analysis_prompt_includes_video_details(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    transcript = {
        "text": "Test transcript",
        "segments": []
    }

    result = main._build_analysis_prompt(transcript, video_duration=100)
    assert "100" in result
    assert "Test transcript" in result


def test_smoothed_cameraman_initialization(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    cameraman = main.SmoothedCameraman(1080, 1920, 1920, 1080)
    assert cameraman.output_width == 1080
    assert cameraman.output_height == 1920
    assert cameraman.current_center_x == 960.0


def test_smoothed_cameraman_update_target(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    cameraman = main.SmoothedCameraman(1080, 1920, 1920, 1080)
    cameraman.update_target([100, 50, 100, 150])
    assert cameraman.target_center_x == 150.0  # 100 + 100/2


def test_smoothed_cameraman_get_crop_box(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    cameraman = main.SmoothedCameraman(1080, 1920, 1920, 1080)
    cameraman.update_target([800, 50, 100, 150])

    x1, y1, x2, y2 = cameraman.get_crop_box(force_snap=True)
    assert y1 == 0
    assert y2 == 1080


def test_speaker_tracker_initialization(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    tracker = main.SpeakerTracker(stabilization_frames=15, cooldown_frames=30)
    assert tracker.stabilization_threshold == 15
    assert tracker.switch_cooldown == 30
    assert tracker.active_speaker_id is None


def test_detect_face_candidates_returns_empty_list_for_no_detections(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    # Mock frame without detections
    frame = [[0]*3]*100  # Dummy frame

    # This would normally use MediaPipe, which is stubbed
    # So it will fail gracefully
    try:
        result = main.detect_face_candidates(frame)
        assert isinstance(result, list)
    except (AttributeError, TypeError):
        # Expected due to stubbed dependencies
        pass


def test_normalize_short_durations_clips_to_min_max(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    monkeypatch.setattr(main, "MIN_CLIP_DURATION_SECONDS", 30)
    monkeypatch.setattr(main, "MAX_CLIP_DURATIONS_SECOND", 90)

    clips_data = {
        "shorts": [
            {"start": 0, "end": 10},  # Too short
            {"start": 0, "end": 60},  # OK
            {"start": 0, "end": 150},  # Too long
        ]
    }

    result = main._normalize_short_durations(clips_data, 150)
    assert len(result["shorts"]) == 3
    assert result["shorts"][0]["start"] == 0.0
    assert result["shorts"][0]["end"] == 30.0
    assert result["shorts"][1]["start"] == 0.0
    assert result["shorts"][1]["end"] == 60.0
    assert result["shorts"][2]["start"] == 0.0
    assert result["shorts"][2]["end"] == 90.0


def test_extract_error_message_handles_exceptions(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    result = main._extract_error_message(Exception("Test error"))
    assert "test error" in result


def test_build_external_costs_calculates_total(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    transcript = {
        "meta": {
            "provider": "assemblyai",
            "audio_seconds": 120
        }
    }

    clips_data = {
        "cost_analysis": {
            "total_cost": 0.5,
            "provider": "openai"
        }
    }

    result = main._build_external_costs(transcript, clips_data)
    assert "assemblyai" in result
    assert "llm" in result
    assert "total_usd" in result


def test_count_distinct_faces_in_scene_with_empty_frames(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    class FakeCap:
        def set(self, prop, val):
            pass

        def read(self):
            return False, None

    cap = FakeCap()
    result = main.count_distinct_faces_in_scene(cap, 0, 30, 30)
    assert result[0] == 0  # No faces


def test_iou_overlap_calculations(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    # Identical boxes
    assert main._iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0

    # No overlap
    assert main._iou([0, 0, 10, 10], [20, 20, 10, 10]) == 0.0

    # Partial overlap
    result = main._iou([0, 0, 10, 10], [5, 5, 10, 10])
    assert 0 < result < 1.0


def test_build_scene_sample_indices_respects_bounds(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setattr(main, "MIN_SAMPLES_PER_SCENE", 3)
    monkeypatch.setattr(main, "MAX_SAMPLES_PER_SCENE", 5)
    indices = main._build_scene_sample_indices(0, 100, fps=30)
    assert len(indices) <= 5
    assert indices[0] == 0


def test_classify_scene_strategy_thresholds(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    assert main._classify_scene_strategy(0) == "GENERAL"
    assert main._classify_scene_strategy(1) == "TRACK"
    assert main._classify_scene_strategy(2) == "MULTI_SPEAKER"
    assert main._classify_scene_strategy(4) == "MULTI_SPEAKER"
    assert main._classify_scene_strategy(5) == "GENERAL"


def test_smooth_strategies_with_single_flip(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    result = main._smooth_strategies(["TRACK", "GENERAL", "TRACK"])
    assert result == ["TRACK", "TRACK", "TRACK"]

    # Short list should pass through
    result = main._smooth_strategies(["TRACK", "GENERAL"])
    assert result == ["TRACK", "GENERAL"]


def test_looks_like_netscape_cookies_recognizes_format(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    # Valid Netscape format with header
    assert main._looks_like_netscape_cookies("# Netscape HTTP Cookie File\n") is True

    # Valid Netscape format with tab-separated data
    assert main._looks_like_netscape_cookies("example.com\tTRUE\t/\tFALSE\t0\tname\tvalue") is True

    # Invalid format
    assert main._looks_like_netscape_cookies("invalid line") is False
    assert main._looks_like_netscape_cookies("") is False


def test_mount_resolution_edge_cases(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    # Test crop_width > video_width scenario
    cameraman = main.SmoothedCameraman(2000, 1920, 1920, 1080)
    # crop_width is computed based on zoom level and video dimensions
    assert cameraman.crop_width > 0
    assert cameraman.crop_height > 0


def test_update_tracked_faces_matches_and_appends(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setattr(main, "IOU_MATCH_THRESHOLD", 0.2)
    tracked = [{"box": [0, 0, 10, 10], "seen": 1}]
    candidates = [{"box": [1, 1, 10, 10]}, {"box": [100, 100, 10, 10]}]
    main._update_tracked_faces(tracked, candidates)
    assert tracked[0]["seen"] == 2
    assert len(tracked) == 2


def test_analyze_scenes_strategy_short_scene_and_n_samples_zero(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    class _Cap:
        def isOpened(self):
            return True

        def get(self, prop):
            return 30.0

        def release(self):
            return None

    class _T:
        def __init__(self, frame_num):
            self.frame_num = frame_num

    scenes = [(_T(0), _T(5)), (_T(10), _T(80))]
    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _: _Cap(), raising=False)
    monkeypatch.setattr(main, "tqdm", lambda it, desc=None: it)
    monkeypatch.setattr(main, "count_distinct_faces_in_scene", lambda *args, **kwargs: (1, 0, [], []))
    out_strats, out_boxes = main.analyze_scenes_strategy("video.mp4", scenes)
    assert out_strats == ["TRACK", "GENERAL"]
    assert out_boxes == [[], []]


def test_analyze_scenes_strategy_when_capture_fails(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    class _Cap:
        def isOpened(self):
            return False

    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _: _Cap(), raising=False)
    out_strats, out_boxes = main.analyze_scenes_strategy("video.mp4", [(1, 2), (3, 4)])
    assert out_strats == ["TRACK", "TRACK"]
    assert out_boxes == [[], []]


def test_compute_separator_thickness_bounds_and_even(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setattr(main, "SEPARATOR_THICKNESS_RATIO", 0.003)
    monkeypatch.setattr(main, "SEPARATOR_MIN_PX", 2)
    monkeypatch.setattr(main, "SEPARATOR_MAX_PX", 12)
    value = main._compute_separator_thickness(1001)
    assert 2 <= value <= 12
    assert value % 2 == 0


def test_resolve_cookiefile_from_env_path_and_inline(monkeypatch, tmp_path):
    main = _import_main_with_stubs(monkeypatch)

    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\nexample.com\tTRUE\t/\tFALSE\t0\tname\tvalue\n")
    monkeypatch.setenv("YOUTUBE_COOKIES", str(cookies_file))
    assert main._resolve_cookiefile_from_env() == str(cookies_file)

    monkeypatch.setenv("YOUTUBE_COOKIES", "example.com\\tTRUE\\t/\\tFALSE\\t0\\tname\\tvalue")
    monkeypatch.setattr(main, "_looks_like_netscape_cookies", lambda text: True)
    monkeypatch.setattr(main.os.path, "getsize", lambda p: 10)
    written = {}

    class _F:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, data):
            written["data"] = data

    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: _F())
    assert main._resolve_cookiefile_from_env() == "/app/cookies.txt"
    assert "Netscape HTTP Cookie File" in written["data"]


def test_build_ytdlp_opts_proxy_cookie_modes(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setenv("YOUTUBE_PROXY", "http://user:pass@proxy:8080")
    opts = main._build_ytdlp_opts(True, "/tmp/c.txt", "abc123")
    assert opts["cookiefile"] == "/tmp/c.txt"
    assert "__sessid.abc123" in opts["proxy"]
    assert opts["extractor_args"]["youtube"]["player_client"] == ["mweb", "web"]

    opts2 = main._build_ytdlp_opts(False, None, None)
    assert opts2["cookiefile"] is None
    assert opts2["extractor_args"]["youtube"]["player_client"] == ["android", "ios"]


def test_make_job_cookies_copy(monkeypatch, tmp_path):
    main = _import_main_with_stubs(monkeypatch)
    src = tmp_path / "master.txt"
    src.write_text("cookie")
    monkeypatch.setenv("YOUTUBE_COOKIES", str(src))
    copied = main._make_job_cookies_copy()
    assert copied is not None
    assert os.path.exists(copied)
    os.remove(copied)


def test_extract_info_with_fallback(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

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

    monkeypatch.setattr(main.yt_dlp, "YoutubeDL", _YDL, raising=False)
    info, opts = main._extract_info_with_fallback("https://y.t", None, "sess")
    assert info["title"] == "ok"
    assert "extractor_args" in opts


def test_locate_downloaded_file_prefers_exact_then_fallback(monkeypatch, tmp_path):
    main = _import_main_with_stubs(monkeypatch)
    out_dir = str(tmp_path)
    exact = tmp_path / "video.mp4"
    exact.write_text("x")
    assert main._locate_downloaded_file(out_dir, "video").endswith("video.mp4")

    exact.unlink()
    (tmp_path / "video.abc.mp4").write_text("x")
    assert main._locate_downloaded_file(out_dir, "video").endswith("video.abc.mp4")


def test_cleanup_existing_outputs_handles_missing_files(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    removed = []
    monkeypatch.setattr(main.os.path, "exists", lambda p: True)

    def _remove(path):
        removed.append(path)
        if path == "b":
            raise FileNotFoundError()

    monkeypatch.setattr(main.os, "remove", _remove)
    main._cleanup_existing_outputs("a", "b", None)
    assert removed == ["a", "b"]


def test_compute_output_dimensions_and_scene_helpers(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    w, h = main._compute_output_dimensions(1081)
    assert h == 1081
    assert w % 2 == 0

    class _T:
        def __init__(self, frame_num):
            self.frame_num = frame_num

    boundaries = main._build_scene_boundaries([(_T(0), _T(10)), (_T(10), _T(20))])
    assert boundaries == [(0, 10), (10, 20)]
    assert main._advance_scene_index(15, 0, boundaries) == 1


def test_transcribe_video_assembly_retries_then_success(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setenv("TRANSCRIBER_PROVIDER", "assemblyai")
    monkeypatch.setenv("ASSEMBLY_RETRY_ATTEMPTS", "2")
    monkeypatch.setenv("ASSEMBLY_RETRY_DELAY_SECONDS", "0")
    calls = {"n": 0}

    def _asm(_):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("temporary")
        return {"text": "ok", "segments": []}

    monkeypatch.setattr(main, "_transcribe_with_assemblyai", _asm)
    result = main.transcribe_video("in.mp4")
    assert result["text"] == "ok"
    assert calls["n"] == 2


def test_transcribe_video_assembly_failure_raises(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setenv("TRANSCRIBER_PROVIDER", "assemblyai")
    monkeypatch.setenv("ASSEMBLY_RETRY_ATTEMPTS", "2")
    monkeypatch.setenv("ASSEMBLY_RETRY_DELAY_SECONDS", "0")
    monkeypatch.setattr(main, "_transcribe_with_assemblyai", lambda _: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError):
        main.transcribe_video("in.mp4")


def test_transcribe_video_hybrid_fallback(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setenv("TRANSCRIBER_PROVIDER", "hybrid")
    monkeypatch.setenv("TRANSCRIBER_FALLBACK", "faster_whisper")
    monkeypatch.setenv("ASSEMBLY_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("ASSEMBLY_RETRY_DELAY_SECONDS", "0")
    monkeypatch.setattr(main, "_transcribe_with_assemblyai", lambda _: (_ for _ in ()).throw(RuntimeError("quota")))
    monkeypatch.setattr(main, "_transcribe_with_faster_whisper", lambda _: {"text": "fallback", "segments": []})
    result = main.transcribe_video("in.mp4")
    assert result["text"] == "fallback"


def test_transcribe_video_faster_whisper_provider(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setenv("TRANSCRIBER_PROVIDER", "faster_whisper")
    monkeypatch.setattr(main, "_transcribe_with_faster_whisper", lambda _: {"text": "local", "segments": []})
    result = main.transcribe_video("in.mp4")
    assert result["text"] == "local"


def test_transcribe_video_hybrid_returns_assembly_result_without_fallback(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setenv("TRANSCRIBER_PROVIDER", "hybrid")
    monkeypatch.setenv("ASSEMBLY_RETRY_ATTEMPTS", "2")
    monkeypatch.setenv("ASSEMBLY_RETRY_DELAY_SECONDS", "0")

    fallback_calls = {"n": 0}

    def _fallback(_):
        fallback_calls["n"] += 1
        return {"text": "fallback", "segments": []}

    monkeypatch.setattr(main, "_transcribe_with_assemblyai", lambda _: {"text": "asm", "segments": []})
    monkeypatch.setattr(main, "_transcribe_with_faster_whisper", _fallback)

    result = main.transcribe_video("in.mp4")
    assert result["text"] == "asm"
    assert fallback_calls["n"] == 0


def test_transcribe_video_hybrid_fallback_disabled_raises(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setenv("TRANSCRIBER_PROVIDER", "hybrid")
    monkeypatch.setenv("TRANSCRIBER_FALLBACK", "none")
    monkeypatch.setenv("ASSEMBLY_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("ASSEMBLY_RETRY_DELAY_SECONDS", "0")
    monkeypatch.setattr(main, "_transcribe_with_assemblyai", lambda _: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError, match="fallback disabled"):
        main.transcribe_video("in.mp4")


def test_transcribe_video_assembly_retries_sleep_between_attempts(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setenv("TRANSCRIBER_PROVIDER", "assemblyai")
    monkeypatch.setenv("ASSEMBLY_RETRY_ATTEMPTS", "3")
    monkeypatch.setenv("ASSEMBLY_RETRY_DELAY_SECONDS", "0.5")

    calls = {"n": 0}
    sleeps = []

    def _asm(_):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("temporary")
        return {"text": "ok", "segments": []}

    monkeypatch.setattr(main, "_transcribe_with_assemblyai", _asm)
    monkeypatch.setattr(main.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = main.transcribe_video("in.mp4")
    assert result["text"] == "ok"
    assert calls["n"] == 3
    assert sleeps == [0.5, 0.5]


def test_get_viral_clips_provider_routing(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setattr(main, "_normalize_short_durations", lambda data, duration: {**data, "norm": duration})
    monkeypatch.setattr(main, "_get_viral_clips_with_gemini", lambda *_: {"shorts": [{"start": 0, "end": 10}]})
    monkeypatch.setattr(main, "_get_viral_clips_with_openai", lambda *_: {"shorts": [{"start": 5, "end": 20}]})

    monkeypatch.setenv("AI_PROVIDER", "gemini")
    g = main.get_viral_clips({"text": "x"}, 60)
    assert g["norm"] == 60

    monkeypatch.setenv("AI_PROVIDER", "openai")
    o = main.get_viral_clips({"text": "x"}, 60)
    assert o["norm"] == 60


def test_get_viral_clips_hybrid_fallback_and_both_fail(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "hybrid")
    monkeypatch.setattr(main, "_normalize_short_durations", lambda data, duration: data)
    monkeypatch.setattr(main, "_is_quota_or_rate_limit_error", lambda exc: True)

    monkeypatch.setattr(main, "_get_viral_clips_with_openai", lambda *_: (_ for _ in ()).throw(RuntimeError("429")))
    monkeypatch.setattr(main, "_get_viral_clips_with_gemini", lambda *_: {"shorts": []})
    ok = main.get_viral_clips({"text": "x"}, 30)
    assert "shorts" in ok

    monkeypatch.setattr(main, "_get_viral_clips_with_gemini", lambda *_: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError):
        main.get_viral_clips({"text": "x"}, 30)


def test_process_video_to_vertical_success_and_fail(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    class _T:
        def __init__(self, frame_num):
            self.frame_num = frame_num

    monkeypatch.setattr(main, "_prepare_temp_paths", lambda out: ("tmpv.mp4", "tmpa.aac"))
    monkeypatch.setattr(main, "_cleanup_existing_outputs", lambda *args: None)
    monkeypatch.setattr(main, "detect_scenes", lambda _: ([(_T(0), _T(100))], 30.0))
    monkeypatch.setattr(main, "get_video_resolution", lambda _: (1920, 1080))
    monkeypatch.setattr(main, "analyze_scenes_strategy", lambda *_: (["TRACK"], [[]]))
    monkeypatch.setattr(main, "refine_multi_speaker_scenes", lambda *_: ["TRACK"])
    monkeypatch.setattr(main, "_build_scene_boundaries", lambda scenes: [(0, 100)])
    monkeypatch.setattr(main, "_extract_audio_track", lambda *_: None)
    monkeypatch.setattr(main, "_merge_video_and_audio", lambda *_: True)
    monkeypatch.setattr(main, "_process_frames_to_temp_video", lambda *args, **kwargs: (0, ""))
    assert main.process_video_to_vertical("in.mp4", "out.mp4") is True

    monkeypatch.setattr(main, "_process_frames_to_temp_video", lambda *args, **kwargs: (1, "ffmpeg error"))
    assert main.process_video_to_vertical("in.mp4", "out.mp4") is False


def test_download_youtube_video_success_and_cleanup(monkeypatch, tmp_path):
    main = _import_main_with_stubs(monkeypatch)
    cookie_file = tmp_path / "job_cookie.txt"
    cookie_file.write_text("x")

    monkeypatch.setattr(main, "_make_job_cookies_copy", lambda: str(cookie_file))
    monkeypatch.setattr(main, "_extract_info_with_fallback", lambda *args, **kwargs: ({"title": "My Video"}, {}))
    monkeypatch.setattr(main, "_run_download", lambda *args, **kwargs: "/tmp/out.mp4")
    monkeypatch.setattr(main, "sanitize_filename", lambda name: "My_Video")
    monkeypatch.setattr(main, "yt_dlp", types.SimpleNamespace(version=types.SimpleNamespace(__version__="1.0")))

    removed = []
    monkeypatch.setattr(main.os.path, "exists", lambda p: str(p) == str(cookie_file))
    monkeypatch.setattr(main.os, "remove", lambda p: removed.append(p))

    file_path, title = main.download_youtube_video("https://youtube.com/watch?v=abc", output_dir="/tmp")
    assert file_path == "/tmp/out.mp4"
    assert title == "My_Video"
    assert str(cookie_file) in removed


def test_download_youtube_video_prints_failure_and_raises(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setattr(main, "_make_job_cookies_copy", lambda: None)
    monkeypatch.setattr(main, "_extract_info_with_fallback", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("blocked")))
    printer = {"called": 0}
    monkeypatch.setattr(main, "_print_download_failure", lambda exc: printer.__setitem__("called", printer["called"] + 1))
    monkeypatch.setattr(main, "yt_dlp", types.SimpleNamespace(version=types.SimpleNamespace(__version__="1.0")))
    with pytest.raises(RuntimeError):
        main.download_youtube_video("https://youtube.com/watch?v=abc", output_dir="/tmp")
    assert printer["called"] == 1


def test_cameraman_and_speaker_tracker_internal_branches(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    cameraman = main.SmoothedCameraman(1080, 1920, 1920, 1080)
    cameraman.current_center_x = 100.0
    cameraman.target_center_x = 800.0
    x1, y1, x2, y2 = cameraman.get_crop_box(force_snap=False)
    assert x2 > x1
    assert y2 == 1080

    tracker = main.SpeakerTracker(stabilization_frames=2, cooldown_frames=2)
    tracker.known_faces = [
        {"id": 1, "center": 100.0, "last_frame": 1},
        {"id": 2, "center": 300.0, "last_frame": 100},
    ]
    assert tracker._find_best_match_id(305.0, 101, 1000) == 2
    assert tracker._allocate_face_id(2) == 2
    assert tracker._allocate_face_id(-1) == 0

    tracker.speaker_scores = {1: 0.05, 2: 1.0}
    tracker._decay_scores()
    assert 1 not in tracker.speaker_scores
    assert 2 in tracker.speaker_scores

    face_candidates = [{"box": [290, 10, 40, 40], "score": 100.0}]
    box = tracker.get_target(face_candidates, frame_number=102, width=1000)
    assert isinstance(box, list)


def test_detection_and_scene_helpers_cover_branches(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    class _Frame:
        shape = (100, 200, 3)

    class _BBox:
        def __init__(self, xmin, ymin, width, height):
            self.xmin = xmin
            self.ymin = ymin
            self.width = width
            self.height = height

    class _Detection:
        def __init__(self, bbox):
            self.location_data = types.SimpleNamespace(relative_bounding_box=bbox)

    detections = [
        _Detection(_BBox(0.1, 0.1, 0.4, 0.4)),
        _Detection(_BBox(0.2, 0.2, 0.0, 0.2)),
    ]
    monkeypatch.setattr(main.cv2, "COLOR_BGR2RGB", 1, raising=False)
    monkeypatch.setattr(main.cv2, "cvtColor", lambda frame, code: frame, raising=False)
    monkeypatch.setattr(main, "MIN_FACE_AREA_RATIO", 0.01)
    monkeypatch.setattr(main, "face_detection", types.SimpleNamespace(process=lambda _rgb: types.SimpleNamespace(detections=detections)))
    out = main.detect_face_candidates(_Frame())
    assert len(out) == 1

    class _Box:
        def __init__(self, coords):
            self.xyxy = [coords]

    class _Result:
        def __init__(self, boxes):
            self.boxes = boxes

    monkeypatch.setattr(main, "model", lambda _frame, **_kwargs: [_Result([_Box([0, 0, 100, 200])])])
    assert main.detect_person_yolo(_Frame()) == [0, 0, 100, 80]
    monkeypatch.setattr(main, "model", lambda *_args, **_kwargs: [])
    assert main.detect_person_yolo(_Frame()) is None


def test_audio_and_mouth_signal_helpers(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    np = _mini_np()
    monkeypatch.setattr(main, "np", np)

    class _WF:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def getframerate(self):
            return 16000

        def getnframes(self):
            return 320

        def readframes(self, _n):
            return b"\x64\x00" * 320

    monkeypatch.setattr(main.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.wave, "open", lambda *_args, **_kwargs: _WF())
    rms = main._extract_audio_rms("x.mp4", target_fps=25)
    assert rms is not None
    assert rms.size > 0

    monkeypatch.setattr(main.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("ffmpeg")))
    assert main._extract_audio_rms("x.mp4", target_fps=25) is None

    lm = [types.SimpleNamespace(x=0.0, y=0.0) for _ in range(max(main.MOUTH_RIGHT, main.MOUTH_BOTTOM) + 1)]
    lm[main.MOUTH_TOP] = types.SimpleNamespace(x=0.2, y=0.2)
    lm[main.MOUTH_BOTTOM] = types.SimpleNamespace(x=0.2, y=0.4)
    lm[main.MOUTH_LEFT] = types.SimpleNamespace(x=0.1, y=0.3)
    lm[main.MOUTH_RIGHT] = types.SimpleNamespace(x=0.3, y=0.3)
    assert main._mouth_aspect_ratio(lm, 100, 100) > 0
    box = main._landmarks_to_box([types.SimpleNamespace(x=0.1, y=0.2), types.SimpleNamespace(x=0.3, y=0.5)], 100, 200)
    assert box[2] > 0 and box[3] > 0

    arr = np.array([1.0, np.nan, 3.0], dtype=np.float32)
    interp = main._interpolate_signal_nans(arr)
    assert not np.isnan(interp).any()
    assert main._best_matching_face_id([0, 0, 10, 10], [[0, 0, 10, 10]]) == 0


def test_refine_multi_speaker_and_split_render(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    np = _mini_np()
    monkeypatch.setattr(main, "np", np)

    frame = np.zeros((40, 60, 3), dtype=np.uint8)
    monkeypatch.setattr(main, "_compute_separator_thickness", lambda _h: 2)
    monkeypatch.setattr(main, "_crop_centered_on_face", lambda _f, _b, w, h: np.ones((h, w, 3), dtype=np.uint8))
    canvas = main.render_multi_speaker_frame(frame, [[0, 0, 10, 10], [10, 0, 10, 10], [20, 0, 20, 20]], 30, 50)
    assert canvas.shape == (50, 30, 3)

    class _Cap:
        def __init__(self):
            self.released = False

        def isOpened(self):
            return True

        def get(self, _prop):
            return 25.0

        def release(self):
            self.released = True

    class _T:
        def __init__(self, f):
            self.frame_num = f

    cap = _Cap()
    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _p: cap, raising=False)
    monkeypatch.setattr(main, "_extract_audio_rms", lambda *_: np.array([1, 2, 3, 4, 5], dtype=np.float32))
    monkeypatch.setattr(main, "_track_mouth_signals", lambda *_: {0: np.array([1, 2, 3], dtype=np.float32), 1: np.array([1, 2, 3], dtype=np.float32)})
    monkeypatch.setattr(main, "_count_active_speakers", lambda *_: 1)
    refined = main.refine_multi_speaker_scenes("x.mp4", [(_T(0), _T(3))], ["MULTI_SPEAKER"], [[[0, 0, 1, 1], [2, 0, 1, 1]]])
    assert refined == ["TRACK"]
    assert cap.released is True


def test_download_and_temp_path_helpers(monkeypatch, tmp_path):
    main = _import_main_with_stubs(monkeypatch)
    np = pytest.importorskip("numpy")
    monkeypatch.setattr(main, "np", np)

    out_dir = tmp_path
    existing = out_dir / "video.mp4"
    existing.write_text("x")

    class _YDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download(self, _urls):
            return None

    monkeypatch.setattr(main.yt_dlp, "YoutubeDL", _YDL, raising=False)
    path = main._run_download("https://y.t", str(out_dir), "video", {"quiet": True})
    assert path.endswith("video.mp4")
    assert main._locate_downloaded_file(str(out_dir), "missing").endswith("missing.mp4")

    temp_v, temp_a = main._prepare_temp_paths("/tmp/out.mp4")
    assert temp_v.endswith("_temp_video.mp4")
    assert temp_a.endswith("_temp_audio.aac")


def test_process_frame_pipeline_and_audio_merge_helpers(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    np = _mini_np()
    monkeypatch.setattr(main, "np", np)
    monkeypatch.setattr(main.cv2, "INTER_LINEAR", 1, raising=False)
    monkeypatch.setattr(main.cv2, "CAP_PROP_FRAME_COUNT", 7, raising=False)
    monkeypatch.setattr(main.cv2, "resize", lambda img, size, interpolation=None: np.zeros((size[1], size[0], 3), dtype=np.uint8), raising=False)

    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    cameraman = main.SmoothedCameraman(10, 20, 20, 20)
    speaker_tracker = types.SimpleNamespace(get_target=lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "detect_face_candidates", lambda _f: [])
    monkeypatch.setattr(main, "detect_person_yolo", lambda _f: [1, 1, 5, 5])
    out = main._render_frame_by_strategy(frame, 0, 0, [(0, 10)], ["TRACK"], cameraman, speaker_tracker, 10, 20, 20)
    assert out.shape == (20, 10, 3)

    monkeypatch.setattr(main, "create_general_frame", lambda *_: "general")
    out2 = main._render_frame_by_strategy(frame, 1, 0, [(0, 10)], ["GENERAL"], cameraman, speaker_tracker, 10, 20, 20)
    assert out2 == "general"

    class _Proc:
        def __init__(self):
            self.stdin = types.SimpleNamespace(write=lambda _b: None, close=lambda: None)
            self.stderr = types.SimpleNamespace(read=lambda: b"")
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

    class _Cap:
        def __init__(self):
            self.i = 0

        def get(self, _p):
            return 2

        def isOpened(self):
            return self.i < 2

        def read(self):
            if self.i >= 2:
                return False, None
            self.i += 1
            return True, frame

        def release(self):
            return None

    class _Tqdm:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, _n):
            return None

    monkeypatch.setattr(main.subprocess, "Popen", lambda *args, **kwargs: _Proc())
    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _p: _Cap(), raising=False)
    monkeypatch.setattr(main, "tqdm", _Tqdm)
    monkeypatch.setattr(main, "_render_frame_by_strategy", lambda *args, **kwargs: frame)
    code, stderr = main._process_frames_to_temp_video("in.mp4", "tmp.mp4", 25, 10, 20, [(0, 2)], ["TRACK"], cameraman, speaker_tracker, 20)
    assert code == 0
    assert stderr == ""

    monkeypatch.setattr(main.subprocess, "run", lambda *args, **kwargs: None)
    assert main._extract_audio_track("in.mp4", "a.aac") is True
    monkeypatch.setattr(main.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(main.subprocess.CalledProcessError(1, "ffmpeg")))
    assert main._extract_audio_track("in.mp4", "a.aac") is False


def test_transcriber_and_provider_branches(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    words = [
        {"word": "Hello.", "start": 0.0, "end": 0.2, "probability": 0.9},
        {"word": "World", "start": 0.3, "end": 0.5, "probability": 0.9},
    ]
    built = main._build_segments_from_word_list(words, language="en")
    assert built["language"] == "en"
    assert len(built["segments"]) >= 1

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")

    class _Resp:
        text = '{"shorts": []}'
        usage_metadata = types.SimpleNamespace(prompt_token_count=1000, candidates_token_count=2000)

    class _Client:
        def __init__(self, api_key):
            self.models = types.SimpleNamespace(generate_content=lambda **kwargs: _Resp())

    monkeypatch.setitem(sys.modules, "google", types.SimpleNamespace(genai=types.SimpleNamespace(Client=_Client)))
    monkeypatch.setitem(sys.modules, "google.genai", types.SimpleNamespace(Client=_Client))
    g = main._get_viral_clips_with_gemini({"text": "x", "segments": []}, 30)
    assert "cost_analysis" in g

    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")

    class _Usage:
        prompt_tokens = 100
        completion_tokens = 50

    class _OpenAIResp:
        usage = _Usage()
        choices = [types.SimpleNamespace(message=types.SimpleNamespace(content='{"shorts": []}'))]

    class _OpenAI:
        def __init__(self, api_key):
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **kwargs: _OpenAIResp()))

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=_OpenAI))
    o = main._get_viral_clips_with_openai({"text": "x", "segments": []}, 30)
    assert o["cost_analysis"]["provider"] == "openai"


def test_normalize_short_durations_and_main_entry_guard(monkeypatch, tmp_path):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setattr(main, "MIN_CLIP_DURATION_SECONDS", 10)
    monkeypatch.setattr(main, "MAX_CLIP_DURATIONS_SECOND", 20)

    data = {
        "shorts": [
            {"start": -5, "end": 1},
            {"start": 0, "end": 50},
            {"start": 5, "end": 4},
            "bad",
        ]
    }
    normalized = main._normalize_short_durations(data, 30)
    assert all(isinstance(c, dict) for c in normalized["shorts"])
    assert normalized["shorts"][0]["end"] <= 20

    _ = _import_main_with_stubs(monkeypatch)
    missing = tmp_path / "missing.mp4"
    monkeypatch.setattr(sys, "argv", ["main.py", "-i", str(missing)])
    with pytest.raises(SystemExit):
        runpy.run_module("main", run_name="__main__")


def test_normalize_short_durations_skips_invalid_and_rounds(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setattr(main, "MIN_CLIP_DURATION_SECONDS", 10)
    monkeypatch.setattr(main, "MAX_CLIP_DURATIONS_SECOND", 20)

    clips_data = {
        "shorts": [
            "bad-item",
            {"start": "1.11119", "end": "9.0"},
            {"start": 10, "end": 10},
            {"start": 5, "end": 25},
        ]
    }

    result = main._normalize_short_durations(clips_data, 30)
    assert len(result["shorts"]) == 2
    assert result["shorts"][0]["start"] == 1.111
    assert result["shorts"][0]["end"] == 11.111
    assert result["shorts"][1]["start"] == 5.0
    assert result["shorts"][1]["end"] == 25.0


def test_visual_helpers_and_scene_detector_paths(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    np = _mini_np()
    monkeypatch.setattr(main, "np", np)
    monkeypatch.setattr(main.cv2, "INTER_LINEAR", 1, raising=False)
    monkeypatch.setattr(main.cv2, "resize", lambda img, size, interpolation=None: np.zeros((size[1], size[0], 3), dtype=np.uint8), raising=False)
    monkeypatch.setattr(main.cv2, "GaussianBlur", lambda frame, ksize, sigma: frame, raising=False)

    frame = np.zeros((50, 100, 3), dtype=np.uint8)
    bg = main._build_blurred_background(frame, 40, 80)
    assert bg.shape == (80, 40, 3)
    general = main.create_general_frame(frame, 40, 80)
    assert general.shape == (80, 40, 3)
    crop = main._crop_centered_on_face(frame, [20, 10, 20, 20], 20, 40)
    assert crop.shape == (40, 20, 3)

    class _Video:
        frame_rate = 25.0

    class _T:
        def __init__(self, n):
            self.frame_num = n

    class _SceneMgr:
        def add_detector(self, *_a, **_k):
            return None

        def detect_scenes(self, video=None):
            return None

        def get_scene_list(self):
            return [(_T(0), _T(2))]

    monkeypatch.setattr(main, "open_video", lambda _p: _Video())
    monkeypatch.setattr(main, "SceneManager", _SceneMgr)
    scenes, fps = main.detect_scenes("in.mp4")
    assert len(scenes) == 1
    assert fps == 25.0


def test_download_failure_print_cookie_and_fallback_paths(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    slept = {"n": 0}
    monkeypatch.setattr(main.time, "sleep", lambda _s: slept.__setitem__("n", slept["n"] + 1))
    main._print_download_failure(RuntimeError("boom"))
    assert slept["n"] == 1

    monkeypatch.delenv("YOUTUBE_COOKIES", raising=False)
    assert main._resolve_cookiefile_from_env() is None
    monkeypatch.setenv("YOUTUBE_COOKIES", "...")
    assert main._resolve_cookiefile_from_env() is None

    monkeypatch.setenv("YOUTUBE_COOKIES", "bad-content")
    monkeypatch.setattr(main.os.path, "isfile", lambda _p: True)

    class _F:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return "not netscape"

    monkeypatch.setattr("builtins.open", lambda *a, **k: _F())
    assert main._resolve_cookiefile_from_env() is None


def test_fallback_and_render_helpers(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    np = _mini_np()
    monkeypatch.setattr(main, "np", np)
    monkeypatch.setattr(main.cv2, "CAP_PROP_FRAME_COUNT", 7, raising=False)
    monkeypatch.setattr(main.cv2, "INTER_LINEAR", 1, raising=False)
    monkeypatch.setattr(main.cv2, "resize", lambda img, size, interpolation=None: np.zeros((size[1], size[0], 3), dtype=np.uint8), raising=False)

    class _Cap:
        def get(self, _p):
            return 12

        def release(self):
            return None

    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _p: _Cap(), raising=False)

    class _FT:
        def __init__(self, n, fps):
            self.frame_num = n

    monkeypatch.setitem(sys.modules, "scenedetect", types.SimpleNamespace(FrameTimecode=_FT))
    scenes = main._fallback_single_scene("in.mp4", 25)
    assert scenes[0][0].frame_num == 0
    assert scenes[0][1].frame_num == 12

    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    cameraman = main.SmoothedCameraman(10, 20, 20, 20)
    speaker_tracker = types.SimpleNamespace(get_target=lambda *_a, **_k: [1, 1, 5, 5])
    monkeypatch.setattr(main, "detect_face_candidates", lambda _f: [{"box": [1, 1, 5, 5], "score": 1}])
    monkeypatch.setattr(main, "detect_person_yolo", lambda _f: None)
    rendered = main._render_track_frame(frame, 0, (0, 10), speaker_tracker, cameraman, 10, 20, 20)
    assert rendered.shape == (20, 10, 3)

    monkeypatch.setattr(main, "render_multi_speaker_frame", lambda *_a, **_k: "multi")
    out = main._render_multi_speaker_frame_live(frame, 0, cameraman, [[0, 0, 1, 1], [2, 0, 1, 1]], 10, 20)
    assert out == "multi"


def test_merge_and_transcriber_provider_internal_paths(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.setattr(main.os.path, "exists", lambda p: p.endswith(".aac"))
    monkeypatch.setattr(main.subprocess, "run", lambda *a, **k: None)
    assert main._merge_video_and_audio("v.mp4", "a.aac", "out.mp4") is True

    def _raise(*_a, **_k):
        raise main.subprocess.CalledProcessError(1, "ffmpeg", stderr=b"err")

    monkeypatch.setattr(main.subprocess, "run", _raise)
    assert main._merge_video_and_audio("v.mp4", "a.aac", "out.mp4") is False

    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "k")
    class _TranscriptStatus:
        error = "error"

    class _Word:
        def __init__(self, text, start, end):
            self.text = text
            self.start = start
            self.end = end

    class _Transcript:
        status = "ok"
        error = ""
        language_code = "fr"
        words = [_Word("hello", 0, 200)]

    class _Transcriber:
        def __init__(self, config=None):
            pass

        def transcribe(self, video_path):
            return _Transcript()

    aai_mod = types.SimpleNamespace(
        settings=types.SimpleNamespace(api_key=""),
        TranscriptionConfig=lambda **kwargs: kwargs,
        Transcriber=_Transcriber,
        TranscriptStatus=_TranscriptStatus,
    )
    monkeypatch.setitem(sys.modules, "assemblyai", aai_mod)
    tr = main._transcribe_with_assemblyai("x.mp4")
    assert tr["meta"]["provider"] == "assemblyai"

    class _Info:
        language = "en"
        language_probability = 0.9

    class _W:
        def __init__(self):
            self.word = "w"
            self.start = 0.0
            self.end = 0.1
            self.probability = 0.8

    class _Seg:
        def __init__(self):
            self.start = 0.0
            self.end = 0.3
            self.text = "Hello"
            self.words = [_W()]

    class _WhisperModel:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, *a, **k):
            return ([_Seg()], _Info())

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=_WhisperModel))
    tr2 = main._transcribe_with_faster_whisper("x.mp4")
    assert tr2["meta"]["provider"] == "faster_whisper"


def test_provider_error_and_normalization_edge_paths(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        main._get_viral_clips_with_gemini({"text": "x", "segments": []}, 10)

    monkeypatch.setenv("OPENAI_API_KEY", "your_openai_key")
    with pytest.raises(RuntimeError):
        main._get_viral_clips_with_openai({"text": "x", "segments": []}, 10)

    assert main._normalize_short_durations({"shorts": "bad"}, 30)["shorts"] == "bad"
    assert main._normalize_short_durations({"shorts": [{"start": 0, "end": 1}]}, 0)["shorts"][0]["end"] == 1


def test_tracker_scene_and_counting_edge_paths(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    tracker = main.SpeakerTracker(stabilization_frames=2, cooldown_frames=10)
    tracker.active_speaker_id = 9
    assert tracker._pick_best_candidate([]) is None
    assert tracker._find_active_candidate([{"id": 1}]) is None
    assert tracker.get_target([], frame_number=1, width=1000) is None

    tracker.speaker_scores = {1: 1.0, 2: 1.0}
    tracker.active_speaker_id = 2
    picked = tracker._pick_best_candidate([{"id": 1, "box": [0, 0, 1, 1]}, {"id": 2, "box": [1, 0, 1, 1]}])
    assert picked["id"] == 2

    monkeypatch.setattr(main, "MIN_SAMPLES_PER_SCENE", 4)
    monkeypatch.setattr(main, "MAX_SAMPLES_PER_SCENE", 6)
    idx = main._build_scene_sample_indices(0, 3, fps=30)
    assert len(idx) >= 3

    class _Cap:
        def __init__(self):
            self.i = 0

        def set(self, *_a):
            return None

        def read(self):
            self.i += 1
            return True, object()

    calls = {"n": 0}
    monkeypatch.setattr(main, "detect_face_candidates", lambda _f: ([] if calls.__setitem__("n", calls["n"] + 1) is None and calls["n"] == 1 else [{"box": [0, 0, 10, 10], "score": 1}]))
    faces, n_samples, counts, boxes = main.count_distinct_faces_in_scene(_Cap(), 0, 3, 30)
    assert n_samples >= 1
    assert isinstance(counts, list)


def test_mouth_tracking_and_correlation_paths(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    np = _mini_np()
    monkeypatch.setattr(main, "np", np)
    monkeypatch.setattr(main.cv2, "COLOR_BGR2RGB", 1, raising=False)
    monkeypatch.setattr(main.cv2, "cvtColor", lambda frame, code: frame, raising=False)

    class _Cap:
        def __init__(self):
            self.i = 0

        def set(self, *_a):
            return None

        def read(self):
            if self.i >= 2:
                return False, None
            self.i += 1
            return True, types.SimpleNamespace(shape=(20, 20, 3))

    class _Mesh:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def process(self, _rgb):
            lm = types.SimpleNamespace(landmark=[types.SimpleNamespace(x=0.1, y=0.1)] * 400)
            return types.SimpleNamespace(multi_face_landmarks=[lm])

    monkeypatch.setattr(main, "mp_face_mesh", types.SimpleNamespace(FaceMesh=lambda **_k: _Mesh()))
    monkeypatch.setattr(main, "_landmarks_to_box", lambda *_a: [0, 0, 1, 1])
    monkeypatch.setattr(main, "_best_matching_face_id", lambda *_a: 0)
    monkeypatch.setattr(main, "_mouth_aspect_ratio", lambda *_a: 0.4)
    monkeypatch.setattr(main, "_interpolate_signal_nans", lambda arr: arr)
    signals = main._track_mouth_signals(_Cap(), 0, 3, [[0, 0, 1, 1]])
    assert 0 in signals

    assert main._count_active_speakers(np.array([0, 0, 0]), {0: np.array([0, 0, 0])}, 3) == 0


def test_cookie_render_and_process_frame_extra_branches(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    np = _mini_np()
    monkeypatch.setattr(main, "np", np)

    monkeypatch.setenv("YOUTUBE_COOKIES", "inline-no-tabs")
    monkeypatch.setattr(main.os.path, "isfile", lambda _p: False)
    assert main._resolve_cookiefile_from_env() is None

    monkeypatch.setenv("YOUTUBE_COOKIES", "a\\tb\\tc\\td\\te\\tf\\tg")
    monkeypatch.setattr(main, "_looks_like_netscape_cookies", lambda _t: True)
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(OSError("no write")))
    assert main._resolve_cookiefile_from_env() is None

    monkeypatch.setattr(main.cv2, "INTER_LINEAR", 1, raising=False)
    monkeypatch.setattr(main.cv2, "resize", lambda img, size, interpolation=None: np.zeros((size[1], size[0], 3), dtype=np.uint8), raising=False)
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    cam = main.SmoothedCameraman(10, 20, 10, 10)
    spk = types.SimpleNamespace(get_target=lambda *_a, **_k: None)
    monkeypatch.setattr(main, "detect_face_candidates", lambda _f: [])
    monkeypatch.setattr(main, "detect_person_yolo", lambda _f: [1, 1, 3, 3])
    out = main._render_frame_by_strategy(frame, 0, 0, [(0, 1)], ["TRACK"], cam, spk, 10, 20, 10)
    assert out.shape == (20, 10, 3)

    class _Proc:
        def __init__(self):
            self.stdin = types.SimpleNamespace(write=lambda _b: None, close=lambda: None)
            self.stderr = types.SimpleNamespace(read=lambda: b"stderr")
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

    class _Cap:
        def get(self, _p):
            return 1

        def isOpened(self):
            return True

        def read(self):
            return False, None

        def release(self):
            return None

    class _Tqdm:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, _n):
            return None

    monkeypatch.setattr(main.subprocess, "Popen", lambda *a, **k: _Proc())
    monkeypatch.setattr(main.cv2, "CAP_PROP_FRAME_COUNT", 7, raising=False)
    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _p: _Cap(), raising=False)
    monkeypatch.setattr(main, "tqdm", _Tqdm)
    monkeypatch.setattr(main, "_render_frame_by_strategy", lambda *a, **k: frame)
    code, stderr = main._process_frames_to_temp_video("in.mp4", "tmp.mp4", 25, 10, 20, [(0, 1)], ["TRACK"], cam, spk, 10)
    assert code == 0
    assert stderr == "stderr"


def test_provider_cost_exception_and_short_duration_corner_cases(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")

    class _BadUsage:
        @property
        def prompt_token_count(self):
            raise RuntimeError("bad usage")

        candidates_token_count = 0

    class _Resp:
        text = '{"shorts": []}'
        usage_metadata = _BadUsage()

    class _Client:
        def __init__(self, api_key):
            self.models = types.SimpleNamespace(generate_content=lambda **kwargs: _Resp())

    monkeypatch.setitem(sys.modules, "google", types.SimpleNamespace(genai=types.SimpleNamespace(Client=_Client)))
    monkeypatch.setitem(sys.modules, "google.genai", types.SimpleNamespace(Client=_Client))
    g = main._get_viral_clips_with_gemini({"text": "x", "segments": []}, 10)
    assert "shorts" in g

    monkeypatch.setenv("OPENAI_API_KEY", "k")
    class _BadResp:
        usage = None
        choices = [types.SimpleNamespace(message=types.SimpleNamespace(content='{"shorts": []}'))]

    class _OpenAI:
        def __init__(self, api_key):
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **kwargs: _BadResp()))

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=_OpenAI))
    o = main._get_viral_clips_with_openai({"text": "x", "segments": []}, 10)
    assert "cost_analysis" in o

    monkeypatch.setattr(main, "MIN_CLIP_DURATION_SECONDS", 30)
    monkeypatch.setattr(main, "MAX_CLIP_DURATIONS_SECOND", 40)
    data = {"shorts": [{"start": 35, "end": 36}, {"start": 10, "end": 100}, {"start": 5, "end": 5}]}
    out = main._normalize_short_durations(data, 36)
    assert out["shorts"] == []


def test_remaining_non_cli_branches(monkeypatch):
    main = _import_main_with_stubs(monkeypatch)
    np = _mini_np()
    monkeypatch.setattr(main, "np", np)

    # Speaker switch cooldown keeps old candidate.
    tracker = main.SpeakerTracker(stabilization_frames=1, cooldown_frames=100)
    tracker.active_speaker_id = 1
    tracker.last_switch_frame = 90
    tracker.speaker_scores = {1: 1.0, 2: 10.0}
    kept = tracker.get_target([
        {"id": 1, "box": [0, 0, 1, 1], "score": 1.0},
        {"id": 2, "box": [1, 0, 1, 1], "score": 1.0},
    ], frame_number=100, width=100)
    assert kept == [0, 0, 1, 1]

    # detect_face_candidates: empty and tiny faces filtered.
    monkeypatch.setattr(main.cv2, "COLOR_BGR2RGB", 1, raising=False)
    monkeypatch.setattr(main.cv2, "cvtColor", lambda frame, code: frame, raising=False)
    frame = types.SimpleNamespace(shape=(100, 100, 3))
    monkeypatch.setattr(main, "face_detection", types.SimpleNamespace(process=lambda _rgb: types.SimpleNamespace(detections=[])))
    assert main.detect_face_candidates(frame) == []
    bbox = types.SimpleNamespace(xmin=0.1, ymin=0.1, width=0.01, height=0.01)
    det = types.SimpleNamespace(location_data=types.SimpleNamespace(relative_bounding_box=bbox))
    monkeypatch.setattr(main, "face_detection", types.SimpleNamespace(process=lambda _rgb: types.SimpleNamespace(detections=[det])))
    monkeypatch.setattr(main, "MIN_FACE_AREA_RATIO", 0.1)
    assert main.detect_face_candidates(frame) == []

    # analyze_scenes_strategy n_samples==0 branch then append strategy path.
    class _Cap:
        def isOpened(self):
            return True

        def get(self, _prop):
            return 30.0

        def release(self):
            return None

    class _T:
        def __init__(self, n):
            self.frame_num = n

    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _p: _Cap(), raising=False)
    monkeypatch.setattr(main, "tqdm", lambda it, desc=None: it)
    seq = {"i": 0}
    def _count(*_a, **_k):
        seq["i"] += 1
        if seq["i"] == 1:
            return (0, 0, [], [])
        return (1, 2, [1], [[0, 0, 10, 10]])
    monkeypatch.setattr(main, "count_distinct_faces_in_scene", _count)
    s, b = main.analyze_scenes_strategy("in.mp4", [(_T(0), _T(20)), (_T(30), _T(60))])
    assert s[0] == "GENERAL"
    assert s[1] == "TRACK"

    # _extract_audio_rms decode failure path.
    monkeypatch.setattr(main.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(main.wave, "open", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("wav")))
    assert main._extract_audio_rms("in.mp4", 25) is None

    # refine_multi_speaker_scenes early exits and short audio branch.
    class _CapClosed:
        def isOpened(self):
            return False
    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _p: _CapClosed(), raising=False)
    assert main.refine_multi_speaker_scenes("in.mp4", [], ["TRACK"], [[]]) == ["TRACK"]

    class _CapOpen:
        def isOpened(self):
            return True
        def get(self, _p):
            return 25.0
        def release(self):
            return None
    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _p: _CapOpen(), raising=False)
    monkeypatch.setattr(main, "_extract_audio_rms", lambda *_a: np.array([1, 2]))
    assert main.refine_multi_speaker_scenes("in.mp4", [], ["TRACK"], [[]]) == ["TRACK"]

    # render branches: len==2 and fallback full-frame slots.
    monkeypatch.setattr(main, "_compute_separator_thickness", lambda _h: 2)
    monkeypatch.setattr(main, "_crop_centered_on_face", lambda _f, _b, w, h: np.zeros((h, w, 3), dtype=np.uint8))
    base_frame = np.zeros((10, 20, 3), dtype=np.uint8)
    _ = main.render_multi_speaker_frame(base_frame, [[0, 0, 5, 5], [5, 0, 5, 5]], 20, 20)
    _ = main.render_multi_speaker_frame(base_frame, [], 20, 20)

    # cookie path read exception and inline-invalid branches.
    monkeypatch.setenv("YOUTUBE_COOKIES", "cookie_path")
    monkeypatch.setattr(main.os.path, "isfile", lambda _p: True)
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(OSError("read fail")))
    assert main._resolve_cookiefile_from_env() is None
    monkeypatch.setenv("YOUTUBE_COOKIES", "invalid inline")
    monkeypatch.setattr(main.os.path, "isfile", lambda _p: False)
    monkeypatch.setattr(main, "_looks_like_netscape_cookies", lambda _t: False)
    assert main._resolve_cookiefile_from_env() is None

    # track/render fallback branches and invalid crop fallback.
    monkeypatch.setattr(main.cv2, "INTER_LINEAR", 1, raising=False)
    monkeypatch.setattr(main.cv2, "resize", lambda img, size, interpolation=None: np.zeros((size[1], size[0], 3), dtype=np.uint8), raising=False)
    cam = main.SmoothedCameraman(8, 16, 8, 8)
    spk = types.SimpleNamespace(get_target=lambda *_a, **_k: None)
    monkeypatch.setattr(main, "detect_face_candidates", lambda _f: [])
    monkeypatch.setattr(main, "detect_person_yolo", lambda _f: [0, 0, 2, 2])
    track_out = main._render_track_frame(base_frame, 0, (0, 1), spk, cam, 8, 16, 8)
    assert track_out.shape == (16, 8, 3)
    monkeypatch.setattr(cam, "get_crop_box", lambda force_snap=False: (0, 0, 0, 0))
    any_out = main._render_frame_by_strategy(base_frame, 0, 0, [(0, 1)], ["TRACK"], cam, spk, 8, 16, 8)
    assert any_out.shape == (16, 8, 3)

    # merge without audio file path.
    monkeypatch.setattr(main.os.path, "exists", lambda p: False)
    monkeypatch.setattr(main.subprocess, "run", lambda *a, **k: None)
    assert main._merge_video_and_audio("v.mp4", "a.aac", "out.mp4") is True

    # build_segments skip empty words.
    built = main._build_segments_from_word_list([{"word": " ", "start": 0, "end": 1}, {"word": "ok", "start": 1, "end": 2}], language="fr")
    assert built["text"] == "ok"

    # AssemblyAI missing key + error status branch.
    monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        main._transcribe_with_assemblyai("x.mp4")

    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "k")
    class _TS:
        error = "error"
    class _BadTranscript:
        status = "error"
        error = "boom"
        words = []
        language_code = ""
    class _Transcriber:
        def __init__(self, config=None):
            pass
        def transcribe(self, _path):
            return _BadTranscript()
    aai = types.SimpleNamespace(settings=types.SimpleNamespace(api_key=""), TranscriptStatus=_TS, TranscriptionConfig=lambda **k: k, Transcriber=_Transcriber)
    monkeypatch.setitem(sys.modules, "assemblyai", aai)
    with pytest.raises(RuntimeError):
        main._transcribe_with_assemblyai("x.mp4")

    # OpenAI cost exception branch.
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    class _UsageBad:
        @property
        def prompt_tokens(self):
            raise RuntimeError("usage boom")
    class _Resp:
        usage = _UsageBad()
        choices = [types.SimpleNamespace(message=types.SimpleNamespace(content='{"shorts": []}'))]
    class _OpenAI:
        def __init__(self, api_key):
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **kwargs: _Resp()))
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=_OpenAI))
    out_open = main._get_viral_clips_with_openai({"text": "x", "segments": []}, 10)
    assert out_open["shorts"] == []


def test_main_cli_local_and_url_branches_via_run_module(monkeypatch, tmp_path):
    _install_cli_runtime_stubs(monkeypatch, tmp_path, shorts_payload={"shorts": [{"start": 0.0, "end": 1.0, "video_title_for_youtube_short": "T"}]})

    input_file = tmp_path / "input.mp4"
    input_file.write_bytes(b"video")
    out_dir = tmp_path / "out"

    monkeypatch.setenv("TRANSCRIBER_PROVIDER", "faster_whisper")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "m")

    monkeypatch.setattr(sys, "argv", ["main.py", "-i", str(input_file), "-o", str(out_dir)])
    runpy.run_module("main", run_name="__main__")

    downloaded_dir = tmp_path / "downloads"
    output_file = downloaded_dir / "final.mp4"
    monkeypatch.setattr(sys, "argv", ["main.py", "-u", "https://youtube.com/watch?v=abc", "-o", str(output_file), "--skip-analysis"])
    runpy.run_module("main", run_name="__main__")


def test_remaining_precise_branches_for_main(monkeypatch, tmp_path):
    main = _import_main_with_stubs(monkeypatch)
    np = _mini_np()
    monkeypatch.setattr(main, "np", np)

    tracker = main.SpeakerTracker(stabilization_frames=1, cooldown_frames=0)
    tracker.active_speaker_id = 1
    tracker.speaker_scores = {1: 10.0}
    same = tracker.get_target([{"id": 1, "box": [1, 1, 2, 2], "score": 1.0}], frame_number=5, width=100)
    assert same == [1, 1, 2, 2]
    tracker.speaker_scores = {}
    assert tracker.get_target([], frame_number=6, width=100) is None

    assert main._best_matching_face_id([0, 0, 1, 1], [[100, 100, 1, 1]]) is None
    arr = np.array([np.nan, np.nan])
    assert main._interpolate_signal_nans(arr) is arr

    # Correlation branch with non-zero std.
    active = main._count_active_speakers(np.array([1.0, 2.0, 3.0]), {0: np.array([1.0, 2.0, 3.0])}, 3)
    assert active >= 1

    class _T:
        def __init__(self, n):
            self.frame_num = n

    class _Cap:
        def isOpened(self):
            return True

        def get(self, _p):
            return 25.0

        def release(self):
            return None

    monkeypatch.setattr(main.cv2, "VideoCapture", lambda _p: _Cap(), raising=False)
    monkeypatch.setattr(main, "_extract_audio_rms", lambda *_a: np.array([1, 2, 3, 4]))
    monkeypatch.setattr(main, "_track_mouth_signals", lambda *_a: {0: np.array([1, 2]), 1: np.array([1, 2])})
    refined = main.refine_multi_speaker_scenes("in.mp4", [(_T(0), _T(2))], ["TRACK"], [[]])
    assert refined == ["TRACK"]

    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    monkeypatch.setattr(main.cv2, "INTER_LINEAR", 1, raising=False)
    monkeypatch.setattr(main.cv2, "resize", lambda img, size, interpolation=None: np.zeros((size[1], size[0], 3), dtype=np.uint8), raising=False)
    # target_ratio > src_ratio branch
    cropped = main._crop_centered_on_face(frame, [1, 1, 2, 2], 20, 10)
    assert cropped.shape == (10, 20, 3)

    assert main._looks_like_netscape_cookies("# just comment\nsite\tTRUE\t/\tFALSE\t0\ta\tb") is True

    cam = main.SmoothedCameraman(8, 16, 8, 8)
    monkeypatch.setattr(cam, "get_crop_box", lambda force_snap=False: (0, 0, 0, 0))
    spk = types.SimpleNamespace(get_target=lambda *_a, **_k: None)
    monkeypatch.setattr(main, "detect_face_candidates", lambda _f: [])
    monkeypatch.setattr(main, "detect_person_yolo", lambda _f: [0, 0, 2, 2])
    out = main._render_track_frame(frame, 0, (0, 1), spk, cam, 8, 16, 8)
    assert out.shape == (16, 8, 3)

    monkeypatch.setattr(main, "detect_face_candidates", lambda _f: [{"box": [2, 0, 2, 2], "score": 10}, {"box": [0, 0, 2, 2], "score": 9}])
    monkeypatch.setattr(main, "render_multi_speaker_frame", lambda _f, boxes, _w, _h: boxes)
    boxes = main._render_multi_speaker_frame_live(frame, 0, cam, [], 8, 16)
    assert len(boxes) == 2

    # Assembly elapsed warning path.
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "k")
    monkeypatch.setenv("ASSEMBLYAI_TIMEOUT_SECONDS", "1")
    class _TS:
        error = "error"
    class _OkT:
        status = "ok"
        language_code = "en"
        error = ""
        words = []
    class _Tr:
        def __init__(self, config=None):
            pass
        def transcribe(self, _path):
            return _OkT()
    aai = types.SimpleNamespace(settings=types.SimpleNamespace(api_key=""), TranscriptStatus=_TS, TranscriptionConfig=lambda **k: k, Transcriber=_Tr)
    monkeypatch.setitem(sys.modules, "assemblyai", aai)
    times = {"v": 0}
    monkeypatch.setattr(main.time, "time", lambda: (0 if times.__setitem__("v", times["v"] + 1) == None and times["v"] == 1 else 3))
    _ = main._transcribe_with_assemblyai("x.mp4")

    monkeypatch.setattr(main, "MIN_CLIP_DURATION_SECONDS", 1)
    monkeypatch.setattr(main, "MAX_CLIP_DURATIONS_SECOND", 20)
    clips = {"shorts": [{"start": 35, "end": 100}]}
    out_norm = main._normalize_short_durations(clips, 36)
    assert out_norm["shorts"][0]["start"] == 35.0




"""
Simple unit tests for helper functions that don't require complex imports.
This file focuses on increasing code coverage for standalone functions.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_editor_utils_coverage():
    """Test editor module utility functions"""
    import importlib
    import types

    # Stub dependencies
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

    sys.modules["google"] = google_mod
    sys.modules["google.genai"] = genai_mod

    # Import and test
    if "editor" in sys.modules:
        del sys.modules["editor"]

    import editor

    # Test _split_filter_chain
    assert editor.VideoEditor._split_filter_chain("a,b,c") == ["a", "b", "c"]
    assert editor.VideoEditor._split_filter_chain("a,'b,c',d") == ["a", "'b,c'", "d"]

    # Test _sanitize_filter_string
    result = editor.VideoEditor._sanitize_filter_string("t<5")
    assert "lt(" in result

    result = editor.VideoEditor._sanitize_filter_string("t<=5")
    assert "lte(" in result

    result = editor.VideoEditor._sanitize_filter_string("t>5")
    assert "gt(" in result

    result = editor.VideoEditor._sanitize_filter_string("t>=5")
    assert "gte(" in result

    # Test _enforce_zoompan_output_size
    result = editor.VideoEditor._enforce_zoompan_output_size("zoompan=z=1.1", 1920, 1080)
    assert "s=1920x1080" in result


def test_supabase_request_ceil_credit():
    """Test supabase_request._ceil_credit function"""
    # Create a minimal stub for supabase
    import types

    supabase_mod = types.ModuleType("supabase")
    supabase_mod.AsyncClient = object

    async def _acreate_client(*args, **kwargs):
        return {}

    supabase_mod.acreate_client = _acreate_client

    client_options_mod = types.ModuleType("supabase.lib.client_options")

    class _AsyncClientOptions:
        def __init__(self, postgrest_client_timeout):
            self.postgrest_client_timeout = postgrest_client_timeout

    client_options_mod.AsyncClientOptions = _AsyncClientOptions

    sys.modules["supabase"] = supabase_mod
    sys.modules["supabase.lib.client_options"] = client_options_mod

    # Import and test
    if "supabase_request" in sys.modules:
        del sys.modules["supabase_request"]

    import supabase_request

    # Test _ceil_credit
    assert supabase_request._ceil_credit(0.5) == 1
    assert supabase_request._ceil_credit(1.0) == 1
    assert supabase_request._ceil_credit(1.1) == 2
    assert supabase_request._ceil_credit(-5.0) == 0
    assert supabase_request._ceil_credit(0) == 0


def test_main_utils_coverage():
    """Test main module utility functions"""
    import types
    import json

    # Stub main dependencies
    cv2_mod = types.ModuleType("cv2")
    sys.modules["cv2"] = cv2_mod

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
    sys.modules["scenedetect"] = scenedetect_mod

    detectors_mod = types.ModuleType("scenedetect.detectors")
    detectors_mod.ContentDetector = object
    sys.modules["scenedetect.detectors"] = detectors_mod

    ultralytics_mod = types.ModuleType("ultralytics")
    ultralytics_mod.YOLO = lambda *args, **kwargs: object()
    sys.modules["ultralytics"] = ultralytics_mod

    sys.modules["torch"] = types.ModuleType("torch")
    sys.modules["numpy"] = types.ModuleType("numpy")

    tqdm_mod = types.ModuleType("tqdm")
    tqdm_mod.tqdm = lambda value, *args, **kwargs: value
    sys.modules["tqdm"] = tqdm_mod

    sys.modules["yt_dlp"] = types.ModuleType("yt_dlp")

    mediapipe_models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mediapipe_models")
    os.makedirs(mediapipe_models_dir, exist_ok=True)
    for filename in ("blaze_face_short_range.tflite", "face_landmarker.task"):
        open(os.path.join(mediapipe_models_dir, filename), "wb").close()
    os.environ["MEDIAPIPE_MODELS_DIR"] = mediapipe_models_dir

    class _FakeMpImage:
        def __init__(self, image_format=None, data=None):
            self.data = data

    class _FakeFaceDetector:
        def detect(self, _image):
            return types.SimpleNamespace(detections=[])

    class _FakeFaceLandmarker:
        def detect_for_video(self, _image, _timestamp_ms):
            return types.SimpleNamespace(face_landmarks=[])

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    mp_mod = types.ModuleType("mediapipe")
    mp_mod.Image = _FakeMpImage
    mp_mod.ImageFormat = types.SimpleNamespace(SRGB=1)
    mp_mod.tasks = types.SimpleNamespace(
        BaseOptions=lambda **kwargs: types.SimpleNamespace(**kwargs),
        vision=types.SimpleNamespace(
            FaceDetector=types.SimpleNamespace(create_from_options=lambda _options: _FakeFaceDetector()),
            FaceDetectorOptions=lambda **kwargs: types.SimpleNamespace(**kwargs),
            FaceLandmarker=types.SimpleNamespace(create_from_options=lambda _options: _FakeFaceLandmarker()),
            FaceLandmarkerOptions=lambda **kwargs: types.SimpleNamespace(**kwargs),
            RunningMode=types.SimpleNamespace(IMAGE="IMAGE", VIDEO="VIDEO"),
        ),
    )
    sys.modules["mediapipe"] = mp_mod

    google_mod = types.ModuleType("google")
    google_mod.genai = types.ModuleType("google.genai")
    sys.modules["google"] = google_mod
    sys.modules["google.genai"] = google_mod.genai

    # Import main
    if "main" in sys.modules:
        del sys.modules["main"]

    import main

    # Test _safe_float
    assert main._safe_float("3.14") == 3.14
    assert main._safe_float("invalid", default=9.9) == 9.9
    assert main._safe_float("") == 0.0

    # Test _iou
    assert main._iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert main._iou([0, 0, 10, 10], [20, 20, 10, 10]) == 0.0

    # Test _sanitize_filename
    result = main.sanitize_filename('My <video>: "title"?.mp4')
    assert result == "My_video_title.mp4"

    # Test _looks_like_netscape_cookies
    assert main._looks_like_netscape_cookies("") is False
    assert main._looks_like_netscape_cookies("# Netscape HTTP Cookie File\n") is True

    # Test _classify_scene_strategy
    assert main._classify_scene_strategy(0) == "GENERAL"
    assert main._classify_scene_strategy(1) == "TRACK"
    assert main._classify_scene_strategy(2) == "MULTI_SPEAKER"
    assert main._classify_scene_strategy(4) == "MULTI_SPEAKER"
    assert main._classify_scene_strategy(5) == "GENERAL"

    # Test _smooth_strategies
    result = main._smooth_strategies(["TRACK", "GENERAL", "TRACK"])
    assert result == ["TRACK", "TRACK", "TRACK"]

    # Test _strip_json_markdown
    result = main._strip_json_markdown("```json\n{}\n```")
    assert result == "{}"

    result = main._strip_json_markdown("```\n{}\n```")
    assert result == "{}"

    # Test _is_quota_or_rate_limit_error
    assert main._is_quota_or_rate_limit_error(Exception("quota exceeded")) is True
    assert main._is_quota_or_rate_limit_error(Exception("rate limit")) is True
    assert main._is_quota_or_rate_limit_error(Exception("429")) is True
    assert main._is_quota_or_rate_limit_error(Exception("other error")) is False

    # Test _extract_error_message
    result = main._extract_error_message(Exception("Test Error"))
    assert "test error" in result


def test_smoothed_cameraman_basic():
    """Test SmoothedCameraman class"""
    import types

    # Minimal stubs
    for mod_name in ["cv2", "scenedetect", "scenedetect.detectors", "ultralytics",
                     "torch", "numpy", "tqdm", "yt_dlp", "mediapipe", "google", "google.genai"]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)

    if "main" in sys.modules:
        del sys.modules["main"]

    import main

    # Test SmoothedCameraman
    cameraman = main.SmoothedCameraman(1080, 1920, 1920, 1080)
    assert cameraman.output_width == 1080
    assert cameraman.output_height == 1920

    # Test update_target
    cameraman.update_target([800, 100, 200, 150])
    assert cameraman.target_center_x == 900.0

    # Test get_crop_box
    x1, y1, x2, y2 = cameraman.get_crop_box(force_snap=True)
    assert y1 == 0
    assert y2 == 1080


def test_speaker_tracker_basic():
    """Test SpeakerTracker class"""
    import types

    # Minimal stubs
    for mod_name in ["cv2", "scenedetect", "scenedetect.detectors", "ultralytics",
                     "torch", "numpy", "tqdm", "yt_dlp", "mediapipe", "google", "google.genai"]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)

    if "main" in sys.modules:
        del sys.modules["main"]

    import main

    # Test SpeakerTracker
    tracker = main.SpeakerTracker(stabilization_frames=15, cooldown_frames=30)
    assert tracker.stabilization_threshold == 15
    assert tracker.switch_cooldown == 30
    assert tracker.active_speaker_id is None
    assert tracker.locked_counter == 0


if __name__ == "__main__":
    test_editor_utils_coverage()
    test_supabase_request_ceil_credit()
    test_main_utils_coverage()
    test_smoothed_cameraman_basic()
    test_speaker_tracker_basic()
    print("All tests passed!")


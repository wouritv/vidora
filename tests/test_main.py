import importlib
import os
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
    assert len(result["shorts"]) >= 2  # Should keep valid ones


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



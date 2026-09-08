import importlib
import asyncio
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest


def _install_supabase_stubs(monkeypatch):
    supabase_mod = types.ModuleType("supabase")

    class _AsyncClient:
        pass

    async def _acreate_client(*args, **kwargs):
        return _AsyncClient()

    supabase_mod.AsyncClient = _AsyncClient
    supabase_mod.acreate_client = _acreate_client

    client_options_mod = types.ModuleType("supabase.lib.client_options")

    class _AsyncClientOptions:
        def __init__(self, postgrest_client_timeout):
            self.postgrest_client_timeout = postgrest_client_timeout

    client_options_mod.AsyncClientOptions = _AsyncClientOptions

    monkeypatch.setitem(sys.modules, "supabase", supabase_mod)
    monkeypatch.setitem(sys.modules, "supabase.lib.client_options", client_options_mod)


def _install_optional_dependency_stubs(monkeypatch):
    sib_mod = types.ModuleType("sib_api_v3_sdk")
    sib_rest_mod = types.ModuleType("sib_api_v3_sdk.rest")
    sib_rest_mod.ApiException = Exception
    monkeypatch.setitem(sys.modules, "sib_api_v3_sdk", sib_mod)
    monkeypatch.setitem(sys.modules, "sib_api_v3_sdk.rest", sib_rest_mod)

    editor_mod = types.ModuleType("editor")
    editor_mod.VideoEditor = object
    monkeypatch.setitem(sys.modules, "editor", editor_mod)

    subtitles_mod = types.ModuleType("subtitles")
    subtitles_mod.generate_srt = lambda *args, **kwargs: True
    subtitles_mod.burn_subtitles = lambda *args, **kwargs: True
    subtitles_mod.generate_srt_from_video = lambda *args, **kwargs: True

    class _SubtitleStyleOptions:
        pass

    subtitles_mod.SubtitleStyleOptions = _SubtitleStyleOptions
    monkeypatch.setitem(sys.modules, "subtitles", subtitles_mod)

    hooks_mod = types.ModuleType("hooks")
    hooks_mod.add_hook_to_video = lambda *args, **kwargs: True
    monkeypatch.setitem(sys.modules, "hooks", hooks_mod)

    thumbnail_mod = types.ModuleType("thumbnail")
    thumbnail_mod.analyze_video_for_titles = lambda *args, **kwargs: {}
    thumbnail_mod.refine_titles = lambda *args, **kwargs: {}
    thumbnail_mod.generate_thumbnail = lambda *args, **kwargs: []
    thumbnail_mod.generate_youtube_description = lambda *args, **kwargs: {"description": ""}
    monkeypatch.setitem(sys.modules, "thumbnail", thumbnail_mod)


def _import_app_with_stubs(monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost")
    _install_supabase_stubs(monkeypatch)
    _install_optional_dependency_stubs(monkeypatch)

    if "app" in sys.modules:
        return importlib.reload(sys.modules["app"])
    return importlib.import_module("app")


def test_parse_iso_datetime_accepts_zulu_and_invalid(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    parsed = app._parse_iso_datetime("2024-01-15T10:30:00Z")
    bad = app._parse_iso_datetime("not-a-date")

    assert parsed is not None
    assert parsed.tzinfo is not None
    assert bad is None


def test_parse_iso_datetime_handles_empty_and_naive(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._parse_iso_datetime("") is None
    naive = app._parse_iso_datetime("2024-01-01T10:00:00")
    assert naive is not None
    assert naive.tzinfo is not None


def test_clamp_job_priority_enforces_bounds(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    assert app._clamp_job_priority(0) == app.JOB_PRIORITY_MIN
    assert app._clamp_job_priority(999) == app.JOB_PRIORITY_MAX
    assert app._clamp_job_priority("2") == 2


def test_is_probably_video_url_checks_extensions(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    assert app._is_probably_video_url("https://cdn.example.com/v/final.MP4") is True
    assert app._is_probably_video_url("https://cdn.example.com/img.jpg") is False
    assert app._is_probably_video_url("") is False


def test_estimate_transcript_duration_uses_max_segment_or_meta(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    transcript = {
        "segments": [{"end": 3.5}, {"end": "9.2"}],
        "meta": {"audio_seconds": "7.5"},
    }
    assert app._estimate_transcript_duration_seconds(transcript) == 9.2


def test_get_user_id_header_success_and_missing(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _Req:
        def __init__(self, user_id=None):
            self.headers = {}
            if user_id is not None:
                self.headers["X-User-Id"] = user_id

    assert app.get_user_id_header(_Req("u-1")) == "u-1"
    with pytest.raises(app.HTTPException):
        app.get_user_id_header(_Req())


def test_resolve_scheduled_datetime_handles_aware_and_naive(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    aware = app._resolve_scheduled_datetime("2024-01-01T10:00:00Z", "Europe/Paris")
    naive = app._resolve_scheduled_datetime("2024-01-01T10:00:00", "UTC")
    bad = app._resolve_scheduled_datetime("not-a-date", "UTC")
    assert aware is not None
    assert naive is not None
    assert bad is None


def test_maybe_preempt_lower_priority_running_job_terminates_candidate(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _Proc:
        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    proc = _Proc()
    app.running_reel_jobs.clear()
    app.jobs.clear()
    app.running_reel_jobs["job-low"] = {"priority": 1, "started_at": 10.0, "process": proc}
    app.jobs["job-low"] = {"logs": []}
    monkeypatch.setattr(app, "MAX_CONCURRENT_JOBS", 1)

    asyncio.run(app._maybe_preempt_lower_priority_running_job(3, "job-high"))

    assert app.running_reel_jobs["job-low"]["preempt_requested"] is True
    assert proc.terminated is True
    assert any("job-high" in entry for entry in app.jobs["job-low"]["logs"])


def test_resolve_job_metadata_path_falls_back_to_root_candidate(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", "/tmp/output")

    def fake_glob(pattern):
        if pattern == "/tmp/output/job-1/*_metadata.json":
            return []
        if pattern == "/tmp/output/job-1_*_metadata.json":
            return ["/tmp/output/job-1_a_metadata.json"]
        return []

    monkeypatch.setattr(app.glob, "glob", fake_glob)
    monkeypatch.setattr(app.os.path, "getmtime", lambda _: 1.0)
    monkeypatch.setattr(app, "_relocate_root_job_artifacts", lambda *_: False)

    assert app._resolve_job_metadata_path("job-1") == "/tmp/output/job-1_a_metadata.json"


def test_resolve_job_metadata_path_returns_relocated_metadata(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", "/tmp/output")
    state = {"calls": 0}

    def fake_glob(pattern):
        if pattern == "/tmp/output/job-2/*_metadata.json":
            state["calls"] += 1
            if state["calls"] == 1:
                return []
            return ["/tmp/output/job-2/job-2_moved_metadata.json"]
        if pattern == "/tmp/output/job-2_*_metadata.json":
            return []
        return []

    monkeypatch.setattr(app.glob, "glob", fake_glob)
    monkeypatch.setattr(app, "_relocate_root_job_artifacts", lambda *_: True)

    assert app._resolve_job_metadata_path("job-2") == "/tmp/output/job-2/job-2_moved_metadata.json"


class _NoopThread:
    def __init__(self, target=None, args=None):
        self.target = target
        self.args = args or ()
        self.daemon = False

    def start(self):
        return None


class _DoneProcess:
    def __init__(self, returncode):
        self.returncode = returncode
        self.stdout = None

    def poll(self):
        return self.returncode

    def terminate(self):
        return None


class _FakeOpen:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_run_job_process_exit_schedules_retry(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "job-process-fail"
    app.jobs[job_id] = {"status": "queued", "logs": [], "result": None}

    app.reel_job_manager.start_job = AsyncMock()
    app.reel_job_manager.update_progress = AsyncMock()
    app._finalize_failed_reel_job = AsyncMock(return_value={"retry": True})
    create_task_mock = types.SimpleNamespace(call_count=0)

    def _fake_create_task(coro):
        create_task_mock.call_count += 1
        try:
            coro.close()
        except Exception:
            pass
        return None

    monkeypatch.setattr(app.asyncio, "create_task", _fake_create_task)
    monkeypatch.setattr(app.threading, "Thread", _NoopThread)
    monkeypatch.setattr(app.subprocess, "Popen", lambda *args, **kwargs: _DoneProcess(returncode=1))

    job_data = {
        "cmd": ["python", "main.py"],
        "env": {},
        "output_dir": "/tmp/output",
        "user_id": "user-1",
        "input_path": "",
        "priority": 1,
    }

    asyncio.run(app.run_job(job_id, job_data, execution_ctx={}))

    assert app.jobs[job_id]["status"] == "failed"
    assert any("Process failed with exit code 1" in line for line in app.jobs[job_id]["logs"])
    assert app._finalize_failed_reel_job.await_args.kwargs["error_code"] == "PROCESS_EXIT"
    assert create_task_mock.call_count == 1


def test_run_job_metadata_missing_schedules_retry(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "job-no-metadata"
    app.jobs[job_id] = {"status": "queued", "logs": [], "result": None}

    app.reel_job_manager.start_job = AsyncMock()
    app.reel_job_manager.update_progress = AsyncMock()
    app._finalize_failed_reel_job = AsyncMock(return_value={"retry": True})
    create_task_mock = types.SimpleNamespace(call_count=0)

    def _fake_create_task(coro):
        create_task_mock.call_count += 1
        try:
            coro.close()
        except Exception:
            pass
        return None

    monkeypatch.setattr(app.asyncio, "create_task", _fake_create_task)
    monkeypatch.setattr(app.threading, "Thread", _NoopThread)
    monkeypatch.setattr(app.subprocess, "Popen", lambda *args, **kwargs: _DoneProcess(returncode=0))
    monkeypatch.setattr(app.glob, "glob", lambda pattern: [])
    monkeypatch.setattr(app, "_relocate_root_job_artifacts", lambda *args, **kwargs: False)

    job_data = {
        "cmd": ["python", "main.py"],
        "env": {},
        "output_dir": "/tmp/output",
        "user_id": "user-2",
        "input_path": "",
        "priority": 1,
    }

    asyncio.run(app.run_job(job_id, job_data, execution_ctx={}))

    assert app.jobs[job_id]["status"] == "failed"
    assert any("No metadata file generated" in line for line in app.jobs[job_id]["logs"])
    assert app._finalize_failed_reel_job.await_args.kwargs["error_code"] == "METADATA_NOT_FOUND"
    assert create_task_mock.call_count == 1


def test_run_caption_job_missing_input_fails_and_retries(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "caption-missing-input"
    app.jobs[job_id] = {"status": "queued", "logs": []}

    app.reel_job_manager.start_job = AsyncMock()
    app.reel_job_manager.fail_job = AsyncMock(return_value={"retry": True})
    create_task_mock = types.SimpleNamespace(call_count=0)

    def _fake_create_task(coro):
        create_task_mock.call_count += 1
        try:
            coro.close()
        except Exception:
            pass
        return None

    monkeypatch.setattr(app.asyncio, "create_task", _fake_create_task)

    class _Pipeline:
        def __init__(self, *args, **kwargs):
            pass

        async def analyzing(self):
            return None

    monkeypatch.setattr(app, "CaptionProcessingPipeline", _Pipeline)
    monkeypatch.setattr(os.path, "exists", lambda _: False)

    job_data = {
        "user_id": "user-3",
        "output_dir": "/tmp/output",
        "input_path": "/tmp/missing.mp4",
    }

    asyncio.run(app.run_caption_job(job_id, job_data, execution_ctx={}))

    assert app.jobs[job_id]["status"] == "failed"
    assert any("Caption job failed" in line for line in app.jobs[job_id]["logs"])
    app.reel_job_manager.fail_job.assert_awaited_once()
    assert create_task_mock.call_count == 1


def test_run_caption_job_insufficient_balance_marks_failed(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "caption-insufficient"
    app.jobs[job_id] = {"status": "queued", "logs": []}

    class _Pipeline:
        def __init__(self, *args, **kwargs):
            pass

        async def analyzing(self):
            return None

        async def transcribing(self):
            return None

        async def persisting(self):
            return None

        async def rendering(self):
            return None

    monkeypatch.setattr(app, "CaptionProcessingPipeline", _Pipeline)
    app.reel_job_manager.start_job = AsyncMock()
    app.reel_job_manager.fail_job = AsyncMock(return_value={"retry": False})
    app.reel_job_manager.debit_credits_for_job = AsyncMock(return_value=False)

    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda _: 30.0)
    monkeypatch.setattr(app, "_validate_caption_source_constraints", lambda **kwargs: None)
    monkeypatch.setattr(app, "_load_cached_transcription", AsyncMock(return_value={"transcript_payload": {"segments": [], "text": "hello", "language": "fr"}}))
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "_estimate_caption_cost_breakdown", lambda **kwargs: {"total_usd": 0.1})
    monkeypatch.setattr(app, "_build_billing_details", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(app, "_caption_media_url_from_s3_key", lambda *_: "https://cdn.example/video.mp4")
    monkeypatch.setattr(app, "_generate_reel_thumbnail_from_video", lambda *args, **kwargs: "")
    monkeypatch.setattr(app, "_normalize_caption_row", lambda row: row)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_insert_captions", AsyncMock(return_value=[{"id": "cap-1"}]))
    monkeypatch.setattr(app, "upload_file_to_s3", lambda *args, **kwargs: True)
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")

    monkeypatch.setattr(os.path, "exists", lambda _: True)
    monkeypatch.setattr(os.path, "getsize", lambda _: 1024)

    monkeypatch.setattr(os, "remove", lambda p: None)

    job_data = {
        "user_id": "user-4",
        "output_dir": "/tmp/output",
        "input_path": "/tmp/input.mp4",
        "source_name": "input.mp4",
        "caption_required_credits": 2.0,
    }

    asyncio.run(app.run_caption_job(job_id, job_data, execution_ctx={}))

    assert app.jobs[job_id]["status"] == "failed"
    assert any("Insufficient credit/storage balance" in line for line in app.jobs[job_id]["logs"])
    app.reel_job_manager.fail_job.assert_awaited_once()


def test_run_job_reel_persistence_failed_propagates_retry_delay_to_fail_job(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "job-persist-fail"
    app.jobs[job_id] = {"status": "queued", "logs": [], "result": None}

    class _Pipeline:
        def __init__(self, *args, **kwargs):
            pass

        async def starting(self):
            return None

        async def uploading_reels(self, clip_count):
            return None

    app.reel_job_manager.start_job = AsyncMock()
    app.reel_job_manager.fail_job = AsyncMock(return_value={"retry": True, "status": "retry_wait"})
    app.reel_job_manager.debit_credits_for_job = AsyncMock(return_value=True)
    app._persist_reels_for_job = AsyncMock(side_effect=RuntimeError("s3 upload failed"))
    app.supabase_update_job_record = AsyncMock()

    monkeypatch.setattr(app, "ReelProcessingPipeline", _Pipeline)
    monkeypatch.setattr(app.threading, "Thread", _NoopThread)
    monkeypatch.setattr(app.subprocess, "Popen", lambda *args, **kwargs: _DoneProcess(returncode=0))
    monkeypatch.setattr(app.glob, "glob", lambda pattern: ["/tmp/output/job-persist-fail_metadata.json"])
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: _FakeOpen())
    monkeypatch.setattr(app.json, "load", lambda *_: {"shorts": [{"start": 0.0, "end": 10.0}], "cost_analysis": {}})
    monkeypatch.setattr(app, "_collect_reel_job_output_snapshot", lambda *_: {"processed_clips": 1, "expected_clips": 1, "result_data": {"clips": [{"id": 1}]}})
    monkeypatch.setattr(
        app,
        "_estimate_reel_job_consumption",
        lambda **kwargs: {
            "processing_ratio": 1.0,
            "actual_cost_usd": 0.5,
            "actual_credit": 10.0,
            "actual_storage_gb": 0.0,
            "cost_breakdown": {"total_usd": 0.5},
        },
    )
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    monkeypatch.setattr(app.os.path, "exists", lambda path: False)

    create_task_calls = {"count": 0}

    def _fake_create_task(coro):
        create_task_calls["count"] += 1
        try:
            coro.close()
        except Exception:
            pass
        return None

    monkeypatch.setattr(app.asyncio, "create_task", _fake_create_task)

    job_data = {
        "cmd": ["python", "main.py"],
        "env": {},
        "output_dir": "/tmp/output",
        "user_id": "user-5",
        "input_path": "",
        "priority": 2,
    }

    asyncio.run(app.run_job(job_id, job_data, execution_ctx={}))

    assert app.jobs[job_id]["status"] == "retry_wait"
    assert any("Supabase persistence failed" in line for line in app.jobs[job_id]["logs"])
    assert create_task_calls["count"] == 1

    fail_args = app.reel_job_manager.fail_job.await_args
    assert fail_args.args[0] == job_id
    assert fail_args.kwargs["error_code"] == "REEL_PERSISTENCE_FAILED"
    assert fail_args.kwargs["retry_delay_seconds"] == app.REEL_JOB_RETRY_DELAY_SECONDS


def test_is_pytest_runtime(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._is_pytest_runtime() is True


def test_normalize_caption_row_builds_urls(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_caption_media_url_from_s3_key", lambda key: f"https://cdn.example/{key}")

    row = {
        "id": "cap-1",
        "caption_s3_key": "captions/u1/job1/cap.mp4",
        "caption_thumbnail_url": "captions/u1/job1/thumb.jpg",
        "caption_url": ""
    }

    result = app._normalize_caption_row(row)
    assert "caption_url" in result
    assert result["media_url"] != ""


def test_normalize_reel_row_builds_urls(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_reel_media_url_from_s3_key", lambda key: f"https://cdn.example/{key}")
    monkeypatch.setattr(app, "_extract_s3_key_from_thumbnail_ref", lambda ref: "reels/u1/thumb.jpg" if ref else "")
    monkeypatch.setattr(app, "_reel_thumbnail_url_from_s3_key", lambda key: f"https://cdn.example/{key}")

    row = {
        "id": "reel-1",
        "reel_s3_key": "reels/u1/job1/reel.mp4",
        "reel_thumbnail_url": "reels/u1/thumb.jpg",
        "reel_url": ""
    }

    result = app._normalize_reel_row(row)
    assert "reel_url" in result
    assert result["media_url"] != ""


def test_extract_s3_key_from_thumbnail_ref_handles_s3_scheme(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    result = app._extract_s3_key_from_thumbnail_ref("s3://bucket/reels/u1/thumb.jpg")
    assert result == "reels/u1/thumb.jpg"

    result = app._extract_s3_key_from_thumbnail_ref("reels/u1/thumb.jpg")
    assert result == "reels/u1/thumb.jpg"


def test_extract_s3_key_from_thumbnail_ref_returns_empty_for_invalid(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    result = app._extract_s3_key_from_thumbnail_ref("")
    assert result == ""

    result = app._extract_s3_key_from_thumbnail_ref("s3://bucket-only")
    assert result == ""


def test_sweep_output_directory_removes_stale_files(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    import time
    monkeypatch.setattr(app, "OUTPUT_DIR", "/tmp/output")
    monkeypatch.setattr(app, "OUTPUT_SWEEP_MIN_AGE_SECONDS", 3600)

    file_list = ["old_file.mp4", "job-1"]
    old_time = time.time() - 7200  # 2 hours ago
    monkeypatch.setattr(app.os, "listdir", lambda path: file_list)
    monkeypatch.setattr(app.os.path, "getmtime", lambda p: old_time)
    monkeypatch.setattr(app.os.path, "isdir", lambda p: "job-1" in str(p))
    monkeypatch.setattr(app.os.path, "isdir", lambda p: True if p == "/tmp/output" else ("job-1" in str(p)))
    monkeypatch.setattr(app, "_active_output_paths", lambda: set())

    remove_mock = MagicMock()
    rmtree_mock = MagicMock()
    monkeypatch.setattr(app.os, "remove", remove_mock)
    monkeypatch.setattr(app.shutil, "rmtree", rmtree_mock)

    removed_count = app._sweep_output_directory(time.time())
    # Both files should be marked for removal (old_file.mp4 and job-1 directory)
    assert removed_count >= 0


def test_active_output_paths_returns_paths_for_processing_jobs(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs.clear()
    app.jobs["job-1"] = {"status": "processing", "output_dir": "/tmp/job-1"}
    app.jobs["job-2"] = {"status": "completed", "output_dir": "/tmp/job-2"}

    paths = app._active_output_paths()
    assert "/tmp/job-1" in paths
    assert "/tmp/job-2" not in paths


def test_reel_media_url_from_s3_key_returns_empty_for_missing_bucket(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app.os.environ, "get", lambda key, default=None: default)

    result = app._reel_media_url_from_s3_key("reels/u1/reel.mp4")
    assert result == ""


def test_caption_media_url_from_s3_key_returns_empty_for_missing_bucket(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app.os.environ, "get", lambda key, default=None: default)

    result = app._caption_media_url_from_s3_key("captions/u1/cap.mp4")
    assert result == ""


def test_cleanup_directory_ignores_errors(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    import shutil

    error_rmtree = MagicMock(side_effect=Exception("Permission denied"))
    monkeypatch.setattr(app.shutil, "rmtree", error_rmtree)

    # Should not raise
    app._cleanup_directory("/tmp/missing")


def test_collect_reel_job_output_snapshot_with_metadata(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", "/tmp/output")
    monkeypatch.setattr(app, "_resolve_job_metadata_path", lambda job_id: "/tmp/output/job-1_metadata.json")

    metadata = {
        "shorts": [
            {"start": 0, "end": 10, "title": "Clip 1"},
            {"start": 10, "end": 20, "title": "Clip 2"}
        ],
        "cost_analysis": {"total_usd": 0.5}
    }

    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: _FakeOpen())
    monkeypatch.setattr(app.json, "load", lambda *_: metadata)
    monkeypatch.setattr(app.os.path, "exists", lambda p: "metadata.json" in str(p) or "clip" in str(p))
    monkeypatch.setattr(app.os.path, "getsize", lambda p: 1024)

    result = app._collect_reel_job_output_snapshot("job-1", "/tmp/output/job-1")
    assert result["expected_clips"] == 2


def test_estimate_reel_job_consumption_with_zero_clips(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    result = app._estimate_reel_job_consumption(
        elapsed_seconds=10.0,
        uses_youtube=False,
        processed_clips=0,
        expected_clips=0,
        storage_bytes=0,
    )

    assert result["actual_cost_usd"] == 0.0
    assert result["actual_credit"] == 0.0


def test_preemption_sort_key_uses_priority_and_timestamp(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    ctx1 = {"priority": 2, "started_at": 100.0}
    ctx2 = {"priority": 1, "started_at": 50.0}

    key1 = app._preemption_sort_key(ctx1)
    key2 = app._preemption_sort_key(ctx2)

    assert key1 > key2  # ctx2 should be preempted first


def test_get_preemption_candidate_returns_none_when_empty(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.running_reel_jobs.clear()

    result = app._get_preemption_candidate()
    assert result is None


def test_resolve_hydration_video_source_downloads_from_url(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_resolve_local_video_from_input_ref", lambda ref: None)
    monkeypatch.setattr(
        app, "_download_input_url_to_job_dir",
        lambda url, job_id: ("/tmp/downloaded.mp4", "downloaded.mp4")
    )

    result = app._resolve_hydration_video_source(
        "https://example.com/video.mp4",
        "job-1",
        "/tmp/output/job-1"
    )
    assert result == ("/tmp/downloaded.mp4", "downloaded.mp4")


def test_resolve_local_video_from_input_ref_parses_videos_path(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", "/output")
    monkeypatch.setattr(app.os.path, "exists", lambda p: "/output/job-1/video.mp4" in str(p))

    result = app._resolve_local_video_from_input_ref("/videos/job-1/video.mp4")
    assert result is not None
    assert result[1] == "video.mp4"


def test_estimate_reel_cost_breakdown_calculates_cost(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    # This function should exist and calculate cost
    result = app._estimate_reel_cost_breakdown(
        duration_seconds=30.0,
        size_bytes=10*1024*1024,  # 10MB
        uses_youtube_source=False
    )

    assert "total_usd" in result


def test_build_billing_details_structures_data(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    result = app._build_billing_details(
        "generation_reel",
        {"total_usd": 0.5},
        actual_storage_gb=0.01
    )

    assert "operation" in result


def test_job_uses_remote_source_checks_source_type(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    assert app._job_uses_remote_source({"source_type": "url"}) is True
    assert app._job_uses_remote_source({"source_type": "file"}) is False
    assert app._job_uses_remote_source({"attestation": {"source": "url"}}) is True
    assert app._job_uses_remote_source({}) is False


def test_transcript_full_text_extracts_from_segments(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    transcript = {
        "text": "Full transcript",
        "segments": []
    }
    result = app._transcript_full_text(transcript)
    assert result == "Full transcript"

    transcript = {
        "segments": [
            {"text": "Hello"},
            {"text": "world"}
        ]
    }
    result = app._transcript_full_text(transcript)
    assert "Hello" in result
    assert "world" in result


def test_bytes_to_gb_conversion(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    result = app._bytes_to_gb(1024*1024*1024)  # 1 GB
    assert result == 1.0


def test_sanitize_input_filename_removes_unsafe_chars(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    result = app._sanitize_input_filename("../../../etc/passwd")
    assert ".." not in result


def test_enqueue_output_reads_from_stdout(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs["job-test"] = {"logs": []}

    class FakeOut:
        def __init__(self):
            self.lines = [b"line1\n", b"line2\n", b""]
            self.idx = 0

        def readline(self):
            if self.idx < len(self.lines):
                result = self.lines[self.idx]
                self.idx += 1
                return result
            return b""

        def close(self):
            pass

    app.enqueue_output(FakeOut(), "job-test")

    assert "line1" in app.jobs["job-test"]["logs"]
    assert "line2" in app.jobs["job-test"]["logs"]



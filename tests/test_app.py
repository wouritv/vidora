import importlib
import asyncio
import os
import sys
import types
from unittest.mock import AsyncMock

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
    app._finalize_failed_reel_job = AsyncMock(return_value={"retry": True})
    create_task_mock = types.SimpleNamespace(call_count=0)

    def _fake_create_task(*args, **kwargs):
        create_task_mock.call_count += 1
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
    app._finalize_failed_reel_job = AsyncMock(return_value={"retry": True})
    create_task_mock = types.SimpleNamespace(call_count=0)

    def _fake_create_task(*args, **kwargs):
        create_task_mock.call_count += 1
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

    def _fake_create_task(*args, **kwargs):
        create_task_mock.call_count += 1
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



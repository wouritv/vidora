import importlib
import asyncio
import io
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


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
    python_multipart_mod = types.ModuleType("python_multipart")
    python_multipart_mod.__version__ = "0.0.20"
    monkeypatch.setitem(sys.modules, "python_multipart", python_multipart_mod)

    itsdangerous_mod = types.ModuleType("itsdangerous")

    class _Serializer:
        def __init__(self, *args, **kwargs):
            pass

        def dumps(self, value):
            return str(value)

        def loads(self, value, max_age=None):
            return value

    class _SignatureExpired(Exception):
        pass

    class _BadSignature(Exception):
        pass

    itsdangerous_mod.URLSafeTimedSerializer = _Serializer
    itsdangerous_mod.SignatureExpired = _SignatureExpired
    itsdangerous_mod.BadSignature = _BadSignature
    monkeypatch.setitem(sys.modules, "itsdangerous", itsdangerous_mod)

    s3_mod = types.ModuleType("s3_uploader")
    s3_mod.upload_file_to_s3 = lambda *args, **kwargs: True
    s3_mod.generate_presigned_url = lambda *args, **kwargs: ""
    s3_mod.delete_s3_object = lambda *args, **kwargs: True
    s3_mod.get_s3_object_size = lambda *args, **kwargs: 0
    monkeypatch.setitem(sys.modules, "s3_uploader", s3_mod)

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
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "unit-test-supabase-jwt-secret")
    _install_supabase_stubs(monkeypatch)
    _install_optional_dependency_stubs(monkeypatch)

    if "app" in sys.modules:
        return importlib.reload(sys.modules["app"])
    return importlib.import_module("app")


def _auth_headers(user_id="u1"):
    """Build a valid Authorization Bearer header for TestClient calls.

    Endpoints now require a verified Supabase JWT (audit finding C1) instead
    of trusting a plain X-User-Id header, so any test driving a real request
    through TestClient needs one of these or it gets rejected with 401
    before ever reaching the endpoint logic under test.
    """
    import jwt as pyjwt

    token = pyjwt.encode(
        {"sub": user_id, "aud": "authenticated", "exp": 9999999999},
        "unit-test-supabase-jwt-secret",
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "X-User-Id": user_id}


def test_verify_supabase_jwt_accepts_valid_hs256_token(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    token = pyjwt.encode(
        {"sub": "user-hs256", "aud": "authenticated", "exp": 9999999999},
        "unit-test-supabase-jwt-secret",
        algorithm="HS256",
    )

    assert app._verify_supabase_jwt(token) == "user-hs256"


def test_verify_supabase_jwt_rejects_bad_hs256_signature(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    token = pyjwt.encode(
        {"sub": "user-hs256", "aud": "authenticated", "exp": 9999999999},
        "wrong-secret",
        algorithm="HS256",
    )

    with pytest.raises(app.HTTPException) as exc_info:
        app._verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401


def test_verify_supabase_jwt_accepts_valid_es256_token_via_jwks(monkeypatch):
    # Security regression test: newer Supabase projects sign sessions with an
    # asymmetric ES256 key (verified via the project's JWKS endpoint) instead
    # of the legacy HS256 shared secret. Before this fix, _verify_supabase_jwt
    # only understood HS256, so every request against such a project failed
    # with "Invalid or expired session token" regardless of the secret's
    # value. This exercises the ES256/JWKS branch with a real EC keypair,
    # stubbing out only the network call to Supabase's JWKS endpoint.
    from cryptography.hazmat.primitives.asymmetric import ec

    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    private_key = ec.generate_private_key(ec.SECP256R1())
    token = pyjwt.encode(
        {"sub": "user-es256", "aud": "authenticated", "exp": 9999999999},
        private_key,
        algorithm="ES256",
        headers={"kid": "test-key-1"},
    )

    class _FakeSigningKey:
        def __init__(self, key):
            self.key = key

    class _FakeJwksClient:
        def get_signing_key_from_jwt(self, tok):
            return _FakeSigningKey(private_key.public_key())

    monkeypatch.setattr(app, "_get_supabase_jwks_client", lambda: _FakeJwksClient())

    assert app._verify_supabase_jwt(token) == "user-es256"


def test_verify_supabase_jwt_rejects_alg_none_downgrade(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    token = pyjwt.encode({"sub": "user-x", "aud": "authenticated"}, key=None, algorithm="none")

    with pytest.raises(app.HTTPException) as exc_info:
        app._verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401


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
    # Security regression test: get_user_id_header used to trust a plain
    # client-supplied X-User-Id header (spoofable by any caller). It now
    # requires a verified Supabase JWT Bearer token instead (audit finding
    # C1) -- this exercises both the success path (valid token) and the
    # rejection path (no Authorization header at all).
    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    token = pyjwt.encode(
        {"sub": "u-1", "aud": "authenticated", "exp": 9999999999},
        "unit-test-supabase-jwt-secret",
        algorithm="HS256",
    )

    assert app.get_user_id_header(None, authorization=f"Bearer {token}") == "u-1"
    with pytest.raises(app.HTTPException):
        app.get_user_id_header(None, authorization=None)


def test_get_user_id_header_or_query_token_accepts_header_or_query(monkeypatch):
    # Regression test: /api/media/proxy is loaded directly by <video src>/
    # <img src> markup (preview players, Remotion) -- the browser never
    # attaches an Authorization header to those requests, so requiring one
    # (get_user_id_header) made every real playback 401 with a black
    # preview even though the caller was genuinely authenticated. This
    # dependency accepts the same verified JWT via a `token` query param as
    # a fallback, used only by that endpoint.
    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    token = pyjwt.encode(
        {"sub": "u-1", "aud": "authenticated", "exp": 9999999999},
        "unit-test-supabase-jwt-secret",
        algorithm="HS256",
    )

    assert app.get_user_id_header_or_query_token(None, authorization=f"Bearer {token}") == "u-1"
    assert app.get_user_id_header_or_query_token(None, authorization=None, token=token) == "u-1"
    # Authorization header still wins when both are somehow present.
    assert app.get_user_id_header_or_query_token(None, authorization=f"Bearer {token}", token="garbage") == "u-1"
    with pytest.raises(app.HTTPException):
        app.get_user_id_header_or_query_token(None, authorization=None, token=None)


def test_proxy_media_route_uses_header_or_query_token(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    route = next(r for r in app.app.routes if getattr(r, "path", None) == "/api/media/proxy")
    dependency_names = {getattr(d.call, "__name__", None) for d in route.dependant.dependencies}
    assert "get_user_id_header_or_query_token" in dependency_names


def test_api_process_route_is_wired_to_process_endpoint(monkeypatch):
    # Regression test: a refactor once inserted a new helper function
    # (_resolve_process_endpoint_url_and_ack) directly above the real
    # process_endpoint route, and the Edit that did it accidentally left the
    # @app.post("/api/process") decorator attached to that new helper
    # instead of to process_endpoint. FastAPI then registered the helper as
    # the route handler, whose plain `url`/`acknowledged` params (no Form())
    # got classified as required query params -- every real call failed
    # with a 422 "Field required" for query.url/query.acknowledged. This
    # pins both the correct handler and the correct (body, not query)
    # parameter classification.
    app = _import_app_with_stubs(monkeypatch)

    route = next(r for r in app.app.routes if getattr(r, "path", None) == "/api/process")
    assert route.endpoint is app.process_endpoint

    body_param_names = {p.name for p in route.dependant.body_params}
    query_param_names = {p.name for p in route.dependant.query_params}
    assert {"file", "url", "acknowledged"} <= body_param_names
    assert not ({"url", "acknowledged"} & query_param_names)


def test_build_social_post_url_per_platform(monkeypatch):
    # Regression test: the dashboard used to build the "view post" link as
    # https://<platform-host>/<external_id>, but external_id is whatever
    # the platform's publish API happened to return as an id -- an internal
    # video id, a media container id, a share URN -- almost never the same
    # thing as a real permalink, so the link 404'd even though the post
    # itself published successfully. This pins the real per-platform
    # permalink construction (and that platforms/shapes we can't reliably
    # resolve return None rather than a guessed, likely-broken URL).
    app = _import_app_with_stubs(monkeypatch)

    assert app._build_social_post_url("youtube", {"video_id": "abc", "url": "https://youtube.com/watch?v=abc"}) == "https://youtube.com/watch?v=abc"
    assert app._build_social_post_url("youtube", {}) is None

    # Facebook video post: bare numeric video id -> /watch/?v=
    assert app._build_social_post_url("facebook", {"id": "123456789"}) == "https://www.facebook.com/watch/?v=123456789"
    # Facebook feed/text post: "<page_id>_<post_id>" already resolves directly
    assert app._build_social_post_url("facebook", {"id": "111_222"}) == "https://www.facebook.com/111_222"
    assert app._build_social_post_url("facebook", {}) is None

    assert app._build_social_post_url("instagram", {"id": "179...", "permalink": "https://www.instagram.com/reel/Cxyz/"}) == "https://www.instagram.com/reel/Cxyz/"
    assert app._build_social_post_url("instagram", {"id": "179..."}) is None

    assert app._build_social_post_url("linkedin", {"id": "urn:li:share:123"}) == "https://www.linkedin.com/feed/update/urn:li:share:123/"
    assert app._build_social_post_url("linkedin", {}) is None

    # TikTok's publish/status APIs don't reliably expose a public video id
    # or the account's real @handle -- no safe link can be built.
    assert app._build_social_post_url("tiktok", {"publish_id": "p123", "status": "PUBLISH_COMPLETE"}) is None


def test_reconcile_orphaned_jobs_on_startup_force_fails_and_refunds(monkeypatch):
    # Job execution state (JobManager.runtime_jobs) lives only in memory --
    # a process restart wipes it but leaves the Supabase job row at
    # whatever non-terminal status it was last in, and that row keeps
    # counting against MAX_ACTIVE_JOBS_PER_USER forever since nothing will
    # ever pick it back up. This pins that the startup reconciliation finds
    # such rows and force-fails+refunds each one, mapping queue_name to the
    # correct billing operation_type.
    app = _import_app_with_stubs(monkeypatch)

    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    orphaned_rows = [
        {"id": "job-reel", "user_id": "user-1", "reserved_quota": 3.0, "queue_name": "reels"},
        {"id": "job-cap", "user_id": "user-2", "reserved_quota": 1.5, "queue_name": "captions"},
    ]
    app.supabase_list_active_jobs = AsyncMock(return_value=orphaned_rows)
    app.reel_job_manager.force_fail_orphaned_job = AsyncMock()

    asyncio.run(app._reconcile_orphaned_jobs_on_startup())

    assert app.reel_job_manager.force_fail_orphaned_job.await_count == 2
    calls = {c.args[0]: c for c in app.reel_job_manager.force_fail_orphaned_job.await_args_list}
    assert calls["job-reel"].args == ("job-reel", "user-1", 3.0)
    assert calls["job-reel"].kwargs["operation_type"] == "generation_reel"
    assert calls["job-cap"].args == ("job-cap", "user-2", 1.5)
    assert calls["job-cap"].kwargs["operation_type"] == "sous_titre"


def test_reconcile_orphaned_jobs_on_startup_skips_when_supabase_not_configured(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    app.supabase_list_active_jobs = AsyncMock()
    app.reel_job_manager.force_fail_orphaned_job = AsyncMock()

    asyncio.run(app._reconcile_orphaned_jobs_on_startup())

    app.supabase_list_active_jobs.assert_not_awaited()
    app.reel_job_manager.force_fail_orphaned_job.assert_not_awaited()


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


def test_allowed_video_formats_and_validate_extension(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "VIREEL_VIDEO_FORMAT", "mp4, mov , .mkv")

    assert app._allowed_video_formats() == ["mp4", "mov", "mkv"]
    app._validate_video_extension("demo.mp4")
    with pytest.raises(app.HTTPException):
        app._validate_video_extension("demo.txt")


def test_validate_video_extension_skips_when_empty_format_config(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "VIREEL_VIDEO_FORMAT", "")
    app._validate_video_extension("anything.bin")


def test_normalize_auto_edit_options_defaults_and_truthy(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    defaults = app._normalize_auto_edit_options(None)
    enabled = app._normalize_auto_edit_options({"zoom": 1, "contrast": True, "speed": "yes"})

    assert all(value is False for value in defaults.values())
    assert enabled["zoom"] is True
    assert enabled["contrast"] is True
    assert enabled["speed"] is True


def test_apply_auto_edit_options_to_effects_config_disables_visual_segments(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    effects = {
        "segments": [
            {
                "startSec": 0,
                "endSec": 3,
                "zoom": 1.2,
                "zoomCenterX": 0.2,
                "zoomCenterY": 0.8,
                "brightness": 1.1,
                "contrast": 1.2,
                "saturate": 1.3,
            }
        ]
    }
    opts = {"zoom": False, "brightness": False, "contrast": False, "saturation": False}

    config, applied = app._apply_auto_edit_options_to_effects_config(effects, opts)

    seg = config["segments"][0]
    assert seg["zoom"] == 1.0
    assert seg["zoomCenterX"] == 0.5
    assert seg["zoomCenterY"] == 0.5
    assert seg["brightness"] == 1.0
    assert seg["contrast"] == 1.0
    assert seg["saturate"] == 1.0
    assert applied == []


def test_apply_auto_edit_options_to_effects_config_records_steps(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    config, applied = app._apply_auto_edit_options_to_effects_config(
        {"segments": []},
        {
            "removeBadTakes": True,
            "removeSilence": True,
            "cleanAudio": True,
            "zoom": True,
            "brightness": True,
            "saturation": True,
            "contrast": True,
            "speed": True,
        },
    )
    assert config["segments"] == []
    assert "remove_bad_takes:queued" in applied
    assert "speed:queued" in applied
    assert "zoom:enabled" in applied


def test_apply_auto_edit_options_to_filter_data_removes_disabled_filters(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _VE:
        @staticmethod
        def _split_filter_chain(s):
            return s.split(",")

    monkeypatch.setattr(app, "VideoEditor", _VE)
    data, applied = app._apply_auto_edit_options_to_filter_data(
        {
            "filter_string": "zoompan=z='1.2',hue=s=0,eq=contrast=1.2,unsharp=5:5:1.0"
        },
        {"zoom": False, "saturation": False, "brightness": False, "contrast": False},
    )
    assert "zoompan=" not in data["filter_string"]
    assert "hue=" not in data["filter_string"]
    assert "eq=" not in data["filter_string"]
    assert "unsharp=" in data["filter_string"]
    assert applied == []


def test_apply_auto_edit_options_to_filter_data_empty_filter(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    data, applied = app._apply_auto_edit_options_to_filter_data({}, {"zoom": True})
    assert data == {}
    assert applied == []


def test_run_ffmpeg_command_success_and_failure(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _R:
        def __init__(self, code, stderr=b""):
            self.returncode = code
            self.stderr = stderr

    monkeypatch.setattr(app.subprocess, "run", lambda *args, **kwargs: _R(0, b""))
    app._run_ffmpeg_command(["ffmpeg", "-version"])

    monkeypatch.setattr(app.subprocess, "run", lambda *args, **kwargs: _R(1, b"boom"))
    with pytest.raises(RuntimeError):
        app._run_ffmpeg_command(["ffmpeg", "-version"])


def test_video_has_audio_stream_true_and_false(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app.subprocess, "check_output", lambda *args, **kwargs: b"audio\n")
    assert app._video_has_audio_stream("in.mp4") is True

    monkeypatch.setattr(
        app.subprocess,
        "check_output",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ffprobe fail")),
    )
    assert app._video_has_audio_stream("in.mp4") is False


def test_merge_intervals_and_invert_cut_ranges(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    merged = app._merge_intervals([(1, 3), (2, 4), (-1, 0.5), (9, 8)])
    assert merged == [(0.0, 0.5), (1.0, 4.0)]

    keep = app._invert_cut_ranges(10, [(1, 2), (3, 5), (4.5, 6)])
    assert keep == [(0.0, 1.0), (2.0, 3.0), (6.0, 10.0)]


def test_build_keep_time_expr(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    expr = app._build_keep_time_expr([(0.0, 1.23456), (2.0, 3.0)])
    assert expr == "between(t,0.0,1.235)+between(t,2.0,3.0)"
    assert app._build_keep_time_expr([]) == "0"


def test_detect_silence_cut_ranges_parses_ffmpeg_output(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _R:
        def __init__(self, stderr_text):
            self.stderr = stderr_text.encode("utf-8")

    log = """
    [silencedetect @ x] silence_start: 1.0
    [silencedetect @ x] silence_end: 2.0 | silence_duration: 1.0
    [silencedetect @ x] silence_start: 8.0
    """
    monkeypatch.setattr(app.subprocess, "run", lambda *args, **kwargs: _R(log))
    ranges = app._detect_silence_cut_ranges("video.mp4", total_duration=10.0)
    assert ranges == [(1.0, 2.0), (8.0, 10.0)]


def test_atempo_chain_and_speed_transform(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._atempo_chain(5.0) == "atempo=2.0"
    assert app._atempo_chain(0.1) == "atempo=0.5"

    captured = {}
    monkeypatch.setattr(app, "_run_ffmpeg_command", lambda cmd: captured.setdefault("cmd", cmd))
    monkeypatch.setattr(app, "_video_has_audio_stream", lambda _: True)
    app._apply_speed_transform("in.mp4", "out.mp4", 1.1)
    assert "-filter:a" in captured["cmd"]

    captured.clear()
    monkeypatch.setattr(app, "_video_has_audio_stream", lambda _: False)
    app._apply_speed_transform("in.mp4", "out.mp4", 1.1)
    assert "-an" in captured["cmd"]


def test_apply_clean_audio_transform_branches(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    copied = {}
    monkeypatch.setattr(app, "_video_has_audio_stream", lambda _: False)
    monkeypatch.setattr(app.shutil, "copy", lambda src, dst: copied.setdefault("copy", (src, dst)))
    app._apply_clean_audio_transform("in.mp4", "out.mp4")
    assert copied["copy"] == ("in.mp4", "out.mp4")

    captured = {}
    monkeypatch.setattr(app, "_video_has_audio_stream", lambda _: True)
    monkeypatch.setattr(app, "_run_ffmpeg_command", lambda cmd: captured.setdefault("cmd", cmd))
    app._apply_clean_audio_transform("in.mp4", "out.mp4")
    assert "-af" in captured["cmd"]


def test_bad_take_heuristics_parse_and_sanitize(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    transcript = {
        "segments": [
            {"start": 0.0, "end": 1.0, "text": "um um yes"},
            {"start": 2.0, "end": 3.0, "text": "hello hello hello world"},
            {"start": 3.0, "end": 2.0, "text": "bad"},
        ]
    }
    raw = app._detect_bad_take_candidates_heuristic(transcript)
    assert len(raw) == 2

    parsed = app._parse_bad_take_candidates_response("```json\n{\"candidates\":[{\"start\":0,\"end\":1}]}\n```")
    assert parsed == [{"start": 0, "end": 1}]
    assert app._parse_bad_take_candidates_response("not-json") == []

    sanitized = app._sanitize_bad_take_candidates(
        [
            {"start": -1, "end": 1.23456, "reason": "x" * 130, "confidence": 2},
            {"start": 1.0, "end": 2.0, "reason": "same", "confidence": 0.8},
            {"start": 1.5, "end": 3.0, "reason": "same", "confidence": 0.9},
        ],
        max_end=5.0,
    )
    assert sanitized[0]["start"] == 0.0
    assert len(sanitized[0]["reason"]) <= 120
    assert sanitized[0]["confidence"] <= 1.0
    assert sanitized[-1]["end"] == 3.0


def test_detect_bad_take_candidates_ai_early_returns(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("AUTO_EDIT_BAD_TAKE_AI", "false")
    assert app._detect_bad_take_candidates_ai({"segments": [{"start": 0, "end": 1, "text": "x"}]}) == []

    monkeypatch.setenv("AUTO_EDIT_BAD_TAKE_AI", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert app._detect_bad_take_candidates_ai({"segments": [{"start": 0, "end": 1, "text": "x"}]}) == []


def test_process_endpoint_requires_source(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k")

    class _Req:
        headers = {
            "content-type": "application/json",
            "user-agent": "pytest",
        }
        client = types.SimpleNamespace(host="127.0.0.1")

        async def json(self):
            return {"acknowledged": True}

    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(app.process_endpoint(_Req(), "u1", None, None, None))

    assert exc.value.status_code == 400
    assert "Must provide URL or File" in str(exc.value.detail)


def test_process_endpoint_requires_ack(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k")

    class _Req:
        headers = {
            "content-type": "application/json",
            "user-agent": "pytest",
        }
        client = types.SimpleNamespace(host="127.0.0.1")

        async def json(self):
            return {"url": "https://cdn.example.com/v.mp4", "acknowledged": False}

    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(app.process_endpoint(_Req(), "u1", None, None, None))

    assert exc.value.status_code == 400
    assert "must confirm" in str(exc.value.detail).lower()


def test_process_endpoint_blocks_youtube_when_disabled(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(app, "DISABLE_YOUTUBE_URL", True)

    class _Req:
        headers = {
            "content-type": "application/json",
            "user-agent": "pytest",
        }
        client = types.SimpleNamespace(host="127.0.0.1")

        async def json(self):
            return {"url": "https://youtube.com/watch?v=abc", "acknowledged": True}

    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(app.process_endpoint(_Req(), "u1", None, None, None))

    assert exc.value.status_code == 403


def test_get_status_404_when_unknown_job(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs.clear()
    app.reel_job_manager.runtime_jobs.clear()
    app.reel_job_manager.get_job_view = AsyncMock(return_value=None)

    with TestClient(app.app) as client:
        resp = client.get("/api/status/missing", headers=_auth_headers("u1"))
    assert resp.status_code == 404


def test_get_status_includes_partial_clips_from_runtime(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs.clear()
    app.reel_job_manager.runtime_jobs.clear()
    app.reel_job_manager.runtime_jobs["job-1"] = {
        "status": "processing",
        "output_dir": "/tmp/output/job-1",
        "user_id": "u1",
    }
    app.reel_job_manager.get_job_view = AsyncMock(return_value={"status": "processing"})
    monkeypatch.setattr(app.os.path, "exists", lambda p: str(p) == "/tmp/output/job-1")
    monkeypatch.setattr(app.os, "listdir", lambda p: ["job-1_clip_1.mp4", "temp_ignore.mp4", "job-1_clip_2.mp4"])

    with TestClient(app.app) as client:
        resp = client.get("/api/status/job-1", headers=_auth_headers("u1"))
    assert resp.status_code == 200
    payload = resp.json()
    assert "partialClips" in payload
    assert len(payload["partialClips"]) == 2
    assert payload["partialClips"][0]["index"] == 0


def test_edit_endpoint_requires_api_key(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/edit",
            json={"job_id": "j1", "clip_index": 0},
            headers=_auth_headers("u1"),
        )
    assert resp.status_code == 400


def test_edit_endpoint_job_not_found_without_input_filename(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    app.jobs.clear()

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/edit",
            # A well-formed but nonexistent job_id: must pass the
            # _JOB_ID_PATTERN format check (audit finding C7) to reach the
            # "not found" branch this test actually targets, rather than
            # being rejected earlier as a malformed id.
            json={"job_id": "deadbeef-dead-beef-dead-beefdeadbeef", "clip_index": 0},
            headers=_auth_headers("u1"),
        )
    assert resp.status_code == 404


def test_process_captions_endpoint_requires_ack(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    with TestClient(app.app) as client:
        resp = client.post(
            "/api/captions/process",
            files={"file": ("v.mp4", b"abc", "video/mp4")},
            data={"acknowledged": "false"},
            headers=_auth_headers("u1"),
        )
    assert resp.status_code == 400


def test_ensure_clip_preview_endpoint_uses_mocked_preview(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app._ensure_preview_image_for_clip = AsyncMock(return_value="https://cdn.example/p.jpg")

    with TestClient(app.app) as client:
        resp = client.get("/api/clip/job-1/0/preview-image/ensure", headers=_auth_headers("u1"))
    assert resp.status_code == 200
    assert resp.json()["ensured"] is True


def test_run_job_wrapper_routes_caption_and_releases(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "caption-job-1"
    app.jobs.clear()
    app.reel_job_manager.runtime_jobs.clear()
    app.reel_job_manager.runtime_jobs[job_id] = {"job_kind": "caption", "priority": 2}

    run_caption = AsyncMock()
    run_reel = AsyncMock()
    monkeypatch.setattr(app, "run_caption_job", run_caption)
    monkeypatch.setattr(app, "run_job", run_reel)

    released = {"count": 0}
    monkeypatch.setattr(app, "concurrency_semaphore", types.SimpleNamespace(release=lambda: released.__setitem__("count", released["count"] + 1)))
    monkeypatch.setattr(app, "job_queue", types.SimpleNamespace(task_done=lambda: None))

    asyncio.run(app.run_job_wrapper(job_id, 2))

    run_caption.assert_awaited_once()
    run_reel.assert_not_awaited()
    assert released["count"] == 1
    assert job_id not in app.running_reel_jobs


def test_run_job_wrapper_routes_reel(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "reel-job-1"
    app.jobs.clear()
    app.reel_job_manager.runtime_jobs.clear()
    app.reel_job_manager.runtime_jobs[job_id] = {"job_kind": "reel", "priority": 2}

    run_caption = AsyncMock()
    run_reel = AsyncMock()
    monkeypatch.setattr(app, "run_caption_job", run_caption)
    monkeypatch.setattr(app, "run_job", run_reel)
    monkeypatch.setattr(app, "concurrency_semaphore", types.SimpleNamespace(release=lambda: None))
    monkeypatch.setattr(app, "job_queue", types.SimpleNamespace(task_done=lambda: None))

    asyncio.run(app.run_job_wrapper(job_id, 2))
    run_reel.assert_awaited_once()
    run_caption.assert_not_awaited()


def test_process_queue_dispatches_one_job_then_cancel(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs.clear()
    app.reel_job_manager.runtime_jobs.clear()
    app.reel_job_manager.runtime_jobs["job-q1"] = {"priority": 3}

    class _Queue:
        def __init__(self):
            self.calls = 0

        async def get(self):
            self.calls += 1
            if self.calls == 1:
                return (-3, 1, "job-q1")
            raise asyncio.CancelledError()

    queue = _Queue()
    monkeypatch.setattr(app, "job_queue", queue)
    acquire_mock = AsyncMock()
    monkeypatch.setattr(app, "concurrency_semaphore", types.SimpleNamespace(acquire=acquire_mock, release=lambda: None))

    scheduled = {"count": 0}

    def _fake_create_task(coro):
        scheduled["count"] += 1
        try:
            coro.close()
        except Exception:
            pass
        return None

    monkeypatch.setattr(app.asyncio, "create_task", _fake_create_task)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(app.process_queue("w1"))

    acquire_mock.assert_awaited_once()
    assert scheduled["count"] == 1


def test_enforce_subscription_retention_policy_branches(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)

    # active
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value={"id": "sub1"}))
    result = asyncio.run(app._enforce_subscription_retention_policy("u1"))
    assert result["state"] == "active"

    # no subscription
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value=None))
    result = asyncio.run(app._enforce_subscription_retention_policy("u1"))
    assert result["state"] == "no_subscription"


def test_enforce_subscription_retention_policy_retention_and_disabled(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    real_datetime = __import__("datetime").datetime
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value={"id": "sub2", "payment_end_date": "x"}))
    monkeypatch.setattr(app, "_parse_iso_datetime", lambda _: real_datetime(2026, 1, 1, tzinfo=app.timezone.utc))
    monkeypatch.setattr(app, "STORAGE_RETENTION_PERIODE_DAYS", 10)
    monkeypatch.setattr(app, "_ensure_retention_deadline_on_subscription", AsyncMock())
    zero_mock = AsyncMock()
    disable_mock = AsyncMock()
    monkeypatch.setattr(app, "_zero_balances_on_subscription_expiration", zero_mock)
    monkeypatch.setattr(app, "_disable_subscription_account_if_needed", disable_mock)

    class _DTInWindow:
        @staticmethod
        def now(tz=None):
            return real_datetime(2026, 1, 5, tzinfo=app.timezone.utc)

    monkeypatch.setattr(app, "datetime", _DTInWindow)
    result = asyncio.run(app._enforce_subscription_retention_policy("u1"))
    assert result["state"] == "retention_window"

    class _DTPastWindow:
        @staticmethod
        def now(tz=None):
            return real_datetime(2026, 2, 1, tzinfo=app.timezone.utc)

    monkeypatch.setattr(app, "datetime", _DTPastWindow)
    result = asyncio.run(app._enforce_subscription_retention_policy("u1"))
    assert result["state"] == "disabled"
    zero_mock.assert_awaited_once()
    disable_mock.assert_awaited_once()


def test_process_endpoint_json_url_enqueues_job(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(app, "DISABLE_YOUTUBE_URL", False)
    monkeypatch.setattr(app.uuid, "uuid4", lambda: "job-json-1")
    monkeypatch.setattr(app, "_probe_remote_video_metadata", lambda *_: {
        "duration_seconds": 42.0,
        "size_bytes": 2048,
        "title": "Titre test",
        "description": "desc",
    })
    monkeypatch.setattr(app, "_validate_reel_source_constraints", lambda **kwargs: None)
    monkeypatch.setattr(app, "_estimate_reel_required_credits", lambda **kwargs: 1.25)
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=3))
    # Security hardening (audit finding H8): job creation now atomically
    # *reserves* the estimated credits via _reserve_job_credits instead of
    # merely checking the balance with _assert_user_has_required_credits.
    reserve_credits = AsyncMock()
    monkeypatch.setattr(app, "_reserve_job_credits", reserve_credits)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    app.reel_job_manager.create_job = AsyncMock()
    app.reel_job_manager.enqueue_job = AsyncMock()
    enqueue_job = AsyncMock()
    monkeypatch.setattr(app, "enqueue_reel_job", enqueue_job)

    class _Pipeline:
        def __init__(self, *_args, **_kwargs):
            pass

        async def queued(self):
            return None

    monkeypatch.setattr(app, "ReelProcessingPipeline", _Pipeline)

    class _Req:
        headers = {
            "content-type": "application/json",
            "user-agent": "pytest",
        }
        client = types.SimpleNamespace(host="127.0.0.1")

        async def json(self):
            return {"url": "https://cdn.example.com/reel.mp4", "acknowledged": True}

    payload = asyncio.run(
        app.process_endpoint(
            request=_Req(),
            file=None,
            url=None,
            acknowledged=None,
            user_id="u1",
        )
    )

    assert payload["job_id"] == "job-json-1"
    assert payload["status"] == "queued"
    assert "job-json-1" in app.jobs
    assert "-u" in app.jobs["job-json-1"]["cmd"]
    reserve_credits.assert_awaited_once()
    app.reel_job_manager.create_job.assert_awaited_once()
    app.reel_job_manager.enqueue_job.assert_awaited_once_with("job-json-1")
    enqueue_job.assert_awaited_once_with("job-json-1", priority=3)


def test_process_endpoint_upload_rejects_oversized_file(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(app, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(app, "REEL_MAX_STORAGE_GB", 1e-9)
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=1))
    os.makedirs(app.UPLOAD_DIR, exist_ok=True)

    class _Req:
        headers = {"user-agent": "pytest"}
        client = types.SimpleNamespace(host="127.0.0.1")

    class _Upload:
        def __init__(self, content: bytes):
            self.filename = "big.mp4"
            self.content_type = "video/mp4"
            self._content = content
            self._done = False

        async def read(self, _chunk_size: int):
            if self._done:
                return b""
            self._done = True
            return self._content

    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(
            app.process_endpoint(
                request=_Req(),
                file=_Upload(b"0123456789"),
                url=None,
                acknowledged="true",
                user_id="u1",
            )
        )

    assert exc.value.status_code == 413
    assert "Maximum autorise" in str(exc.value.detail)


def test_render_proxy_endpoints_forward_requests(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "RENDER_SERVICE_URL", "http://render.test")

    httpx_mod = types.ModuleType("httpx")

    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers=None):
            return types.SimpleNamespace(json=lambda: {"ok": True, "url": url, "body": json})

        async def get(self, url, headers=None):
            return types.SimpleNamespace(json=lambda: {"ok": True, "url": url})

    httpx_mod.AsyncClient = _Client
    monkeypatch.setitem(sys.modules, "httpx", httpx_mod)

    with TestClient(app.app) as client:
        post_resp = client.post("/api/render", json={"composition": "Main"}, headers=_auth_headers("u1"))
        get_resp = client.get("/api/render/r-123", headers=_auth_headers("u1"))

    assert post_resp.status_code == 200
    assert post_resp.json()["url"] == "http://render.test/render"
    assert post_resp.json()["body"]["composition"] == "Main"
    assert get_resp.status_code == 200
    assert get_resp.json()["url"] == "http://render.test/render/r-123"


def test_generate_effects_config_with_input_filename_success(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    input_dir = tmp_path / "output" / "j-effects"
    input_dir.mkdir(parents=True, exist_ok=True)
    input_file = input_dir / "clip.mp4"
    input_file.write_bytes(b"video")
    monkeypatch.setattr(app.os.path, "getsize", lambda _p: 4096)
    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda _p: 8.0)
    monkeypatch.setattr(app, "_estimate_reel_required_credits", lambda **_kwargs: 0.8)
    assert_credits = AsyncMock()
    monkeypatch.setattr(app, "_assert_user_has_required_credits", assert_credits)
    monkeypatch.setattr(
        app.subprocess,
        "check_output",
        lambda _cmd, **_kwargs: b'{"streams":[{"width":1080,"height":1920,"r_frame_rate":"30/1","duration":8}],"format":{"duration":8}}',
    )
    monkeypatch.setattr(app.shutil, "copy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app.os, "remove", lambda _p: None)
    monkeypatch.setattr(
        app,
        "_apply_auto_edit_options_to_effects_config",
        lambda effects, _opts: (effects, ["normalized"]),
    )

    class _Editor:
        def __init__(self, api_key):
            self.api_key = api_key

        def upload_video(self, _path):
            return "uploaded-ref"

        def get_effects_config(self, *_args, **_kwargs):
            return {"layers": [{"type": "zoom", "start": 0, "end": 60}]}

    monkeypatch.setattr(app, "VideoEditor", _Editor)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/effects/generate",
            json={"job_id": "j-effects", "clip_index": 0, "input_filename": "clip.mp4"},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["effects"]["layers"][0]["type"] == "zoom"
    assert payload["applied_steps"] == ["normalized"]
    assert_credits.assert_awaited_once()


def test_probe_video_stream_for_effects_handles_empty_streams_list(monkeypatch, tmp_path):
    # Regression test: `probe_data.get('streams', [{}])[0]` only falls back
    # to [{}] when the 'streams' key is missing entirely -- a file ffprobe
    # can read but detects no video stream in (streams: []) still indexed
    # into an empty list and raised IndexError, surfacing as a generic 500
    # on /api/effects/generate.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(
        app.subprocess,
        "check_output",
        lambda _cmd, **_kwargs: b'{"streams":[],"format":{"duration":12.5}}',
    )
    width, height, fps, duration = app._probe_video_stream_for_effects(str(tmp_path / "clip.mp4"))
    assert width == 1080
    assert height == 1920
    assert fps == 30.0
    assert duration == 12.5


def test_add_subtitles_dubbed_video_uses_transcription(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    monkeypatch.setattr(app.os.path, "exists", lambda _p: True)
    monkeypatch.setattr(app, "_append_style_version_to_metadata", lambda *_args, **_kwargs: 4)
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *_args, **_kwargs: None)
    assert_credits = AsyncMock()
    monkeypatch.setattr(app, "_assert_user_has_required_credits", assert_credits)

    meta = {
        "transcript": {"segments": [{"text": "hello"}]},
        "shorts": [{"start": 0.0, "end": 4.0, "video_url": "/videos/deadbeef/translated_clip.mp4"}],
    }
    monkeypatch.setattr(app, "_get_or_build_job_metadata", AsyncMock(return_value=("/tmp/meta.json", meta)))

    calls = {"transcribed": 0}

    def _fake_transcribe(_input, _srt, max_words_per_line=4):
        calls["transcribed"] += 1
        return True

    monkeypatch.setattr(app, "generate_srt_from_video", _fake_transcribe)
    monkeypatch.setattr(
        app,
        "generate_srt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("generate_srt should not run for dubbed files")),
    )
    monkeypatch.setattr(app, "burn_subtitles", lambda *_args, **_kwargs: True)

    class _StyleOptions:
        def __init__(self, **_kwargs):
            pass

    monkeypatch.setattr(app, "SubtitleStyleOptions", _StyleOptions)
    app.jobs["deadbeef"] = {
        "user_id": "u1",
        "result": {"clips": [{"video_url": "/videos/deadbeef/translated_clip.mp4"}]},
    }

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/subtitle",
            json={
                "job_id": "deadbeef",
                "clip_index": 0,
                "input_filename": "translated_clip.mp4",
                "words_per_line": 6,
            },
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert payload["version"] == 4
    assert calls["transcribed"] == 1
    assert_credits.assert_awaited_once()


def test_persist_captioned_reel_happy_path_with_s3_supabase_and_style(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda _p: 12.0)
    monkeypatch.setattr(app, "_estimate_caption_cost_breakdown", lambda **_kwargs: {"total_usd": 0.1})
    monkeypatch.setattr(app, "_estimate_caption_required_credits", lambda **_kwargs: 0.5)
    monkeypatch.setattr(app, "_bytes_to_gb", lambda _b: 0.001)
    monkeypatch.setattr(app, "_caption_media_url_from_s3_key", lambda key: f"https://cdn.caption/{key}" if key else "")
    monkeypatch.setattr(app, "_reel_media_url_from_s3_key", lambda key: f"https://cdn.reel/{key}" if key else "")
    monkeypatch.setattr(app, "_reel_thumbnail_url_from_s3_key", lambda key: f"https://cdn.thumb/{key}" if key else "")
    monkeypatch.setattr(app, "_build_billing_details", lambda *_args, **_kwargs: {"ok": True})

    metadata = {
        "shorts": [{"video_url": "/videos/job-1/original.mp4", "start": 0.0, "end": 2.0}],
        "style_history": {},
    }
    monkeypatch.setattr(app, "_get_or_build_job_metadata", AsyncMock(return_value=("/tmp/meta.json", metadata)))
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_append_style_version_to_metadata", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(app, "_assert_user_has_required_credits", AsyncMock())

    thumb_path = tmp_path / "thumb.jpg"
    thumb_path.write_bytes(b"thumb")
    monkeypatch.setattr(app, "_generate_reel_thumbnail_from_video", lambda *_args, **_kwargs: str(thumb_path))
    monkeypatch.setattr(app.os, "remove", lambda _p: None)

    upload_calls = []

    def _upload(path, bucket, key):
        upload_calls.append((path, bucket, key))
        return True

    monkeypatch.setattr(app, "upload_file_to_s3", _upload)
    monkeypatch.setattr(app, "supabase_get_caption_by_job_clip", AsyncMock(return_value={"id": "cap-1", "caption_s3_key": "captions/u1/job-1/prev.mp4"}))
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"reel_s3_key": "reels/u1/job-1/prev.mp4"}))
    app.supabase_update_caption = AsyncMock()
    app.supabase_update_reel_media_by_job_clip = AsyncMock()
    app.supabase_deduct_user_credits = AsyncMock(return_value=True)
    app.supabase_insert_user_data_history = AsyncMock()
    app.supabase_insert_style_edit_version = AsyncMock()

    class _Upload:
        def __init__(self):
            self.filename = "render.mov"
            self.content_type = "video/quicktime"
            self.file = io.BytesIO(b"video-bytes")
            self.closed = False

        async def close(self):
            self.closed = True

    app.jobs["job-1"] = {"result": {"clips": [{"video_url": "/videos/job-1/original.mp4"}]}}
    upload = _Upload()

    result = asyncio.run(
        app.persist_captioned_reel(
            job_id="job-1",
            clip_index=0,
            file=upload,
            subtitle_config='{"style": {"font_name": "Inter"}}',
            remotion_layers='{"layers": [{"type": "caption"}]}',
            user_id="u1",
        )
    )

    assert result["success"] is True
    assert result["persisted"] is True
    assert result["new_video_url"].startswith("https://cdn.caption/captions/u1/job-1/")
    assert result["preview_image_url"].startswith("https://cdn.caption/captions/u1/job-1/thumbnail_")
    assert upload.closed is True
    assert len(upload_calls) >= 3
    app.supabase_update_caption.assert_awaited_once()
    app.supabase_update_reel_media_by_job_clip.assert_awaited_once()
    app.supabase_deduct_user_credits.assert_awaited_once()
    app.supabase_insert_user_data_history.assert_awaited_once()
    app.supabase_insert_style_edit_version.assert_awaited_once()


def test_persist_captioned_reel_falls_back_to_local_urls_when_s3_upload_fails(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda _p: 6.0)
    monkeypatch.setattr(app, "_estimate_caption_cost_breakdown", lambda **_kwargs: {})
    monkeypatch.setattr(app, "_estimate_caption_required_credits", lambda **_kwargs: 0.0)
    monkeypatch.setattr(app, "_bytes_to_gb", lambda _b: 0.0)
    monkeypatch.setattr(app, "_assert_user_has_required_credits", AsyncMock())

    metadata = {"shorts": [{"video_url": "/videos/job-2/base.mp4", "start": 0.0, "end": 1.0}]}
    monkeypatch.setattr(app, "_get_or_build_job_metadata", AsyncMock(return_value=("/tmp/meta.json", metadata)))
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_generate_reel_thumbnail_from_video", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(app, "upload_file_to_s3", lambda *_args, **_kwargs: False)

    class _Upload:
        def __init__(self):
            self.filename = "render.webm"
            self.content_type = "video/webm"
            self.file = io.BytesIO(b"video")

        async def close(self):
            return None

    result = asyncio.run(
        app.persist_captioned_reel(
            job_id="job-2",
            clip_index=0,
            file=_Upload(),
            subtitle_config="{bad-json",
            remotion_layers="{bad-json",
            user_id="u2",
        )
    )

    assert result["success"] is True
    assert result["new_video_url"].startswith("/videos/job-2/captioned_0_")
    assert result["preview_image_url"] == result["new_video_url"]


def test_persist_captioned_reel_rejects_non_video_content_type(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _Upload:
        filename = "render.txt"
        content_type = "text/plain"
        file = io.BytesIO(b"x")

        async def close(self):
            return None

    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(
            app.persist_captioned_reel(
                job_id="job-3",
                clip_index=0,
                file=_Upload(),
                subtitle_config=None,
                remotion_layers=None,
                user_id="u3",
            )
        )

    assert exc.value.status_code == 400
    assert "Invalid rendered video content type" in str(exc.value.detail)



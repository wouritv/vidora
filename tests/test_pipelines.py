import asyncio
import importlib
import sys
import types
from unittest.mock import AsyncMock


def _import_pipelines_with_job_manager_stub(monkeypatch):
    job_manager_stub = types.ModuleType("job_manager")

    class _JobManager:
        pass

    job_manager_stub.JobManager = _JobManager
    monkeypatch.setitem(sys.modules, "job_manager", job_manager_stub)

    if "pipelines" in sys.modules:
        return importlib.reload(sys.modules["pipelines"])
    return importlib.import_module("pipelines")


def test_reel_pipeline_uploading_reels_reports_expected_progress(monkeypatch):
    pipelines = _import_pipelines_with_job_manager_stub(monkeypatch)

    manager = types.SimpleNamespace(update_progress=AsyncMock())
    pipe = pipelines.ReelProcessingPipeline(manager, "job-123")

    asyncio.run(pipe.uploading_reels(clip_count=4))

    manager.update_progress.assert_awaited_once_with("job-123", 75, "uploading_reels", metadata={"clip_count": 4})


def test_caption_pipeline_transcribing_reports_expected_progress(monkeypatch):
    pipelines = _import_pipelines_with_job_manager_stub(monkeypatch)

    manager = types.SimpleNamespace(update_progress=AsyncMock())
    pipe = pipelines.CaptionProcessingPipeline(manager, "job-abc")

    asyncio.run(pipe.transcribing())

    manager.update_progress.assert_awaited_once_with("job-abc", 45, "transcribing", metadata={})


def test_pipeline_step_uses_empty_metadata_by_default(monkeypatch):
    pipelines = _import_pipelines_with_job_manager_stub(monkeypatch)
    manager = types.SimpleNamespace(update_progress=AsyncMock())
    pipe = pipelines.Pipeline(manager, "job-base")
    asyncio.run(pipe.step(10, "custom"))
    manager.update_progress.assert_awaited_once_with("job-base", 10, "custom", metadata={})


def test_reel_pipeline_methods_progress(monkeypatch):
    pipelines = _import_pipelines_with_job_manager_stub(monkeypatch)
    manager = types.SimpleNamespace(update_progress=AsyncMock())
    pipe = pipelines.ReelProcessingPipeline(manager, "job-r")

    asyncio.run(pipe.queued())
    asyncio.run(pipe.starting())
    asyncio.run(pipe.cutting_clips())
    asyncio.run(pipe.finalizing())

    calls = [call.args for call in manager.update_progress.await_args_list]
    assert calls[0][:3] == ("job-r", 0, "queued")
    assert calls[1][:3] == ("job-r", 5, "starting")
    assert calls[2][:3] == ("job-r", 35, "cutting_clips")
    assert calls[3][:3] == ("job-r", 90, "finalizing")


def test_caption_pipeline_methods_progress(monkeypatch):
    pipelines = _import_pipelines_with_job_manager_stub(monkeypatch)
    manager = types.SimpleNamespace(update_progress=AsyncMock())
    pipe = pipelines.CaptionProcessingPipeline(manager, "job-c")

    asyncio.run(pipe.analyzing())
    asyncio.run(pipe.rendering())
    asyncio.run(pipe.persisting())

    calls = [call.args for call in manager.update_progress.await_args_list]
    assert calls[0][:3] == ("job-c", 20, "analyzing")
    assert calls[1][:3] == ("job-c", 75, "rendering")
    assert calls[2][:3] == ("job-c", 90, "persisting")



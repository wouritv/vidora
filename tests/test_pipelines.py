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


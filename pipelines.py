from typing import Any, Dict

from job_manager import JobManager


class Pipeline:
    def __init__(self, manager: JobManager, job_id: str):
        self.manager = manager
        self.job_id = job_id

    async def step(self, progress: int, current_step: str, metadata: Dict[str, Any] | None = None) -> None:
        await self.manager.update_progress(self.job_id, progress, current_step, metadata=metadata or {})


class ReelProcessingPipeline(Pipeline):
    async def queued(self) -> None:
        await self.step(0, "queued")

    async def starting(self) -> None:
        await self.step(5, "starting")

    async def cutting_clips(self) -> None:
        await self.step(35, "cutting_clips")

    async def uploading_reels(self, clip_count: int) -> None:
        await self.step(75, "uploading_reels", {"clip_count": clip_count})

    async def finalizing(self) -> None:
        await self.step(90, "finalizing")


class CaptionProcessingPipeline(Pipeline):
    async def analyzing(self) -> None:
        await self.step(20, "analyzing")

    async def transcribing(self) -> None:
        await self.step(45, "transcribing")

    async def rendering(self) -> None:
        await self.step(75, "rendering")

    async def persisting(self) -> None:
        await self.step(90, "persisting")


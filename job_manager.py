import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from supabase_request import (
    append_job_log,
    create_job_record,
    get_job_record,
    list_job_logs,
    update_job_record,
    deduct_user_credits as supabase_deduct_user_credits,
    insert_user_data_history as supabase_insert_user_data_history,
    get_user_data as supabase_get_user_data,
)


class JobType:
    TRANSCRIBE = "TRANSCRIBE"
    GENERATE_SUBTITLES = "GENERATE_SUBTITLES"
    TRANSLATE = "TRANSLATE"
    DETECT_HIGHLIGHTS = "DETECT_HIGHLIGHTS"
    GENERATE_REELS = "GENERATE_REELS"
    GENERATE_HIGHLIGHT_VIDEO = "GENERATE_HIGHLIGHT_VIDEO"
    RENDER_VIDEO = "RENDER_VIDEO"
    GENERATE_THUMBNAIL = "GENERATE_THUMBNAIL"


class JobManager:
    """Supabase-backed job lifecycle manager with in-memory runtime payloads."""

    def __init__(self, queue_name: str = "default"):
        self.queue_name = queue_name
        self.runtime_jobs: Dict[str, Dict[str, Any]] = {}

    async def create_job(
        self,
        user_id: str,
        job_type: str,
        job_data: Dict[str, Any],
        pipeline_name: str,
        job_id: Optional[str] = None,
        runtime_data: Optional[Dict[str, Any]] = None,
        max_attempts: int = 2,
        reserved_quota: float = 0.0,
        estimated_cost_usd: float = 0.0,
        priority: int = 1,
    ) -> Dict[str, Any]:
        job_id = job_id or str(uuid.uuid4())
        row = await create_job_record(
            job_id=job_id,
            user_id=user_id,
            job_type=job_type,
            status="created",
            job_data=job_data,
            queue_name=self.queue_name,
            pipeline_name=pipeline_name,
            max_attempts=max_attempts,
            reserved_quota=reserved_quota,
            estimated_cost_usd=estimated_cost_usd,
            priority=max(1, min(3, int(priority or 1))),
        )
        if runtime_data:
            runtime_copy = dict(runtime_data)
            runtime_copy["priority"] = max(1, min(3, int(priority or 1)))
            self.runtime_jobs[job_id] = runtime_copy
        await append_job_log(
            job_id,
            "INFO",
            "Job created",
            {"job_type": job_type, "priority": max(1, min(3, int(priority or 1)))},
        )
        return row

    async def enqueue_job(self, job_id: str) -> None:
        await update_job_record(
            job_id,
            {
                "status": "queued",
                "current_step": "queued",
                "progress": 0,
            },
        )
        await append_job_log(job_id, "INFO", "Job enqueued")

    async def start_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        row = await get_job_record(job_id)
        if not row:
            return None
        attempts = int(row.get("attempts") or 0) + 1
        await append_job_log(job_id, "INFO", "Job started", {"attempt": attempts})
        return await update_job_record(
            job_id,
            {
                "status": "processing",
                "attempts": attempts,
                "current_step": "processing",
            },
        )

    async def update_progress(self, job_id: str, progress: int, current_step: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        pct = min(max(int(progress), 0), 100)
        await update_job_record(job_id, {"progress": pct, "current_step": current_step})
        if metadata is not None:
            await append_job_log(job_id, "INFO", f"Progress {pct}%", metadata)

    async def complete_job(self, job_id: str, result_data: Dict[str, Any], actual_cost_usd: float = 0.0, actual_credit: float = 0.0) -> None:
        await update_job_record(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "current_step": "completed",
                "result_data": result_data or {},
                "actual_cost_usd": float(actual_cost_usd),
                "actual_credit": float(actual_credit),
                # Consume reserved quota only when success is confirmed.
                "consumed_quota": float(1.0),
            },
        )
        await append_job_log(job_id, "INFO", "Job completed")
        self.runtime_jobs.pop(job_id, None)

    async def debit_credits_for_job(
        self,
        job_id: str,
        user_id: str,
        credits: float,
        storage_delta: float = 0.0,
        operation_type: str = "reels",
    ) -> bool:
        """Deduct ``credits`` from the user and record the operation in history.

        Returns ``True`` if the deduction succeeded, ``False`` if insufficient funds.
        """
        if credits <= 0:
            return True
        success = await supabase_deduct_user_credits(user_id, credits, storage_delta)
        if success:
            await supabase_insert_user_data_history(
                user_id=user_id,
                credit=credits,
                storage=abs(storage_delta),
                operation="output",
                operation_type=operation_type,
                operation_id=job_id,
            )
            await update_job_record(job_id, {"actual_credit": float(credits)})
            await append_job_log(job_id, "INFO", f"Credits debited: {credits}", {"operation_type": operation_type})
        else:
            await append_job_log(job_id, "WARN", f"Insufficient credits to debit {credits}", {"user_id": user_id})
        return success

    async def fail_job(self, job_id: str, error_message: str, error_code: str = "JOB_FAILED", retry_delay_seconds: int = 0) -> Dict[str, Any]:
        row = await get_job_record(job_id)
        if not row:
            return {"status": "failed", "retry": False}

        attempts = int(row.get("attempts") or 0)
        max_attempts = int(row.get("max_attempts") or 1)
        can_retry = attempts < max_attempts

        status = "retry_wait" if can_retry else "failed"
        step = "retry_scheduled" if can_retry else "failed"
        updates: Dict[str, Any] = {
            "status": status,
            "current_step": step,
            "error_code": error_code,
            "error_message": error_message,
        }
        await update_job_record(job_id, updates)
        await append_job_log(
            job_id,
            "ERROR",
            error_message,
            {"error_code": error_code, "retry": can_retry, "retry_delay_seconds": int(max(0, retry_delay_seconds))},
        )

        if not can_retry:
            # Release reservation on terminal failure.
            await update_job_record(job_id, {"consumed_quota": 0.0})
            self.runtime_jobs.pop(job_id, None)

        return {"status": status, "retry": can_retry, "retry_delay_seconds": int(max(0, retry_delay_seconds))}

    async def retry_job(self, job_id: str) -> None:
        await update_job_record(job_id, {"status": "queued", "current_step": "retry_enqueued"})
        await append_job_log(job_id, "WARN", "Job retry enqueued")

    async def cancel_job(self, job_id: str, reason: str = "Canceled by user") -> None:
        await update_job_record(
            job_id,
            {
                "status": "canceled",
                "current_step": "canceled",
                "error_code": "CANCELED",
                "error_message": reason,
                "consumed_quota": 0.0,
            },
        )
        await append_job_log(job_id, "WARN", reason)
        self.runtime_jobs.pop(job_id, None)

    async def get_job_view(self, job_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        row = await get_job_record(job_id, user_id=user_id)
        if not row:
            return None
        logs = await list_job_logs(job_id)
        return {
            "id": row.get("id"),
            "status": row.get("status"),
            "progress": row.get("progress"),
            "current_step": row.get("current_step"),
            "result": row.get("result_data") or None,
            "error": {
                "code": row.get("error_code"),
                "message": row.get("error_message"),
            }
            if row.get("error_code") or row.get("error_message")
            else None,
            "logs": logs,
            "attempts": row.get("attempts"),
            "max_attempts": row.get("max_attempts"),
            "priority": row.get("priority"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    async def schedule_retry_after(self, queue: asyncio.Queue, job_id: str, delay_seconds: int) -> None:
        await asyncio.sleep(max(0, int(delay_seconds)))
        await self.retry_job(job_id)
        await queue.put(job_id)


def calc_elapsed_seconds(start_ts: float) -> float:
    return max(0.0, time.time() - start_ts)



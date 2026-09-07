import asyncio
import time
import uuid
import logging
import math
from typing import Any, Dict, Optional

from supabase_request import (
    append_job_log,
    create_job_record,
    get_job_record,
    list_job_logs,
    update_job_record,
    deduct_user_credits as supabase_deduct_user_credits,
    refund_user_credits as supabase_refund_user_credits,
    insert_user_data_history as supabase_insert_user_data_history,
    get_user_data as supabase_get_user_data,
)

logger = logging.getLogger(__name__)


def _ceil_credit(value: float) -> int:
    return int(max(0, math.ceil(float(value or 0.0))))

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

    async def reserve_credits(self, user_id: str, credits: float) -> bool:
        """Atomically reserve ``credits`` from the user's balance at job
        creation time, instead of merely checking that the balance covers
        the estimate. This closes the race where several concurrent job
        submissions could all pass a non-mutating balance check before any
        of them is actually billed at completion (see security audit
        finding H8). Returns False if the balance is insufficient.
        """
        normalized = _ceil_credit(credits)
        if normalized <= 0:
            return True
        return await supabase_deduct_user_credits(user_id, normalized)

    async def refund_reservation(
        self,
        job_id: str,
        user_id: str,
        reserved_credits: float,
        operation_type: str = "reels",
    ) -> None:
        """Give back a reservation in full -- used when a job ends with no
        billable output (terminal failure, cancellation)."""
        normalized = _ceil_credit(reserved_credits)
        if normalized <= 0:
            return
        await supabase_refund_user_credits(user_id, normalized)
        await supabase_insert_user_data_history(
            user_id=user_id,
            credit=normalized,
            storage=0.0,
            operation="refund",
            operation_type=operation_type,
            operation_id=job_id,
        )
        await append_job_log(
            job_id,
            "INFO",
            f"Reservation refunded: credits={normalized}",
            {"operation_type": operation_type},
        )

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
        queue_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        job_id = job_id or str(uuid.uuid4())
        effective_queue_name = str(queue_name or self.queue_name)
        row = await create_job_record(
            job_id=job_id,
            user_id=user_id,
            job_type=job_type,
            status="created",
            job_data=job_data,
            queue_name=effective_queue_name,
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

    async def complete_job(
        self,
        job_id: str,
        result_data: Dict[str, Any],
        actual_cost_usd: float = 0.0,
        actual_credit: float = 0.0,
        actual_storage_gb: float = 0.0,
        consumed_quota: float = 1.0,
        cost_breakdown: Optional[Dict[str, Any]] = None,
    ) -> None:
        billed_credit = _ceil_credit(actual_credit)
        await update_job_record(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "current_step": "completed",
                "result_data": result_data or {},
                "actual_cost_usd": float(actual_cost_usd),
                "actual_credit": billed_credit,
                "actual_storage_gb": float(max(0.0, actual_storage_gb)),
                "cost_breakdown": cost_breakdown or {},
                # Consume reserved quota only when success is confirmed.
                "consumed_quota": float(max(0.0, consumed_quota)),
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
        reserved_credits: float = 0.0,
    ) -> bool:
        """Bill ``credits`` (the actual cost) for a completed job.

        If ``reserved_credits`` was already atomically debited at job
        creation time (see reserve_credits), this settles the *delta*
        between the actual cost and the reservation -- an extra debit if
        the job cost more than estimated, or a refund if it cost less --
        instead of debiting the full actual cost again (which would double
        -charge the user on top of the reservation). Pass 0 (the default)
        for jobs that don't use reservations, which debits the full amount
        exactly as before.

        Returns ``True`` if the settlement succeeded, ``False`` if an
        additional debit was needed but the balance was insufficient.
        """
        normalized_credits = _ceil_credit(credits)
        normalized_storage_gb = abs(float(storage_delta or 0.0))
        normalized_reserved = _ceil_credit(reserved_credits)
        delta = normalized_credits - normalized_reserved

        if delta == 0 and storage_delta == 0:
            # Reservation exactly covered the actual cost and there's no
            # storage change to apply -- nothing to settle, but still
            # record what was billed for history/audit.
            if normalized_reserved > 0:
                await update_job_record(
                    job_id,
                    {"actual_credit": normalized_credits, "actual_storage_gb": normalized_storage_gb},
                )
            return True

        if delta >= 0:
            # Reservation covered less than the actual cost (or there was no
            # reservation): debit the remaining delta plus any storage change.
            success = await supabase_deduct_user_credits(user_id, delta, storage_delta)
        else:
            # Reservation covered more than the actual cost: refund the
            # difference, still applying any storage change.
            success = await supabase_refund_user_credits(user_id, abs(delta), storage_delta)

        if success:
            await supabase_insert_user_data_history(
                user_id=user_id,
                credit=normalized_credits,
                storage=normalized_storage_gb,
                operation="output",
                operation_type=operation_type,
                operation_id=job_id,
            )
            await update_job_record(
                job_id,
                {
                    "actual_credit": normalized_credits,
                    "actual_storage_gb": normalized_storage_gb,
                },
            )
            await append_job_log(
                job_id,
                "INFO",
                f"Credits/storage settled: actual={normalized_credits}, reserved={normalized_reserved}, "
                f"delta={delta}, storage_gb={normalized_storage_gb}",
                {"operation_type": operation_type},
            )
        else:
            await append_job_log(
                job_id,
                "WARN",
                f"Insufficient balance to settle credits: actual={normalized_credits}, reserved={normalized_reserved}, "
                f"delta={delta}, storage_gb={normalized_storage_gb}",
                {"user_id": user_id, "operation_type": operation_type},
            )
        return success

    async def fail_job(
        self,
        job_id: str,
        error_message: str,
        error_code: str = "JOB_FAILED",
        retry_delay_seconds: int = 0,
        actual_cost_usd: Optional[float] = None,
        actual_credit: Optional[float] = None,
        actual_storage_gb: Optional[float] = None,
        consumed_quota: Optional[float] = None,
        result_data: Optional[Dict[str, Any]] = None,
        cost_breakdown: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        if actual_cost_usd is not None:
            updates["actual_cost_usd"] = float(max(0.0, actual_cost_usd))
        if actual_credit is not None:
            updates["actual_credit"] = _ceil_credit(actual_credit)
        if actual_storage_gb is not None:
            updates["actual_storage_gb"] = float(max(0.0, actual_storage_gb))
        if consumed_quota is not None:
            updates["consumed_quota"] = float(max(0.0, consumed_quota))
        if result_data is not None:
            updates["result_data"] = result_data
        if cost_breakdown is not None:
            updates["cost_breakdown"] = cost_breakdown
        await update_job_record(job_id, updates)
        await append_job_log(
            job_id,
            "ERROR",
            error_message,
            {"error_code": error_code, "retry": can_retry, "retry_delay_seconds": int(max(0, retry_delay_seconds))},
        )

        if not can_retry:
            # Release reservation on terminal failure.
            if consumed_quota is None:
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
            "actual_cost_usd": row.get("actual_cost_usd"),
            "actual_credit": row.get("actual_credit"),
            "actual_storage_gb": row.get("actual_storage_gb"),
            "consumed_quota": row.get("consumed_quota"),
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



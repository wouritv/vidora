import asyncio
import importlib
import sys
import types
from unittest.mock import AsyncMock


def _import_job_manager_with_supabase_stub(monkeypatch):
    supabase_request_stub = types.ModuleType("supabase_request")

    async def _noop(*args, **kwargs):
        return None

    supabase_request_stub.append_job_log = _noop
    supabase_request_stub.create_job_record = _noop
    supabase_request_stub.get_job_record = _noop
    supabase_request_stub.list_job_logs = _noop
    supabase_request_stub.update_job_record = _noop
    supabase_request_stub.deduct_user_credits = _noop
    supabase_request_stub.refund_user_credits = _noop
    supabase_request_stub.insert_user_data_history = _noop
    supabase_request_stub.get_user_data = _noop

    monkeypatch.setitem(sys.modules, "supabase_request", supabase_request_stub)

    if "job_manager" in sys.modules:
        return importlib.reload(sys.modules["job_manager"])
    return importlib.import_module("job_manager")


def test_ceil_credit_handles_negative_and_fractional_values(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)

    assert job_manager._ceil_credit(-2.0) == 0
    assert job_manager._ceil_credit(0) == 0
    assert job_manager._ceil_credit(2.01) == 3


def test_debit_credits_for_job_success_path_updates_log_and_record(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()

    job_manager.supabase_deduct_user_credits = AsyncMock(return_value=True)
    job_manager.supabase_insert_user_data_history = AsyncMock()
    job_manager.update_job_record = AsyncMock()
    job_manager.append_job_log = AsyncMock()

    result = asyncio.run(
        manager.debit_credits_for_job(
            job_id="job-1",
            user_id="user-1",
            credits=2.2,
            storage_delta=-1.3,
            operation_type="reels",
        )
    )

    assert result is True
    job_manager.supabase_deduct_user_credits.assert_awaited_once_with("user-1", 3, -1.3)
    job_manager.update_job_record.assert_awaited()
    job_manager.append_job_log.assert_awaited()


def test_debit_credits_for_job_insufficient_balance_logs_warning(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()

    job_manager.supabase_deduct_user_credits = AsyncMock(return_value=False)
    job_manager.supabase_insert_user_data_history = AsyncMock()
    job_manager.update_job_record = AsyncMock()
    job_manager.append_job_log = AsyncMock()

    result = asyncio.run(
        manager.debit_credits_for_job(
            job_id="job-2",
            user_id="user-2",
            credits=5.1,
            storage_delta=0.3,
            operation_type="captions",
        )
    )

    assert result is False
    job_manager.supabase_insert_user_data_history.assert_not_awaited()
    job_manager.update_job_record.assert_not_awaited()
    job_manager.append_job_log.assert_awaited_once()
    assert job_manager.append_job_log.await_args.args[1] == "WARN"


def test_debit_credits_for_job_settles_extra_debit_above_reservation(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()

    job_manager.supabase_deduct_user_credits = AsyncMock(return_value=True)
    job_manager.supabase_refund_user_credits = AsyncMock(return_value=True)
    job_manager.supabase_insert_user_data_history = AsyncMock()
    job_manager.update_job_record = AsyncMock()
    job_manager.append_job_log = AsyncMock()

    result = asyncio.run(
        manager.debit_credits_for_job(
            job_id="job-3",
            user_id="user-3",
            credits=5.0,
            storage_delta=0.0,
            operation_type="reels",
            reserved_credits=3.0,
        )
    )

    assert result is True
    # actual (5) exceeds reservation (3): only the 2-credit delta is debited,
    # never the full actual cost again on top of the reservation.
    job_manager.supabase_deduct_user_credits.assert_awaited_once_with("user-3", 2, 0.0)
    job_manager.supabase_refund_user_credits.assert_not_awaited()


def test_debit_credits_for_job_refunds_surplus_below_reservation(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()

    job_manager.supabase_deduct_user_credits = AsyncMock(return_value=True)
    job_manager.supabase_refund_user_credits = AsyncMock(return_value=True)
    job_manager.supabase_insert_user_data_history = AsyncMock()
    job_manager.update_job_record = AsyncMock()
    job_manager.append_job_log = AsyncMock()

    result = asyncio.run(
        manager.debit_credits_for_job(
            job_id="job-4",
            user_id="user-4",
            credits=2.0,
            storage_delta=0.0,
            operation_type="reels",
            reserved_credits=5.0,
        )
    )

    assert result is True
    # actual (2) cost less than the reservation (5): the 3-credit surplus is
    # refunded rather than the full actual cost being debited a second time.
    job_manager.supabase_refund_user_credits.assert_awaited_once_with("user-4", 3, 0.0)
    job_manager.supabase_deduct_user_credits.assert_not_awaited()


def test_reserve_credits_debits_ceiled_amount(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()

    job_manager.supabase_deduct_user_credits = AsyncMock(return_value=True)

    result = asyncio.run(manager.reserve_credits("user-5", 4.2))

    assert result is True
    job_manager.supabase_deduct_user_credits.assert_awaited_once_with("user-5", 5)


def test_refund_reservation_refunds_and_logs(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()

    job_manager.supabase_refund_user_credits = AsyncMock(return_value=True)
    job_manager.supabase_insert_user_data_history = AsyncMock()
    job_manager.append_job_log = AsyncMock()

    asyncio.run(manager.refund_reservation("job-6", "user-6", 4.0, operation_type="sous_titre"))

    job_manager.supabase_refund_user_credits.assert_awaited_once_with("user-6", 4)
    job_manager.supabase_insert_user_data_history.assert_awaited_once()
    job_manager.append_job_log.assert_awaited_once()


def test_fail_job_returns_failed_when_attempts_exhausted(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()

    job_manager.get_job_record = AsyncMock(return_value={"attempts": 1, "max_attempts": 1})
    job_manager.update_job_record = AsyncMock()
    job_manager.append_job_log = AsyncMock()

    result = asyncio.run(manager.fail_job("job-42", "boom"))

    assert result["status"] == "failed"
    assert result["retry"] is False
    assert job_manager.update_job_record.await_count >= 1


def test_fail_job_returns_retry_wait_when_attempts_remaining(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()
    manager.runtime_jobs["job-r"] = {"payload": True}

    job_manager.get_job_record = AsyncMock(return_value={"attempts": 0, "max_attempts": 2})
    job_manager.update_job_record = AsyncMock()
    job_manager.append_job_log = AsyncMock()

    result = asyncio.run(manager.fail_job("job-r", "temporary error", retry_delay_seconds=12))

    assert result["status"] == "retry_wait"
    assert result["retry"] is True
    assert manager.runtime_jobs.get("job-r") is not None
    _, updates = job_manager.update_job_record.await_args.args
    assert updates["status"] == "retry_wait"
    assert updates["current_step"] == "retry_scheduled"


def test_create_job_stores_runtime_data_and_clamps_priority(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager(queue_name="reels")

    job_manager.create_job_record = AsyncMock(return_value={"id": "job-created"})
    job_manager.append_job_log = AsyncMock()

    row = asyncio.run(
        manager.create_job(
            user_id="user-x",
            job_type="GENERATE_REELS",
            job_data={"input": "file.mp4"},
            pipeline_name="reel_pipeline",
            job_id="job-created",
            runtime_data={"local_path": "/tmp/in.mp4"},
            priority=99,
        )
    )

    assert row == {"id": "job-created"}
    assert manager.runtime_jobs["job-created"]["local_path"] == "/tmp/in.mp4"
    assert manager.runtime_jobs["job-created"]["priority"] == 3
    assert job_manager.create_job_record.await_args.kwargs["priority"] == 3


def test_retry_job_sets_status_and_logs(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()

    job_manager.update_job_record = AsyncMock()
    job_manager.append_job_log = AsyncMock()

    asyncio.run(manager.retry_job("job-retry"))

    job_manager.update_job_record.assert_awaited_once_with(
        "job-retry", {"status": "queued", "current_step": "retry_enqueued"}
    )
    job_manager.append_job_log.assert_awaited_once_with("job-retry", "WARN", "Job retry enqueued")


def test_cancel_job_updates_status_and_clears_runtime(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()
    manager.runtime_jobs["job-cancel"] = {"tmp": True}

    job_manager.update_job_record = AsyncMock()
    job_manager.append_job_log = AsyncMock()

    asyncio.run(manager.cancel_job("job-cancel", reason="Canceled by API"))

    assert "job-cancel" not in manager.runtime_jobs
    _, payload = job_manager.update_job_record.await_args.args
    assert payload["status"] == "canceled"
    assert payload["current_step"] == "canceled"
    assert payload["error_code"] == "CANCELED"
    assert payload["consumed_quota"] == 0.0
    job_manager.append_job_log.assert_awaited_once_with("job-cancel", "WARN", "Canceled by API")


def test_get_job_view_returns_row_and_logs(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()

    job_manager.get_job_record = AsyncMock(
        return_value={
            "id": "job-v",
            "status": "failed",
            "progress": 35,
            "current_step": "retry_scheduled",
            "result_data": {"clips": []},
            "actual_cost_usd": 1.2,
            "actual_credit": 4,
            "actual_storage_gb": 0.5,
            "consumed_quota": 0.5,
            "error_code": "PROCESS_EXIT",
            "error_message": "boom",
            "attempts": 1,
            "max_attempts": 2,
            "priority": 2,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:01:00Z",
        }
    )
    job_manager.list_job_logs = AsyncMock(return_value=[{"level": "ERROR", "message": "boom"}])

    view = asyncio.run(manager.get_job_view("job-v", user_id="user-v"))

    assert view is not None
    assert view["id"] == "job-v"
    assert view["error"] == {"code": "PROCESS_EXIT", "message": "boom"}
    assert view["logs"] == [{"level": "ERROR", "message": "boom"}]
    job_manager.get_job_record.assert_awaited_once_with("job-v", user_id="user-v")


def test_schedule_retry_after_waits_then_requeues(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()

    sleep_mock = AsyncMock()
    retry_mock = AsyncMock()
    queue = types.SimpleNamespace(put=AsyncMock())

    monkeypatch.setattr(job_manager.asyncio, "sleep", sleep_mock)
    manager.retry_job = retry_mock

    asyncio.run(manager.schedule_retry_after(queue, "job-delay", 7))

    sleep_mock.assert_awaited_once_with(7)
    retry_mock.assert_awaited_once_with("job-delay")
    queue.put.assert_awaited_once_with("job-delay")


def test_enqueue_job_sets_status_and_logs(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()
    job_manager.update_job_record = AsyncMock()
    job_manager.append_job_log = AsyncMock()

    asyncio.run(manager.enqueue_job("job-q"))

    _, payload = job_manager.update_job_record.await_args.args
    assert payload["status"] == "queued"
    assert payload["progress"] == 0
    assert payload["current_step"] == "queued"
    job_manager.append_job_log.assert_awaited_once()


def test_start_job_returns_none_when_missing(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()
    job_manager.get_job_record = AsyncMock(return_value=None)

    result = asyncio.run(manager.start_job("job-missing"))

    assert result is None


def test_start_job_increments_attempts(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()
    job_manager.get_job_record = AsyncMock(return_value={"attempts": 2})
    job_manager.append_job_log = AsyncMock()
    job_manager.update_job_record = AsyncMock(return_value={"id": "job-s", "attempts": 3})

    result = asyncio.run(manager.start_job("job-s"))

    assert result == {"id": "job-s", "attempts": 3}
    _, payload = job_manager.update_job_record.await_args.args
    assert payload["status"] == "processing"
    assert payload["attempts"] == 3


def test_update_progress_clamps_and_optional_log(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()
    job_manager.update_job_record = AsyncMock()
    job_manager.append_job_log = AsyncMock()

    asyncio.run(manager.update_progress("job-p", 999, "step", metadata=None))
    _, payload = job_manager.update_job_record.await_args.args
    assert payload["progress"] == 100
    job_manager.append_job_log.assert_not_awaited()

    asyncio.run(manager.update_progress("job-p", -5, "step", metadata={"a": 1}))
    _, payload2 = job_manager.update_job_record.await_args.args
    assert payload2["progress"] == 0
    job_manager.append_job_log.assert_awaited()


def test_complete_job_sets_terminal_fields_and_clears_runtime(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()
    manager.runtime_jobs["job-done"] = {"tmp": True}
    job_manager.update_job_record = AsyncMock()
    job_manager.append_job_log = AsyncMock()

    asyncio.run(
        manager.complete_job(
            "job-done",
            {"ok": True},
            actual_cost_usd=1.23,
            actual_credit=2.2,
            actual_storage_gb=-5,
            consumed_quota=-1,
            cost_breakdown={"x": 1},
        )
    )

    _, payload = job_manager.update_job_record.await_args.args
    assert payload["status"] == "completed"
    assert payload["progress"] == 100
    assert payload["actual_credit"] == 3
    assert payload["actual_storage_gb"] == 0.0
    assert payload["consumed_quota"] == 0.0
    assert "job-done" not in manager.runtime_jobs


def test_get_job_view_returns_none_when_missing(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    manager = job_manager.JobManager()
    job_manager.get_job_record = AsyncMock(return_value=None)

    assert asyncio.run(manager.get_job_view("job-none")) is None


def test_calc_elapsed_seconds_never_negative(monkeypatch):
    job_manager = _import_job_manager_with_supabase_stub(monkeypatch)
    monkeypatch.setattr(job_manager.time, "time", lambda: 50.0)
    assert job_manager.calc_elapsed_seconds(100.0) == 0.0



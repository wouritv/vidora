import os
from datetime import datetime, timezone
import calendar
from typing import Any, Dict, List, Optional, Tuple

from supabase import acreate_client, AsyncClient
from supabase.lib.client_options import AsyncClientOptions

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_REELS_TABLE = os.environ.get("SUPABASE_REELS_TABLE", "reels")
SUPABASE_CAPTIONS_TABLE = os.environ.get("SUPABASE_CAPTIONS_TABLE", "ia_caption")
SUPABASE_ABONNEMENTS_TABLE = os.environ.get("SUPABASE_ABONNEMENTS_TABLE", "abonnement")
SUPABASE_SOUSCRIPTION_TABLE = os.environ.get("SUPABASE_SOUSCRIPTION_TABLE", "souscription")
SUPABASE_JOBS_TABLE = os.environ.get("SUPABASE_JOBS_TABLE", "jobs")
SUPABASE_JOB_LOGS_TABLE = os.environ.get("SUPABASE_JOB_LOGS_TABLE", "job_logs")
SUPABASE_USER_DATA_TABLE = os.environ.get("SUPABASE_USER_DATA_TABLE", "user_data")
SUPABASE_USER_DATA_HISTORY_TABLE = os.environ.get("SUPABASE_USER_DATA_HISTORY_TABLE", "user_data_history")


class SupabaseNotConfiguredError(RuntimeError):
	pass


def is_supabase_configured() -> bool:
	return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


# --------------------------------------------------------------------------
# Client singleton (à réutiliser plutôt que d'en recréer un à chaque appel)
# --------------------------------------------------------------------------
_client: Optional[AsyncClient] = None


async def get_client() -> AsyncClient:
	"""Retourne un client Supabase async partagé (créé une seule fois)."""
	global _client

	if not is_supabase_configured():
		raise SupabaseNotConfiguredError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

	if _client is None:
		_client = await acreate_client(
			SUPABASE_URL,
			SUPABASE_SERVICE_ROLE_KEY,
			options=AsyncClientOptions(postgrest_client_timeout=20),
		)
	return _client


# --------------------------------------------------------------------------
# Reels
# --------------------------------------------------------------------------
async def insert_reels(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	if not rows:
		return []

	client = await get_client()
	response = await client.table(SUPABASE_REELS_TABLE).insert(rows).execute()
	return response.data


async def list_reels(
	user_id: str,
	page: int,
	page_size: int,
	status: Optional[str] = None,
	query: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
	page = max(page, 1)
	page_size = min(max(page_size, 1), 100)
	offset = (page - 1) * page_size

	client = await get_client()
	q = (
		client.table(SUPABASE_REELS_TABLE)
		.select("*", count="exact")
		.eq("reel_user_id", user_id)
		.is_("deleted_at", "null")
		.order("reel_created_at", desc=True)
		.range(offset, offset + page_size - 1)
	)

	if status:
		q = q.eq("reel_status", status)

	if query:
		escaped = query.replace("*", "")
		q = q.or_(f"reel_title.ilike.*{escaped}*,reel_description.ilike.*{escaped}*")

	response = await q.execute()
	return response.data, response.count or 0


async def get_reel(reel_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	client = await get_client()
	response = (
		await client.table(SUPABASE_REELS_TABLE)
		.select("*")
		.eq("id", reel_id)
		.eq("reel_user_id", user_id)
		.is_("deleted_at", "null")
		.limit(1)
		.execute()
	)

	rows = response.data
	if not rows:
		return None
	return rows[0]


async def get_reel_by_job_clip(job_id: str, clip_index: int) -> Optional[Dict[str, Any]]:
	client = await get_client()
	response = (
		await client.table(SUPABASE_REELS_TABLE)
		.select("*")
		.eq("reel_job_id", job_id)
		.eq("reel_clip_index", clip_index)
		.is_("deleted_at", "null")
		.order("reel_updated_at", desc=True)
		.limit(1)
		.execute()
	)

	rows = response.data
	if not rows:
		return None
	return rows[0]


async def soft_delete_reel(reel_id: str, user_id: str) -> bool:
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()

	response = (
		await client.table(SUPABASE_REELS_TABLE)
		.update({"deleted_at": now_iso, "reel_updated_at": now_iso})
		.eq("id", reel_id)
		.eq("reel_user_id", user_id)
		.is_("deleted_at", "null")
		.execute()
	)

	return bool(response.data)


# --------------------------------------------------------------------------
# IA Captions
# --------------------------------------------------------------------------
CAPTION_COLUMNS = (
	"id, caption_url, caption_thumbnail_url, caption_title, caption_description, "
	"caption_duration, caption_created_at, caption_updated_at, caption_user_id, "
	"caption_status, caption_job_id, caption_clip_index, caption_s3_key, generation_inputs, "
	"input_source_type, input_source_value, deleted_at"
)


def caption_status_value(status: Optional[str]) -> str:
	if status in {"en_cours", "termine", "echec"}:
		return status
	return "termine"


async def insert_captions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	if not rows:
		return []
	client = await get_client()
	response = await client.table(SUPABASE_CAPTIONS_TABLE).insert(rows).execute()
	return response.data or []


async def list_captions(
	user_id: str,
	page: int,
	page_size: int,
	status: Optional[str] = None,
	query: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
	page = max(page, 1)
	page_size = min(max(page_size, 1), 100)
	offset = (page - 1) * page_size

	client = await get_client()
	q = (
		client.table(SUPABASE_CAPTIONS_TABLE)
		.select(CAPTION_COLUMNS, count="exact")
		.eq("caption_user_id", user_id)
		.is_("deleted_at", "null")
		.order("caption_created_at", desc=True)
		.range(offset, offset + page_size - 1)
	)

	if status:
		q = q.eq("caption_status", status)

	if query:
		escaped = query.replace("*", "")
		q = q.or_(f"caption_title.ilike.*{escaped}*,caption_description.ilike.*{escaped}*")

	response = await q.execute()
	return response.data or [], response.count or 0


async def get_caption(caption_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	client = await get_client()
	response = (
		await client.table(SUPABASE_CAPTIONS_TABLE)
		.select(CAPTION_COLUMNS)
		.eq("id", caption_id)
		.eq("caption_user_id", user_id)
		.is_("deleted_at", "null")
		.limit(1)
		.execute()
	)
	rows = response.data or []
	if not rows:
		return None
	return rows[0]


async def soft_delete_caption(caption_id: str, user_id: str) -> bool:
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	response = (
		await client.table(SUPABASE_CAPTIONS_TABLE)
		.update({"deleted_at": now_iso, "caption_updated_at": now_iso})
		.eq("id", caption_id)
		.eq("caption_user_id", user_id)
		.is_("deleted_at", "null")
		.execute()
	)
	return bool(response.data)


# --------------------------------------------------------------------------
# Abonnements
# --------------------------------------------------------------------------
ABONNEMENT_COLUMNS = "*"
SOUSCRIPTION_COLUMNS = (
	"id, created_at, userid, abonnement, payment_mode, payment_amount, payment_reference, "
	"payment_start_date, payment_end_date, payment_status, payment_comment, "
	"auto_renew, canceled_at, reactivated_at, paused_at, resumed_at, "
	"retention_deadline_at, account_disabled_at"
)

async def list_abonnements() -> List[Dict[str, Any]]:
	"""Récupère tous les abonnements disponibles."""
	client = await get_client()
	response = (
		await client.table(SUPABASE_ABONNEMENTS_TABLE)
		.select(ABONNEMENT_COLUMNS)
		.order("created_at", desc=False)
		.execute()
	)
	return response.data


async def get_abonnement(abonnement_uuid: str) -> Optional[Dict[str, Any]]:
	"""Récupère un abonnement précis par son uuid."""
	client = await get_client()
	response = (
		await client.table(SUPABASE_ABONNEMENTS_TABLE)
		.select(ABONNEMENT_COLUMNS)
		.eq("id", abonnement_uuid)
		.limit(1)
		.execute()
	)

	rows = response.data
	if not rows:
		return None
	return rows[0]


def _add_one_month(dt: datetime) -> datetime:
	"""Add one calendar month while keeping day within target month bounds."""
	year = dt.year + (1 if dt.month == 12 else 0)
	month = 1 if dt.month == 12 else dt.month + 1
	day = min(dt.day, calendar.monthrange(year, month)[1])
	return dt.replace(year=year, month=month, day=day)


async def insert_souscription(
	user_id: str,
	abonnement: str,
	payment_mode: str,
	payment_amount: float,
	payment_reference: str,
	payment_status: str = "confirmed",
	payment_comment: str = "",
	payment_date: Optional[datetime] = None,
) -> Dict[str, Any]:
	"""Create a subscription row after a confirmed payment."""
	client = await get_client()
	start_date = payment_date or datetime.now(timezone.utc)
	if start_date.tzinfo is None:
		start_date = start_date.replace(tzinfo=timezone.utc)
	end_date = _add_one_month(start_date)

	payload = {
		"userid": user_id,
		"abonnement": abonnement,
		"payment_mode": payment_mode,
		"payment_amount": float(payment_amount),
		"payment_reference": payment_reference,
		"payment_start_date": start_date.isoformat(),
		"payment_end_date": end_date.isoformat(),
		"payment_status": payment_status,
		"payment_comment": payment_comment,
	}

	response = await client.table(SUPABASE_SOUSCRIPTION_TABLE).insert(payload).execute()
	rows = response.data or []
	if not rows:
		return payload
	return rows[0]


async def get_souscription_by_reference(payment_reference: str) -> Optional[Dict[str, Any]]:
	"""Fetch a subscription row by payment reference for webhook idempotency."""
	if not payment_reference:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("payment_reference", payment_reference)
		.limit(1)
		.execute()
	)

	rows = response.data
	if not rows:
		return None
	return rows[0]

async def get_user_abonnement(user_id: str) -> Optional[Dict[str, Any]]:
	"""Récupère l'abonnement actif d'un utilisateur."""
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("userid", user_id)
		.eq("payment_status", "completed")
		.neq("payment_mode", "stripe_credits")
		.not_.is_("abonnement", "null")
		.is_("account_disabled_at", "null")
		.gte("payment_end_date", now_iso)
		.limit(1)
		.execute()
	)

	rows = response.data
	if not rows:
		return None
	row = dict(rows[0])

	# Resolve plan priority from the abonnement table; default to 1 when unknown.
	priority = 1
	try:
		abonnement_id = row.get("abonnement")
		if abonnement_id:
			abonnement = await get_abonnement(str(abonnement_id))
			raw_priority = (abonnement or {}).get("priorite")
			if raw_priority is not None:
				priority = int(raw_priority)
	except Exception:
		priority = 1

	row["priorite"] = max(1, min(3, int(priority or 1)))
	return row


async def get_latest_user_souscription(user_id: str) -> Optional[Dict[str, Any]]:
	"""Get latest subscription row for a user (active or expired)."""
	if not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("userid", user_id)
		.order("payment_end_date", desc=True)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def get_latest_user_paid_subscription(user_id: str) -> Optional[Dict[str, Any]]:
	"""Get latest confirmed plan subscription (excluding direct credit purchases)."""
	if not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("userid", user_id)
		.eq("payment_status", "completed")
		.neq("payment_mode", "stripe_credits")
		.not_.is_("abonnement", "null")
		.order("payment_end_date", desc=True)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def list_user_souscriptions(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
	"""List latest subscriptions/payments for a user."""
	if not user_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("userid", user_id)
		.order("payment_start_date", desc=True)
		.limit(min(max(limit, 1), 500))
		.execute()
	)
	return response.data or []


async def update_souscription_row(subscription_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	"""Update one subscription row and return it."""
	if not subscription_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.update(dict(updates or {}))
		.eq("id", subscription_id)
		.select(SOUSCRIPTION_COLUMNS)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------
JOB_COLUMNS = (
	"id, created_at, updated_at, user_id, job_type, status, attempts, max_attempts, "
	"progress, current_step, error_code, error_message, queue_name, pipeline_name, "
	"reserved_quota, consumed_quota, estimated_cost_usd, actual_cost_usd, priority, job_data, result_data"
)


async def create_job_record(
	job_id: str,
	user_id: str,
	job_type: str,
	status: str,
	job_data: Dict[str, Any],
	queue_name: str,
	pipeline_name: str,
	max_attempts: int = 2,
	reserved_quota: float = 0.0,
	estimated_cost_usd: float = 0.0,
	priority: int = 1,
) -> Dict[str, Any]:
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	payload = {
		"id": job_id,
		"user_id": user_id,
		"job_type": job_type,
		"status": status,
		"attempts": 0,
		"max_attempts": max(1, int(max_attempts)),
		"progress": 0,
		"current_step": "created",
		"queue_name": queue_name,
		"pipeline_name": pipeline_name,
		"reserved_quota": float(reserved_quota),
		"consumed_quota": 0.0,
		"estimated_cost_usd": float(estimated_cost_usd),
		"actual_cost_usd": 0.0,
		"priority": max(1, min(3, int(priority or 1))),
		"job_data": job_data or {},
		"result_data": {},
		"created_at": now_iso,
		"updated_at": now_iso,
	}
	response = await client.table(SUPABASE_JOBS_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def update_job_record(job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if not job_id:
		return None
	client = await get_client()
	payload = dict(updates or {})
	payload["updated_at"] = datetime.now(timezone.utc).isoformat()
	response = (
		await client.table(SUPABASE_JOBS_TABLE)
		.update(payload)
		.eq("id", job_id)
		.select(JOB_COLUMNS)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def get_job_record(job_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
	if not job_id:
		return None
	client = await get_client()
	q = (
		client.table(SUPABASE_JOBS_TABLE)
		.select(JOB_COLUMNS)
		.eq("id", job_id)
		.limit(1)
	)
	if user_id:
		q = q.eq("user_id", user_id)
	response = await q.execute()
	rows = response.data or []
	return rows[0] if rows else None


async def append_job_log(job_id: str, level: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
	if not job_id:
		return
	client = await get_client()
	payload = {
		"job_id": job_id,
		"level": (level or "INFO").upper(),
		"message": message or "",
		"metadata": metadata or {},
		"created_at": datetime.now(timezone.utc).isoformat(),
	}
	await client.table(SUPABASE_JOB_LOGS_TABLE).insert(payload).execute()


async def list_job_logs(job_id: str, limit: int = 300) -> List[Dict[str, Any]]:
	if not job_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_JOB_LOGS_TABLE)
		.select("id, job_id, level, message, metadata, created_at")
		.eq("job_id", job_id)
		.order("created_at", desc=False)
		.limit(min(max(limit, 1), 1000))
		.execute()
	)
	return response.data or []


async def list_recoverable_jobs(queue_name: str, statuses: Optional[List[str]] = None, limit: int = 200) -> List[Dict[str, Any]]:
	client = await get_client()
	status_values = statuses or ["queued", "processing", "retry_wait"]
	q = (
		client.table(SUPABASE_JOBS_TABLE)
		.select(JOB_COLUMNS)
		.eq("queue_name", queue_name)
		.in_("status", status_values)
		.order("created_at", desc=False)
		.limit(min(max(limit, 1), 1000))
	)
	response = await q.execute()
	return response.data or []


# --------------------------------------------------------------------------
# User Data (credits & storage)
# --------------------------------------------------------------------------

async def get_user_data(user_id: str) -> Optional[Dict[str, Any]]:
	"""Get the credit/storage balance for a user."""
	if not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_USER_DATA_TABLE)
		.select("*")
		.eq("user_id", user_id)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def upsert_user_data_credits(
    user_id: str,
    credit_delta: float,
    storage_delta: float = 0.0,
) -> Dict[str, Any]:
    client = await get_client()
    existing = await get_user_data(user_id)

    if existing:
        new_credit  = int(max(0.0, float(existing.get("credit", 0)) + float(credit_delta)))
        new_storage = float(existing.get("stockage", 0)) + float(storage_delta)
        response = (
            await client.table(SUPABASE_USER_DATA_TABLE)
            .update({
                "credit":     new_credit,
                "stockage":   new_storage,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("user_id", user_id)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else existing
    else:
        payload = {
            "user_id":  user_id,
            "credit":   int(max(0.0, float(credit_delta))),
            "stockage": max(0.0, float(storage_delta)),
        }
        response = await client.table(SUPABASE_USER_DATA_TABLE).insert(payload).execute()
        rows = response.data or []
        return rows[0] if rows else payload


async def set_user_data_balance(
	user_id: str,
	credit: float,
	storage: float,
) -> Dict[str, Any]:
	"""Set absolute credit/storage values for a user balance row."""
	if not user_id:
		return {"user_id": "", "credit": 0.0, "stockage": 0.0}
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	payload = {
		"user_id": user_id,
		"credit": max(0.0, float(credit or 0.0)),
		"stockage": max(0.0, float(storage or 0.0)),
		"updated_at": now_iso,
	}
	existing = await get_user_data(user_id)
	if existing:
		response = (
			await client.table(SUPABASE_USER_DATA_TABLE)
			.update({
				"credit": payload["credit"],
				"stockage": payload["stockage"],
				"updated_at": now_iso,
			})
			.eq("user_id", user_id)
			.execute()
		)
		rows = response.data or []
		return rows[0] if rows else payload

	response = await client.table(SUPABASE_USER_DATA_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def deduct_user_credits(
	user_id: str,
	credits: float,
	storage_delta: float = 0.0,
) -> bool:
	"""Deduct ``credits`` from the user balance.

	Returns ``False`` if the user does not have sufficient credits.
	"""
	client = await get_client()
	existing = await get_user_data(user_id)
	if not existing:
		return False

	current_credits = float(existing.get("credit", 0))
	if current_credits < float(credits):
		return False

	new_credit  = max(0.0, current_credits - float(credits))
	new_storage = float(existing.get("stockage", 0)) + float(storage_delta)

	await (
		client.table(SUPABASE_USER_DATA_TABLE)
		.update({
			"credit":     new_credit,
			"stockage":   new_storage,
			"updated_at": datetime.now(timezone.utc).isoformat(),
		})
		.eq("user_id", user_id)
		.execute()
	)
	return True


async def insert_user_data_history(
    user_id: str,
    credit: float,
    storage: float,
    operation: str,        # 'input' or 'output'
    operation_type: str,   # 'subscription' | 'reels' | 'captions' | 'publications' | 'credit_purchase'
    operation_id: str = "",
) -> Dict[str, Any]:
    """Append an entry to the user credit/storage history table."""
    client = await get_client()
    payload = {
        "user_id":        user_id,
        "credit":         int(credit),      # ✅ colonne integer côté Supabase
        "storage":        float(storage),   # reste float/numeric
        "operation":      operation,
        "operation_type": operation_type,
        "operation_id":   operation_id or "",
    }
    response = await client.table(SUPABASE_USER_DATA_HISTORY_TABLE).insert(payload).execute()
    rows = response.data or []
    return rows[0] if rows else payload


async def get_user_data_history(
	user_id: str,
	page: int = 1,
	page_size: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
	"""Return paginated credit/storage history for a user."""
	if not user_id:
		return [], 0
	client = await get_client()
	page      = max(page, 1)
	page_size = min(max(page_size, 1), 100)
	offset    = (page - 1) * page_size

	response = (
		await client.table(SUPABASE_USER_DATA_HISTORY_TABLE)
		.select("*", count="exact")
		.eq("user_id", user_id)
		.order("created_at", desc=True)
		.range(offset, offset + page_size - 1)
		.execute()
	)
	return response.data or [], response.count or 0



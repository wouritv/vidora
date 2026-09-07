import os
from datetime import datetime, timezone
import calendar
import math
from typing import Any, Dict, List, Optional, Tuple

from supabase import acreate_client, AsyncClient
from supabase.lib.client_options import AsyncClientOptions

import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_REELS_TABLE = os.environ.get("SUPABASE_REELS_TABLE", "reels")
SUPABASE_CAPTIONS_TABLE = os.environ.get("SUPABASE_CAPTIONS_TABLE", "captions")
SUPABASE_PROJECTS_TABLE = os.environ.get("SUPABASE_PROJECTS_TABLE", "projects")
SUPABASE_ABONNEMENTS_TABLE = os.environ.get("SUPABASE_ABONNEMENTS_TABLE", "abonnement")
SUPABASE_SOUSCRIPTION_TABLE = os.environ.get("SUPABASE_SOUSCRIPTION_TABLE", "souscription")
SUPABASE_JOBS_TABLE = os.environ.get("SUPABASE_JOBS_TABLE", "jobs")
SUPABASE_JOB_LOGS_TABLE = os.environ.get("SUPABASE_JOB_LOGS_TABLE", "job_logs")
SUPABASE_USER_DATA_TABLE = os.environ.get("SUPABASE_USER_DATA_TABLE", "user_data")
SUPABASE_USER_DATA_HISTORY_TABLE = os.environ.get("SUPABASE_USER_DATA_HISTORY_TABLE", "user_data_history")
SUPABASE_USER_CREDIT_BANK_TABLE = os.environ.get("SUPABASE_USER_CREDIT_BANK_TABLE", "user_credit_bank")
SUPABASE_TRANSCRIPTIONS_TABLE = os.environ.get("SUPABASE_TRANSCRIPTIONS_TABLE", "transcriptions")
SUPABASE_STYLE_EDIT_VERSIONS_TABLE = os.environ.get("SUPABASE_STYLE_EDIT_VERSIONS_TABLE", "style_edit_versions")
STORAGE_OVERAGE_TOLERANCE_PERCENT = max(0.0, float(os.environ.get("STORAGE_OVERAGE_TOLERANCE_PERCENT", "10") or "10"))


class SupabaseNotConfiguredError(RuntimeError):
	pass


def is_supabase_configured() -> bool:
	return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


# --------------------------------------------------------------------------
# Client singleton (à réutiliser plutôt que d'en recréer un à chaque appel)
# --------------------------------------------------------------------------
_client: Optional[AsyncClient] = None


def _ceil_credit(value: float) -> int:
	return int(max(0, math.ceil(float(value or 0.0))))


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


async def get_reel_by_job_clip(
	job_id: str,
	clip_index: int,
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Look up a reel by (job_id, clip_index). Pass ``user_id`` whenever the
	caller has an authenticated identity available -- it adds a second,
	defense-in-depth ownership filter so this lookup can never return
	another user's reel even if an upstream authorization check were ever
	missing or buggy."""
	client = await get_client()
	q = (
		client.table(SUPABASE_REELS_TABLE)
		.select("*")
		.eq("reel_job_id", job_id)
		.eq("reel_clip_index", clip_index)
		.is_("deleted_at", "null")
	)
	if user_id:
		q = q.eq("reel_user_id", user_id)
	response = (
		await q
		.order("reel_updated_at", desc=True)
		.limit(1)
		.execute()
	)

	rows = response.data
	if not rows:
		return None
	return rows[0]


async def update_reel_media_by_job_clip(
	job_id: str,
	clip_index: int,
	reel_url: str,
	reel_s3_key: Optional[str] = None,
	reel_thumbnail_url: Optional[str] = None,
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Update a reel's media URL by (job_id, clip_index). Pass ``user_id``
	whenever available for a defense-in-depth ownership filter (see
	get_reel_by_job_clip)."""
	if not job_id or clip_index is None or not reel_url:
		return None

	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	payload: Dict[str, Any] = {
		"reel_url": reel_url,
		"reel_updated_at": now_iso,
	}
	if reel_s3_key:
		payload["reel_s3_key"] = reel_s3_key
	if reel_thumbnail_url is not None:
		payload["reel_thumbnail_url"] = reel_thumbnail_url

	q = (
		client.table(SUPABASE_REELS_TABLE)
		.update(payload)
		.eq("reel_job_id", job_id)
		.eq("reel_clip_index", int(clip_index))
		.is_("deleted_at", "null")
	)
	if user_id:
		q = q.eq("reel_user_id", user_id)
	response = await q.execute()
	rows = response.data or []
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
# Projects
# --------------------------------------------------------------------------
async def create_project(
	user_id: str,
	name: str,
	project_type: str,
	source_type: str,
	source_s3_key: str,
	source_size: int,
	description: Optional[str] = None,
	source_url: Optional[str] = None,
	source_duration: Optional[int] = None,
	thumbnail_url: Optional[str] = None,
	status: str = "processing",
) -> Dict[str, Any]:
	"""Create a new project."""
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	payload = {
		"user_id": user_id,
		"name": name,
		"project_type": project_type,
		"source_type": source_type,
		"source_s3_key": source_s3_key,
		"source_size": int(source_size),
		"description": description,
		"source_url": source_url,
		"source_duration": source_duration,
		"thumbnail_url": thumbnail_url,
		"output_count": 0,
		"status": status,
		"created_at": now_iso,
		"updated_at": now_iso,
	}
	response = await client.table(SUPABASE_PROJECTS_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def list_projects(
	user_id: str,
	page: int = 1,
	page_size: int = 20,
	project_type: Optional[str] = None,
	status: Optional[str] = None,
	query: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
	"""List projects for a user with optional filtering."""
	page = max(page, 1)
	page_size = min(max(page_size, 1), 100)
	offset = (page - 1) * page_size

	client = await get_client()
	q = (
		client.table(SUPABASE_PROJECTS_TABLE)
		.select("*", count="exact")
		.eq("user_id", user_id)
		.order("created_at", desc=True)
		.range(offset, offset + page_size - 1)
	)

	if project_type:
		q = q.eq("project_type", project_type)

	if status:
		q = q.eq("status", status)

	if query:
		escaped = query.replace("*", "")
		q = q.or_(f"name.ilike.*{escaped}*,description.ilike.*{escaped}*")

	response = await q.execute()
	return response.data or [], response.count or 0


async def get_project(project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	"""Get a project by ID (user must own it)."""
	client = await get_client()
	response = (
		await client.table(SUPABASE_PROJECTS_TABLE)
		.select("*")
		.eq("id", project_id)
		.eq("user_id", user_id)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def update_project(
	project_id: str,
	user_id: str,
	updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
	"""Update a project (user must own it)."""
	if not project_id:
		return None
	client = await get_client()
	payload = dict(updates or {})
	payload["updated_at"] = datetime.now(timezone.utc).isoformat()
	await (
		client.table(SUPABASE_PROJECTS_TABLE)
		.update(payload)
		.eq("id", project_id)
		.eq("user_id", user_id)
		.execute()
	)
	response = (
		await client.table(SUPABASE_PROJECTS_TABLE)
		.select("*")
		.eq("id", project_id)
		.eq("user_id", user_id)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def update_project_status(
	project_id: str,
	status: str,
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Update project status (completed, failed, or cancelled) and set completed_at if applicable.
	Pass ``user_id`` whenever available for a defense-in-depth ownership filter."""
	if not project_id or status not in ("completed", "failed", "cancelled"):
		return None
	client = await get_client()

	payload = {
		"status": status,
		"updated_at": datetime.now(timezone.utc).isoformat(),
	}

	# Set completed_at when transitioning from processing to terminal state
	if status in ("completed", "failed", "cancelled"):
		payload["completed_at"] = datetime.now(timezone.utc).isoformat()

	q = (
		client.table(SUPABASE_PROJECTS_TABLE)
		.update(payload)
		.eq("id", project_id)
	)
	if user_id:
		q = q.eq("user_id", user_id)
	response = await q.execute()
	rows = response.data or []
	return rows[0] if rows else None


async def soft_delete_project(project_id: str, user_id: str) -> bool:
	"""Hard delete a project and all its contents (reels, captions, files on S3)."""
	client = await get_client()

	# Security: verify ownership BEFORE cascading any deletes. The reels/
	# captions deletes below filter only by project_id (they have no
	# user_id column of their own to check against project ownership), so
	# if we deleted them first and only verified ownership on the final
	# project delete, a caller supplying another user's project_id could
	# have that user's reels/captions deleted even though the project row
	# itself would survive (0 rows affected on the ownership-filtered
	# delete). Verifying first makes the whole operation a no-op for a
	# project the caller doesn't own.
	owned = (
		await client.table(SUPABASE_PROJECTS_TABLE)
		.select("id")
		.eq("id", project_id)
		.eq("user_id", user_id)
		.limit(1)
		.execute()
	)
	if not owned.data:
		return False

	# Delete all reels associated with this project
	await (
		client.table(SUPABASE_REELS_TABLE)
		.delete()
		.eq("project_id", project_id)
		.execute()
	)

	# Delete all captions associated with this project
	await (
		client.table(SUPABASE_CAPTIONS_TABLE)
		.delete()
		.eq("project_id", project_id)
		.execute()
	)

	# Delete the project itself
	response = (
		await client.table(SUPABASE_PROJECTS_TABLE)
		.delete()
		.eq("id", project_id)
		.eq("user_id", user_id)
		.execute()
	)

	return bool(response.data)


async def get_reels_by_project(project_id: str) -> List[Dict[str, Any]]:
	"""Get all reels associated with a project."""
	if not project_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_REELS_TABLE)
		.select("*")
		.eq("project_id", project_id)
		.execute()
	)
	return response.data or []


async def get_captions_by_project(project_id: str) -> List[Dict[str, Any]]:
	"""Get all captions associated with a project."""
	if not project_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_CAPTIONS_TABLE)
		.select("*")
		.eq("project_id", project_id)
		.execute()
	)
	return response.data or []


# --------------------------------------------------------------------------
# IA Captions
# --------------------------------------------------------------------------
CAPTION_COLUMNS = (
	"id, caption_url, caption_thumbnail_url, caption_title, caption_description, "
	"caption_duration, caption_created_at, caption_updated_at, caption_user_id, "
	"caption_status, caption_job_id, caption_clip_index, caption_s3_key, generation_inputs, "
	"input_source_type, input_source_value, billing_details, total_cost_usd, deleted_at, project_id"
)


def caption_status_value(status: Optional[str]) -> str:
	if status in {"en_cours", "termine", "echec"}:
		return status
	return "termine"


async def increment_project_output_count(
	project_id: str,
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Increment the output_count of a project. Pass ``user_id`` whenever
	available for a defense-in-depth ownership filter."""
	if not project_id:
		return None
	client = await get_client()
	q = client.table(SUPABASE_PROJECTS_TABLE).select("*").eq("id", project_id)
	if user_id:
		q = q.eq("user_id", user_id)
	response = await q.limit(1).execute()
	rows = response.data or []
	current = rows[0] if rows else None
	if not current:
		return None
	new_count = (current.get("output_count") or 0) + 1
	update_q = (
		client.table(SUPABASE_PROJECTS_TABLE)
		.update({"output_count": new_count})
		.eq("id", project_id)
	)
	if user_id:
		update_q = update_q.eq("user_id", user_id)
	response = await update_q.execute()
	rows = response.data or []
	return rows[0] if rows else None


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


async def get_caption_by_job_clip(job_id: str, clip_index: int, user_id: str) -> Optional[Dict[str, Any]]:
	client = await get_client()
	response = (
		await client.table(SUPABASE_CAPTIONS_TABLE)
		.select(CAPTION_COLUMNS)
		.eq("caption_job_id", job_id)
		.eq("caption_clip_index", int(clip_index))
		.eq("caption_user_id", user_id)
		.is_("deleted_at", "null")
		.order("caption_updated_at", desc=True)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	if not rows:
		return None
	return rows[0]


async def get_caption_by_job_clip_any(job_id: str, clip_index: int) -> Optional[Dict[str, Any]]:
	"""Internal helper: fetch latest caption row by job/clip regardless of owner."""
	client = await get_client()
	response = (
		await client.table(SUPABASE_CAPTIONS_TABLE)
		.select(CAPTION_COLUMNS)
		.eq("caption_job_id", job_id)
		.eq("caption_clip_index", int(clip_index))
		.is_("deleted_at", "null")
		.order("caption_updated_at", desc=True)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def update_caption(caption_id: str, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if not caption_id:
		return None
	client = await get_client()
	payload = dict(updates or {})
	payload["caption_updated_at"] = datetime.now(timezone.utc).isoformat()
	await (
		client.table(SUPABASE_CAPTIONS_TABLE)
		.update(payload)
		.eq("id", caption_id)
		.eq("caption_user_id", user_id)
		.is_("deleted_at", "null")
		.execute()
	)
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
	return rows[0] if rows else None


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
# Transcriptions cache (transcript + translation cache)
# --------------------------------------------------------------------------
async def get_transcription_by_job_clip(job_id: str, clip_index: int, user_id: str) -> Optional[Dict[str, Any]]:
	if not job_id or not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_TRANSCRIPTIONS_TABLE)
		.select("*")
		.eq("job_id", job_id)
		.eq("clip_index", int(clip_index))
		.eq("user_id", user_id)
		.order("updated_at", desc=True)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def upsert_transcription(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if not row:
		return None
	client = await get_client()
	response = await client.table(SUPABASE_TRANSCRIPTIONS_TABLE).upsert(
		row,
		on_conflict="user_id,job_id,clip_index",
	).execute()
	rows = response.data or []
	return rows[0] if rows else row


async def update_transcription_translations_cache(
	job_id: str,
	clip_index: int,
	user_id: str,
	translations_cache: Dict[str, Any],
	billing_details: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
	if not job_id or not user_id:
		return None
	client = await get_client()
	payload: Dict[str, Any] = {
		"translations_cache": translations_cache or {},
		"updated_at": datetime.now(timezone.utc).isoformat(),
	}
	if billing_details is not None:
		payload["billing_details"] = billing_details
	await (
		client.table(SUPABASE_TRANSCRIPTIONS_TABLE)
		.update(payload)
		.eq("job_id", job_id)
		.eq("clip_index", int(clip_index))
		.eq("user_id", user_id)
		.execute()
	)
	return await get_transcription_by_job_clip(job_id, clip_index, user_id)


# --------------------------------------------------------------------------
# Style edit versions
# --------------------------------------------------------------------------
async def insert_style_edit_version(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if not row:
		return None
	client = await get_client()
	response = await client.table(SUPABASE_STYLE_EDIT_VERSIONS_TABLE).insert(row).execute()
	rows = response.data or []
	return rows[0] if rows else row


async def list_style_edit_versions(job_id: str, clip_index: int, user_id: str) -> List[Dict[str, Any]]:
	if not job_id or not user_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_STYLE_EDIT_VERSIONS_TABLE)
		.select("*")
		.eq("job_id", job_id)
		.eq("clip_index", int(clip_index))
		.eq("user_id", user_id)
		.order("version_number", desc=False)
		.execute()
	)
	return response.data or []


async def delete_style_edit_versions(job_id: str, clip_index: int, user_id: str) -> int:
	if not job_id or not user_id:
		return 0
	client = await get_client()
	response = (
		await client.table(SUPABASE_STYLE_EDIT_VERSIONS_TABLE)
		.delete()
		.eq("job_id", job_id)
		.eq("clip_index", int(clip_index))
		.eq("user_id", user_id)
		.execute()
	)
	rows = response.data or []
	return len(rows)


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
	abonnement: Optional[str],
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


async def update_souscription_row(
	subscription_id: str,
	updates: Dict[str, Any],
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Update one subscription row and return it. Pass ``user_id`` whenever
	available for a defense-in-depth ownership filter (column: ``userid``)."""
	if not subscription_id:
		return None
	client = await get_client()
	q = (
		client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.update(dict(updates or {}))
		.eq("id", subscription_id)
	)
	if user_id:
		q = q.eq("userid", user_id)
	await q.execute()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("id", subscription_id)
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
	"reserved_quota, consumed_quota, estimated_cost_usd, estimated_credit, actual_cost_usd, actual_credit, "
	"actual_storage_gb, cost_breakdown, priority, job_data, result_data"
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
		"estimated_credit": 0.0,
		"actual_cost_usd": 0.0,
		"actual_credit": 0.0,
		"actual_storage_gb": 0.0,
		"cost_breakdown": {},
		"priority": max(1, min(3, int(priority or 1))),
		"job_data": job_data or {},
		"result_data": {},
		"created_at": now_iso,
		"updated_at": now_iso,
	}
	response = await client.table(SUPABASE_JOBS_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def update_job_record(
	job_id: str,
	updates: Dict[str, Any],
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Update a job row. Pass ``user_id`` whenever available for a
	defense-in-depth ownership filter -- without it, any caller with only a
	job_id can rewrite any user's job status/results/cost fields."""
	if not job_id:
		return None
	client = await get_client()
	payload = dict(updates or {})
	payload["updated_at"] = datetime.now(timezone.utc).isoformat()
	q = client.table(SUPABASE_JOBS_TABLE).update(payload).eq("id", job_id)
	if user_id:
		q = q.eq("user_id", user_id)
	await q.execute()
	response = (
		await client.table(SUPABASE_JOBS_TABLE)
		.select(JOB_COLUMNS)
		.eq("id", job_id)
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


ACTIVE_JOB_STATUSES = ("created", "queued", "processing", "retry_wait")


async def count_active_jobs_for_user(user_id: str) -> int:
	"""Count a user's jobs currently in a non-terminal state (created, queued,
	processing, or waiting to retry). Used to cap per-user concurrent job
	submissions so a single account can't flood the queue/disk/S3 storage
	(see security audit finding H7)."""
	if not user_id:
		return 0
	client = await get_client()
	response = (
		await client.table(SUPABASE_JOBS_TABLE)
		.select("id", count="exact")
		.eq("user_id", user_id)
		.in_("status", list(ACTIVE_JOB_STATUSES))
		.execute()
	)
	return int(response.count or 0)


async def get_latest_job_record_by_project(project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	"""Return the latest job row linked to a project for a specific user."""
	if not project_id or not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_JOBS_TABLE)
		.select(JOB_COLUMNS)
		.eq("user_id", user_id)
		.order("created_at", desc=True)
		.limit(300)
		.execute()
	)
	rows = response.data or []
	for row in rows:
		job_data = row.get("job_data") or {}
		if str(job_data.get("project_id") or "") == str(project_id):
			return row
	return None


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
	update_credit_max: bool = False,
	update_stockage_max: bool = False,
	operation_type: str = "credit_recharge",
	operation_id: str = "",
) -> Dict[str, Any]:
	client = await get_client()
	existing = await get_user_data(user_id)

	if existing:
		current_credit = float(existing.get("credit", 0) or 0.0)
		current_storage = float(existing.get("stockage", 0) or 0.0)
		current_credit_max = float(existing.get("credit_max", current_credit) or 0.0)
		current_stockage_max = float(existing.get("stockage_max", max(current_storage, 0.0)) or 0.0)

		logger.info(f"Current user data for {user_id}: credit={current_credit}, stockage={current_storage}, credit_max={current_credit_max}, stockage_max={current_stockage_max}")

		delta_credit = float(credit_delta)
		current_debt = float(existing.get("credit_debt", 0) or 0.0)
		debt_paid = 0.0
		if delta_credit > 0 and current_debt > 0:
			debt_paid = min(current_debt, delta_credit)
			delta_credit -= debt_paid
			current_debt = max(0.0, current_debt - debt_paid)

		new_credit = float(_ceil_credit(current_credit + delta_credit))
		new_storage = float(current_storage + float(storage_delta))
		new_credit_max = max(0.0, current_credit_max)
		new_stockage_max = max(0.0, current_stockage_max)

		if update_credit_max:
			# Credit top-ups and subscription allocations can redefine the user's ceiling.
			new_credit_max = float(_ceil_credit(current_credit_max + float(credit_delta)))
		if update_stockage_max:
			new_stockage_max = float(current_stockage_max + float(storage_delta))

		if new_credit > new_credit_max:
			new_credit_max = float(new_credit)

		logger.info(f"Updating user data for {user_id}: credit={new_credit}, stockage={new_storage}, credit_max={new_credit_max}, stockage_max={new_stockage_max}")

		response = (
			await client.table(SUPABASE_USER_DATA_TABLE)
			.update({
				"credit":     new_credit,
				"credit_debt": current_debt,
				"stockage":   new_storage,
				"credit_max": new_credit_max,
				"stockage_max": new_stockage_max,
				"updated_at": datetime.now(timezone.utc).isoformat(),
			})
			.eq("user_id", user_id)
			.execute()
		)
		rows = response.data or []
		if debt_paid > 0:
			await insert_user_credit_bank_entry(
				user_id=user_id,
				direction="debt_payment",
				amount=debt_paid,
				debt_balance_after=current_debt,
				operation_type=operation_type,
				operation_id=operation_id,
				metadata={"source": "upsert_user_data_credits"},
			)
		return rows[0] if rows else existing
	else:
		initial_credit = _ceil_credit(credit_delta)
		initial_storage = max(0.0, float(storage_delta))
		payload = {
			"user_id":  user_id,
			"credit":   initial_credit,
			"credit_debt": 0.0,
			"stockage": initial_storage,
			"credit_max": float(initial_credit),
			"stockage_max": float(initial_storage),
		}
		response = await client.table(SUPABASE_USER_DATA_TABLE).insert(payload).execute()
		rows = response.data or []
		return rows[0] if rows else payload


async def set_user_data_balance(
	user_id: str,
	credit: float,
	storage: float,
	credit_max: Optional[float] = None,
	storage_max: Optional[float] = None,
	operation_type: str = "subscription",
	operation_id: str = "",
) -> Dict[str, Any]:
	"""Set absolute credit/storage values for a user balance row."""
	if not user_id:
		return {"user_id": "", "credit": 0.0, "stockage": 0.0, "credit_max": 0.0, "stockage_max": 0.0}
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	clamped_credit = _ceil_credit(credit)
	clamped_storage = float(storage or 0.0)
	payload = {
		"user_id": user_id,
		"credit": clamped_credit,
		"credit_debt": 0.0,
		"stockage": clamped_storage,
		"credit_max": _ceil_credit(credit_max if credit_max is not None else clamped_credit),
		"stockage_max": max(0.0, float(storage_max if storage_max is not None else max(clamped_storage, 0.0))),
		"updated_at": now_iso,
	}
	existing = await get_user_data(user_id)
	if existing:
		existing_debt = float(existing.get("credit_debt", 0) or 0.0)
		debt_paid = min(existing_debt, float(clamped_credit))
		net_credit = max(0.0, float(clamped_credit) - debt_paid)
		remaining_debt = max(0.0, existing_debt - debt_paid)
		next_credit_max = payload["credit_max"]
		next_storage_max = payload["stockage_max"]
		if credit_max is None:
			next_credit_max = _ceil_credit(existing.get("credit_max", existing.get("credit", 0.0)) or 0.0)
		if storage_max is None:
			next_storage_max = max(0.0, float(existing.get("stockage_max", max(existing.get("stockage", 0.0), 0.0)) or 0.0))
		if clamped_credit > next_credit_max:
			next_credit_max = _ceil_credit(net_credit)
		response = (
			await client.table(SUPABASE_USER_DATA_TABLE)
			.update({
				"credit": net_credit,
				"credit_debt": remaining_debt,
				"stockage": payload["stockage"],
				"credit_max": next_credit_max,
				"stockage_max": next_storage_max,
				"updated_at": now_iso,
			})
			.eq("user_id", user_id)
			.execute()
		)
		rows = response.data or []
		if debt_paid > 0:
			await insert_user_credit_bank_entry(
				user_id=user_id,
				direction="debt_payment",
				amount=debt_paid,
				debt_balance_after=remaining_debt,
				operation_type=operation_type,
				operation_id=operation_id,
				metadata={"source": "set_user_data_balance"},
			)
		return rows[0] if rows else payload

	response = await client.table(SUPABASE_USER_DATA_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


MAX_CREDIT_DEBT = max(0.0, float(os.environ.get("MAX_CREDIT_DEBT", "0") or "0"))


async def deduct_user_credits(
	user_id: str,
	credits: float,
	storage_delta: float = 0.0,
	max_attempts: int = 5,
) -> bool:
	"""Deduct ``credits`` from the user balance.

	Returns ``False`` if the user does not have sufficient credits/storage
	headroom, or if the account's debt would exceed MAX_CREDIT_DEBT.

	Security: this uses optimistic concurrency (a conditional UPDATE that
	only applies if credit/stockage still match what we just read, retried
	on conflict) so two concurrent operations can never both silently debit
	against the same stale balance -- one of them detects the conflict and
	recomputes against the fresh row instead of the update being lost. It
	also enforces a hard ceiling on ``credit_debt`` instead of allowing it to
	grow without bound while the account keeps consuming paid processing
	(see security audit finding C7).
	"""
	client = await get_client()

	for _ in range(max_attempts):
		existing = await get_user_data(user_id)
		if not existing:
			return False

		current_credits = float(existing.get("credit", 0) or 0.0)
		current_debt = float(existing.get("credit_debt", 0) or 0.0)
		debit_credits = max(0.0, float(credits or 0.0))

		new_credit = current_credits - debit_credits
		debt_delta = 0.0
		if new_credit < 0:
			debt_delta = abs(new_credit)
			new_credit = 0.0

		new_debt = current_debt + debt_delta
		if new_debt > MAX_CREDIT_DEBT:
			return False

		current_storage = float(existing.get("stockage", 0) or 0.0)
		new_storage = current_storage + float(storage_delta)
		storage_max = float(existing.get("stockage_max", max(current_storage, 0.0)) or 0.0)
		overage_limit = (storage_max * STORAGE_OVERAGE_TOLERANCE_PERCENT) / 100.0
		if new_storage < -overage_limit:
			return False

		response = await (
			client.table(SUPABASE_USER_DATA_TABLE)
			.update({
				"credit":     new_credit,
				"credit_debt": new_debt,
				"stockage":   new_storage,
				"updated_at": datetime.now(timezone.utc).isoformat(),
			})
			.eq("user_id", user_id)
			.eq("credit", current_credits)
			.eq("stockage", current_storage)
			.execute()
		)

		if not response.data:
			# Another concurrent request changed the balance between our read
			# and this write -- retry against the fresh balance rather than
			# silently dropping this deduction (classic TOCTOU double-spend).
			continue

		if debt_delta > 0:
			await insert_user_credit_bank_entry(
				user_id=user_id,
				direction="debt_increase",
				amount=debt_delta,
				debt_balance_after=new_debt,
				operation_type="operation",
				operation_id="",
				metadata={"requested_credit_debit": debit_credits},
			)
		return True

	return False


async def refund_user_credits(
	user_id: str,
	credits: float,
	storage_delta: float = 0.0,
	max_attempts: int = 5,
) -> bool:
	"""Add ``credits`` back to a user's balance (releasing a reservation made
	via deduct_user_credits, e.g. on job failure/cancellation, or settling a
	completed job whose actual cost was lower than its reservation).

	Existing debt is paid down first, same as set_user_data_balance's
	top-up logic, before any surplus is added to the spendable balance.
	Uses the same optimistic-concurrency retry as deduct_user_credits so a
	concurrent refund/debit can never be silently lost.
	"""
	if credits <= 0 and storage_delta == 0:
		return True
	client = await get_client()

	for _ in range(max_attempts):
		existing = await get_user_data(user_id)
		if not existing:
			return False

		current_credits = float(existing.get("credit", 0) or 0.0)
		current_debt = float(existing.get("credit_debt", 0) or 0.0)
		credit_amount = max(0.0, float(credits or 0.0))

		debt_paid = min(current_debt, credit_amount)
		new_debt = current_debt - debt_paid
		new_credit = current_credits + (credit_amount - debt_paid)

		current_storage = float(existing.get("stockage", 0) or 0.0)
		new_storage = current_storage + float(storage_delta)

		response = await (
			client.table(SUPABASE_USER_DATA_TABLE)
			.update({
				"credit":     new_credit,
				"credit_debt": new_debt,
				"stockage":   new_storage,
				"updated_at": datetime.now(timezone.utc).isoformat(),
			})
			.eq("user_id", user_id)
			.eq("credit", current_credits)
			.eq("stockage", current_storage)
			.execute()
		)

		if not response.data:
			continue

		if debt_paid > 0:
			await insert_user_credit_bank_entry(
				user_id=user_id,
				direction="debt_payment",
				amount=debt_paid,
				debt_balance_after=new_debt,
				operation_type="refund",
				operation_id="",
				metadata={"refunded_credit": credit_amount},
			)
		return True

	return False


async def insert_user_credit_bank_entry(
	user_id: str,
	direction: str,
	amount: float,
	debt_balance_after: float,
	operation_type: str,
	operation_id: str = "",
	metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
	"""Track credit debt creation/repayment events."""
	client = await get_client()
	payload = {
		"user_id": user_id,
		"direction": (direction or "").strip().lower(),
		"amount": float(max(0.0, amount or 0.0)),
		"debt_balance_after": float(max(0.0, debt_balance_after or 0.0)),
		"operation_type": operation_type,
		"operation_id": operation_id or "",
		"metadata": metadata or {},
	}
	response = await client.table(SUPABASE_USER_CREDIT_BANK_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


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
	rounded_credit = _ceil_credit(credit)
	payload = {
		"user_id":        user_id,
		"credit":         rounded_credit,
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



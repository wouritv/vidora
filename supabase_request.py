import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from supabase import acreate_client, AsyncClient
from supabase.lib.client_options import AsyncClientOptions

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_REELS_TABLE = os.environ.get("SUPABASE_REELS_TABLE", "reels")
SUPABASE_ABONNEMENTS_TABLE = os.environ.get("SUPABASE_ABONNEMENTS_TABLE", "abonnement")
SUPABASE_SOUSCRIPTION_TABLE = os.environ.get("SUPABASE_SOUSCRIPTION_TABLE", "souscription")


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
# Abonnements
# --------------------------------------------------------------------------
ABONNEMENT_COLUMNS = "id, created_at, price, name, features, icon, retention, reels, captions, credit, color, highlighted, ordre"
SOUSCRIPTION_COLUMNS = "id, created_at, userid, abonnement, payment_mode, payment_amount, payment_reference, payment_start_date, payment_end_date, payment_status, payment_comment"

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
		.eq("uuid", abonnement_uuid)
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
        .gte("payment_end_date", now_iso)
        .limit(1)
        .execute()
    )

    rows = response.data
    if not rows:
        return None
    return rows[0]

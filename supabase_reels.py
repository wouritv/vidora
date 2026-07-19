import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_REELS_TABLE = os.environ.get("SUPABASE_REELS_TABLE", "reels")


class SupabaseNotConfiguredError(RuntimeError):
	pass


def is_supabase_reels_configured() -> bool:
	return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _headers(prefer: Optional[str] = None) -> Dict[str, str]:
	if not is_supabase_reels_configured():
		raise SupabaseNotConfiguredError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

	headers = {
		"apikey": SUPABASE_SERVICE_ROLE_KEY,
		"Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
		"Content-Type": "application/json",
	}
	if prefer:
		headers["Prefer"] = prefer
	return headers


def _extract_total_from_content_range(content_range: Optional[str]) -> int:
	if not content_range:
		return 0
	match = re.match(r"^\d+-\d+\/(\d+|\*)$", content_range)
	if not match:
		return 0
	total = match.group(1)
	if total == "*":
		return 0
	return int(total)


async def insert_reels(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	if not rows:
		return []

	endpoint = f"{SUPABASE_URL}/rest/v1/{SUPABASE_REELS_TABLE}"
	async with httpx.AsyncClient(timeout=20.0) as client:
		response = await client.post(
			endpoint,
			headers=_headers(prefer="return=representation"),
			json=rows,
		)
	response.raise_for_status()
	return response.json()


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

	endpoint = f"{SUPABASE_URL}/rest/v1/{SUPABASE_REELS_TABLE}"
	params: Dict[str, Any] = {
		"select": "*",
		"reel_user_id": f"eq.{user_id}",
		"deleted_at": "is.null",
		"order": "reel_created_at.desc",
		"limit": str(page_size),
		"offset": str(offset),
	}

	if status:
		params["reel_status"] = f"eq.{status}"

	if query:
		escaped = query.replace("*", "")
		params["or"] = f"(reel_title.ilike.*{escaped}*,reel_description.ilike.*{escaped}*)"

	async with httpx.AsyncClient(timeout=20.0) as client:
		response = await client.get(
			endpoint,
			headers=_headers(prefer="count=exact"),
			params=params,
		)
	response.raise_for_status()

	data = response.json()
	total = _extract_total_from_content_range(response.headers.get("content-range"))
	return data, total


async def get_reel(reel_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	endpoint = f"{SUPABASE_URL}/rest/v1/{SUPABASE_REELS_TABLE}"
	params = {
		"select": "*",
		"id": f"eq.{reel_id}",
		"reel_user_id": f"eq.{user_id}",
		"deleted_at": "is.null",
		"limit": "1",
	}

	async with httpx.AsyncClient(timeout=20.0) as client:
		response = await client.get(endpoint, headers=_headers(), params=params)
	response.raise_for_status()

	rows = response.json()
	if not rows:
		return None
	return rows[0]


async def soft_delete_reel(reel_id: str, user_id: str) -> bool:
	endpoint = f"{SUPABASE_URL}/rest/v1/{SUPABASE_REELS_TABLE}"
	params = {
		"id": f"eq.{reel_id}",
		"reel_user_id": f"eq.{user_id}",
		"deleted_at": "is.null",
		"select": "id",
	}
	now_iso = datetime.now(timezone.utc).isoformat()

	async with httpx.AsyncClient(timeout=20.0) as client:
		response = await client.patch(
			endpoint,
			headers=_headers(prefer="return=representation"),
			params=params,
			json={"deleted_at": now_iso, "reel_updated_at": now_iso},
		)

	if response.status_code >= 400:
		response.raise_for_status()
	deleted = response.json()
	return bool(deleted)


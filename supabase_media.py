import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


class SupabaseNotConfiguredError(RuntimeError):
    pass


@dataclass(frozen=True)
class MediaTableConfig:
    table_name: str
    media_prefix: str
    title_field: str
    description_field: str
    duration_field: str
    created_field: str
    updated_field: str
    user_field: str
    status_field: str
    url_field: str
    thumbnail_field: str
    s3_key_field: str
    inputs_field: str = "generation_inputs"
    deleted_field: str = "deleted_at"


MEDIA_TABLES: Dict[str, MediaTableConfig] = {
    "reels": MediaTableConfig(
        table_name="reels",
        media_prefix="reel",
        title_field="reel_title",
        description_field="reel_description",
        duration_field="reel_duration",
        created_field="reel_created_at",
        updated_field="reel_updated_at",
        user_field="reel_user_id",
        status_field="reel_status",
        url_field="reel_url",
        thumbnail_field="reel_thumbnail_url",
        s3_key_field="reel_s3_key",
    ),
    "ia_short": MediaTableConfig(
        table_name="ia_short",
        media_prefix="reel",
        title_field="reel_title",
        description_field="reel_description",
        duration_field="reel_duration",
        created_field="reel_created_at",
        updated_field="reel_updated_at",
        user_field="reel_user_id",
        status_field="reel_status",
        url_field="reel_url",
        thumbnail_field="reel_thumbnail_url",
        s3_key_field="reel_s3_key",
    ),
    "youtube_resume": MediaTableConfig(
        table_name="youtube_resume",
        media_prefix="resume",
        title_field="resume_title",
        description_field="resume_description",
        duration_field="resume_duration",
        created_field="resume_created_at",
        updated_field="resume_updated_at",
        user_field="resume_user_id",
        status_field="resume_status",
        url_field="resume_url",
        thumbnail_field="resume_thumbnail_url",
        s3_key_field="resume_s3_key",
    ),
    "ia_caption": MediaTableConfig(
        table_name="ia_caption",
        media_prefix="caption",
        title_field="caption_title",
        description_field="caption_description",
        duration_field="caption_duration",
        created_field="caption_created_at",
        updated_field="caption_updated_at",
        user_field="caption_user_id",
        status_field="caption_status",
        url_field="caption_url",
        thumbnail_field="caption_thumbnail_url",
        s3_key_field="caption_s3_key",
    ),
}

NULL_FILTER = "is.null"


def is_supabase_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _headers(prefer: Optional[str] = None) -> Dict[str, str]:
    if not is_supabase_configured():
        raise SupabaseNotConfiguredError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _table_config(table_name: str) -> MediaTableConfig:
    if table_name not in MEDIA_TABLES:
        raise ValueError(f"Unknown media table: {table_name}")
    return MEDIA_TABLES[table_name]


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


def _query_key(config: MediaTableConfig, suffix: str) -> str:
    return f"{config.media_prefix}_{suffix}"


def _build_row_query(
    config: MediaTableConfig,
    user_id: str,
    page: int,
    page_size: int,
    status: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size

    params: Dict[str, Any] = {
        "select": "*",
        config.user_field: f"eq.{user_id}",
        config.deleted_field: NULL_FILTER,
        "order": f"{config.created_field}.desc",
        "limit": str(page_size),
        "offset": str(offset),
    }

    if status:
        params[config.status_field] = f"eq.{status}"

    if query:
        escaped = query.replace("*", "")
        params["or"] = f"({config.title_field}.ilike.*{escaped}*,{config.description_field}.ilike.*{escaped}*)"

    return params


async def insert_rows(table_name: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return []

    config = _table_config(table_name)
    endpoint = f"{SUPABASE_URL}/rest/v1/{config.table_name}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            endpoint,
            headers=_headers(prefer="return=representation"),
            json=rows,
        )
    response.raise_for_status()
    return response.json()


async def list_rows(
    table_name: str,
    user_id: str,
    page: int,
    page_size: int,
    status: Optional[str] = None,
    query: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    config = _table_config(table_name)
    endpoint = f"{SUPABASE_URL}/rest/v1/{config.table_name}"
    params = _build_row_query(config, user_id=user_id, page=page, page_size=page_size, status=status, query=query)

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


async def get_row(table_name: str, row_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    config = _table_config(table_name)
    endpoint = f"{SUPABASE_URL}/rest/v1/{config.table_name}"
    params = {
        "select": "*",
        "id": f"eq.{row_id}",
        config.user_field: f"eq.{user_id}",
        config.deleted_field: NULL_FILTER,
        "limit": "1",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(endpoint, headers=_headers(), params=params)
    response.raise_for_status()

    rows = response.json()
    if not rows:
        return None
    return rows[0]


async def soft_delete_row(table_name: str, row_id: str, user_id: str) -> bool:
    config = _table_config(table_name)
    endpoint = f"{SUPABASE_URL}/rest/v1/{config.table_name}"
    params = {
        "id": f"eq.{row_id}",
        config.user_field: f"eq.{user_id}",
        config.deleted_field: NULL_FILTER,
        "select": "id",
    }
    now_iso = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.patch(
            endpoint,
            headers=_headers(prefer="return=representation"),
            params=params,
            json={config.deleted_field: now_iso, config.updated_field: now_iso},
        )

    if response.status_code >= 400:
        response.raise_for_status()
    deleted = response.json()
    return bool(deleted)


async def save_media_rows(table_name: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return await insert_rows(table_name, rows)


def media_status_value(status: Optional[str]) -> str:
    if status in {"en_cours", "termine", "echec"}:
        return status
    return "termine"



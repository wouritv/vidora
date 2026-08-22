import os
import uuid
import subprocess
import threading
import json
import hashlib
import base64
import shutil
import glob
import time
import asyncio
import itertools
import secrets
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from typing import Dict, Optional, List, Any
from contextlib import asynccontextmanager
from urllib.parse import urlparse, unquote, urlencode
from urllib.request import Request as UrlRequest, urlopen
from starlette.background import BackgroundTask
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Header, BackgroundTasks, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from pydantic import BaseModel
try:
    import stripe
except ImportError:  # pragma: no cover - optional at import time
    stripe = None
from s3_uploader import (
    upload_file_to_s3,
    generate_presigned_url,
)
from supabase_request import (
    insert_reels as supabase_insert_reels,
    list_reels as supabase_list_reels,
    get_reel as supabase_get_reel,
    get_reel_by_job_clip as supabase_get_reel_by_job_clip,
    soft_delete_reel as supabase_soft_delete_reel,
    is_supabase_configured,
    list_abonnements as supabase_list_abonnements,
    get_user_abonnement,
    get_abonnement as supabase_get_abonnement,
    insert_souscription as supabase_insert_souscription,
    get_souscription_by_reference as supabase_get_souscription_by_reference,
    get_client as supabase_get_client,
    get_user_data as supabase_get_user_data,
    upsert_user_data_credits as supabase_upsert_user_data_credits,
    set_user_data_balance as supabase_set_user_data_balance,
    deduct_user_credits as supabase_deduct_user_credits,
    insert_user_data_history as supabase_insert_user_data_history,
    get_user_data_history as supabase_get_user_data_history,
    get_latest_user_paid_subscription as supabase_get_latest_user_paid_subscription,
    update_souscription_row as supabase_update_souscription_row,
    list_user_souscriptions as supabase_list_user_souscriptions,
    update_job_record as supabase_update_job_record,
)
from billing import (
    usd_to_credits,
    usd_to_final_credits,
    calculate_credits_for_operation,
    estimate_reel_cost_usd,
    estimate_caption_cost_usd,
    estimate_publication_cost_usd,
    DEFAULT_REEL_CREDITS,
    DEFAULT_CAPTION_CREDITS,
    DEFAULT_PUBLICATION_CREDITS,
    CREDIT_UNIT_PRICE_BY_DOLLAR,
)
from job_manager import JobManager, JobType, calc_elapsed_seconds
from pipelines import ReelProcessingPipeline
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "no-reply@tonsite.com")
SENDGRID_PAYMENT_CONFIRMATION_TEMPLATE_ID = os.getenv("SENDGRID_PAYMENT_CONFIRMATION_TEMPLATE_ID")

load_dotenv()

# Constants
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configuration
# Default to 1 if not set, but user can set higher for powerful servers
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "5"))
QUEUE_WORKER_COUNT = int(os.environ.get("QUEUE_WORKER_COUNT", "1"))
REEL_JOB_MAX_ATTEMPTS = int(os.environ.get("REEL_JOB_MAX_ATTEMPTS", "2"))
REEL_JOB_RETRY_DELAY_SECONDS = int(os.environ.get("REEL_JOB_RETRY_DELAY_SECONDS", "15"))
MAX_FILE_SIZE_MB = 2048  # 2GB limit
REEL_MAX_DURATION_MINUTES = float(os.environ.get("REEL_MAX_DURATION", "180"))
REEL_MAX_STORAGE_GB = float(os.environ.get("REEL_MAX_STORAGE", "15"))
VIREEL_VIDEO_FORMAT = os.environ.get("VIREEL_VIDEO_FORMAT", "mp4,mov,avi")
JOB_RETENTION_SECONDS = 3600  # 1 hour retention
OUTPUT_SWEEP_INTERVAL_SECONDS = int(os.environ.get("OUTPUT_SWEEP_INTERVAL_SECONDS", str(6 * 3600)))
OUTPUT_SWEEP_MIN_AGE_SECONDS = int(os.environ.get("OUTPUT_SWEEP_MIN_AGE_SECONDS", "1800"))
DISABLE_YOUTUBE_URL = os.environ.get("DISABLE_YOUTUBE_URL", "false").lower() in ("1", "true", "yes")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = os.environ.get("STRIPE_CURRENCY", "eur").lower()
STRIPE_SUCCESS_URL = os.environ.get("STRIPE_SUCCESS_URL", "")
STRIPE_CANCEL_URL = os.environ.get("STRIPE_CANCEL_URL", "")
STORAGE_RETENTION_PERIODE_DAYS = max(0, int(os.environ.get("STORAGE_RETENTION_PERIODE", "7") or "7"))
STORAGE_OVERAGE_TOLERANCE_PERCENT = max(0.0, float(os.environ.get("STORAGE_OVERAGE_TOLERANCE_PERCENT", "10") or "10"))
PLATFORM_CONFIG = {
    "linkedin": {
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
        "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET"),
        "scopes": ["w_member_social", "openid", "profile","email"],
    },
    "facebook": {
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "client_id": os.getenv("FACEBOOK_CLIENT_ID"),
        "client_secret": os.getenv("FACEBOOK_CLIENT_SECRET"),
        "scopes": ["pages_manage_posts", "pages_read_engagement"],
    },
    "instagram": {
        "auth_url": "https://www.instagram.com/oauth/authorize",
        "token_url": "https://api.instagram.com/oauth/access_token",
        "long_lived_token_url": "https://graph.instagram.com/access_token",
        "client_id": os.getenv("INSTAGRAM_APP_ID"),
        "client_secret": os.getenv("INSTAGRAM_APP_SECRET"),
        "scopes": [
            "instagram_business_basic",
            "instagram_business_manage_messages",
            "instagram_business_manage_comments",
            "instagram_business_content_publish",
            "instagram_business_manage_insights",
        ],
    },
    "youtube": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "client_id": os.getenv("YOUTUBE_CLIENT_ID"),
        "client_secret": os.getenv("YOUTUBE_CLIENT_SECRET"),
        "scopes": ["https://www.googleapis.com/auth/youtube.upload","https://www.googleapis.com/auth/youtube.readonly"],
    },
    "tiktok": {
        "auth_url": "https://www.tiktok.com/v2/auth/authorize",
        "token_url": "https://open.tiktokapis.com/v2/oauth/token/",
        "client_id": os.getenv("TIKTOK_CLIENT_KEY"),
        "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
        "scopes": ["video.upload", "user.info.basic"],
    },
}

if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Application State
job_queue: asyncio.PriorityQueue[tuple[int, int, str]] = asyncio.PriorityQueue()
job_queue_seq = itertools.count()
JOB_PRIORITY_MIN = 1
JOB_PRIORITY_MAX = 3
DEFAULT_JOB_PRIORITY = 1
jobs: Dict[str, Dict] = {}
thumbnail_sessions: Dict[str, Dict] = {}
publish_jobs: Dict[str, Dict] = {}  # {publish_id: {status, result, error}}
# Semester to limit concurrency to MAX_CONCURRENT_JOBS
concurrency_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
reel_job_manager = JobManager(queue_name="reels")
running_reel_jobs: Dict[str, Dict[str, Any]] = {}
running_reel_jobs_lock = asyncio.Lock()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY manquant dans l'environnement")

_oauth_serializer = URLSafeTimedSerializer(SECRET_KEY)

def _relocate_root_job_artifacts(job_id: str, job_output_dir: str) -> bool:
    """
    Backward-compat rescue:
    If main.py accidentally wrote metadata/clips into OUTPUT_DIR root (e.g. output/<jobid>_...),
    move them into output/<job_id>/ so the API can find and serve them.
    """
    try:
        os.makedirs(job_output_dir, exist_ok=True)
        root = OUTPUT_DIR
        pattern = os.path.join(root, f"{job_id}_*_metadata.json")
        meta_candidates = sorted(glob.glob(pattern), key=lambda p: os.path.getmtime(p), reverse=True)
        if not meta_candidates:
            return False

        # Move the newest metadata and its associated clips.
        metadata_path = meta_candidates[0]
        base_name = os.path.basename(metadata_path).replace("_metadata.json", "")

        # Move metadata
        dest_metadata = os.path.join(job_output_dir, os.path.basename(metadata_path))
        if os.path.abspath(metadata_path) != os.path.abspath(dest_metadata):
            shutil.move(metadata_path, dest_metadata)

        # Move any clips that match the same base_name into the job folder
        clip_pattern = os.path.join(root, f"{base_name}_clip_*.mp4")
        for clip_path in glob.glob(clip_pattern):
            dest_clip = os.path.join(job_output_dir, os.path.basename(clip_path))
            if os.path.abspath(clip_path) != os.path.abspath(dest_clip):
                shutil.move(clip_path, dest_clip)

        # Also move any temp_ clips that might remain
        temp_clip_pattern = os.path.join(root, f"temp_{base_name}_clip_*.mp4")
        for clip_path in glob.glob(temp_clip_pattern):
            dest_clip = os.path.join(job_output_dir, os.path.basename(clip_path))
            if os.path.abspath(clip_path) != os.path.abspath(dest_clip):
                shutil.move(clip_path, dest_clip)

        return True
    except Exception:
        return False


def _cleanup_directory(path: str) -> None:
    """Best-effort recursive cleanup for ephemeral processing artifacts."""
    try:
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def _resolve_job_metadata_path(job_id: str) -> Optional[str]:
    """Find metadata JSON for a job, including legacy root-output layouts."""
    output_dir = os.path.join(OUTPUT_DIR, job_id)
    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
    if json_files:
        return json_files[0]

    # Backward-compat rescue for artifacts emitted into OUTPUT_DIR root.
    if _relocate_root_job_artifacts(job_id, output_dir):
        json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
        if json_files:
            return json_files[0]

    # Last-chance fallback: read directly from root if relocation could not run.
    root_candidates = sorted(
        glob.glob(os.path.join(OUTPUT_DIR, f"{job_id}_*_metadata.json")),
        key=lambda path: os.path.getmtime(path),
        reverse=True,
    )
    if root_candidates:
        return root_candidates[0]

    return None


def _estimate_transcript_duration_seconds(transcript: Dict[str, Any]) -> float:
    segments = (transcript or {}).get("segments") or []
    max_end = 0.0
    for seg in segments:
        try:
            max_end = max(max_end, float(seg.get("end", 0) or 0))
        except Exception:
            continue

    try:
        meta_seconds = float(((transcript or {}).get("meta") or {}).get("audio_seconds", 0) or 0)
    except Exception:
        meta_seconds = 0.0

    return max(max_end, meta_seconds)


async def get_user_id_header(request: Request) -> str:
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    return user_id

def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Accept both native ISO and trailing Z formats.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clamp_job_priority(value: Any) -> int:
    try:
        raw = int(value)
    except Exception:
        raw = DEFAULT_JOB_PRIORITY
    return max(JOB_PRIORITY_MIN, min(JOB_PRIORITY_MAX, raw))


async def _resolve_user_job_priority(user_id: str) -> int:
    if not user_id or not is_supabase_configured():
        return DEFAULT_JOB_PRIORITY
    try:
        active = await get_user_abonnement(user_id)
        if not active:
            return DEFAULT_JOB_PRIORITY
        return _clamp_job_priority(active.get("priorite"))
    except Exception:
        return DEFAULT_JOB_PRIORITY


async def _maybe_preempt_lower_priority_running_job(incoming_priority: int, incoming_job_id: str) -> None:
    incoming_priority = _clamp_job_priority(incoming_priority)
    async with running_reel_jobs_lock:
        if not running_reel_jobs:
            return

        if len(running_reel_jobs) < MAX_CONCURRENT_JOBS:
            return

        candidate_job_id = ""
        candidate_priority = JOB_PRIORITY_MAX
        candidate_started_at = float("inf")
        for running_job_id, ctx in running_reel_jobs.items():
            running_priority = _clamp_job_priority(ctx.get("priority", DEFAULT_JOB_PRIORITY))
            started_at = float(ctx.get("started_at", 0.0) or 0.0)
            if (
                running_priority < candidate_priority
                or (running_priority == candidate_priority and started_at < candidate_started_at)
            ):
                candidate_job_id = running_job_id
                candidate_priority = running_priority
                candidate_started_at = started_at

        if not candidate_job_id or incoming_priority <= candidate_priority:
            return

        ctx = running_reel_jobs.get(candidate_job_id) or {}
        ctx["preempt_requested"] = True
        process = ctx.get("process")

        if candidate_job_id in jobs:
            jobs[candidate_job_id]["logs"].append(
                f"Preemption requested by higher-priority job {incoming_job_id} (priority {incoming_priority})."
            )

        if process and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass


async def enqueue_reel_job(job_id: str, priority: Optional[int] = None) -> None:
    runtime_job = reel_job_manager.runtime_jobs.get(job_id) or jobs.get(job_id) or {}
    final_priority = _clamp_job_priority(
        priority if priority is not None else runtime_job.get("priority", DEFAULT_JOB_PRIORITY)
    )
    runtime_job["priority"] = final_priority
    if job_id in reel_job_manager.runtime_jobs:
        reel_job_manager.runtime_jobs[job_id]["priority"] = final_priority
    if job_id in jobs:
        jobs[job_id]["priority"] = final_priority

    await _maybe_preempt_lower_priority_running_job(final_priority, job_id)
    await job_queue.put((-final_priority, next(job_queue_seq), job_id))


async def _schedule_reel_retry(job_id: str, delay_seconds: int) -> None:
    await asyncio.sleep(max(0, int(delay_seconds)))
    await reel_job_manager.retry_job(job_id)
    runtime = reel_job_manager.runtime_jobs.get(job_id) or jobs.get(job_id) or {}
    await enqueue_reel_job(job_id, priority=runtime.get("priority", DEFAULT_JOB_PRIORITY))


async def _enforce_subscription_retention_policy(user_id: str) -> Dict[str, Any]:
    """Apply subscription retention policy and zero balances after retention deadline."""
    if not user_id or not is_supabase_configured():
        return {"state": "skipped"}

    active = await get_user_abonnement(user_id)
    if active:
        return {"state": "active", "subscription": active}

    latest = await supabase_get_latest_user_paid_subscription(user_id)
    if not latest:
        return {"state": "no_subscription"}

    end_date = _parse_iso_datetime(latest.get("payment_end_date"))
    if not end_date:
        return {"state": "no_subscription_end", "subscription": latest}

    now_utc = datetime.now(timezone.utc)
    retention_deadline = end_date + timedelta(days=STORAGE_RETENTION_PERIODE_DAYS)

    if latest.get("id") and not latest.get("retention_deadline_at"):
        await supabase_update_souscription_row(
            str(latest.get("id")),
            {"retention_deadline_at": retention_deadline.isoformat()},
        )

    if now_utc <= retention_deadline:
        return {
            "state": "retention_window",
            "subscription": latest,
            "retention_deadline_at": retention_deadline.isoformat(),
        }

    user_data = await supabase_get_user_data(user_id) or {}
    current_credit = float(user_data.get("credit") or 0.0)
    current_storage = float(user_data.get("stockage") or 0.0)

    if current_credit > 0.0 or current_storage > 0.0:
        await supabase_set_user_data_balance(user_id=user_id, credit=0.0, storage=0.0)
        await supabase_insert_user_data_history(
            user_id=user_id,
            credit=current_credit,
            storage=current_storage,
            operation="output",
            operation_type="subscription_expiration",
            operation_id=str(latest.get("id") or ""),
        )

    if latest.get("id") and not latest.get("account_disabled_at"):
        await supabase_update_souscription_row(
            str(latest.get("id")),
            {
                "account_disabled_at": now_utc.isoformat(),
                "retention_deadline_at": retention_deadline.isoformat(),
            },
        )

    return {
        "state": "disabled",
        "subscription": latest,
        "retention_deadline_at": retention_deadline.isoformat(),
    }


async def _resolve_reel_input_url(job_id: str, clip_index: int) -> Optional[str]:
    if not is_supabase_configured():
        return None

    try:
        row = await supabase_get_reel_by_job_clip(job_id, clip_index)
    except Exception as e:
        print(f"⚠️ Supabase reel lookup failed for metadata hydration: {e}")
        return None

    if not row:
        return None

    # Prefer a fresh presigned URL from S3 key; fallback to stored URL.
    return _reel_media_url_from_s3_key(row.get("reel_s3_key") or "") or row.get("reel_url") or None


def _resolve_local_video_from_input_ref(input_ref: Optional[str]) -> Optional[tuple[str, str]]:
    """Resolve /videos/<job_id>/<filename> refs to local output file when possible."""
    ref = (input_ref or "").strip()
    if not ref:
        return None

    parsed = urlparse(ref)
    path_part = parsed.path or ref
    if not path_part.startswith("/videos/"):
        return None

    parts = path_part.split("/")
    if len(parts) < 4:
        return None

    ref_job_id = parts[2]
    ref_filename = _sanitize_input_filename("/".join(parts[3:]))
    if not ref_job_id or not ref_filename:
        return None

    candidate_path = os.path.join(OUTPUT_DIR, ref_job_id, ref_filename)
    if not os.path.exists(candidate_path):
        return None

    return candidate_path, ref_filename


async def _hydrate_missing_job_metadata(
    job_id: str,
    clip_index: int,
    input_url: Optional[str] = None,
) -> Optional[str]:
    """Create minimal metadata for old reels by downloading and transcribing the clip on demand."""
    source_ref = (input_url or "").strip() or await _resolve_reel_input_url(job_id, clip_index)
    if not source_ref:
        return None

    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)

    local_ref = _resolve_local_video_from_input_ref(source_ref)
    if local_ref:
        local_video_path, local_video_name = local_ref
        hydrated_video_path = os.path.join(output_dir, local_video_name)
        if os.path.abspath(local_video_path) != os.path.abspath(hydrated_video_path):
            try:
                shutil.copy(local_video_path, hydrated_video_path)
                local_video_path = hydrated_video_path
            except Exception as e:
                print(f"⚠️ Could not copy local reel for metadata hydration: {e}")
                return None
    else:
        parsed_source = urlparse(source_ref)
        if parsed_source.scheme not in ("http", "https"):
            return None

        try:
            local_video_path, local_video_name = _download_input_url_to_job_dir(source_ref, job_id)
        except Exception as e:
            print(f"⚠️ Could not download reel for metadata hydration: {e}")
            return None

    try:
        from main import transcribe_video

        loop = asyncio.get_event_loop()
        transcript = await loop.run_in_executor(None, transcribe_video, local_video_path)
    except Exception as e:
        print(f"⚠️ Could not transcribe reel for metadata hydration: {e}")
        return None

    duration_sec = max(0.5, _estimate_transcript_duration_seconds(transcript))

    shorts = [
        {
            "title": f"Clip {i + 1}",
            "start": 0.0,
            "end": duration_sec,
            "duration": duration_sec,
            "video_url": "",
        }
        for i in range(clip_index + 1)
    ]
    shorts[clip_index]["video_url"] = f"/videos/{job_id}/{local_video_name}"

    metadata = {
        "shorts": shorts,
        "transcript": transcript,
        "generated_from_reel_fallback": {
            "created_at": int(time.time()),
            "source": "supabase_reel_or_input_url",
            "clip_index": clip_index,
        },
    }

    metadata_path = os.path.join(output_dir, f"{job_id}_fallback_metadata.json")
    try:
        _persist_metadata_json(metadata_path, metadata)
    except Exception as e:
        print(f"⚠️ Failed to write hydrated metadata: {e}")
        return None

    return metadata_path


async def _get_or_build_job_metadata(
    job_id: str,
    clip_index: int,
    input_url: Optional[str] = None,
) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    metadata_path = _resolve_job_metadata_path(job_id)
    if not metadata_path:
        metadata_path = await _hydrate_missing_job_metadata(job_id, clip_index, input_url=input_url)
    if not metadata_path:
        return None, None

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            return metadata_path, json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to read metadata: {e}")
        return None, None


def _active_output_paths() -> set[str]:
    active_paths: set[str] = set()
    for job_data in jobs.values():
        if job_data.get("status") not in ("queued", "processing"):
            continue
        out_dir = job_data.get("output_dir")
        if out_dir:
            active_paths.add(os.path.abspath(out_dir))
    return active_paths


def _sweep_output_directory(now_ts: float) -> int:
    """Delete stale output artifacts in batches instead of per-job cleanup."""
    if not os.path.isdir(OUTPUT_DIR):
        return 0

    removed = 0
    active_paths = _active_output_paths()
    thumbnails_dir = os.path.abspath(os.path.join(OUTPUT_DIR, "thumbnails"))

    for child in os.listdir(OUTPUT_DIR):
        child_path = os.path.join(OUTPUT_DIR, child)
        abs_child = os.path.abspath(child_path)

        if abs_child == thumbnails_dir:
            continue
        if abs_child in active_paths:
            continue

        try:
            if now_ts - os.path.getmtime(child_path) < OUTPUT_SWEEP_MIN_AGE_SECONDS:
                continue

            if os.path.isdir(child_path):
                shutil.rmtree(child_path, ignore_errors=True)
            else:
                os.remove(child_path)
            removed += 1
        except Exception:
            continue

    return removed


def _reel_media_url_from_s3_key(s3_key: str) -> str:
    if not s3_key:
        return ""
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return ""
    return generate_presigned_url(bucket, s3_key, expiration=7200) or ""


def _reel_thumbnail_url_from_s3_key(s3_key: str) -> str:
    if not s3_key:
        return ""
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return ""
    return generate_presigned_url(bucket, s3_key, expiration=7200) or ""


def _job_uses_remote_source(job_data: Optional[Dict[str, Any]]) -> bool:
    payload = job_data or {}
    source_type = str(
        payload.get("source_type")
        or ((payload.get("attestation") or {}).get("source"))
        or ""
    ).strip().lower()
    return source_type == "url"


def _collect_reel_job_output_snapshot(job_id: str, output_dir: str) -> Dict[str, Any]:
    metadata_path = _resolve_job_metadata_path(job_id)
    metadata: Dict[str, Any] = {}
    shorts: List[Dict[str, Any]] = []
    cost_analysis = None
    base_name = ""

    if metadata_path and os.path.exists(metadata_path) and os.path.getsize(metadata_path) > 0:
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f) or {}
        except Exception:
            metadata = {}
        shorts = metadata.get("shorts") or []
        cost_analysis = metadata.get("cost_analysis")
        base_name = os.path.basename(metadata_path).replace("_metadata.json", "")

    ready_entries: List[Dict[str, Any]] = []
    if base_name and shorts:
        for index, clip in enumerate(shorts, start=1):
            clip_filename = f"{base_name}_clip_{index}.mp4"
            clip_path = os.path.join(output_dir, clip_filename)
            if not os.path.exists(clip_path) or os.path.getsize(clip_path) <= 0:
                continue
            ready_entries.append(
                {
                    "filename": clip_filename,
                    "path": clip_path,
                    "size_bytes": int(os.path.getsize(clip_path) or 0),
                    "clip": dict(clip or {}),
                }
            )

    if not ready_entries and os.path.isdir(output_dir):
        fallback_files = sorted(
            file_name
            for file_name in os.listdir(output_dir)
            if file_name.endswith(".mp4") and not file_name.startswith("temp_")
        )
        for file_name in fallback_files:
            clip_path = os.path.join(output_dir, file_name)
            ready_entries.append(
                {
                    "filename": file_name,
                    "path": clip_path,
                    "size_bytes": int(os.path.getsize(clip_path) or 0),
                    "clip": {},
                }
            )

    partial_clips: List[Dict[str, Any]] = []
    for idx, entry in enumerate(ready_entries, start=1):
        clip_payload = dict(entry.get("clip") or {})
        clip_payload["video_url"] = f"/videos/{job_id}/{entry['filename']}"
        clip_payload.setdefault("title", f"Clip {idx}")
        partial_clips.append(clip_payload)

    expected_clips = len(shorts) if shorts else len(ready_entries)
    total_size_bytes = sum(int(entry.get("size_bytes") or 0) for entry in ready_entries)
    result_data: Dict[str, Any] = {}
    if partial_clips:
        result_data["clips"] = partial_clips
    if cost_analysis is not None:
        result_data["cost_analysis"] = cost_analysis

    return {
        "metadata_path": metadata_path,
        "expected_clips": expected_clips,
        "processed_clips": len(ready_entries),
        "total_size_bytes": total_size_bytes,
        "result_data": result_data,
    }


def _estimate_reel_job_consumption(
    *,
    elapsed_seconds: float,
    uses_youtube: bool,
    processed_clips: int,
    expected_clips: int,
    storage_bytes: int,
) -> Dict[str, Any]:
    processed_count = max(0, int(processed_clips or 0))
    expected_count = max(0, int(expected_clips or 0))
    if processed_count <= 0:
        return {
            "processing_ratio": 0.0,
            "actual_cost_usd": 0.0,
            "actual_credit": 0.0,
            "actual_storage_gb": 0.0,
            "cost_breakdown": {},
        }

    processing_ratio = 1.0 if expected_count <= 0 else min(1.0, processed_count / expected_count)
    actual_storage_gb = _bytes_to_gb(storage_bytes)
    billed_video_size_gb = max(actual_storage_gb, 0.5)
    breakdown = estimate_reel_cost_usd(
        duration_minutes=max(float(elapsed_seconds or 0.0) / 60.0, 1.0),
        video_size_gb=billed_video_size_gb,
        uses_youtube_download=uses_youtube,
        youtube_download_gb=0.3 if uses_youtube else 0.0,
        uses_openai=True,
        uses_assembly=True,
    )
    credit_info = calculate_credits_for_operation(breakdown)
    return {
        "processing_ratio": round(processing_ratio, 4),
        "actual_cost_usd": round(float(breakdown.get("total_usd") or 0.0) * processing_ratio, 6),
        "actual_credit": round(float(credit_info.get("final_credits") or 0.0) * processing_ratio, 2),
        "actual_storage_gb": round(actual_storage_gb, 6),
        "cost_breakdown": credit_info,
    }


async def _finalize_failed_reel_job(
    *,
    job_id: str,
    user_id: Optional[str],
    output_dir: str,
    job_data: Optional[Dict[str, Any]],
    start_ts: float,
    error_message: str,
    error_code: str,
    retry_delay_seconds: int,
) -> Dict[str, Any]:
    elapsed = round(calc_elapsed_seconds(start_ts), 3)
    snapshot = _collect_reel_job_output_snapshot(job_id, output_dir)
    consumption = _estimate_reel_job_consumption(
        elapsed_seconds=elapsed,
        uses_youtube=_job_uses_remote_source(job_data),
        processed_clips=snapshot.get("processed_clips", 0),
        expected_clips=snapshot.get("expected_clips", 0),
        storage_bytes=0,
    )
    result_data = dict(snapshot.get("result_data") or {})
    result_data["duration_seconds"] = elapsed
    result_data["billing"] = {
        "actual_cost_usd": consumption["actual_cost_usd"],
        "actual_credit": consumption["actual_credit"],
        "actual_storage_gb": 0.0,
        "processing_ratio": consumption["processing_ratio"],
        "debit_applied": False,
        "partial_failure": True,
    }

    fail_result = await reel_job_manager.fail_job(
        job_id,
        error_message,
        error_code=error_code,
        retry_delay_seconds=retry_delay_seconds,
        actual_cost_usd=consumption["actual_cost_usd"],
        actual_credit=consumption["actual_credit"],
        actual_storage_gb=0.0,
        consumed_quota=consumption["processing_ratio"],
        result_data=result_data,
        cost_breakdown=consumption["cost_breakdown"],
    )

    debit_applied = False
    if not fail_result.get("retry") and user_id and consumption["actual_credit"] > 0:
        try:
            debit_applied = await reel_job_manager.debit_credits_for_job(
                job_id=job_id,
                user_id=user_id,
                credits=consumption["actual_credit"],
                storage_delta=0.0,
                operation_type="reels",
            )
        except Exception as billing_error:
            jobs[job_id]["logs"].append(f"Partial billing failed: {billing_error}")

    result_data["billing"]["debit_applied"] = bool(debit_applied)
    await supabase_update_job_record(
        job_id,
        {
            "result_data": result_data,
            "cost_breakdown": consumption["cost_breakdown"],
        },
    )

    if result_data.get("clips"):
        jobs[job_id]["result"] = result_data
    jobs[job_id]["status"] = fail_result.get("status") or "failed"
    return fail_result


def _extract_s3_key_from_thumbnail_ref(thumbnail_ref: str) -> str:
    """Accept raw S3 keys or s3://bucket/key refs and return object key only."""
    ref = (thumbnail_ref or "").strip()
    if not ref:
        return ""
    if ref.startswith("s3://"):
        without_scheme = ref[5:]
        parts = without_scheme.split("/", 1)
        if len(parts) == 2:
            return parts[1]
        return ""
    if ref.startswith("reels/"):
        return ref
    return ""

def _generate_reel_thumbnail_from_video(
    video_path: str,
    output_dir: str,
    job_id: str,
    clip_index: int,
) -> str:
    """Extract a representative frame from a clip and save it as a JPEG thumbnail."""
    if not video_path or not os.path.exists(video_path):
        return ""

    thumb_dir = os.path.join(output_dir, "thumbnails", job_id)
    os.makedirs(thumb_dir, exist_ok=True)
    thumb_path = os.path.join(thumb_dir, f"thumb_{clip_index + 1}.jpg")

    cap = None
    try:
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return ""

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if frame_count > 0:
            target_frame = max(0, min(frame_count - 1, frame_count // 5))
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

        ok, frame = cap.read()
        if not ok or frame is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()

        if not ok or frame is None:
            return ""

        if cv2.imwrite(thumb_path, frame):
            return thumb_path
        return ""
    except Exception:
        return ""
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass


def _normalize_reel_row(row: Dict[str, Any]) -> Dict[str, Any]:
    media_url = _reel_media_url_from_s3_key(row.get("reel_s3_key") or "") or row.get("reel_url") or ""
    thumbnail_ref = row.get("reel_thumbnail_url") or row.get("reel_thumbnail_s3_key") or ""
    thumbnail_s3_key = _extract_s3_key_from_thumbnail_ref(thumbnail_ref)
    thumbnail_url = _reel_thumbnail_url_from_s3_key(thumbnail_s3_key) or thumbnail_ref or ""
    preview_url = thumbnail_url or media_url

    return {
        **row,
        "reel_url": media_url or row.get("reel_url") or "",
        "reel_thumbnail_url": thumbnail_url,
        "reel_preview_url": preview_url,
        "reel_playback_url": media_url,
        "reel_download_url": media_url,
        "media_url": media_url,
    }


async def _persist_reels_for_job(
    job_id: str,
    user_id: str,
    output_dir: str,
    metadata_path: str,
    clips: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not user_id:
        raise RuntimeError("Missing app user id for reel persistence")
    if not is_supabase_configured():
        raise RuntimeError("Supabase reels is not configured")

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        raise RuntimeError("AWS_S3_BUCKET is required for reel persistence")

    base_name = os.path.basename(metadata_path).replace("_metadata.json", "")
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows: List[Dict[str, Any]] = []

    for i, clip in enumerate(clips, start=1):
        clip_filename = f"{base_name}_clip_{i}.mp4"
        clip_path = os.path.join(output_dir, clip_filename)
        if not os.path.exists(clip_path):
            continue

        s3_key = f"reels/{user_id}/{job_id}/{clip_filename}"
        uploaded = upload_file_to_s3(clip_path, bucket, s3_key)
        if not uploaded:
            raise RuntimeError(f"Failed to upload clip to S3: {clip_filename}")

        media_url = _reel_media_url_from_s3_key(s3_key)
        source_thumbnail = clip.get("thumbnail_url") or ""
        if not source_thumbnail:
            source_thumbnail = _generate_reel_thumbnail_from_video(
                clip_path,
                output_dir,
                job_id,
                i - 1,
            )

        print("🖼️ Uploading thumbnail for clip", i, "from source:", source_thumbnail)

        thumbnail_s3_key = f"reels/{user_id}/{job_id}/thumbnail.jpg"
        uploaded_thumb = upload_file_to_s3(source_thumbnail, bucket, thumbnail_s3_key)
        if not uploaded_thumb:
                    raise RuntimeError(f"Failed to upload thumbnail to S3: {thumbnail_s3_key}")

        duration = clip.get("duration")
        if duration is None:
            try:
                start = float(clip.get("start", 0) or 0)
                end = float(clip.get("end", 0) or 0)
                duration = max(0, int(round(end - start)))
            except Exception:
                duration = 0

        rows.append(
            {
                "reel_url": media_url,
                "reel_thumbnail_url": _reel_media_url_from_s3_key(thumbnail_s3_key),
                "reel_title": clip.get("title") or clip.get("video_title_for_youtube_short") or f"Clip {i}",
                "reel_description": clip.get("video_description_for_instagram") or clip.get("video_description_for_tiktok") or "",
                "reel_duration": max(30, int(duration or 0)),
                "reel_created_at": now_iso,
                "reel_updated_at": now_iso,
                "reel_user_id": user_id,
                "reel_status": "termine",
                "reel_size_bytes": int(os.path.getsize(clip_path) or 0),
                "reel_s3_key": s3_key,
                "reel_job_id": job_id,
                "reel_clip_index": i - 1,
            }
        )

    if not rows:
        raise RuntimeError("No generated clips were available for Supabase persistence")

    saved_rows = await supabase_insert_reels(rows)
    return [_normalize_reel_row(row) for row in saved_rows]

async def cleanup_jobs():
    """Background task to remove old jobs and files."""
    import time
    print("🧹 Cleanup task started.")
    last_output_sweep = 0.0
    while True:
        try:
            await asyncio.sleep(300) # Check every 5 minutes
            now = time.time()

            if OUTPUT_SWEEP_INTERVAL_SECONDS > 0 and (now - last_output_sweep) >= OUTPUT_SWEEP_INTERVAL_SECONDS:
                removed_count = _sweep_output_directory(now)
                print(f"🧹 Output sweep completed (removed {removed_count} entries).")
                last_output_sweep = now

            # Cleanup in-memory API jobs (artifacts are cleaned by batched output sweeps).
            expired_api_jobs = [
                jid for jid, jdata in list(jobs.items())
                if jdata.get("status") in ("completed", "failed")
                and jdata.get("output_dir")
                and os.path.isdir(jdata["output_dir"])
                and now - os.path.getmtime(jdata["output_dir"]) > JOB_RETENTION_SECONDS
            ]
            for jid in expired_api_jobs:
                del jobs[jid]

            # Cleanup SaaSShorts jobs from memory
            try:
                saas_expired = [
                    jid for jid, jdata in list(saas_jobs.items())
                    if jdata.get("status") in ("completed", "failed")
                    and jdata.get("output_dir")
                    and os.path.isdir(jdata["output_dir"])
                    and now - os.path.getmtime(jdata["output_dir"]) > JOB_RETENTION_SECONDS
                ]
                for jid in saas_expired:
                    del saas_jobs[jid]
            except NameError:
                pass

            # Cleanup Uploads
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                try:
                    if now - os.path.getmtime(file_path) > JOB_RETENTION_SECONDS:
                         os.remove(file_path)
                except Exception: pass

        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")

async def process_queue(worker_name: str):
    """Background worker to process jobs from the queue with concurrency limit."""
    print(f"🚀 Job Queue Worker {worker_name} started with {MAX_CONCURRENT_JOBS} concurrent slots.")
    while True:
        try:
            # Wait for a job
            queue_item = await job_queue.get()
            _, _, job_id = queue_item
            runtime_job = reel_job_manager.runtime_jobs.get(job_id) or jobs.get(job_id) or {}
            job_priority = _clamp_job_priority(runtime_job.get("priority", DEFAULT_JOB_PRIORITY))

            # Acquire semaphore slot (waits if max jobs are running)
            await concurrency_semaphore.acquire()
            print(f"🔄 [{worker_name}] Acquired slot for job: {job_id} (priority={job_priority})")

            # Process in background task to not block the loop (allowing other slots to fill)
            asyncio.create_task(run_job_wrapper(job_id, job_priority))

        except Exception as e:
            print(f"❌ Queue dispatch error: {e}")
            await asyncio.sleep(1)

async def run_job_wrapper(job_id: str, job_priority: int):
    """Wrapper to run job and release semaphore"""
    execution_ctx: Dict[str, Any] = {
        "process": None,
        "preempt_requested": False,
        "priority": _clamp_job_priority(job_priority),
        "started_at": time.time(),
    }
    async with running_reel_jobs_lock:
        running_reel_jobs[job_id] = execution_ctx
    try:
        job = reel_job_manager.runtime_jobs.get(job_id) or jobs.get(job_id)
        if job:
            job["priority"] = execution_ctx["priority"]
            await run_job(job_id, job, execution_ctx=execution_ctx)
    except Exception as e:
         print(f"❌ Job wrapper error {job_id}: {e}")
    finally:
        async with running_reel_jobs_lock:
            running_reel_jobs.pop(job_id, None)
        # Always release semaphore and mark queue task done
        concurrency_semaphore.release()
        job_queue.task_done()
        print(f"✅ Released slot for job: {job_id}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start worker and cleanup
    worker_tasks = [
        asyncio.create_task(process_queue(f"worker-{idx + 1}"))
        for idx in range(max(1, QUEUE_WORKER_COUNT))
    ]
    cleanup_task = asyncio.create_task(cleanup_jobs())
    yield
    # Cleanup (optional: cancel worker)
    for task in worker_tasks:
        task.cancel()
    cleanup_task.cancel()

app = FastAPI(lifespan=lifespan)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for serving videos
app.mount("/videos", StaticFiles(directory=OUTPUT_DIR), name="videos")

# Mount static files for serving thumbnails
THUMBNAILS_DIR = os.path.join(OUTPUT_DIR, "thumbnails")
os.makedirs(THUMBNAILS_DIR, exist_ok=True)
app.mount("/thumbnails", StaticFiles(directory=THUMBNAILS_DIR), name="thumbnails")

class ProcessRequest(BaseModel):
    url: str

def enqueue_output(out, job_id):
    """Reads output from a subprocess and appends it to jobs logs."""
    try:
        for line in iter(out.readline, b''):
            decoded_line = line.decode('utf-8').strip()
            if decoded_line:
                print(f"📝 [Job Output] {decoded_line}")
                if job_id in jobs:
                    jobs[job_id]['logs'].append(decoded_line)
    except Exception as e:
        print(f"Error reading output for job {job_id}: {e}")
    finally:
        out.close()


async def _close_proxy_stream(upstream, client):
    try:
        await upstream.aclose()
    finally:
        await client.aclose()


@app.get("/api/media/proxy")
async def proxy_media(request: Request, url: str):
    """Proxy remote media through the backend so browser-side Remotion can fetch it same-origin."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Invalid media URL")

    import httpx

    forward_headers = {}
    if request.headers.get("range"):
        forward_headers["Range"] = request.headers["range"]
    if request.headers.get("user-agent"):
        forward_headers["User-Agent"] = request.headers["user-agent"]

    client = httpx.AsyncClient(follow_redirects=True, timeout=120.0)
    try:
        upstream = await client.send(client.build_request("GET", url, headers=forward_headers), stream=True)
    except Exception:
        await client.aclose()
        raise

    passthrough_headers = {}
    for header in ("content-type", "content-length", "accept-ranges", "content-range", "etag", "last-modified", "cache-control"):
        value = upstream.headers.get(header)
        if value:
            passthrough_headers[header] = value

    passthrough_headers["Access-Control-Allow-Origin"] = "*"
    passthrough_headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Range, Accept-Ranges, ETag, Last-Modified"

    return StreamingResponse(
        upstream.aiter_bytes(),
        status_code=upstream.status_code,
        headers=passthrough_headers,
        background=BackgroundTask(_close_proxy_stream, upstream, client),
    )

async def run_job(job_id, job_data, execution_ctx: Optional[Dict[str, Any]] = None):
    """Executes the subprocess for a specific job."""
    
    cmd = job_data['cmd']
    env = job_data['env']
    output_dir = job_data['output_dir']
    user_id = job_data.get("user_id")
    input_path = job_data.get("input_path")
    source_is_url = _job_uses_remote_source(job_data)
    pipeline = ReelProcessingPipeline(reel_job_manager, job_id)
    job_priority = _clamp_job_priority(job_data.get("priority", DEFAULT_JOB_PRIORITY))
    start_ts = time.time()

    jobs[job_id]['status'] = 'processing'
    jobs[job_id]['priority'] = job_priority
    jobs[job_id]['logs'].append("Job started by worker.")
    await reel_job_manager.start_job(job_id)
    await pipeline.starting()
    print(f"🎬 [run_job] Executing command for {job_id}: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Merge stderr to stdout
            env=env,
            cwd=os.getcwd()
        )
        if execution_ctx is not None:
            execution_ctx["process"] = process

        # We need to capture logs in a thread because Popen isn't async
        t_log = threading.Thread(target=enqueue_output, args=(process.stdout, job_id))
        t_log.daemon = True
        t_log.start()
        
        # Async wait for process with incremental updates
        start_wait = time.time()
        while process.poll() is None:
            if execution_ctx and execution_ctx.get("preempt_requested"):
                try:
                    process.terminate()
                except Exception:
                    pass
            await asyncio.sleep(2)
            
            # Check for partial results every 2 seconds
            # Look for metadata file
            try:
                json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
                if json_files:
                    target_json = json_files[0]
                    # Read metadata (it might be being written to, so simple try/except or just read)
                    # Use a lock or just robust read? json.load might fail if file is partial.
                    # Usually main.py writes it once at start (based on my review).
                    if os.path.getsize(target_json) > 0:
                        with open(target_json, 'r') as f:
                            data = json.load(f)
                            
                        base_name = os.path.basename(target_json).replace('_metadata.json', '')
                        clips = data.get('shorts', [])
                        cost_analysis = data.get('cost_analysis')
                        
                        # Check which clips actually exist on disk
                        ready_clips = []
                        for i, clip in enumerate(clips):
                             clip_filename = f"{base_name}_clip_{i+1}.mp4"
                             clip_path = os.path.join(output_dir, clip_filename)
                             if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                                 # Checking if file is growing? For now assume if it exists and main.py moves it there, it's done.
                                 # main.py writes to temp_... then moves to final name. So presence means ready!
                                 clip['video_url'] = f"/videos/{job_id}/{clip_filename}"
                                 ready_clips.append(clip)
                        
                        if ready_clips:
                             jobs[job_id]['result'] = {'clips': ready_clips, 'cost_analysis': cost_analysis}
                             await pipeline.cutting_clips()
            except Exception as e:
                # Ignore read errors during processing
                pass

        returncode = process.returncode
        preempted = bool(execution_ctx and execution_ctx.get("preempt_requested"))

        if preempted:
            jobs[job_id]['status'] = 'queued'
            jobs[job_id]['logs'].append("Job preempted by a higher-priority task and re-queued.")
            await reel_job_manager.enqueue_job(job_id)
            await enqueue_reel_job(job_id, priority=job_priority)
            return

        if returncode == 0:
            jobs[job_id]['status'] = 'completed'
            jobs[job_id]['logs'].append("Process finished successfully.")

            # Find result JSON
            json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
            if not json_files:
                # Backward-compat rescue if outputs were written to OUTPUT_DIR root
                if _relocate_root_job_artifacts(job_id, output_dir):
                    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
            if json_files:
                target_json = json_files[0] 
                with open(target_json, 'r') as f:
                    data = json.load(f)
                
                # Enhance result with video URLs
                clips = data.get('shorts', [])
                cost_analysis = data.get('cost_analysis')

                try:
                    await pipeline.uploading_reels(len(clips))
                    saved_rows = await _persist_reels_for_job(
                        job_id=job_id,
                        user_id=user_id,
                        output_dir=output_dir,
                        metadata_path=target_json,
                        clips=clips,
                    )
                except Exception as persist_error:
                    jobs[job_id]['status'] = 'failed'
                    jobs[job_id]['logs'].append(f"Supabase persistence failed: {persist_error}")
                    fail_result = await _finalize_failed_reel_job(
                        job_id=job_id,
                        user_id=user_id,
                        output_dir=output_dir,
                        job_data=job_data,
                        start_ts=start_ts,
                        error_message=f"Supabase persistence failed: {persist_error}",
                        error_code="REEL_PERSISTENCE_FAILED",
                        retry_delay_seconds=REEL_JOB_RETRY_DELAY_SECONDS,
                    )
                    if fail_result.get("retry"):
                        asyncio.create_task(_schedule_reel_retry(job_id, REEL_JOB_RETRY_DELAY_SECONDS))
                    return

                enriched_clips: List[Dict[str, Any]] = []
                for i, clip in enumerate(clips):
                    clip_copy = dict(clip)
                    if i < len(saved_rows):
                        clip_copy['video_url'] = saved_rows[i].get('reel_playback_url') or saved_rows[i].get('reel_url')
                        clip_copy['reel_id'] = saved_rows[i].get('id')
                    enriched_clips.append(clip_copy)

                jobs[job_id]['result'] = {
                    'clips': enriched_clips,
                    'cost_analysis': cost_analysis,
                    'reels': saved_rows,
                }
                await pipeline.finalizing()
                elapsed = round(calc_elapsed_seconds(start_ts), 3)
                total_reel_size_bytes = sum(int(row.get("reel_size_bytes") or 0) for row in saved_rows)
                billing = _estimate_reel_job_consumption(
                    elapsed_seconds=elapsed,
                    uses_youtube=source_is_url,
                    processed_clips=len(saved_rows),
                    expected_clips=len(clips),
                    storage_bytes=total_reel_size_bytes,
                )
                debit_applied = False
                logger.info(f"Billing info for job {job_id}: {billing}")
                if is_supabase_configured() and user_id and (
                    billing["actual_credit"] > 0 or billing["actual_storage_gb"] > 0
                ):
                    try:
                        logger.info(f"Debiting credits for job {job_id}")
                        debit_applied = await reel_job_manager.debit_credits_for_job(
                            job_id=job_id,
                            user_id=user_id,
                            credits=billing["actual_credit"],
                            storage_delta=-billing["actual_storage_gb"],
                            operation_type="reels",
                        )
                    except Exception as billing_error:
                        logger.error(f"Billing update failed: {billing_error}")
                        jobs[job_id]['logs'].append(f"Billing update failed: {billing_error}")

                result_payload = {
                    'clips': enriched_clips,
                    'cost_analysis': cost_analysis,
                    'reels': saved_rows,
                    'duration_seconds': elapsed,
                    'billing': {
                        'actual_cost_usd': billing['actual_cost_usd'],
                        'actual_credit': billing['actual_credit'],
                        'actual_storage_gb': billing['actual_storage_gb'],
                        'processing_ratio': billing['processing_ratio'],
                        'debit_applied': bool(debit_applied),
                    },
                }
                await reel_job_manager.complete_job(
                    job_id,
                    result_payload,
                    actual_cost_usd=billing['actual_cost_usd'],
                    actual_credit=billing['actual_credit'],
                    actual_storage_gb=billing['actual_storage_gb'],
                    consumed_quota=billing['processing_ratio'],
                    cost_breakdown=billing['cost_breakdown'],
                )
            else:
                 jobs[job_id]['status'] = 'failed'
                 jobs[job_id]['logs'].append("No metadata file generated.")
                 result = await _finalize_failed_reel_job(
                     job_id=job_id,
                     user_id=user_id,
                     output_dir=output_dir,
                     job_data=job_data,
                     start_ts=start_ts,
                     error_message="No metadata file generated",
                     error_code="METADATA_NOT_FOUND",
                     retry_delay_seconds=REEL_JOB_RETRY_DELAY_SECONDS,
                 )
                 if result.get("retry"):
                     asyncio.create_task(_schedule_reel_retry(job_id, REEL_JOB_RETRY_DELAY_SECONDS))
        else:
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['logs'].append(f"Process failed with exit code {returncode}")
            result = await _finalize_failed_reel_job(
                job_id=job_id,
                user_id=user_id,
                output_dir=output_dir,
                job_data=job_data,
                start_ts=start_ts,
                error_message=f"Process failed with exit code {returncode}",
                error_code="PROCESS_EXIT",
                retry_delay_seconds=REEL_JOB_RETRY_DELAY_SECONDS,
            )
            if result.get("retry"):
                asyncio.create_task(_schedule_reel_retry(job_id, REEL_JOB_RETRY_DELAY_SECONDS))

    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['logs'].append(f"Execution error: {str(e)}")
        result = await _finalize_failed_reel_job(
            job_id=job_id,
            user_id=user_id,
            output_dir=output_dir,
            job_data=job_data,
            start_ts=start_ts,
            error_message=f"Execution error: {str(e)}",
            error_code="EXECUTION_ERROR",
            retry_delay_seconds=REEL_JOB_RETRY_DELAY_SECONDS,
        )
        if result.get("retry"):
            asyncio.create_task(_schedule_reel_retry(job_id, REEL_JOB_RETRY_DELAY_SECONDS))
    finally:
        # Keep generated artifacts in output/ until the periodic output sweep runs.
        if input_path and os.path.exists(input_path):
            try:
                os.remove(input_path)
            except Exception:
                pass

@app.get("/api/config")
async def get_config():
    return {"youtubeUrlEnabled": not DISABLE_YOUTUBE_URL}

@app.get("/api/services/status")
async def get_services_status():
    """Check which API services are configured and available."""
    return {
        "gemini": {
            "available": bool(os.getenv("GEMINI_API_KEY")),
            "name": "Google Gemini",
            "description": "AI video analysis and clip generation"
        },
        "openai": {
            "available": bool(os.getenv("OPENAI_API_KEY")),
            "name": "OpenAI",
            "description": "Fallback AI provider"
        },
        "elevenlabs": {
            "available": bool(os.getenv("ELEVENLABS_API_KEY")),
            "name": "ElevenLabs",
            "description": "AI voice dubbing and translation"
        },
        "social_oauth": {
            "available": bool(
                os.getenv("FACEBOOK_CLIENT_ID")
                or os.getenv("LINKEDIN_CLIENT_ID")
                or os.getenv("YOUTUBE_CLIENT_ID")
                or os.getenv("TIKTOK_CLIENT_KEY")
                or os.getenv("INSTAGRAM_CLIENT_ID")
            ),
            "name": "Social OAuth",
            "description": "Native social account publishing"
        },
        "aws_s3": {
            "available": bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")),
            "name": "AWS S3",
            "description": "Video backup and storage"
        },
        "supabase": {
            "available": bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
            "name": "Supabase",
            "description": "Database and authentication"
        }
    }


def _bytes_to_gb(size_bytes: float) -> float:
    return max(0.0, float(size_bytes) / (1024 ** 3))


def _probe_local_video_duration_seconds(video_path: str) -> float:
    """Best-effort local video duration probe using ffprobe, fallback to OpenCV."""
    if not video_path or not os.path.exists(video_path):
        return 0.0

    try:
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        out = subprocess.check_output(probe_cmd, stderr=subprocess.STDOUT).decode().strip()
        duration = float(out or 0)
        if duration > 0:
            return duration
    except Exception:
        pass

    try:
        import cv2

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        duration = frame_count / fps if fps else 0.0
        return max(0.0, float(duration))
    except Exception:
        return 0.0


def _probe_remote_video_metadata(url_value: str) -> Dict[str, float]:
    """Best-effort remote metadata probe via yt-dlp without downloading the file."""
    if not url_value:
        return {"duration_seconds": 0.0, "size_bytes": 0.0}

    try:
        cmd = ["yt-dlp", "--dump-json", "--skip-download", "--no-warnings", url_value]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
        if not out:
            return {"duration_seconds": 0.0, "size_bytes": 0.0}
        payload = json.loads(out.splitlines()[-1])
        duration = float(payload.get("duration") or 0)
        size_bytes = float(payload.get("filesize") or payload.get("filesize_approx") or 0)
        return {
            "duration_seconds": max(0.0, duration),
            "size_bytes": max(0.0, size_bytes),
        }
    except Exception:
        return {"duration_seconds": 0.0, "size_bytes": 0.0}


def _validate_reel_source_constraints(duration_seconds: float, size_bytes: float, source_label: str) -> None:
    max_duration_seconds = max(0.0, REEL_MAX_DURATION_MINUTES) * 60.0
    max_size_bytes = max(0.0, REEL_MAX_STORAGE_GB) * (1024 ** 3)

    if max_size_bytes > 0 and size_bytes > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Source {source_label} trop volumineuse: {_bytes_to_gb(size_bytes):.2f} Go. "
                f"Maximum autorise: {REEL_MAX_STORAGE_GB:.2f} Go."
            ),
        )

    if max_duration_seconds > 0 and duration_seconds > max_duration_seconds:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Source {source_label} trop longue: {duration_seconds / 60.0:.2f} min. "
                f"Maximum autorise: {REEL_MAX_DURATION_MINUTES:.2f} min."
            ),
        )


def _allowed_video_formats() -> List[str]:
    return [
        fmt.strip().lower().lstrip(".")
        for fmt in str(VIREEL_VIDEO_FORMAT or "").split(",")
        if fmt and fmt.strip()
    ]


def _validate_video_extension(filename: str, context_label: str = "fichier") -> None:
    allowed = _allowed_video_formats()
    if not allowed:
        return

    ext = os.path.splitext(str(filename or ""))[1].lower().lstrip(".")
    if not ext or ext not in allowed:
        accepted = ", ".join(allowed)
        raise HTTPException(
            status_code=400,
            detail=f"Format video invalide pour {context_label}. Formats acceptes: {accepted}.",
        )

@app.post("/api/process")
async def process_endpoint(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    acknowledged: Optional[str] = Form(None),
    user_id: str = Depends(get_user_id_header),
):
    # Determine API Key: Use .env configuration (GEMINI_API_KEY or OPENAI_API_KEY as fallback)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key not configured on server (.env)")

    # --- Credit pre-check ---
    if is_supabase_configured():
        uses_youtube = bool(url)
        _reel_cost_breakdown = estimate_reel_cost_usd(
            duration_minutes=10.0,
            video_size_gb=1.0,
            uses_youtube_download=uses_youtube,
            youtube_download_gb=0.5 if uses_youtube else 0.0,
            uses_openai=True,
            uses_assembly=True,
            uses_gemini=False,
        )
        _reel_credit_info = calculate_credits_for_operation(_reel_cost_breakdown)
        _required_credits = _reel_credit_info["final_credits"]
        _user_data = await supabase_get_user_data(user_id)
        _user_credits = float(_user_data.get("credit", 0)) if _user_data else 0.0
        if _user_credits < _required_credits:
            raise HTTPException(
                status_code=402,
                detail=f"Crédits insuffisants. Requis : {_required_credits} cr, disponible : {_user_credits} cr.",
            )

    ack_flag = str(acknowledged).lower() in ("1", "true", "yes")

    # Handle JSON body manually for URL payload
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        url = body.get("url")
        ack_flag = bool(body.get("acknowledged"))

    if not url and not file:
        raise HTTPException(status_code=400, detail="Must provide URL or File")

    if not ack_flag:
        raise HTTPException(status_code=400, detail="You must confirm you own the content or have rights to process it.")

    if url and DISABLE_YOUTUBE_URL:
        raise HTTPException(status_code=403, detail="YouTube URL ingest is disabled on this deployment. Please upload a file you own.")

    if url:
        remote_meta = _probe_remote_video_metadata(url)
        _validate_reel_source_constraints(
            duration_seconds=float(remote_meta.get("duration_seconds") or 0.0),
            size_bytes=float(remote_meta.get("size_bytes") or 0.0),
            source_label="url",
        )

    # Capture attestation context for legal record (IP + timestamp + UA)
    client_ip = request.client.host if request.client else "unknown"
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        client_ip = fwd.split(",")[0].strip()
    user_agent = request.headers.get("user-agent", "")
    attestation = {
        "acknowledged": True,
        "ip": client_ip,
        "user_agent": user_agent,
        "timestamp": time.time(),
        "source": "url" if url else "file",
    }

    job_priority = await _resolve_user_job_priority(user_id)

    job_id = str(uuid.uuid4())
    job_output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(job_output_dir, exist_ok=True)
    input_path = None

    # Prepare Command
    cmd = ["python", "-u", "main.py"] # -u for unbuffered
    env = os.environ.copy()
    env["GEMINI_API_KEY"] = api_key # Override with key from request

    if url:
        cmd.extend(["-u", url])
    else:
        _validate_video_extension(file.filename if file else "", context_label="reel")

        # Save uploaded file with size limit check
        input_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")

        # Read file in chunks to check size
        size = 0
        limit_bytes = max(0.0, REEL_MAX_STORAGE_GB) * (1024 ** 3)

        with open(input_path, "wb") as buffer:
            while content := await file.read(1024 * 1024): # Read 1MB chunks
                size += len(content)
                if limit_bytes > 0 and size > limit_bytes:
                    os.remove(input_path)
                    shutil.rmtree(job_output_dir)
                    raise HTTPException(status_code=413, detail=f"Fichier trop volumineux. Maximum autorise: {REEL_MAX_STORAGE_GB:.2f} Go")
                buffer.write(content)

        local_duration = _probe_local_video_duration_seconds(input_path)
        _validate_reel_source_constraints(
            duration_seconds=local_duration,
            size_bytes=float(size),
            source_label="fichier",
        )

        cmd.extend(["-i", input_path])

    cmd.extend(["-o", job_output_dir])

    print(f"[attestation] job={job_id} ip={attestation['ip']} source={attestation['source']} ack=true")

    # Enqueue job runtime payload.
    runtime_payload = {
        'status': 'queued',
        'logs': [f"Job {job_id} queued."],
        'cmd': cmd,
        'env': env,
        'output_dir': job_output_dir,
        'input_path': input_path,
        'source_type': 'url' if url else 'file',
        'source_value': url if url else (file.filename if file else ''),
        'attestation': attestation,
        'user_id': user_id,
        'priority': job_priority,
    }

    jobs[job_id] = dict(runtime_payload)
    reel_job_manager.runtime_jobs[job_id] = dict(runtime_payload)

    # Persist job state in Supabase.
    await reel_job_manager.create_job(
        user_id=user_id,
        job_type=JobType.GENERATE_REELS,
        pipeline_name="ReelProcessingPipeline",
        job_id=job_id,
        job_data={
            "source_type": "url" if url else "file",
            "source_value": url if url else (file.filename if file else ""),
            "output_dir": job_output_dir,
            "input_path": input_path,
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "reel_max_duration_minutes": REEL_MAX_DURATION_MINUTES,
            "reel_max_storage_gb": REEL_MAX_STORAGE_GB,
            "attestation": attestation,
        },
        runtime_data=dict(runtime_payload),
        max_attempts=REEL_JOB_MAX_ATTEMPTS,
        reserved_quota=1.0,
        priority=job_priority,
    )
    await reel_job_manager.enqueue_job(job_id)
    await ReelProcessingPipeline(reel_job_manager, job_id).queued()

    await enqueue_reel_job(job_id, priority=job_priority)

    return {"job_id": job_id, "status": "queued"}

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    user_id = None
    # Best effort read user scope from in-memory runtime when available.
    runtime_job = reel_job_manager.runtime_jobs.get(job_id) or jobs.get(job_id)
    if runtime_job:
        user_id = runtime_job.get("user_id")

    supabase_view = await reel_job_manager.get_job_view(job_id, user_id=user_id)
    if supabase_view:
        if runtime_job and runtime_job.get('status') in ('queued', 'processing') and runtime_job.get('output_dir'):
            try:
                output_dir = runtime_job['output_dir']
                if os.path.exists(output_dir):
                    clip_files = sorted([
                        f for f in os.listdir(output_dir)
                        if f.endswith('.mp4') and not f.startswith('temp_')
                    ])
                    if clip_files:
                        supabase_view['partialClips'] = [
                            {
                                'video_url': f'/videos/{job_id}/{clip_file}',
                                'file': clip_file,
                                'index': i,
                                'status': 'generated'
                            }
                            for i, clip_file in enumerate(clip_files)
                        ]
            except Exception:
                pass
        return supabase_view

    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    response = {
        "status": job['status'],
        "logs": job['logs'],
        "result": job.get('result')
    }

    # If job is processing, scan for partial clips that have been generated
    if job['status'] in ('queued', 'processing') and job.get('output_dir'):
        try:
            output_dir = job['output_dir']
            if os.path.exists(output_dir):
                # Find all generated clips (not temp ones)
                clip_files = sorted([
                    f for f in os.listdir(output_dir)
                    if f.endswith('.mp4') and not f.startswith('temp_')
                ])
                if clip_files:
                    # Build partial result from generated clips
                    partial_clips = []
                    for i, clip_file in enumerate(clip_files):
                        clip_path = os.path.join(output_dir, clip_file)
                        partial_clips.append({
                            'video_url': f'/videos/{job_id}/{clip_file}',
                            'file': clip_file,
                            'index': i,
                            'status': 'generated'
                        })
                    response['partialClips'] = partial_clips
        except Exception as e:
            # Silently fail - don't break the status endpoint
            pass

    return response

from editor import VideoEditor
from subtitles import generate_srt, burn_subtitles, generate_srt_from_video, SubtitleStyleOptions
from hooks import add_hook_to_video
#from translate import translate_video, get_supported_languages
from thumbnail import analyze_video_for_titles, refine_titles, generate_thumbnail, generate_youtube_description

class EditRequest(BaseModel):
    job_id: str
    clip_index: int
    api_key: Optional[str] = None
    input_filename: Optional[str] = None
    input_url: Optional[str] = None


def _sanitize_input_filename(value: Optional[str]) -> Optional[str]:
    """Normalize a filename or URL into a safe local basename."""
    if not value:
        return None

    candidate = str(value).strip()
    if not candidate:
        return None

    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        candidate = os.path.basename(parsed.path)
    else:
        candidate = os.path.basename(candidate.split('?')[0])

    candidate = unquote(candidate)
    return candidate or None


def _download_input_url_to_job_dir(input_url: str, job_id: str) -> tuple[str, str]:
    """Download a remote clip URL into output/<job_id> and return (path, filename)."""
    parsed = urlparse(input_url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Invalid input URL")

    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)

    source_name = _sanitize_input_filename(input_url) or f"remote_{job_id}.mp4"
    filename = f"remote_{uuid.uuid4().hex[:8]}_{source_name}"
    local_path = os.path.join(output_dir, filename)

    try:
        request = UrlRequest(input_url, headers={"User-Agent": "Vireel/1.0"})
        with urlopen(request, timeout=45) as response, open(local_path, "wb") as f:
            shutil.copyfileobj(response, f)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not download input URL: {e}")

    return local_path, filename

@app.post("/api/edit")
async def edit_clip(
    request: Request,
    req: EditRequest,
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key"),
    user_id: str = Depends(get_user_id_header),
):
    # Determine API Key
    final_api_key = req.api_key or x_gemini_key or os.environ.get("GEMINI_API_KEY")
    
    if not final_api_key:
        raise HTTPException(status_code=400, detail="Missing Gemini API Key (Header or Body)")

    # Credit pre-check for reel auto-edit customization
    edit_required_credits = 0.0
    if is_supabase_configured():
        _edit_breakdown = estimate_reel_cost_usd(
            duration_minutes=3.0,
            video_size_gb=0.3,
            uses_youtube_download=False,
            uses_openai=True,
            uses_assembly=False,
            uses_gemini=False,
        )
        edit_required_credits = calculate_credits_for_operation(_edit_breakdown)["final_credits"]
        _edit_user_data = await supabase_get_user_data(user_id)
        _edit_available = float(_edit_user_data.get("credit", 0)) if _edit_user_data else 0.0
        if _edit_available < edit_required_credits:
            raise HTTPException(
                status_code=402,
                detail=f"Crédits insuffisants. Requis : {edit_required_credits} cr, disponible : {_edit_available} cr.",
            )

    job = jobs.get(req.job_id)

    try:
        # Resolve Input Path: Prefer explict input_filename from frontend (chaining edits)
        if req.input_filename:
            # Security: Ensure just a filename, no paths or signed query params
            safe_name = _sanitize_input_filename(req.input_filename)
            if not safe_name:
                raise HTTPException(status_code=400, detail="Invalid input filename")
            input_path = os.path.join(OUTPUT_DIR, req.job_id, safe_name)
            filename = safe_name
        else:
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            if 'result' not in job or 'clips' not in job['result']:
                raise HTTPException(status_code=400, detail="Job result not available")
            # Fallback to original clip
            clip = job['result']['clips'][req.clip_index]
            filename = clip['video_url'].split('/')[-1]
            input_path = os.path.join(OUTPUT_DIR, req.job_id, filename)

        # Reels page may provide only a signed URL and no live in-memory job.
        if not os.path.exists(input_path) and req.input_url:
            input_path, filename = _download_input_url_to_job_dir(req.input_url, req.job_id)

        if not os.path.exists(input_path):
             raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")

        os.makedirs(os.path.join(OUTPUT_DIR, req.job_id), exist_ok=True)

        # Define output path for edited video
        edited_filename = f"edited_{filename}"
        output_path = os.path.join(OUTPUT_DIR, req.job_id, edited_filename)
        
        # Run editing in a thread to avoid blocking main loop
        # Since VideoEditor uses blocking calls (subprocess, API wait)
        def run_edit():
            editor = VideoEditor(api_key=final_api_key)
            
            # SAFE FILE RENAMING STRATEGY (Avoid UnicodeEncodeError in Docker)
            # Create a safe ASCII filename in the same directory
            safe_filename = f"temp_input_{req.job_id}.mp4"
            safe_input_path = os.path.join(OUTPUT_DIR, req.job_id, safe_filename)
            
            # Copy original file to safe path
            # (Copy is safer than rename if something crashes, we keep original)
            shutil.copy(input_path, safe_input_path)
            
            try:
                # 1. Upload (using safe path)
                vid_file = editor.upload_video(safe_input_path)
                
                # 2. Get duration
                import cv2
                cap = cv2.VideoCapture(safe_input_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                duration = frame_count / fps if fps else 0
                cap.release()
                
                # Load transcript from metadata
                transcript = None
                try:
                    meta_files = glob.glob(os.path.join(OUTPUT_DIR, req.job_id, "*_metadata.json"))
                    if meta_files:
                        with open(meta_files[0], 'r') as f:
                            data = json.load(f)
                            transcript = data.get('transcript')
                except Exception as e:
                    print(f"⚠️ Could not load transcript for editing context: {e}")

                # 3. Get Plan (Filter String)
                filter_data = editor.get_ffmpeg_filter(vid_file, duration, fps=fps, width=width, height=height, transcript=transcript)
                
                # 4. Apply
                # Use safe output name first
                safe_output_path = os.path.join(OUTPUT_DIR, req.job_id, f"temp_output_{req.job_id}.mp4")
                editor.apply_edits(safe_input_path, safe_output_path, filter_data)
                
                # Move result to final destination (rename works even if dest name has unicode if filesystem supports it, 
                # but python might still struggle if locale is broken? No, os.rename usually handles it better than subprocess args)
                # Actually, output_path is defined above: f"edited_{filename}"
                # If filename has unicode, output_path has unicode.
                # Let's hope shutil.move / os.rename works.
                if os.path.exists(safe_output_path):
                    shutil.move(safe_output_path, output_path)
                
                return filter_data
            finally:
                # Cleanup temp safe input
                if os.path.exists(safe_input_path):
                    os.remove(safe_input_path)

        # Run in thread pool
        loop = asyncio.get_event_loop()
        plan = await loop.run_in_executor(None, run_edit)
        
        # Update clip URL in the job result? 
        # Or return new URL and let frontend handle it?
        # Updating job result allows persistence if page refreshes.
        
        new_video_url = f"/videos/{req.job_id}/{edited_filename}"
        
        # Start a new "edited" clip entry or just update the current one?
        # Let's update the current one's video_url but keep backup?
        # Or return the new URL to the frontend to display.
        
        if is_supabase_configured() and edit_required_credits > 0:
            await supabase_deduct_user_credits(user_id, edit_required_credits)
            await supabase_insert_user_data_history(
                user_id=user_id,
                credit=edit_required_credits,
                storage=0.0,
                operation="output",
                operation_type="reels",
                operation_id=f"{req.job_id}:edit:{req.clip_index}",
            )

        return {
            "success": True, 
            "new_video_url": new_video_url,
            "edit_plan": plan
        }

    except Exception as e:
        print(f"❌ Edit Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class SubtitleRequest(BaseModel):
    job_id: str
    clip_index: int
    position: str = "bottom" # top, middle, bottom
    position_x: float = 50.0
    position_y: float = 82.0
    font_size: int = 16
    font_name: str = "Verdana"
    font_color: str = "#FFFFFF"
    highlight_color: str = "#FFDD00"
    border_color: str = "#000000"
    border_width: int = 2
    text_shadow_color: str = "#000000"
    shadow_blur: int = 6
    shadow_offset_x: int = 0
    shadow_offset_y: int = 2
    bg_color: str = "#000000"
    bg_opacity: float = 0.0
    text_case: str = "none"
    bold: bool = True
    italic: bool = False
    words_per_line: int = 4
    animation: str = "pop"
    input_filename: Optional[str] = None
    input_url: Optional[str] = None


@app.get("/api/clip/{job_id}/{clip_index}/transcript")
async def get_clip_transcript(job_id: str, clip_index: int):
    """Return word-level captions for a specific clip, formatted for Remotion."""
    # Do not depend on in-memory jobs: Reels page must keep working after restarts.
    _, data = await _get_or_build_job_metadata(job_id, clip_index)
    if not data:
        # Graceful fallback when metadata cannot be reconstructed.
        return {
            "captions": [],
            "durationSec": 0,
            "language": "en",
            "missing": "metadata",
        }

    transcript = data.get('transcript')
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript not found in metadata")

    clips = data.get('shorts', [])
    if clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")

    clip_data = clips[clip_index]
    clip_start = clip_data.get('start', 0)
    clip_end = clip_data.get('end', 0)

    # Extract words within clip range and convert to CaptionWord format
    captions = []
    for segment in transcript.get('segments', []):
        for word_info in segment.get('words', []):
            if word_info['end'] > clip_start and word_info['start'] < clip_end:
                captions.append({
                    "text": word_info.get('word', '').strip(),
                    "startMs": int((max(0, word_info['start'] - clip_start)) * 1000),
                    "endMs": int((max(0, word_info['end'] - clip_start)) * 1000),
                })

    duration_sec = clip_end - clip_start

    return {
        "captions": captions,
        "durationSec": duration_sec,
        "language": transcript.get('language', 'en'),
    }


@app.post("/api/reels/{job_id}/{clip_index}/captions/persist")
async def persist_captioned_reel(
    job_id: str,
    clip_index: int,
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id_header),
):
    caption_required_credits = 0.0
    if is_supabase_configured():
        caption_breakdown = estimate_caption_cost_usd(
            duration_minutes=3.0,
            video_size_gb=0.2,
            uses_assembly=True,
            uses_openai=True,
            uses_gemini=False,
        )
        caption_required_credits = calculate_credits_for_operation(caption_breakdown)["final_credits"]
        user_data = await supabase_get_user_data(user_id)
        available = float(user_data.get("credit", 0)) if user_data else 0.0
        if available < caption_required_credits:
            raise HTTPException(
                status_code=402,
                detail=f"Crédits insuffisants. Requis : {caption_required_credits} cr, disponible : {available} cr.",
            )

    if not file:
        raise HTTPException(status_code=400, detail="Missing rendered video file")

    content_type = str(file.content_type or "").lower()
    if content_type and not content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Invalid rendered video content type")

    metadata_path, data = await _get_or_build_job_metadata(job_id, clip_index)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail="Metadata not found")

    clips = data.get('shorts', [])
    if clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")

    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)

    upload_name = str(file.filename or "captioned.mp4")
    ext = os.path.splitext(upload_name)[1].lower()
    if ext not in {".mp4", ".mov", ".webm", ".mkv"}:
        ext = ".mp4"

    output_filename = f"captioned_{clip_index}_{int(time.time())}{ext}"
    output_path = os.path.join(output_dir, output_filename)

    try:
        with open(output_path, "wb") as handle:
            shutil.copyfileobj(file.file, handle)
    finally:
        await file.close()

    new_video_url = f"/videos/{job_id}/{output_filename}"

    job = jobs.get(job_id)
    if job and clip_index < len(job.get('result', {}).get('clips', [])):
        job['result']['clips'][clip_index]['video_url'] = new_video_url

    clips[clip_index]['video_url'] = new_video_url
    data['shorts'] = clips
    _persist_metadata_json(metadata_path, data)

    if is_supabase_configured() and caption_required_credits > 0:
        debited = await supabase_deduct_user_credits(user_id, caption_required_credits)
        if not debited:
            raise HTTPException(status_code=500, detail="Failed to debit credits for captions")
        await supabase_insert_user_data_history(
            user_id=user_id,
            credit=caption_required_credits,
            storage=0.0,
            operation="output",
            operation_type="reels",
            operation_id=f"{job_id}:captions:{clip_index}",
        )

    return {
        "success": True,
        "new_video_url": new_video_url,
        "persisted": True,
        "job_id": job_id,
        "clip_index": clip_index,
        "user_id": user_id,
    }


# --- Remotion Render Proxy ---
RENDER_SERVICE_URL = os.getenv("RENDER_SERVICE_URL", "http://renderer:3100")

@app.post("/api/render")
async def proxy_render(request: Request):
    """Proxy render requests to the Node.js Remotion render service."""
    import httpx
    body = await request.json()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{RENDER_SERVICE_URL}/render", json=body)
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Render service unavailable: {e}")

@app.get("/api/render/{render_id}")
async def proxy_render_status(render_id: str):
    """Proxy render status polling to the Node.js Remotion render service."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{RENDER_SERVICE_URL}/render/{render_id}")
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Render service unavailable: {e}")


class EffectsGenerateRequest(BaseModel):
    job_id: str
    clip_index: int
    input_filename: Optional[str] = None
    input_url: Optional[str] = None

@app.post("/api/effects/generate")
async def generate_effects_config(
    req: EffectsGenerateRequest,
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key")
):
    """Generate structured EffectsConfig JSON for Remotion rendering via Gemini AI."""
    final_api_key = x_gemini_key or os.environ.get("GEMINI_API_KEY")

    if not final_api_key:
        raise HTTPException(status_code=400, detail="Missing Gemini API Key (Header)")

    job = jobs.get(req.job_id)

    try:
        # Resolve input path
        if req.input_filename:
            safe_name = _sanitize_input_filename(req.input_filename)
            if not safe_name:
                raise HTTPException(status_code=400, detail="Invalid input filename")
            input_path = os.path.join(OUTPUT_DIR, req.job_id, safe_name)
            filename = safe_name
        else:
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            if 'result' not in job or 'clips' not in job['result']:
                raise HTTPException(status_code=400, detail="Job result not available")
            clip = job['result']['clips'][req.clip_index]
            filename = clip['video_url'].split('/')[-1]
            input_path = os.path.join(OUTPUT_DIR, req.job_id, filename)

        if not os.path.exists(input_path) and req.input_url:
            input_path, filename = _download_input_url_to_job_dir(req.input_url, req.job_id)

        if not os.path.exists(input_path):
            raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")

        os.makedirs(os.path.join(OUTPUT_DIR, req.job_id), exist_ok=True)

        def run_effects_generation():
            editor = VideoEditor(api_key=final_api_key)

            # Create safe ASCII filename to avoid encoding issues
            safe_filename = f"temp_effects_{req.job_id}.mp4"
            safe_input_path = os.path.join(OUTPUT_DIR, req.job_id, safe_filename)
            shutil.copy(input_path, safe_input_path)

            try:
                # Upload video to Gemini
                vid_file = editor.upload_video(safe_input_path)

                # Get video metadata via ffprobe
                probe_cmd = [
                    'ffprobe', '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height,r_frame_rate,duration',
                    '-show_entries', 'format=duration',
                    '-of', 'json',
                    safe_input_path
                ]
                probe_result = subprocess.check_output(probe_cmd).decode().strip()
                probe_data = json.loads(probe_result)

                stream = probe_data.get('streams', [{}])[0]
                width = int(stream.get('width', 1080))
                height = int(stream.get('height', 1920))

                # Parse fps from r_frame_rate (e.g. "30/1")
                r_frame_rate = stream.get('r_frame_rate', '30/1')
                num, den = r_frame_rate.split('/')
                fps = round(int(num) / int(den), 2)

                # Get duration from stream or format
                duration = float(stream.get('duration', 0))
                if duration == 0:
                    duration = float(probe_data.get('format', {}).get('duration', 0))

                # Load transcript from metadata
                transcript = None
                try:
                    meta_files = glob.glob(os.path.join(OUTPUT_DIR, req.job_id, "*_metadata.json"))
                    if meta_files:
                        with open(meta_files[0], 'r') as f:
                            data = json.load(f)
                            transcript = data.get('transcript')
                except Exception as e:
                    print(f"⚠️ Could not load transcript for effects config: {e}")

                # Generate effects config
                effects_config = editor.get_effects_config(
                    vid_file, duration, fps=fps, width=width, height=height, transcript=transcript
                )

                return effects_config
            finally:
                if os.path.exists(safe_input_path):
                    os.remove(safe_input_path)

        loop = asyncio.get_event_loop()
        effects_config = await loop.run_in_executor(None, run_effects_generation)

        if effects_config is None:
            raise HTTPException(status_code=500, detail="Failed to generate effects config from Gemini")

        return {"effects": effects_config}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Effects Generation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/subtitle")
async def add_subtitles(req: SubtitleRequest, user_id: str = Depends(get_user_id_header)):
    subtitle_required_credits = 0.0
    if is_supabase_configured():
        _sub_breakdown = estimate_caption_cost_usd(
            duration_minutes=3.0,
            video_size_gb=0.2,
            uses_assembly=True,
            uses_openai=True,
            uses_gemini=False,
        )
        subtitle_required_credits = calculate_credits_for_operation(_sub_breakdown)["final_credits"]
        _sub_user_data = await supabase_get_user_data(user_id)
        _sub_available = float(_sub_user_data.get("credit", 0)) if _sub_user_data else 0.0
        if _sub_available < subtitle_required_credits:
            raise HTTPException(
                status_code=402,
                detail=f"Crédits insuffisants. Requis : {subtitle_required_credits} cr, disponible : {_sub_available} cr.",
            )

    # Reload job data from disk just in case metadata was updated.
    # The in-memory job may be gone on the Reels page; metadata on disk is enough.
    job = jobs.get(req.job_id)

    # We need to access metadata.json to get the transcript
    output_dir = os.path.join(OUTPUT_DIR, req.job_id)
    metadata_path, data = await _get_or_build_job_metadata(req.job_id, req.clip_index, req.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail="Metadata not found")
        
    transcript = data.get('transcript')
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript not found in metadata. Please process a new video.")
        
    clips = data.get('shorts', [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")
        
    clip_data = clips[req.clip_index]
    
    # Video Path
    if req.input_filename:
        filename = _sanitize_input_filename(req.input_filename)
        if not filename:
            raise HTTPException(status_code=400, detail="Invalid input filename")
    else:
        # Fallback to standard naming
        filename = clip_data.get('video_url', '').split('/')[-1]
        if not filename:
             base_name = os.path.basename(metadata_path).replace('_metadata.json', '')
             filename = f"{base_name}_clip_{req.clip_index+1}.mp4"
         
    input_path = os.path.join(output_dir, filename)
    if not os.path.exists(input_path) and req.input_url:
        input_path, filename = _download_input_url_to_job_dir(req.input_url, req.job_id)

    if not os.path.exists(input_path):
        # Try looking for edited version if url implied it?
        # Just fail if not found.
        raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")
        
    # Define outputs
    srt_filename = f"subs_{req.clip_index}_{int(time.time())}.srt"
    srt_path = os.path.join(output_dir, srt_filename)
    
    # Output video
    # We create a new file "subtitled_..."
    output_filename = f"subtitled_{filename}"
    output_path = os.path.join(output_dir, output_filename)
    
    try:
        # 1. Generate SRT
        # Check if this is a dubbed video - if so, transcribe it fresh
        is_dubbed = filename.startswith("translated_")

        words_per_line = max(2, min(8, int(req.words_per_line or 4)))

        if is_dubbed:
            print(f"🎙️ Dubbed video detected, transcribing audio for subtitles...")
            def run_transcribe_srt():
                return generate_srt_from_video(input_path, srt_path, max_words_per_line=words_per_line)

            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, run_transcribe_srt)
        else:
            success = generate_srt(
                transcript,
                clip_data['start'],
                clip_data['end'],
                srt_path,
                max_words_per_line=words_per_line,
            )

        if not success:
             raise HTTPException(status_code=400, detail="No words found for this clip range.")

        # 2. Burn Subtitles
        # Run in thread pool
        def run_burn():
             style_options = SubtitleStyleOptions(
                 font_name=req.font_name,
                 font_color=req.font_color,
                 border_color=req.border_color,
                 border_width=req.border_width,
                 bg_color=req.bg_color,
                 bg_opacity=req.bg_opacity,
                 text_shadow_color=req.text_shadow_color,
                 shadow_blur=req.shadow_blur,
                 shadow_offset_x=req.shadow_offset_x,
                 shadow_offset_y=req.shadow_offset_y,
                 bold=req.bold,
                 italic=req.italic,
                 text_case=req.text_case,
             )
             burn_subtitles(
                 input_path,
                 srt_path,
                 output_path,
                 alignment=req.position,
                 fontsize=req.font_size,
                 style_options=style_options,
             )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_burn)
        
    except Exception as e:
        print(f"❌ Subtitle Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    # 3. Update Result and Metadata
    # Update InMemory Jobs (only if the job is still alive in memory)
    if job and req.clip_index < len(job.get('result', {}).get('clips', [])):
         job['result']['clips'][req.clip_index]['video_url'] = f"/videos/{req.job_id}/{output_filename}"
    
    # Update Metadata on Disk (Persistence)
    try:
        if req.clip_index < len(clips):
            clips[req.clip_index]['video_url'] = f"/videos/{req.job_id}/{output_filename}"
            # Update the main data structure
            data['shorts'] = clips
            
            # Write back
            _persist_metadata_json(metadata_path, data)
            print(f"✅ Metadata updated with subtitled video for clip {req.clip_index}")
    except Exception as e:
        print(f"⚠️ Failed to update metadata.json: {e}")
        # Non-critical, but good for persistence

    if is_supabase_configured() and subtitle_required_credits > 0:
        await supabase_deduct_user_credits(user_id, subtitle_required_credits)
        await supabase_insert_user_data_history(
            user_id=user_id,
            credit=subtitle_required_credits,
            storage=0.0,
            operation="output",
            operation_type="reels",
            operation_id=f"{req.job_id}:subtitle:{req.clip_index}",
        )

    return {
        "success": True,
        "new_video_url": f"/videos/{req.job_id}/{output_filename}"
    }

class HookRequest(BaseModel):
    job_id: str
    clip_index: int
    text: str
    input_filename: Optional[str] = None
    input_url: Optional[str] = None
    position: Optional[str] = "top" # top, center, bottom
    size: Optional[str] = "M" # S, M, L

@app.post("/api/hook")
async def add_hook(req: HookRequest, user_id: str = Depends(get_user_id_header)):
    hook_required_credits = max(1.0, round(DEFAULT_PUBLICATION_CREDITS * 0.5, 2))
    if is_supabase_configured():
        _hook_user_data = await supabase_get_user_data(user_id)
        _hook_available = float(_hook_user_data.get("credit", 0)) if _hook_user_data else 0.0
        if _hook_available < hook_required_credits:
            raise HTTPException(
                status_code=402,
                detail=f"Crédits insuffisants. Requis : {hook_required_credits} cr, disponible : {_hook_available} cr.",
            )

    job = jobs.get(req.job_id)
    output_dir = os.path.join(OUTPUT_DIR, req.job_id)
    metadata_path, data = await _get_or_build_job_metadata(req.job_id, req.clip_index, req.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail="Metadata not found")
        
    clips = data.get('shorts', [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")
        
    clip_data = clips[req.clip_index]
    
    # Video Path
    if req.input_filename:
        filename = _sanitize_input_filename(req.input_filename)
        if not filename:
            raise HTTPException(status_code=400, detail="Invalid input filename")
    else:
        filename = clip_data.get('video_url', '').split('/')[-1]
        if not filename:
             base_name = os.path.basename(metadata_path).replace('_metadata.json', '')
             filename = f"{base_name}_clip_{req.clip_index+1}.mp4"
         
    input_path = os.path.join(output_dir, filename)
    if not os.path.exists(input_path) and req.input_url:
        input_path, filename = _download_input_url_to_job_dir(req.input_url, req.job_id)

    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")
        
    # Output video
    output_filename = f"hook_{filename}"
    output_path = os.path.join(output_dir, output_filename)
    
    # Map Size to Scale
    size_map = {"S": 0.8, "M": 1.0, "L": 1.3}
    font_scale = size_map.get(req.size, 1.0)
    
    try:
        # Run in thread pool
        def run_hook():
             add_hook_to_video(input_path, req.text, output_path, position=req.position, font_scale=font_scale)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_hook)
        
    except Exception as e:
        print(f"❌ Hook Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    # Update Persistence (Same logic as subtitles)
    # Update InMemory Jobs
    if job and req.clip_index < len(job.get('result', {}).get('clips', [])):
         job['result']['clips'][req.clip_index]['video_url'] = f"/videos/{req.job_id}/{output_filename}"
    
    # Update Metadata on Disk
    try:
        if req.clip_index < len(clips):
            clips[req.clip_index]['video_url'] = f"/videos/{req.job_id}/{output_filename}"
            data['shorts'] = clips
            _persist_metadata_json(metadata_path, data)
            print(f"✅ Metadata updated with hook video for clip {req.clip_index}")
    except Exception as e:
        print(f"⚠️ Failed to update metadata.json: {e}")

    if is_supabase_configured() and hook_required_credits > 0:
        await supabase_deduct_user_credits(user_id, hook_required_credits)
        await supabase_insert_user_data_history(
            user_id=user_id,
            credit=hook_required_credits,
            storage=0.0,
            operation="output",
            operation_type="reels",
            operation_id=f"{req.job_id}:hook:{req.clip_index}",
        )

    return {
        "success": True,
        "new_video_url": f"/videos/{req.job_id}/{output_filename}"
    }

# --- Translation (subtitles-only, keep original voice) ---

class TranslateRequest(BaseModel):
    job_id: str
    clip_index: int
    target_language: str
    source_language: Optional[str] = None
    input_filename: Optional[str] = None
    input_url: Optional[str] = None

    # Subtitle style options (same spirit as SubtitleRequest)
    position: str = "bottom"  # top, middle, bottom
    font_size: int = 16
    font_name: str = "Verdana"
    font_color: str = "#FFFFFF"
    border_color: str = "#000000"
    border_width: int = 2
    bg_color: str = "#000000"
    bg_opacity: float = 0.0


def _srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _normalize_lang(lang: Optional[str]) -> str:
    if not lang:
        return ""
    l = lang.strip().lower()
    mapping = {
        "en-us": "en",
        "en-gb": "en",
        "fr-fr": "fr",
        "es-es": "es",
        "pt-br": "pt",
    }
    return mapping.get(l, l)


def _segment_to_text(segment: Dict) -> str:
    words = segment.get("words") or []
    if words:
        parts = []
        for w in words:
            t = (w.get("word") or "").strip()
            if t:
                parts.append(t)
        txt = " ".join(parts).strip()
        if txt:
            return txt
    return (segment.get("text") or "").strip()


def _load_clip_segments_from_metadata(data: Dict, clip_index: int) -> List[Dict]:
    transcript = data.get("transcript") or {}
    all_segments = transcript.get("segments") or []
    shorts = data.get("shorts") or []
    if not shorts:
        return []

    if clip_index < 0 or clip_index >= len(shorts):
        clip_index = min(max(clip_index, 0), len(shorts) - 1)

    clip = shorts[clip_index]
    clip_start = float(clip.get("start", 0))
    clip_end = float(clip.get("end", 0))

    selected = []
    for seg in all_segments:
        s = float(seg.get("start", 0))
        e = float(seg.get("end", 0))
        if e > clip_start and s < clip_end:
            # clip-relative timing
            rel_start = max(0.0, s - clip_start)
            rel_end = max(rel_start, e - clip_start)
            text = _segment_to_text(seg)
            if text:
                selected.append({
                    "start": rel_start,
                    "end": rel_end,
                    "text": text
                })
    return selected


def _translate_text_openai(text: str, source_lang: str, target_lang: str) -> str:
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_TRANSLATE_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    if not api_key or api_key == "your_openai_key":
        raise RuntimeError("OPENAI_API_KEY missing or placeholder")

    client = OpenAI(api_key=api_key)
    system = (
        "You are a professional subtitle translator. "
        "Translate naturally, keep meaning, keep short subtitle style, "
        "do not add commentary, return only translated text."
    )
    user = (
        f"Source language: {source_lang or 'auto'}\n"
        f"Target language: {target_lang}\n"
        f"Text:\n{text}"
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=600
    )
    out = (resp.choices[0].message.content or "").strip()
    if not out:
        raise RuntimeError("OpenAI returned empty translation")
    return out


def _translate_text_gemini(text: str, source_lang: str, target_lang: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_TRANSLATE_MODEL", os.environ.get("GEMINI_MODEL"))
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing")

    from google import genai
    client = genai.Client(api_key=api_key)

    prompt = (
        "You are a professional subtitle translator.\n"
        "Translate naturally, keep meaning, keep short subtitle style,\n"
        "do not add commentary, return only translated text.\n\n"
        f"Source language: {source_lang or 'auto'}\n"
        f"Target language: {target_lang}\n"
        "Text:\n"
        f"{text}"
    )

    resp = client.models.generate_content(
        model=model,
        contents=prompt
    )
    out = (resp.text or "").strip()
    if not out:
        raise RuntimeError("Gemini returned empty translation")
    return out


def _get_translation_cache(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    cache = data.get("translation_cache")
    if not isinstance(cache, dict):
        cache = {}
        data["translation_cache"] = cache
    return cache


def _build_translation_cache_key(source_lang: str, target_lang: str, text: str) -> str:
    normalized_source = _normalize_lang(source_lang) or "auto"
    normalized_target = _normalize_lang(target_lang)
    normalized_text = " ".join((text or "").split())
    digest = hashlib.sha256(
        f"{normalized_source}:{normalized_target}:{normalized_text}".encode("utf-8")
    ).hexdigest()
    return f"{normalized_source}:{normalized_target}:{digest}"


def _persist_metadata_json(metadata_path: str, data: Dict[str, Any]) -> None:
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _translate_segments_with_fallback(segments: List[Dict], source_lang: str, target_lang: str) -> List[Dict]:
    translated = []
    for seg in segments:
        src_text = seg["text"]
        try:
            # Primary: OpenAI
            dst = _translate_text_openai(src_text, source_lang, target_lang)
            provider = "openai"
        except Exception as e_openai:
            print(f"⚠️ OpenAI translation failed, fallback Gemini. Reason: {e_openai}")
            # Fallback: Gemini
            dst = _translate_text_gemini(src_text, source_lang, target_lang)
            provider = "gemini"

        translated.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": dst,
            "provider": provider,
        })
    return translated


def _translate_segments_with_cache(
    segments: List[Dict],
    source_lang: str,
    target_lang: str,
    translation_cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple[List[Dict], Dict[str, int]]:
    translated: List[Dict] = []
    cache_hits = 0
    cache_misses = 0
    cache_store = translation_cache if isinstance(translation_cache, dict) else None

    for seg in segments:
        src_text = seg.get("text") or ""
        cache_key = _build_translation_cache_key(source_lang, target_lang, src_text)
        cached_entry = cache_store.get(cache_key) if cache_store is not None else None

        if isinstance(cached_entry, dict) and (cached_entry.get("text") or "").strip():
            translated.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": cached_entry["text"],
                "provider": cached_entry.get("provider") or "cache",
            })
            cache_hits += 1
            continue

        translated_segment = _translate_segments_with_fallback([seg], source_lang, target_lang)[0]
        translated.append(translated_segment)
        cache_misses += 1

        if cache_store is not None:
            cache_store[cache_key] = {
                "text": translated_segment["text"],
                "provider": translated_segment.get("provider") or "unknown",
                "source_language": _normalize_lang(source_lang) or "auto",
                "target_language": _normalize_lang(target_lang),
                "cached_at": int(time.time()),
            }

    return translated, {"hits": cache_hits, "misses": cache_misses}


def _translated_segments_to_caption_words(segments: List[Dict]) -> List[Dict]:
    captions: List[Dict] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue

        words = [token for token in text.split() if token]
        if not words:
            continue

        start_ms = int(round(float(seg.get("start", 0)) * 1000))
        end_ms = int(round(float(seg.get("end", 0)) * 1000))
        if end_ms <= start_ms:
            end_ms = start_ms + 200

        total_duration_ms = max(1, end_ms - start_ms)
        step_ms = max(1, total_duration_ms // len(words))

        for index, word in enumerate(words):
            word_start_ms = start_ms + (index * step_ms)
            if index == len(words) - 1:
                word_end_ms = end_ms
            else:
                word_end_ms = min(end_ms, start_ms + ((index + 1) * step_ms))
            if word_end_ms <= word_start_ms:
                word_end_ms = word_start_ms + 1

            captions.append({
                "text": word,
                "startMs": word_start_ms,
                "endMs": word_end_ms,
            })

    return captions


def _write_translated_srt(segments: List[Dict], srt_path: str) -> bool:
    if not segments:
        return False
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            f.write(f"{i}\n")
            f.write(f"{_srt_timestamp(seg['start'])} --> {_srt_timestamp(seg['end'])}\n")
            f.write(f"{seg['text'].strip()}\n\n")
    return True


@app.get("/api/translate/languages")
async def get_languages():
    """
    Return supported languages.
    Kept for frontend compatibility.
    """
    # You can expand this list if needed.
    return {
        "languages": [
            {"code": "en", "name": "English"},
            {"code": "fr", "name": "French"},
            {"code": "es", "name": "Spanish"},
            {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "nl", "name": "Dutch"},
            {"code": "ar", "name": "Arabic"},
            {"code": "hi", "name": "Hindi"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"},
            {"code": "zh", "name": "Chinese"},
            {"code": "ru", "name": "Russian"},
            {"code": "tr", "name": "Turkish"},
            {"code": "id", "name": "Indonesian"},
        ]
    }


@app.post("/api/translate/captions")
async def translate_captions(req: TranslateRequest):
    """Translate reel transcript into Remotion-friendly timed word captions."""
    metadata_path, data = await _get_or_build_job_metadata(req.job_id, req.clip_index, req.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail="Metadata not found")
    translation_cache = _get_translation_cache(data)

    clips = data.get("shorts", [])
    if not clips:
        raise HTTPException(status_code=404, detail="Clip not found")

    normalized_clip_index = req.clip_index
    if normalized_clip_index < 0 or normalized_clip_index >= len(clips):
        normalized_clip_index = min(max(normalized_clip_index, 0), len(clips) - 1)

    clip_data = clips[normalized_clip_index]
    source_lang = _normalize_lang(req.source_language) or _normalize_lang((data.get("transcript") or {}).get("language"))
    target_lang = _normalize_lang(req.target_language)
    if not target_lang:
        raise HTTPException(status_code=400, detail="target_language is required")

    source_segments = _load_clip_segments_from_metadata(data, normalized_clip_index)
    if not source_segments:
        raise HTTPException(status_code=400, detail="No transcript segments found for this clip range")

    def run_translate_segments():
        return _translate_segments_with_cache(source_segments, source_lang, target_lang, translation_cache)

    loop = asyncio.get_event_loop()
    translated_segments, cache_stats = await loop.run_in_executor(None, run_translate_segments)

    if cache_stats["misses"] > 0:
        try:
            _persist_metadata_json(metadata_path, data)
        except Exception as e:
            print(f"⚠️ Failed to persist translation cache: {e}")

    captions = _translated_segments_to_caption_words(translated_segments)
    if not captions:
        raise HTTPException(status_code=500, detail="Failed to build translated captions")

    providers = sorted({seg.get("provider", "unknown") for seg in translated_segments if seg.get("provider")})

    return {
        "success": True,
        "mode": "remotion_subtitles",
        "captions": captions,
        "durationSec": max(0, float(clip_data.get("end", 0)) - float(clip_data.get("start", 0))),
        "source_language": source_lang or "auto",
        "target_language": target_lang,
        "providers": providers,
        "cache": cache_stats,
    }


@app.post("/api/translate")
async def translate_clip(req: TranslateRequest):
    """
    Translate subtitles only (OpenAI first, Gemini fallback),
    keep original voice/audio track unchanged.
    """
    job = jobs.get(req.job_id)
    output_dir = os.path.join(OUTPUT_DIR, req.job_id)
    metadata_path, data = await _get_or_build_job_metadata(req.job_id, req.clip_index, req.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail="Metadata not found")
    translation_cache = _get_translation_cache(data)

    clips = data.get("shorts", [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")

    clip_data = clips[req.clip_index]

    # Resolve input video path
    if req.input_filename:
        filename = _sanitize_input_filename(req.input_filename)
        if not filename:
            raise HTTPException(status_code=400, detail="Invalid input filename")
    else:
        filename = clip_data.get("video_url", "").split("/")[-1]
        if not filename:
            base_name = os.path.basename(metadata_path).replace("_metadata.json", "")
            filename = f"{base_name}_clip_{req.clip_index+1}.mp4"

    input_path = os.path.join(output_dir, filename)
    if not os.path.exists(input_path) and req.input_url:
        input_path, filename = _download_input_url_to_job_dir(req.input_url, req.job_id)

    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")

    # Load clip transcript segments from existing metadata transcript (no re-transcription)
    source_lang = _normalize_lang(req.source_language) or _normalize_lang((data.get("transcript") or {}).get("language"))
    target_lang = _normalize_lang(req.target_language)
    if not target_lang:
        raise HTTPException(status_code=400, detail="target_language is required")

    source_segments = _load_clip_segments_from_metadata(data, req.clip_index)
    if not source_segments:
        raise HTTPException(status_code=400, detail="No transcript segments found for this clip range")

    try:
        # 1) Translate text segments (OpenAI primary, Gemini fallback)
        def run_translate_segments():
            return _translate_segments_with_cache(source_segments, source_lang, target_lang, translation_cache)

        loop = asyncio.get_event_loop()
        translated_segments, cache_stats = await loop.run_in_executor(None, run_translate_segments)

        # 2) Write translated SRT
        base, ext = os.path.splitext(filename)
        srt_filename = f"translated_subs_{target_lang}_{req.clip_index}_{int(time.time())}.srt"
        srt_path = os.path.join(output_dir, srt_filename)

        if not _write_translated_srt(translated_segments, srt_path):
            raise HTTPException(status_code=500, detail="Failed to write translated SRT")

        # 3) Burn subtitles on original video (audio unchanged)
        output_filename = f"translated_{target_lang}_{base}{ext}"
        output_path = os.path.join(output_dir, output_filename)

        def run_burn():
            style_options = SubtitleStyleOptions(
                font_name=req.font_name,
                font_color=req.font_color,
                border_color=req.border_color,
                border_width=req.border_width,
                bg_color=req.bg_color,
                bg_opacity=req.bg_opacity,
            )
            burn_subtitles(
                input_path,
                srt_path,
                output_path,
                alignment=req.position,
                fontsize=req.font_size,
                style_options=style_options,
            )

        await loop.run_in_executor(None, run_burn)

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Translation(subtitles-only) Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Update in-memory job result if the job is still alive in memory.
    if job and req.clip_index < len(job.get("result", {}).get("clips", [])):
        job["result"]["clips"][req.clip_index]["video_url"] = f"/videos/{req.job_id}/{output_filename}"

    # Persist metadata
    try:
        if req.clip_index < len(clips):
            clips[req.clip_index]["video_url"] = f"/videos/{req.job_id}/{output_filename}"
            clips[req.clip_index]["translated_subtitles_language"] = target_lang
            data["shorts"] = clips
            _persist_metadata_json(metadata_path, data)
            print(f"✅ Metadata updated with translated-subtitle video for clip {req.clip_index}")
    except Exception as e:
        print(f"⚠️ Failed to update metadata.json: {e}")

    return {
        "success": True,
        "mode": "subtitles_only",
        "new_video_url": f"/videos/{req.job_id}/{output_filename}",
        "srt_url": f"/videos/{req.job_id}/{srt_filename}",
        "source_language": source_lang or "auto",
        "target_language": target_lang,
        "cache": cache_stats,
    }


class SocialPostRequest(BaseModel):
    job_id: str
    clip_index: int
    user_id: Optional[str] = None
    platforms: Optional[List[str]] = None # ["tiktok", "instagram", "youtube"]
    # Optional overrides if frontend wants to edit them
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: Optional[str] = None # ISO-8601 string
    timezone: Optional[str] = "UTC"

import httpx


def _resolve_request_user_id(explicit_user_id: Optional[str], user_id: str) -> str:
    resolved = (explicit_user_id or user_id or "").strip()
    if not resolved:
        raise HTTPException(status_code=400, detail="Missing user id (user_id body field or X-User-Id header)")
    return resolved


def _resolve_social_platforms(platforms: Optional[List[str]]) -> List[str]:
    allowed = {"tiktok", "instagram", "youtube", "facebook", "linkedin"}
    candidate = [p.strip().lower() for p in (platforms or []) if isinstance(p, str) and p.strip()]
    if not candidate:
        env_value = os.getenv("SOCIAL_DEFAULT_PLATFORMS", "tiktok,instagram,youtube")
        candidate = [p.strip().lower() for p in env_value.split(",") if p.strip()]

    deduped = []
    for p in candidate:
        if p in allowed and p not in deduped:
            deduped.append(p)
    if not deduped:
        raise HTTPException(status_code=400, detail="No valid social platforms selected")
    return deduped


def _resolve_local_video_path(job_id: str, video_ref: str, clip_index: int) -> str:
    ref = (video_ref or "").split("?")[0]
    filename = ref.split("/")[-1] or f"{job_id}_{clip_index + 1}.mp4"
    candidate = os.path.join(OUTPUT_DIR, job_id, filename)
    if not os.path.exists(candidate):
        raise HTTPException(status_code=404, detail=f"Video file not found: {candidate}")
    return candidate


def _resolve_public_video_url(video_ref: str, request: Request, job_id: str, clip_index: int) -> str:
    ref = (video_ref or "").strip()
    if ref.startswith(("https://", "http://")):
        return ref
    if not ref:
        raise HTTPException(status_code=404, detail="Video URL not found for this clip")

    if ref.startswith("/"):
        base_url = SOCIAL_BASE_URL or str(request.base_url).rstrip("/")
        return f"{base_url}{ref}"

    # Fallback to built-in static route pattern.
    base_url = SOCIAL_BASE_URL or str(request.base_url).rstrip("/")
    return f"{base_url}/videos/{job_id}/{ref}"

@app.post("/api/social/post")
async def post_to_socials(req: SocialPostRequest, request: Request):
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[req.job_id]
    if 'result' not in job or 'clips' not in job['result']:
        raise HTTPException(status_code=400, detail="Job result not available")
        
    selected_platforms = _resolve_social_platforms(req.platforms)
    user_id = _resolve_request_user_id(req.user_id, request)
    publish_priority = await _resolve_user_job_priority(user_id)

    try:
        clip = job['result']['clips'][req.clip_index]
    except Exception:
        raise HTTPException(status_code=404, detail="Clip not found")

    video_ref = str(clip.get('video_url') or '').strip()
    if not video_ref:
        raise HTTPException(status_code=404, detail="Video URL not found for this clip")

    local_video_path = _resolve_local_video_path(req.job_id, video_ref, req.clip_index)
    public_video_url = _resolve_public_video_url(video_ref, request, req.job_id, req.clip_index)

    final_title = req.title or clip.get('video_title_for_youtube_short') or clip.get('title') or 'Vireel Short'
    final_description = req.description or clip.get('video_description_for_instagram') or clip.get('video_description_for_tiktok') or "Check this out!"

    results: Dict[str, Any] = {}
    overall_success = True

    for platform_name in selected_platforms:
        try:
            account = await _get_social_account(user_id, platform_name)
            if not account:
                raise HTTPException(status_code=404, detail=f"No connected {platform_name} account found")

            if platform_name in {"tiktok", "instagram"} and not public_video_url.startswith(("https://", "http://")):
                raise HTTPException(status_code=400, detail=f"{platform_name} requires a public video URL")

            publish_payload = PublishRequest(
                user_id=user_id,
                title=final_title,
                description=final_description,
                text=final_description,
                caption=final_description,
                video_url=public_video_url,
                video_file=local_video_path,
            )

            platform_result = await publish_post(account, publish_payload)
            external_id = str(platform_result.get("publish_id") or platform_result.get("id") or platform_result.get("video_id") or "n/a")
            await _insert_publish_job(user_id=user_id, platform=platform_name, external_id=external_id, status="done", priority=publish_priority)
            results[platform_name] = {
                "success": True,
                "result": platform_result,
            }
        except Exception as exc:
            overall_success = False
            err_msg = str(exc)
            await _insert_publish_job(user_id=user_id, platform=platform_name, external_id="n/a", status="failed", error_message=err_msg, priority=publish_priority)
            results[platform_name] = {
                "success": False,
                "error": err_msg,
            }

    return {
        "success": overall_success,
        "results": results,
    }


# --- Thumbnail Studio Endpoints ---

@app.post("/api/thumbnail/upload")
async def thumbnail_upload(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
):
    """Upload video and start background Whisper transcription immediately."""
    if not url and not file:
        raise HTTPException(status_code=400, detail="Must provide URL or File")

    session_id = str(uuid.uuid4())
    transcript_event = asyncio.Event()

    # Save file if uploaded directly
    video_path = None
    if file:
        video_path = os.path.join(UPLOAD_DIR, f"thumb_{session_id}_{file.filename}")
        with open(video_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

    # Initialize session
    thumbnail_sessions[session_id] = {
        "video_path": video_path,
        "transcript_event": transcript_event,
        "transcript_ready": False,
        "transcript": None,
        "transcript_segments": [],
        "video_duration": 0,
        "language": "en",
        "context": "",
        "titles": [],
        "conversation": [],
        "_url": url,  # Store URL for deferred download
    }

    async def run_background_whisper():
        try:
            vpath = video_path
            # Download YouTube video if URL was provided
            if not vpath and url:
                from main import download_youtube_video
                loop = asyncio.get_event_loop()
                vpath, _ = await loop.run_in_executor(None, download_youtube_video, url, UPLOAD_DIR)
                thumbnail_sessions[session_id]["video_path"] = vpath

            from main import transcribe_video
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(None, transcribe_video, vpath)
            segments = transcript.get("segments", [])
            duration = segments[-1]["end"] if segments else 0

            thumbnail_sessions[session_id].update({
                "transcript_ready": True,
                "transcript": transcript,
                "transcript_segments": segments,
                "video_duration": duration,
                "language": transcript.get("language", "en"),
            })
            print(f"✅ [Thumbnail] Background Whisper complete for session {session_id}")
        except Exception as e:
            print(f"❌ [Thumbnail] Background Whisper failed: {e}")
            thumbnail_sessions[session_id]["transcript_error"] = str(e)
        finally:
            transcript_event.set()

    asyncio.create_task(run_background_whisper())

    return {"session_id": session_id}


@app.post("/api/thumbnail/analyze")
async def thumbnail_analyze(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key")
):
    """Analyze a video and suggest viral YouTube titles."""
    # Use .env configuration (ignore header for security)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key not configured on server (.env)")

    pre_transcript = None

    # Check for pre-existing session with background Whisper
    if session_id and session_id in thumbnail_sessions:
        session = thumbnail_sessions[session_id]

        # Wait for background Whisper to complete
        transcript_event = session.get("transcript_event")
        if transcript_event:
            print(f"⏳ [Thumbnail] Waiting for background Whisper to finish...")
            await transcript_event.wait()

        if session.get("transcript_error"):
            raise HTTPException(status_code=500, detail=f"Transcription failed: {session['transcript_error']}")

        video_path = session["video_path"]
        if not video_path or not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video file not found in session")

        if session.get("transcript_ready"):
            pre_transcript = session["transcript"]
    else:
        # No pre-existing session — need file or URL
        if not url and not file:
            raise HTTPException(status_code=400, detail="Must provide URL, File, or session_id")

        session_id = str(uuid.uuid4())

        if url:
            from main import download_youtube_video
            video_path, _ = download_youtube_video(url, UPLOAD_DIR)
        else:
            video_path = os.path.join(UPLOAD_DIR, f"thumb_{session_id}_{file.filename}")
            with open(video_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

    try:
        # Run analysis in thread pool (skips Whisper if pre_transcript is available)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, analyze_video_for_titles, api_key, video_path, pre_transcript)

        # Store/update session context
        if session_id not in thumbnail_sessions:
            thumbnail_sessions[session_id] = {}

        thumbnail_sessions[session_id].update({
            "context": result.get("transcript_summary", ""),
            "titles": result.get("titles", []),
            "language": result.get("language", "en"),
            "conversation": thumbnail_sessions[session_id].get("conversation", []),
            "video_path": video_path,
            "transcript_segments": result.get("segments", []),
            "video_duration": result.get("video_duration", 0)
        })

        return {
            "session_id": session_id,
            "titles": result.get("titles", []),
            "context": result.get("transcript_summary", ""),
            "language": result.get("language", "en"),
            "recommended": result.get("recommended", [])
        }

    except Exception as e:
        print(f"❌ Thumbnail Analyze Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ThumbnailTitlesRequest(BaseModel):
    session_id: Optional[str] = None
    message: Optional[str] = None
    title: Optional[str] = None

@app.post("/api/thumbnail/titles")
async def thumbnail_titles(
    req: ThumbnailTitlesRequest,
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key")
):
    """Refine title suggestions or accept a manual title."""
    # Use .env configuration (ignore header for security)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key not configured on server (.env)")

    # Manual title mode - just create a session with the user's title
    if req.title:
        session_id = req.session_id or str(uuid.uuid4())
        if session_id not in thumbnail_sessions:
            thumbnail_sessions[session_id] = {
                "context": "",
                "titles": [req.title],
                "language": "en",
                "conversation": []
            }
        return {"session_id": session_id, "titles": [req.title]}

    # Refinement mode
    if not req.session_id or req.session_id not in thumbnail_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    if not req.message:
        raise HTTPException(status_code=400, detail="Must provide message or title")

    session = thumbnail_sessions[req.session_id]

    # Add user message to conversation history
    session["conversation"].append({"role": "user", "content": req.message})

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            refine_titles,
            api_key,
            session["context"],
            req.message,
            session["conversation"]
        )

        new_titles = result.get("titles", [])
        session["titles"] = new_titles
        session["conversation"].append({"role": "assistant", "content": json.dumps(new_titles)})

        return {"titles": new_titles}

    except Exception as e:
        print(f"❌ Thumbnail Titles Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/thumbnail/generate")
async def thumbnail_generate(
    request: Request,
    session_id: str = Form(...),
    title: str = Form(...),
    extra_prompt: str = Form(""),
    count: int = Form(3),
    face: Optional[UploadFile] = File(None),
    background: Optional[UploadFile] = File(None),
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key")
):
    """Generate YouTube thumbnails with Gemini image generation."""
    # Use .env configuration (ignore header for security)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key not configured on server (.env)")

    # Clamp count
    count = min(max(1, count), 6)

    # Save optional uploaded images
    face_path = None
    bg_path = None
    thumb_upload_dir = os.path.join(UPLOAD_DIR, f"thumb_{session_id}")
    os.makedirs(thumb_upload_dir, exist_ok=True)

    try:
        if face and face.filename:
            face_path = os.path.join(thumb_upload_dir, f"face_{face.filename}")
            with open(face_path, "wb") as f:
                f.write(await face.read())

        if background and background.filename:
            bg_path = os.path.join(thumb_upload_dir, f"bg_{background.filename}")
            with open(bg_path, "wb") as f:
                f.write(await background.read())

        # Get video context from session (transcript summary from analysis step)
        video_context = ""
        if session_id in thumbnail_sessions:
            video_context = thumbnail_sessions[session_id].get("context", "")

        # Run generation in thread pool
        loop = asyncio.get_event_loop()
        thumbnails = await loop.run_in_executor(
            None,
            generate_thumbnail,
            api_key,
            title,
            session_id,
            face_path,
            bg_path,
            extra_prompt,
            count,
            video_context
        )

        if not thumbnails:
            raise HTTPException(status_code=500, detail="Thumbnail generation failed. Please check your Gemini API key has access to image generation (gemini-3.1-flash-image-preview model).")

        return {"thumbnails": thumbnails}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Thumbnail Generate Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ThumbnailDescribeRequest(BaseModel):
    session_id: str
    title: str

@app.post("/api/thumbnail/describe")
async def thumbnail_describe(
    req: ThumbnailDescribeRequest,
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key")
):
    """Generate a YouTube description with chapters from the transcript."""
    # Use .env configuration (ignore header for security)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key not configured on server (.env)")

    if req.session_id not in thumbnail_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = thumbnail_sessions[req.session_id]
    segments = session.get("transcript_segments", [])
    if not segments:
        raise HTTPException(status_code=400, detail="No transcript segments available. Please analyze a video first.")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            generate_youtube_description,
            api_key,
            req.title,
            segments,
            session.get("language", "en"),
            session.get("video_duration", 0)
        )
        return {"description": result.get("description", "")}

    except Exception as e:
        print(f"❌ Thumbnail Describe Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/thumbnail/publish")
async def thumbnail_publish(
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    thumbnail_url: str = Form(...),
    user_id: str = Form(...),
):
    """Kick off a background upload to YouTube using the user's connected social account."""
    if session_id not in thumbnail_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = thumbnail_sessions[session_id]
    video_path = session.get("video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Original video file not found")

    # Resolve thumbnail path from URL (kept for future YouTube thumbnail API support)
    thumb_relative = thumbnail_url.lstrip("/")
    if thumb_relative.startswith("thumbnails/"):
        thumb_path = os.path.join(OUTPUT_DIR, thumb_relative)
    else:
        thumb_path = os.path.join(THUMBNAILS_DIR, thumb_relative)

    if not os.path.exists(thumb_path):
        raise HTTPException(status_code=404, detail=f"Thumbnail file not found: {thumb_path}")

    # Generate a unique ID for this publish job so the frontend can poll
    publish_id = str(uuid.uuid4())
    publish_jobs[publish_id] = {"status": "uploading", "result": None, "error": None}

    def do_upload():
        """Runs in a thread via BackgroundTasks — does the actual multipart upload."""
        try:
            print(f"📡 [Thumbnail] Publishing to YouTube with connected account... (publish_id={publish_id})")

            account = asyncio.run(_get_social_account(user_id, "youtube"))
            if not account:
                raise RuntimeError("No connected youtube account found")

            payload = PublishRequest(
                user_id=user_id,
                title=title,
                description=description,
                text=description,
                video_file=video_path,
            )
            result = asyncio.run(publish_post(account, payload))
            publish_jobs[publish_id]["status"] = "done"
            publish_jobs[publish_id]["result"] = result
            external_id = str(result.get("video_id") or result.get("id") or "n/a")
            publish_priority = asyncio.run(_resolve_user_job_priority(user_id))
            asyncio.run(_insert_publish_job(user_id=user_id, platform="youtube", external_id=external_id, status="done", priority=publish_priority))

        except Exception as e:
            err = str(e)
            print(f"❌ Thumbnail Publish Background Error: {err}")
            publish_jobs[publish_id]["status"] = "failed"
            publish_jobs[publish_id]["error"] = err

    background_tasks.add_task(do_upload)
    return {"publish_id": publish_id, "status": "uploading"}


@app.get("/api/thumbnail/publish/status/{publish_id}")
async def thumbnail_publish_status(publish_id: str):
    """Poll the status of a background publish job."""
    if publish_id not in publish_jobs:
        raise HTTPException(status_code=404, detail="Publish job not found")
    return publish_jobs[publish_id]


# --- Reels API (Supabase-backed only) ---


class ReelShareRequest(BaseModel):
    platforms: Optional[List[str]] = None
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: Optional[str] = None
    timezone: Optional[str] = "UTC"



class StripeCheckoutRequest(BaseModel):
    plan_id: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


def _require_stripe_ready() -> None:
    if stripe is None:
        raise HTTPException(status_code=503, detail="Stripe SDK not installed on server")
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")


def _frontend_base_url(request: Request) -> str:
    configured = os.environ.get("FRONTEND_URL", "").strip().rstrip("/")
    if configured:
        return configured
    origin = request.headers.get("origin", "").strip().rstrip("/")
    if origin:
        return origin
    return "http://localhost:5175"


@app.post("/api/stripe/checkout-session")
async def create_stripe_checkout_session(
    request: Request,
    payload: StripeCheckoutRequest,
    user_id: str = Depends(get_user_id_header),   # ✅ ici, dans la signature
):
    """Create a hosted Stripe Checkout session for a subscription plan."""
    _require_stripe_ready()

    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    plan = await supabase_get_abonnement(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    try:
        unit_amount = int(round(float(plan.get("price") or 0) * 100))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid plan price")

    if unit_amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid plan price")

    default_base_url = _frontend_base_url(request)
    success_url = (payload.success_url or STRIPE_SUCCESS_URL or f"{default_base_url}/dashboard/abonnement?payment=success").strip()
    cancel_url = (payload.cancel_url or STRIPE_CANCEL_URL or f"{default_base_url}/dashboard/abonnement?payment=cancel").strip()

    metadata = {
        "userid": user_id,
        "abonnement": str(plan.get("id")),
        "plan_name": str(plan.get("name") or ""),
        "payment_mode": "stripe",
    }

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=request.headers.get("X-User-Email") or None,
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": STRIPE_CURRENCY,
                        "unit_amount": unit_amount,
                        "product_data": {
                            "name": str(plan.get("name") or "Abonnement"),
                            "description": "Abonnement mensuel (1 mois)",
                            "tax_code": "txcd_10103001",
                        },
                    },
                }
            ],
            metadata=metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe checkout error: {exc}")

    return {"checkout_url": session.url, "session_id": session.id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_and_parse_event(payload: bytes, signature: str) -> stripe.Event:
    """Validate the Stripe signature and return the parsed event."""
    try:
        return stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature") from exc


def _extract_session_context(session: "stripe.checkout.Session") -> dict:
    """Pull out everything the handlers need from a checkout session, as plain Python types."""
    metadata = session.metadata.to_dict() if session.metadata else {}
    created_ts = session.created

    return {
        "metadata": metadata,
        "user_id": metadata.get("userid"),
        "payment_mode": metadata.get("payment_mode", "stripe"),
        "amount_total": (session.amount_total or 0) / 100,
        "payment_reference": session.payment_intent or session.id or "",
        "payment_date": (
            datetime.fromtimestamp(int(created_ts), tz=timezone.utc)
            if created_ts
            else datetime.now(timezone.utc)
        ),
        "session_id": session.id,
        "customer_email": (
            (session.customer_details.email if session.customer_details else None)
            or session.customer_email
        ),
    }


def _send_payment_confirmation_email(to_email: str, amount_total: float, label: str) -> None:
    """Send a payment confirmation email via SendGrid. Never raises — a failed email
    must not fail the webhook (Stripe would retry it forever otherwise)."""
    if not to_email:
        logger.warning("Skipping payment confirmation email: no customer email on session")
        return
    if not SENDGRID_API_KEY:
        logger.warning("Skipping payment confirmation email: SENDGRID_API_KEY is not configured")
        return

    message = Mail(
        from_email=SENDGRID_FROM_EMAIL,
        to_emails=to_email,
        subject="Confirmation de votre paiement",
        html_content=(
            f"<p>Bonjour,</p>"
            f"<p>Nous confirmons la réception de votre paiement de "
            f"<strong>{amount_total:.2f} €</strong> pour : {label}.</p>"
            f"<p>Merci pour votre confiance !</p>"
        ),
    )
    if SENDGRID_PAYMENT_CONFIRMATION_TEMPLATE_ID:
        message.template_id = SENDGRID_PAYMENT_CONFIRMATION_TEMPLATE_ID
        message.dynamic_template_data = {
            "amount_total": f"{amount_total:.2f}",
            "label": label,
        }

    try:
        SendGridAPIClient(SENDGRID_API_KEY).send(message)
    except Exception:
        # Log and swallow: email failure should never turn a successful payment
        # into a 500, which would make Stripe retry the whole webhook.
        logger.exception("Failed to send payment confirmation email to %s", to_email)


async def _handle_credit_purchase(ctx: dict) -> dict:
    """Handle a one-off credit purchase (payment_mode == 'stripe_credits')."""
    if await supabase_get_souscription_by_reference(ctx["payment_reference"]):
        return {"received": True, "duplicate": True}

    policy_state = await _enforce_subscription_retention_policy(ctx["user_id"])
    if policy_state.get("state") != "active":
        return {
            "received": True,
            "ignored": "no_active_subscription",
            "policy_state": policy_state.get("state"),
        }

    credits_to_add = float(ctx["metadata"].get("credits_to_add", 0))
    if credits_to_add <= 0:
        credits_to_add = usd_to_credits(ctx["amount_total"])

    await supabase_insert_souscription(
        user_id=ctx["user_id"],
        abonnement=None,
        payment_mode="stripe_credits",
        payment_amount=ctx["amount_total"],
        payment_reference=ctx["payment_reference"],
        payment_status="completed",
        payment_comment=f"Credit purchase {credits_to_add} credits",
        payment_date=ctx["payment_date"],
    )
    await supabase_upsert_user_data_credits(
        user_id=ctx["user_id"],
        credit_delta=credits_to_add,
        update_credit_max=True,
    )
    await supabase_insert_user_data_history(
        user_id=ctx["user_id"],
        credit=credits_to_add,
        storage=0.0,
        operation="input",
        operation_type="credit_purchase",
        operation_id=ctx["payment_reference"],
    )
    _send_payment_confirmation_email(
        to_email=ctx["customer_email"],
        amount_total=ctx["amount_total"],
        label=f"{credits_to_add:.0f} crédits",
    )
    return {"received": True, "credits_added": credits_to_add}


async def _allocate_plan_resources(user_id: str, abonnement: str, payment_reference: str, souscription_id: str) -> None:
    """Credit the user's account with whatever the plan grants (credits + storage)."""
    plan = await supabase_get_abonnement(abonnement)
    if not plan:
        return

    plan_credit = float(plan.get("credit") or 0)
    plan_storage = float(plan.get("stockage") or 0)

    # A new/changed plan resets monthly allowances and their maxima to the plan limits.
    await supabase_set_user_data_balance(
        user_id=user_id,
        credit=plan_credit,
        storage=plan_storage,
        credit_max=plan_credit,
        storage_max=plan_storage,
    )
    await supabase_insert_user_data_history(
        user_id=user_id,
        credit=plan_credit,
        storage=plan_storage,
        operation="input",
        operation_type="subscription",
        operation_id=souscription_id or payment_reference,
    )


async def _handle_subscription_purchase(ctx: dict) -> dict:
    """Handle a standard plan subscription checkout."""
    abonnement = ctx["metadata"].get("abonnement")
    if not abonnement:
        raise HTTPException(status_code=400, detail="Missing subscription metadata")

    if await supabase_get_souscription_by_reference(ctx["payment_reference"]):
        return {"received": True, "duplicate": True}

    new_souscription = await supabase_insert_souscription(
        user_id=ctx["user_id"],
        abonnement=abonnement,
        payment_mode="stripe",
        payment_amount=ctx["amount_total"],
        payment_reference=ctx["payment_reference"],
        payment_status="completed",
        payment_comment=f"Stripe checkout session {ctx['session_id']}".strip(),
        payment_date=ctx["payment_date"],
    )

    await _allocate_plan_resources(
        user_id=ctx["user_id"],
        abonnement=abonnement,
        payment_reference=ctx["payment_reference"],
        souscription_id=str(new_souscription.get("id") or ctx["payment_reference"]),
    )
    _send_payment_confirmation_email(
        to_email=ctx["customer_email"],
        amount_total=ctx["amount_total"],
        label=f"l'abonnement {abonnement}",
    )
    return {"received": True}


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe checkout.session.completed events and persist the result."""
    _require_stripe_ready()
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    event = _verify_and_parse_event(payload, signature)

    if event.type != "checkout.session.completed":
        return {"received": True, "ignored": event.type}

    ctx = _extract_session_context(event.data.object)
    if not ctx["user_id"]:
        raise HTTPException(status_code=400, detail="Missing user_id in metadata")

    if ctx["payment_mode"] == "stripe_credits":
        return await _handle_credit_purchase(ctx)

    return await _handle_subscription_purchase(ctx)


@app.get("/api/abonnements")
async def list_abonnements():
    """List available subscription plans from Supabase."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    plans = await supabase_list_abonnements()
    return {"plans": plans}


@app.get("/api/souscription")
async def get_current_souscription(request: Request) -> Optional[Dict[str, Any]]:
    """Get the current active subscription for a user."""
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    await _enforce_subscription_retention_policy(user_id)
    subscription = await get_user_abonnement(user_id)
    if not subscription:
        return None

    abonnement_id = str(subscription.get("abonnement") or "").strip()
    if abonnement_id:
        plan = await supabase_get_abonnement(abonnement_id)
        if plan:
            subscription = {
                **subscription,
                "abonnement_name": plan.get("name") or abonnement_id,
                "abonnement_credit": float(plan.get("credit") or 0.0),
                "abonnement_stockage": float(plan.get("stockage") or 0.0),
            }
    return subscription


@app.get("/api/souscription/history")
async def get_souscription_history(request: Request, limit: int = Query(50, ge=1, le=200)):
    """Return subscription history only (excluding one-off credit purchases)."""
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    rows = await supabase_list_user_souscriptions(user_id, limit=limit)
    plans = await supabase_list_abonnements()
    plan_name_by_id = {
        str(plan.get("id")): str(plan.get("name") or "")
        for plan in (plans or [])
        if plan.get("id")
    }

    filtered: List[Dict[str, Any]] = []
    for row in rows:
        payment_mode = str(row.get("payment_mode") or "")
        if payment_mode == "stripe_credits":
            continue
        abonnement_id = str(row.get("abonnement") or "").strip()
        filtered.append(
            {
                **row,
                "abonnement_name": plan_name_by_id.get(abonnement_id) or abonnement_id or "-",
            }
        )

    return {"items": filtered}


# ---------------------------------------------------------------------------
# User credits & history
# ---------------------------------------------------------------------------

@app.get("/api/user/credits")
async def get_user_credits(request: Request):
    """Return the credit/storage balance for the authenticated user."""
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    await _enforce_subscription_retention_policy(user_id)

    data = await supabase_get_user_data(user_id)
    if not data:
        return {
            "credit":   0.0,
            "stockage": 0.0,
            "credit_max": 0.0,
            "stockage_max": 0.0,
            "storage_overage_tolerance_percent": STORAGE_OVERAGE_TOLERANCE_PERCENT,
            "has_credits": False,
            "abo_costs": {
                "credit":  0.0,
                "storage": 0.0,
            },
            "default_costs": {
                "reel":        DEFAULT_REEL_CREDITS,
                "caption":     DEFAULT_CAPTION_CREDITS,
                "publication": DEFAULT_PUBLICATION_CREDITS,
            },
        }

    credit = float(data.get("credit", 0) or 0.0)
    storage = float(data.get("stockage", 0) or 0.0)
    credit_max = float(data.get("credit_max", credit) or 0.0)
    storage_max = float(data.get("stockage_max", max(storage, 0.0)) or 0.0)

    abonnement = await get_user_abonnement(user_id)
    if not abonnement:
        abo_costs = {
            "credit":  0.0,
            "storage": 0.0,
        }
    else:
        abo_costs = {
            "credit":  float(abonnement.get("credit",   0)),
            "storage": float(abonnement.get("stockage", 0)),
        }

    return {
        "credit":   credit,
        "stockage": storage,
        "credit_max": credit_max,
        "stockage_max": storage_max,
        "storage_overage_tolerance_percent": STORAGE_OVERAGE_TOLERANCE_PERCENT,
        "has_credits": credit > 0,
        "abo_costs": abo_costs,
        "default_costs": {
            "reel":        DEFAULT_REEL_CREDITS,
            "caption":     DEFAULT_CAPTION_CREDITS,
            "publication": DEFAULT_PUBLICATION_CREDITS,
        },
    }


@app.get("/api/user/history")
async def get_user_history(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Return paginated credit/storage history for the authenticated user."""
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    rows, total = await supabase_get_user_data_history(user_id, page=page, page_size=page_size)
    return {
        "items":     rows,
        "total":     total,
        "page":      page,
        "page_size": page_size,
    }


class BuyCreditsRequest(BaseModel):
    amount_usd: float
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@app.post("/api/stripe/buy-credits")
async def buy_credits_checkout(request: Request, payload: BuyCreditsRequest):
    """Create a Stripe Checkout session for purchasing additional credits."""
    _require_stripe_ready()

    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    policy_state = await _enforce_subscription_retention_policy(user_id)
    if policy_state.get("state") != "active":
        raise HTTPException(
            status_code=403,
            detail="Un abonnement actif est requis pour recharger des credits.",
        )

    amount_usd = float(payload.amount_usd)
    if amount_usd < 1.0:
        raise HTTPException(status_code=400, detail="Minimum purchase is 1 EUR")

    credits_to_add = int(usd_to_credits(amount_usd))
    unit_amount    = int(round(amount_usd * 100))  # in cents

    default_base_url = _frontend_base_url(request)
    success_url = (
        payload.success_url
        or f"{default_base_url}/dashboard/settings?credit_purchase=success"
    ).strip()
    cancel_url = (
        payload.cancel_url
        or f"{default_base_url}/dashboard/settings?credit_purchase=cancel"
    ).strip()

    metadata = {
        "userid":         user_id,
        "payment_mode":   "stripe_credits",
        "credits_to_add": str(credits_to_add),
        "amount_usd":     str(amount_usd),
    }

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=request.headers.get("X-User-Email") or None,
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": STRIPE_CURRENCY,
                        "unit_amount": unit_amount,
                        "product_data": {
                            "name": f"{credits_to_add} Vireel Credits",
                            "description": f"Achat de {credits_to_add} crédits Vireel",
                            "tax_code": "txcd_10103001"
                        },
                    },
                }
            ],
            metadata=metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe checkout error: {exc}")

    return {
        "checkout_url":  session.url,
        "session_id":    session.id,
        "credits_to_add": credits_to_add,
    }


@app.get("/api/reels")
async def list_reels(user_id: str = Depends(get_user_id_header), page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), q: Optional[str] = None, status: Optional[str] = None):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase reels is not configured")

    rows, total = await supabase_list_reels(user_id=user_id, page=page, page_size=page_size, status=status, query=q)
    return {
        "items": [_normalize_reel_row(row) for row in rows],
        "total": total,
        "page": max(page, 1),
        "page_size": min(max(page_size, 1), 100),
    }


@app.get("/api/reels/{reel_id}/media-url")
async def reel_media_url(reel_id: str, user_id: str = Depends(get_user_id_header)):
    row = await supabase_get_reel(reel_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reel not found")
    item = _normalize_reel_row(row)
    return {"media_url": item.get("media_url")}


@app.get("/api/reels/{reel_id}/thumbnail-url")
async def reel_thumbnail_url(reel_id: str, user_id: str = Depends(get_user_id_header)):
    row = await supabase_get_reel(reel_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reel not found")
    item = _normalize_reel_row(row)
    return {"thumbnail_url": item.get("reel_thumbnail_url")}


@app.get("/api/reels/{reel_id}/preview-url")
async def reel_preview_url(reel_id: str, user_id: str = Depends(get_user_id_header)):
    row = await supabase_get_reel(reel_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reel not found")
    item = _normalize_reel_row(row)
    return {"preview_url": item.get("reel_preview_url")}


@app.delete("/api/reels/{reel_id}")
async def delete_reel(reel_id: str, user_id: str = Depends(get_user_id_header)):
    deleted = await supabase_soft_delete_reel(reel_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Reel not found")
    return {"deleted": True}


@app.post("/api/reels/{reel_id}/share")
async def share_reel(reel_id: str, payload: ReelShareRequest, user_id: str = Depends(get_user_id_header)):
    # --- Credit pre-check for publication ---
    if is_supabase_configured():
        platform_count = len(payload.platforms) if payload.platforms else 1
        _pub_cost = calculate_credits_for_operation(
            estimate_publication_cost_usd(platform_count=platform_count, video_size_gb=0.5)
        )
        _pub_required = _pub_cost["final_credits"]
        _pub_ud = await supabase_get_user_data(user_id)
        _pub_credits = float(_pub_ud.get("credit", 0)) if _pub_ud else 0.0
        if _pub_credits < _pub_required:
            raise HTTPException(
                status_code=402,
                detail=f"Crédits insuffisants. Requis : {_pub_required} cr, disponible : {_pub_credits} cr.",
            )

    row = await supabase_get_reel(reel_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reel not found")

    item = _normalize_reel_row(row)
    media_url = item.get("media_url")
    if not media_url:
        raise HTTPException(status_code=400, detail="No media URL available")

    final_title = payload.title or row.get("reel_title") or "Vireel"
    final_description = payload.description or row.get("reel_description") or ""
    selected_platforms = _resolve_social_platforms(payload.platforms)
    publish_priority = await _resolve_user_job_priority(user_id)

    results: Dict[str, Any] = {}
    overall_success = True
    for platform_name in selected_platforms:
        try:
            account = await _get_social_account(user_id, platform_name)
            if not account:
                raise HTTPException(status_code=404, detail=f"No connected {platform_name} account found")

            publish_payload = PublishRequest(
                user_id=user_id,
                title=final_title,
                description=final_description,
                text=final_description,
                caption=final_description,
                video_url=media_url,
            )
            platform_result = await publish_post(account, publish_payload)
            external_id = str(platform_result.get("publish_id") or platform_result.get("id") or platform_result.get("video_id") or "n/a")
            await _insert_publish_job(user_id=user_id, platform=platform_name, external_id=external_id, status="done", priority=publish_priority)
            results[platform_name] = {
                "success": True,
                "result": platform_result,
            }
        except Exception as exc:
            overall_success = False
            err_msg = str(exc)
            await _insert_publish_job(user_id=user_id, platform=platform_name, external_id="n/a", status="failed", error_message=err_msg, priority=publish_priority)
            results[platform_name] = {
                "success": False,
                "error": err_msg,
            }

    # Debit credits after publications (best-effort)
    if is_supabase_configured():
        platform_count_done = sum(1 for v in results.values() if v.get("success"))
        if platform_count_done > 0:
            _pub_done_cost = calculate_credits_for_operation(
                estimate_publication_cost_usd(platform_count=platform_count_done, video_size_gb=0.5)
            )
            _pub_done_credits = _pub_done_cost["final_credits"]
            await supabase_deduct_user_credits(user_id, _pub_done_credits)
            await supabase_insert_user_data_history(
                user_id=user_id,
                credit=_pub_done_credits,
                storage=0.0,
                operation="output",
                operation_type="publications",
                operation_id=reel_id,
            )

    return {
        "success": overall_success,
        "results": results,
    }


class SocialAccount(BaseModel):
    id: int
    user_id: int
    platform: str  # "tiktok", "facebook", "linkedin", "youtube"
    access_token: str  # chiffré (Fernet, ou vault)
    refresh_token: str | None
    expires_at: datetime
    platform_user_id: str
    scopes: str


class FacebookPageSelectionRequest(BaseModel):
    user_id: str
    page_id: str
    page_name: str
    page_access_token: str
    user_token_expires_in: int


SOCIAL_BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/")
SUPABASE_SOCIAL_ACCOUNTS_TABLE = os.environ.get("SUPABASE_SOCIAL_ACCOUNTS_TABLE", "social_accounts")
SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE = os.environ.get("SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE", "publish_jobs")
_OAUTH_STATE_TTL_SECONDS = 600
_oauth_states: Dict[str, Dict[str, Any]] = {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _xor_bytes(value: bytes, key: bytes) -> bytes:
    if not key:
        return value
    return bytes(value[i] ^ key[i % len(key)] for i in range(len(value)))


def _encrypt_token(token: str) -> str:
    if not token:
        return ""
    key = (os.environ.get("ENCRYPTION_KEY", "") or "").encode("utf-8")
    raw = token.encode("utf-8")
    return base64.urlsafe_b64encode(_xor_bytes(raw, key)).decode("ascii")


def _decrypt_token(token_encrypted: Optional[str]) -> str:
    if not token_encrypted:
        return ""
    try:
        key = (os.environ.get("ENCRYPTION_KEY", "") or "").encode("utf-8")
        decoded = base64.urlsafe_b64decode(token_encrypted.encode("ascii"))
        return _xor_bytes(decoded, key).decode("utf-8")
    except Exception:
        return ""


def _resolve_platform_config(platform: str) -> Dict[str, Any]:
    key = (platform or "").strip().lower()
    if key not in PLATFORM_CONFIG:
        raise HTTPException(status_code=404, detail="Unsupported platform")
    config = PLATFORM_CONFIG[key]
    if not config.get("client_id") or not config.get("client_secret"):
        raise HTTPException(status_code=503, detail=f"{key} OAuth is not configured")
    return config


def _oauth_popup_response(success: bool, platform: str, message: Optional[str] = None, page_selection_data: Optional[Dict[str, Any]] = None) -> HTMLResponse:
    if page_selection_data:
        # Pour la sélection de pages Facebook
        payload = {
            "type": "oauth_page_selection",
            "platform": platform,
            "pages": page_selection_data.get("pages", []),
            "user_token": page_selection_data.get("user_token"),
            "user_token_expires_in": page_selection_data.get("user_token_expires_in"),
        }
    else:
        payload = {
            "type": "oauth_success" if success else "oauth_error",
            "platform": platform,
            "message": message or "",
        }
    return HTMLResponse(
        f"""
        <script>
          window.opener && window.opener.postMessage({json.dumps(payload)}, '*');
          window.close();
        </script>
        """
    )



def _public_request_base_url(request: Request) -> str:
    """Build public base URL from proxy headers when available."""
    xf_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    xf_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if xf_proto and xf_host:
        return f"{xf_proto}://{xf_host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def _oauth_redirect_uri(platform: str, request: Optional[Request] = None) -> str:
    if SOCIAL_BASE_URL:
        return f"{SOCIAL_BASE_URL}/api/auth/{platform}/callback"
    if request:
        base = _public_request_base_url(request)
        return f"{base}/api/auth/{platform}/callback"
    return f"http://localhost:8000/api/auth/{platform}/callback"


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE verifier/challenge pair (S256) for OAuth providers like TikTok."""
    # token_urlsafe already produces URL-safe chars; trim to stay within PKCE recommended bounds.
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge

async def fetch_facebook_granted_scopes(access_token: str) -> List[str]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://graph.facebook.com/me/permissions",
            params={"access_token": access_token},
        )
    response.raise_for_status()
    data = response.json().get("data") or []
    return [
        item.get("permission")
        for item in data
        if item.get("status") == "granted" and item.get("permission")
    ]


async def fetch_facebook_pages(user_access_token: str) -> List[Dict[str, Any]]:
    """
    Récupère les pages gérées par l'utilisateur avec leurs access tokens.
    Les tokens de page sont long-lived si le user_access_token est long-lived.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={
                "fields": "id,name,picture.width(200).height(200),access_token,category",
                "access_token": user_access_token,
            },
        )
    response.raise_for_status()
    data = response.json()

    pages = []
    for item in data.get("data", []):
        pages.append({
            "page_id": item.get("id"),
            "page_name": item.get("name"),
            "page_picture": item.get("picture", {}).get("data", {}).get("url"),
            "page_category": item.get("category"),
            "page_access_token": item.get("access_token"),
        })

    return pages


async def _extract_token_data(platform: str, token_data: Dict[str, Any]) -> Dict[str, Any]:
    if platform == "tiktok":
        token_data = token_data.get("data", token_data)

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="OAuth provider did not return access_token")

    scopes = token_data.get("scope") or token_data.get("scopes") or ""

    if platform == "facebook":
        try:
            granted_scopes = await fetch_facebook_granted_scopes(access_token)
            if granted_scopes:
                scopes = " ".join(granted_scopes)
        except Exception:
            # On garde le fallback éventuel renvoyé par le provider
            pass

    return {
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
        "expires_in": int(token_data.get("expires_in") or 3600),
        "scopes": scopes,
    }

async def _get_social_account(user_id: str, platform: str) -> Optional[Dict[str, Any]]:
    client = await supabase_get_client()
    response = (
        await client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .eq("platform", platform)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


async def _upsert_social_account(
    user_id: str,
    platform: str,
    access_token: str,
    refresh_token: Optional[str],
    expires_in: int,
    platform_user_id: str,
    platform_account_name: str,
    scopes: str,
) -> None:
    client = await supabase_get_client()
    expires_at = datetime.fromtimestamp(time.time() + max(expires_in, 60), tz=timezone.utc).isoformat()
    payload = {
        "user_id": user_id,
        "platform": platform,
        "access_token_encrypted": _encrypt_token(access_token),
        "refresh_token_encrypted": _encrypt_token(refresh_token or ""),
        "platform_user_id": platform_user_id,
        "platform_account_name": platform_account_name,
        "scopes": scopes,
        "expires_at": expires_at,
        "updated_at": _utcnow_iso(),
    }

    existing = await _get_social_account(user_id, platform)
    if existing and existing.get("id"):
        await (
            client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
            .update(payload)
            .eq("id", existing["id"])
            .execute()
        )
    else:
        await client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE).insert(payload).execute()


async def _insert_publish_job(
    user_id: str,
    platform: str,
    external_id: str,
    status: str,
    error_message: Optional[str] = None,
    priority: int = DEFAULT_JOB_PRIORITY,
) -> None:
    client = await supabase_get_client()
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "platform": platform,
        "external_id": external_id,
        "status": status,
        "priority": _clamp_job_priority(priority),
    }
    if error_message:
        payload["error_message"] = error_message
    if status in {"done", "failed"}:
        payload["completed_at"] = _utcnow_iso()
    await client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE).insert(payload).execute()


@app.get("/api/social/accounts")
async def list_social_accounts(user_id: str = Query(...)):
    client = await supabase_get_client()
    response = (
        await client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
        .select("id, created_at, user_id, platform, platform_user_id, platform_account_name, scopes, expires_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = response.data or []
    accounts = [
        {
            **row,
            "connected": True,
        }
        for row in rows
    ]
    return {"accounts": accounts}


@app.delete("/api/social/accounts/{platform}")
async def disconnect_social_account(platform: str, user_id: str = Query(...)):
    key = (platform or "").strip().lower()
    if key not in PLATFORM_CONFIG:
        raise HTTPException(status_code=404, detail="Unsupported platform")
    client = await supabase_get_client()
    response = (
        await client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
        .delete()
        .eq("user_id", user_id)
        .eq("platform", key)
        .execute()
    )
    return {"deleted": bool(response.data)}


@app.get("/api/social/publish-jobs")
async def list_publish_jobs(
    user_id: str = Depends(get_user_id_header),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    platform: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_filter: Optional[str] = Query(None),  # all, today, week, month
    search: Optional[str] = Query(None),
):
    """
    Récupère les publications sociales de l'utilisateur avec filtres.

    Args:
        user_id: ID utilisateur
        page: Numéro de page (par défaut 1)
        page_size: Nombre d'items par page (par défaut 20, max 100)
        platform: Filtre par plateforme (facebook, instagram, tiktok, youtube, linkedin)
        status: Filtre par statut (pending, processing, done, failed)
        date_filter: Filtre par date (all, today, week, month)
        search: Recherche dans l'ID externe ou la plateforme
    """
    try:
        client = await supabase_get_client()

        # Construire la requête de base
        query = (
            client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE)
            .select("*", count="exact")
            .eq("user_id", user_id)
        )

        # Filtrer par plateforme
        if platform and platform not in ("all", ""):
            query = query.eq("platform", platform.lower())

        # Filtrer par statut
        if status and status not in ("all", ""):
            query = query.eq("status", status.lower())

        # Filtrer par date
        if date_filter and date_filter != "all":
            now = datetime.now(timezone.utc)
            if date_filter == "today":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                query = query.gte("created_at", start_date)
            elif date_filter == "week":
                week_ago = now - timedelta(days=7)
                query = query.gte("created_at", week_ago.isoformat())
            elif date_filter == "month":
                month_ago = now - timedelta(days=30)
                query = query.gte("created_at", month_ago.isoformat())

        # Ordonner par date de création (plus récent en premier)
        query = query.order("created_at", desc=True)

        # Exécuter la requête avec pagination
        offset = (page - 1) * page_size
        response = await query.range(offset, offset + page_size - 1).execute()

        items = response.data or []
        total = response.count or 0

        # Filtrer par recherche si fournie (filtre côté client pour simplifier)
        if search and search.strip():
            search_lower = search.lower().strip()
            items = [
                item for item in items
                if (item.get("external_id", "").lower().find(search_lower) >= 0 or
                    item.get("platform", "").lower().find(search_lower) >= 0)
            ]
            total = len(items)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }
    except Exception as e:
        print(f"⚠️ Erreur lors de la récupération des publications: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.post("/api/auth/facebook/select-page")
async def facebook_select_page(
    payload: FacebookPageSelectionRequest,
    user_id: str = Depends(get_user_id_header),
):
    """
    L'utilisateur a sélectionné une page Facebook à connecter.
    Stocke le page_id + page_access_token (pas le token utilisateur).
    """

    if not payload.page_access_token:
        raise HTTPException(status_code=400, detail="Missing page_access_token")

    # Stocke le compte avec :
    # - platform_user_id = page_id
    # - access_token_encrypted = page_access_token (long-lived)
    await _upsert_social_account(
        user_id=user_id,
        platform="facebook",
        access_token=payload.page_access_token,
        refresh_token=None,  # Les tokens de page n'ont pas de refresh token
        expires_in=payload.user_token_expires_in or 5184000,  # ~60 jours par défaut
        platform_user_id=payload.page_id,
        platform_account_name=payload.page_name,
        scopes="pages_manage_posts,pages_read_engagement",  # Scopes réels pour les pages
    )

    return {
        "success": True,
        "message": f"Connected Facebook page '{payload.page_name}'",
        "platform": "facebook",
        "page_id": payload.page_id,
    }


@app.get("/api/auth/{platform}/connect")
def connect(platform: str, request: Request, user_id: str = Query(...)):
    key = (platform or "").strip().lower()
    config = _resolve_platform_config(key)
    redirect_uri = _oauth_redirect_uri(key, request)

    # Payload signé qui remplace le dict _oauth_states — plus besoin de stockage en mémoire
    state_payload = {
        "user_id": user_id,
        "platform": key,
        "redirect_uri": redirect_uri,
    }

    params = {
        "client_id": config["client_id"],
        "redirect_uri": redirect_uri,
        "scope": " ".join(config["scopes"]),
        "response_type": "code",
    }

    if key == "youtube":
        params["access_type"] = "offline"
        params["prompt"] = "consent"

    if key == "tiktok":
        code_verifier, code_challenge = generate_pkce_pair()
        state_payload["code_verifier"] = code_verifier

        params["client_key"] = config["client_id"]
        params.pop("client_id", None)  # TikTok utilise client_key, pas client_id
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
        params["scope"] = ",".join(config["scopes"])  # TikTok utilise scope séparé par des espaces

    # Signe le payload → devient le state envoyé à la plateforme
    state = _oauth_serializer.dumps(state_payload)
    params["state"] = state

    auth_url = f"{config['auth_url']}?{urlencode(params)}"
    return {"auth_url": auth_url}


@app.get("/api/auth/{platform}/callback")
async def callback(platform: str, code: Optional[str] = None, state: str = "", error: Optional[str] = None):
    key = (platform or "").strip().lower()

    try:
        state_data = _oauth_serializer.loads(state, max_age=_OAUTH_STATE_TTL_SECONDS)
    except SignatureExpired:
        return _oauth_popup_response(False, key, "OAuth state expired")
    except BadSignature:
        return _oauth_popup_response(False, key, "Invalid OAuth state")

    if state_data.get("platform") != key:
        return _oauth_popup_response(False, key, "Platform mismatch in OAuth state")
    if error:
        return _oauth_popup_response(False, key, error)
    if not code:
        return _oauth_popup_response(False, key, "Missing OAuth code")

    config = _resolve_platform_config(key)

    token_payload = {
        "code": code,
        "redirect_uri": state_data.get("redirect_uri") or _oauth_redirect_uri(key),
        "grant_type": "authorization_code",
    }

    if key == "tiktok":
        token_payload["client_key"] = config["client_id"]
        token_payload["client_secret"] = config["client_secret"]
        token_payload["code_verifier"] = state_data["code_verifier"]  # ← récupéré du connect
    else:
        token_payload["client_id"] = config["client_id"]
        token_payload["client_secret"] = config["client_secret"]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(config["token_url"], data=token_payload)
        response.raise_for_status()
        raw_token_data = response.json()

        # Instagram : échange immédiatement contre un long-lived token
        if key == "instagram":
            raw_token_data = await _exchange_instagram_long_lived_token(
                config, raw_token_data["access_token"]
            )

        token_data = await _extract_token_data(key, raw_token_data)

        # Facebook : récupère les pages et affiche la sélection
        if key == "facebook":
            try:
                pages = await fetch_facebook_pages(token_data["access_token"])
                if pages:
                    # Retourne le modal de sélection de pages
                    return _oauth_popup_response(
                        False, key, None,
                        page_selection_data={
                            "pages": pages,
                            "user_token": token_data["access_token"],
                            "user_token_expires_in": token_data.get("expires_in", 5184000),
                        }
                    )
            except Exception as e:
                # En cas d'erreur, on continue avec le fallback utilisateur
                print(f"⚠️ Erreur lors de la récupération des pages Facebook: {e}")

        identity = await fetch_platform_identity(key, token_data["access_token"])
        await _upsert_social_account(
            user_id=state_data["user_id"],
            platform=key,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_in=int(token_data.get("expires_in") or 3600),
            platform_user_id=identity.get("id", ""),
            platform_account_name=identity.get("name", key),
            scopes=str(token_data.get("scopes") or ""),
        )
        return _oauth_popup_response(True, key)
    except Exception as exc:
        return _oauth_popup_response(False, key, str(exc))


async def _exchange_instagram_long_lived_token(config: dict, short_lived_token: str) -> dict:
    """
    Instagram : le token initial expire en 1h.
    On l'échange immédiatement contre un token valide 60 jours.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            config["long_lived_token_url"],
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": config["client_secret"],
                "access_token": short_lived_token,
            },
        )
    response.raise_for_status()
    data = response.json()
    # data = {"access_token": "...", "token_type": "bearer", "expires_in": 5184000}  # 60 jours en secondes
    return data

async def fetch_platform_identity(platform: str, access_token: str):
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        if platform == "linkedin":
            response = await client.get("https://api.linkedin.com/v2/userinfo", headers=headers)
            response.raise_for_status()
            data = response.json()
            return {"id": str(data.get("sub") or ""), "name": data.get("name") or "LinkedIn"}

        if platform == "facebook":
            response = await client.get("https://graph.facebook.com/me", params={"fields": "id,name"}, headers=headers)
            response.raise_for_status()
            data = response.json()
            return {"id": str(data.get("id") or ""), "name": data.get("name") or "Facebook"}

        if platform == "instagram":
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://graph.instagram.com/me",
                    params={
                        "fields": "id,username,account_type",
                        "access_token": access_token,
                    },
                )
            response.raise_for_status()
            data = response.json()
            return {"id": data["id"], "name": data.get("username", "instagram")}

        if platform == "youtube":
            response = await client.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"}, headers=headers)
            response.raise_for_status()
            items = response.json().get("items") or []
            first = items[0] if items else {}
            return {"id": str(first.get("id") or ""), "name": ((first.get("snippet") or {}).get("title") or "YouTube")}

        if platform == "tiktok":
            response = await client.get(
                "https://open.tiktokapis.com/v2/user/info/",
                params={"fields": "open_id,display_name"},
                headers=headers,
            )
            response.raise_for_status()
            user = ((response.json().get("data") or {}).get("user") or {})
            return {"id": str(user.get("open_id") or ""), "name": user.get("display_name") or "TikTok"}

    raise HTTPException(status_code=404, detail="Unsupported platform")


def _is_token_expiring(account: Dict[str, Any], margin_seconds: int = 300) -> bool:
    expires_at = account.get("expires_at")
    if not expires_at:
        return True
    try:
        expires_dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        platform = str(account.get("platform") or "").lower()
        # Instagram tokens (via Meta) ont une fenêtre de 60 jours mais se dégradent silencieusement ;
        # forcer un refresh si l'expiration est dans moins de 5 jours.
        if platform == "instagram":
            margin_seconds = max(margin_seconds, 5 * 24 * 3600)  # 432 000 secondes
        return expires_dt <= datetime.now(timezone.utc) + timedelta(seconds=margin_seconds)
    except Exception:
        return True


async def get_valid_token(account: Dict[str, Any]) -> str:
    access_token = _decrypt_token(account.get("access_token_encrypted"))
    if access_token and not _is_token_expiring(account):
        return access_token

    platform = str(account.get("platform") or "").lower()

    # Instagram : pas de refresh_token classique, on rafraîchit le long-lived
    # access_token directement via un GET dédié (ig_refresh_token)
    if platform == "instagram":
        if not access_token:
            raise HTTPException(status_code=401, detail="Instagram account token missing, reconnection required")

        config = _resolve_platform_config(platform)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://graph.instagram.com/refresh_access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "access_token": access_token,
                },
            )
        response.raise_for_status()
        new_data = response.json()

        refreshed_access_token = new_data["access_token"]
        expires_in = int(new_data.get("expires_in") or 5184000)  # 60 jours par défaut

        client = await supabase_get_client()
        await (
            client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
            .update(
                {
                    "access_token_encrypted": _encrypt_token(refreshed_access_token),
                    "expires_at": datetime.fromtimestamp(time.time() + max(expires_in, 60), tz=timezone.utc).isoformat(),
                    "updated_at": _utcnow_iso(),
                }
            )
            .eq("id", account.get("id"))
            .execute()
        )
        return refreshed_access_token

    # --- Flow générique existant pour les autres plateformes ---
    refresh_token = _decrypt_token(account.get("refresh_token_encrypted"))
    if not refresh_token:
        if access_token:
            return access_token
        raise HTTPException(status_code=401, detail="Account token expired and no refresh token available")

    config = _resolve_platform_config(platform)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            config["token_url"],
            data={
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    response.raise_for_status()

    new_tokens = await _extract_token_data(platform, response.json())
    refreshed_access_token = new_tokens["access_token"]
    refreshed_refresh_token = new_tokens.get("refresh_token") or refresh_token
    expires_in = int(new_tokens.get("expires_in") or 3600)

    client = await supabase_get_client()
    await (
        client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
        .update(
            {
                "access_token_encrypted": _encrypt_token(refreshed_access_token),
                "refresh_token_encrypted": _encrypt_token(refreshed_refresh_token),
                "expires_at": datetime.fromtimestamp(time.time() + max(expires_in, 60), tz=timezone.utc).isoformat(),
                "updated_at": _utcnow_iso(),
            }
        )
        .eq("id", account.get("id"))
        .execute()
    )
    return refreshed_access_token


class PublishRequest(BaseModel):
    user_id: str
    text: Optional[str] = None
    caption: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None
    video_file: Optional[str] = None
    privacy_level: Optional[str] = "PUBLIC_TO_EVERYONE"


async def publish_post(account: Dict[str, Any], content: PublishRequest):
    token = await get_valid_token(account)
    headers = {"Authorization": f"Bearer {token}"}
    platform = str(account.get("platform") or "").lower()
    text_value = content.text or content.caption or content.description or "Posted from Vireel"

    if platform == "linkedin":

        if content.video_url:
            try:
                return await publish_to_linkedin_video(
                    access_token=token,
                    owner_urn=f"urn:li:person:{account.get('platform_user_id')}",
                    video_url=content.video_url,
                    title=content.title or "Vireel",
                    description=text_value,
                )
            except Exception:
                # fallback texte seul
                pass

        payload = {
            "author": f"urn:li:person:{account.get('platform_user_id')}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text_value},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post("https://api.linkedin.com/v2/ugcPosts", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    if platform == "facebook":
        if content.video_url:
            try:
                return await publish_to_facebook_video(
                    access_token=token,
                    target_id=str(account.get("platform_user_id") or ""),
                    video_url=content.video_url,
                    message=text_value,
                    title=content.title or "Vireel",
                    description=content.description or text_value,
                )
            except Exception:
                # fallback texte seul
                pass

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://graph.facebook.com/{account.get('platform_user_id')}/feed",
                data={"message": text_value, "access_token": token},
            )
        response.raise_for_status()
        return response.json()

    if platform == "instagram":
        if not content.video_url:
            raise HTTPException(status_code=400, detail="video_url is required for Instagram publication")
        ig_user_id = str(account.get("platform_user_id") or "").strip()
        if not ig_user_id:
            raise HTTPException(status_code=400, detail="Connected Instagram account id is missing")
        return await publish_to_instagram(token, ig_user_id, content.video_url, text_value)

    if platform == "youtube":
        video_path = (content.video_file or "").strip()
        temp_path = ""
        if not video_path:
            if not content.video_url:
                raise HTTPException(status_code=400, detail="video_file or video_url is required for YouTube publication")
            temp_path = os.path.join(UPLOAD_DIR, f"yt_publish_{uuid.uuid4().hex}.mp4")
            async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                media_response = await client.get(content.video_url)
                media_response.raise_for_status()
            with open(temp_path, "wb") as handle:
                handle.write(media_response.content)
            video_path = temp_path

        try:
            return await upload_youtube_video(
                token,
                video_path,
                content.title or "Vireel Short",
                content.description or text_value,
            )
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    if platform == "tiktok":
        if not content.video_url:
            raise HTTPException(status_code=400, detail="video_url is required for TikTok publication")
        return await publish_to_tiktok(token, content.video_url, text_value, content.privacy_level or "PUBLIC_TO_EVERYONE")

    raise HTTPException(status_code=404, detail="Unsupported platform")


async def upload_youtube_video(access_token: str, video_path: str, title: str, description: str, privacy: str = "public"):
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {video_path}")

    headers = {"Authorization": f"Bearer {access_token}"}
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": privacy,
        },
    }

    file_size = os.path.getsize(video_path)
    async with httpx.AsyncClient(timeout=120.0) as client:
        init_response = await client.post(
            "https://www.googleapis.com/upload/youtube/v3/videos",
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                **headers,
                "X-Upload-Content-Type": "video/*",
                "X-Upload-Content-Length": str(file_size),
                "Content-Type": "application/json; charset=UTF-8",
            },
            json=metadata,
        )
    init_response.raise_for_status()

    upload_url = init_response.headers.get("Location")
    if not upload_url:
        raise HTTPException(status_code=502, detail="YouTube upload session URL is missing")

    with open(video_path, "rb") as file_handle:
        file_data = file_handle.read()

    async with httpx.AsyncClient(timeout=300.0) as client:
        upload_response = await client.put(
            upload_url,
            headers={
                "Content-Type": "video/*",
                "Content-Length": str(file_size),
            },
            content=file_data,
        )
    upload_response.raise_for_status()
    result = upload_response.json()
    return {
        "video_id": result.get("id"),
        "url": f"https://youtube.com/watch?v={result.get('id')}",
    }


async def publish_to_tiktok(access_token: str, video_url: str, caption: str, privacy_level: str = "PUBLIC_TO_EVERYONE"):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "post_info": {
            "title": caption,
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "brand_content_toggle": False,
            "brand_organic_toggle": False,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        init_response = await client.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers=headers,
            json=payload,
        )
    init_response.raise_for_status()

    init_data = init_response.json()
    if init_data.get("error", {}).get("code") != "ok":
        raise HTTPException(status_code=502, detail=f"TikTok publish init failed: {init_data}")

    publish_id = ((init_data.get("data") or {}).get("publish_id") or "").strip()
    if not publish_id:
        raise HTTPException(status_code=502, detail="TikTok publish_id missing")
    return await poll_tiktok_status(access_token, publish_id)


async def poll_tiktok_status(access_token: str, publish_id: str, max_attempts: int = 20):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    delay = 2.0
    for _ in range(max_attempts):
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
                headers=headers,
                json={"publish_id": publish_id},
            )
        response.raise_for_status()
        data = (response.json().get("data") or {})
        status = data.get("status")
        if status == "PUBLISH_COMPLETE":
            return {"success": True, "publish_id": publish_id, "status": status}
        if status == "FAILED":
            return {"success": False, "publish_id": publish_id, "status": status, "error": data.get("fail_reason") or "unknown"}
        await asyncio.sleep(delay)
        delay = min(delay * 1.5, 30.0)

    return {"success": False, "publish_id": publish_id, "status": "TIMEOUT", "error": "timeout"}


async def publish_to_facebook_video(
    access_token: str,
    target_id: str,
    video_url: str,
    message: str,
    title: str,
    description: str,
):
    """
    Publie une vidéo sur une page Facebook.

    Args:
        access_token: Page access token (long-lived, stocké en DB)
        target_id: page_id (stocké en platform_user_id)
        video_url: URL publique de la vidéo
        message: Texte du post
        title: Titre (optionnel pour Facebook)
        description: Description (optionnel)
    """
    if not target_id:
        raise HTTPException(status_code=400, detail="Connected Facebook target id is missing")

    if not access_token:
        raise HTTPException(status_code=401, detail="Facebook page access token expired or missing")

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            f"https://graph.facebook.com/v19.0/{target_id}/videos",
            data={
                "file_url": video_url,
                "description": message or description,
                "title": title,
                "access_token": access_token,
            },
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Facebook publish failed: {response.text}"
        )

    data = response.json()
    return {
        "id": data.get("id"),
    }


async def publish_to_instagram(account: SocialAccount, content: PublishRequest):
    token = await get_valid_token(account)
    ig_user_id = account.platform_user_id

    # Étape 1 — Créer le container média (l'image/vidéo doit être une URL publique HTTPS)
    async with httpx.AsyncClient(timeout=60.0) as client:
        container_response = await client.post(
            f"https://graph.instagram.com/v25.0/{ig_user_id}/media",
            data={
                "video_url": content.video_url,  # ou image_url selon le type
                "caption": content.text,
                "media_type": "REELS",  # ou "IMAGE", "VIDEO", "STORIES"
                "access_token": token,
            },
        )
    container_response.raise_for_status()
    creation_id = container_response.json()["id"]

    # Étape 2 — Attendre que le container soit prêt (polling, comme TikTok)
    status = await _poll_instagram_container_status(token, creation_id)
    if status != "FINISHED":
        raise Exception(f"Container Instagram non prêt: {status}")

    # Étape 3 — Publier le container
    async with httpx.AsyncClient(timeout=30.0) as client:
        publish_response = await client.post(
            f"https://graph.instagram.com/v25.0/{ig_user_id}/media_publish",
            data={
                "creation_id": creation_id,
                "access_token": token,
            },
        )
    publish_response.raise_for_status()
    return publish_response.json()  # contient l'id du post publié


async def _poll_instagram_container_status(token: str, creation_id: str, max_attempts: int = 20):
    delay = 2
    for _ in range(max_attempts):
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://graph.instagram.com/v25.0/{creation_id}",
                params={"fields": "status_code", "access_token": token},
            )
        status = response.json().get("status_code")
        if status in ("FINISHED", "ERROR"):
            return status
        await asyncio.sleep(delay)
        delay = min(delay * 1.5, 30)
    return "TIMEOUT"


async def publish_to_facebook_page(page_id: str, page_access_token: str, message: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://graph.facebook.com/v19.0/{page_id}/feed",
            data={
                "message": message,
                "access_token": page_access_token,  # token de la Page, pas de l'utilisateur
            },
        )
    response.raise_for_status()
    return response.json()

async def get_facebook_long_lived_token(short_lived_token: str) -> str:
    """Échange un token court-terme contre un token long-terme (~60 jours)"""
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": os.getenv("FACEBOOK_CLIENT_ID"),
                "client_secret": os.getenv("FACEBOOK_CLIENT_SECRET"),
                "access_token": short_lived_token,
            },
        )
    response.raise_for_status()
    return response.json().get("access_token")



import os
import uuid
import math
import subprocess
import threading
import json
import hashlib
import base64
import shutil
import glob
import time
import asyncio
import aiofiles
import itertools
import secrets
import re
import ipaddress
import socket
import sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from typing import Dict, Optional, List, Any
from contextlib import asynccontextmanager
from urllib.parse import urlparse, unquote, urlencode
from urllib.request import Request as UrlRequest, urlopen, HTTPRedirectHandler, build_opener
from starlette.background import BackgroundTask
from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, Request, Header, BackgroundTasks, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from pydantic import BaseModel
import jwt as pyjwt
from jwt import PyJWTError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
try:
    import stripe
except ImportError:  # pragma: no cover - optional at import time
    stripe = None
from s3_uploader import (
    upload_file_to_s3,
    generate_presigned_url,
    delete_s3_object,
    get_s3_object_size,
)
from supabase_request import (
	insert_reels as supabase_insert_reels,
	list_reels as supabase_list_reels,
	get_reel as supabase_get_reel,
	get_reel_by_job_clip as supabase_get_reel_by_job_clip,
	update_reel_media_by_job_clip as supabase_update_reel_media_by_job_clip,
	soft_delete_reel as supabase_soft_delete_reel,
	insert_captions as supabase_insert_captions,
	list_captions as supabase_list_captions,
	get_caption as supabase_get_caption,
	get_caption_by_job_clip as supabase_get_caption_by_job_clip,
	get_caption_by_job_clip_any as supabase_get_caption_by_job_clip_any,
	update_caption as supabase_update_caption,
	soft_delete_caption as supabase_soft_delete_caption,
	is_supabase_configured,
	create_project as supabase_create_project,
	list_projects as supabase_list_projects,
	get_project as supabase_get_project,
	update_project as supabase_update_project,
	update_project_status as supabase_update_project_status,
	soft_delete_project as supabase_soft_delete_project,
	get_reels_by_project as supabase_get_reels_by_project,
	get_captions_by_project as supabase_get_captions_by_project,
	increment_project_output_count as supabase_increment_project_output_count,
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
	count_active_jobs_for_user as supabase_count_active_jobs_for_user,
  get_latest_job_record_by_project as supabase_get_latest_job_record_by_project,
	get_transcription_by_job_clip as supabase_get_transcription_by_job_clip,
	upsert_transcription as supabase_upsert_transcription,
	update_transcription_translations_cache as supabase_update_transcription_translations_cache,
	insert_style_edit_version as supabase_insert_style_edit_version,
	list_style_edit_versions as supabase_list_style_edit_versions,
	delete_style_edit_versions as supabase_delete_style_edit_versions,
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
    estimate_llm_usage_cost_usd,
)
from job_manager import JobManager, JobType, calc_elapsed_seconds
from pipelines import ReelProcessingPipeline, CaptionProcessingPipeline
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Shared literals (audit: SonarQube python:S1192 -- avoid duplicating the
# same string in many places, since a future edit to one copy easily misses
# the others).
_METADATA_JSON_SUFFIX = "_metadata.json"
_METADATA_JSON_GLOB = "*_metadata.json"
_INVALID_OR_EXPIRED_SESSION_TOKEN = "Invalid or expired session token"
_CAPTIONS_PREFIX = "captions/"
_GEMINI_API_KEY_NOT_CONFIGURED = "Gemini API Key not configured on server (.env)"
_CONTENT_TYPE_JSON = "application/json"
_DEFAULT_UPLOAD_FILENAME = "upload.mp4"
_CLIP_INDEX_SUFFIX_PATTERN = r"_clip_(\d+)\.mp4$"
_JOB_NOT_FOUND = "Job not found"
_INVALID_INPUT_FILENAME = "Invalid input filename"
_CLIP_NOT_FOUND = "Clip not found"
_METADATA_NOT_FOUND = "Metadata not found"
_HTTPS_SCHEME_PREFIX = "https://"
_INVALID_SCHEDULED_DATE = "Invalid scheduled_date (expected ISO-8601)"
_SESSION_NOT_FOUND = "Session not found"
_SUPABASE_NOT_CONFIGURED = "Supabase is not configured"
_CAPTION_NOT_FOUND = "Caption not found"
_SUPABASE_PROJECTS_NOT_CONFIGURED = "Supabase projects is not configured"
_PROJECT_NOT_FOUND = "Project not found"
_REEL_NOT_FOUND = "Reel not found"
_UNSUPPORTED_PLATFORM = "Unsupported platform"


def _generic_error(
    log_message: str,
    exc: Exception,
    status_code: int = 500,
    detail: str = "Une erreur interne est survenue. Veuillez reessayer.",
) -> HTTPException:
    """Log the full exception server-side (with traceback) and return an
    HTTPException carrying only a generic, non-identifying message for the
    client. Raw exception text can leak internal file paths, library stack
    fragments, or upstream API error bodies to any caller (audit finding:
    information disclosure via error messages) -- callers should always
    `raise _generic_error(...) from exc` instead of `detail=str(exc)`.
    """
    logger.exception("%s: %s", log_message, exc)
    return HTTPException(status_code=status_code, detail=detail)


BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL", "noreply@vireel.co")
BREVO_PAYMENT_CONFIRMATION_TEMPLATE_ID = os.getenv("BREVO_PAYMENT_CONFIRMATION_TEMPLATE_ID")

load_dotenv()

# Constants
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configuration
# Default to 1 if not set, but user can set higher for powerful servers
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "5"))
# Security: caps how many non-terminal (created/queued/processing/retry_wait)
# jobs a single user can have at once, independent of MAX_CONCURRENT_JOBS
# (which only throttles *execution*, not submission). Without this, one
# account could flood the queue, local disk, and S3 storage with an
# unbounded number of simultaneous submissions (see audit finding H7).
MAX_ACTIVE_JOBS_PER_USER = int(os.environ.get("MAX_ACTIVE_JOBS_PER_USER", "3"))
QUEUE_WORKER_COUNT = int(os.environ.get("QUEUE_WORKER_COUNT", "1"))
REEL_JOB_MAX_ATTEMPTS = int(os.environ.get("REEL_JOB_MAX_ATTEMPTS", "2"))
REEL_JOB_RETRY_DELAY_SECONDS = int(os.environ.get("REEL_JOB_RETRY_DELAY_SECONDS", "15"))
CAPTION_JOB_MAX_ATTEMPTS = int(os.environ.get("CAPTION_JOB_MAX_ATTEMPTS", "2"))
CAPTION_JOB_RETRY_DELAY_SECONDS = int(os.environ.get("CAPTION_JOB_RETRY_DELAY_SECONDS", "10"))
CAPTION_TRANSCRIBE_TIMEOUT_SECONDS = int(os.environ.get("CAPTION_TRANSCRIBE_TIMEOUT_SECONDS", "1800"))
MAX_FILE_SIZE_MB = 2048  # 2GB limit
REEL_MAX_DURATION_MINUTES = float(os.environ.get("REEL_MAX_DURATION", "180"))
# Security: hard ceiling on how long the main reel-generation subprocess may
# run before being killed. Without this, a pathological/adversarial input
# (a file or filter chain that makes ffmpeg/whisper/detection spin) could
# hang a worker slot indefinitely, and since MAX_CONCURRENT_JOBS is small,
# a handful of such jobs can starve the whole queue for every user (see
# security audit finding H13).
REEL_JOB_MAX_PROCESSING_SECONDS = int(os.environ.get("REEL_JOB_MAX_PROCESSING_SECONDS", str(4 * 3600)))
# Hard ceiling for individual ffmpeg/ffprobe subprocess calls elsewhere
# (thumbnail generation, format probing, single-clip edits) that are
# expected to be quick relative to the whole job.
FFPROBE_TIMEOUT_SECONDS = int(os.environ.get("FFPROBE_TIMEOUT_SECONDS", "60"))
FFMPEG_STEP_TIMEOUT_SECONDS = int(os.environ.get("FFMPEG_STEP_TIMEOUT_SECONDS", str(2 * 3600)))
REEL_MAX_STORAGE_GB = float(os.environ.get("REEL_MAX_STORAGE", "15"))
CAPTION_MAX_DURATION_MINUTES = float(os.environ.get("CAPTION_MAX_DURATION", str(REEL_MAX_DURATION_MINUTES)))
CAPTION_MAX_STORAGE_GB = float(os.environ.get("CAPTION_MAX_STORAGE", str(REEL_MAX_STORAGE_GB)))
VIREEL_VIDEO_FORMAT = os.environ.get("VIREEL_VIDEO_FORMAT", "mp4,mov,avi")
JOB_RETENTION_SECONDS = 3600  # 1 hour retention
OUTPUT_SWEEP_INTERVAL_SECONDS = int(os.environ.get("OUTPUT_SWEEP_INTERVAL_SECONDS", str(6 * 3600)))
OUTPUT_SWEEP_MIN_AGE_SECONDS = int(os.environ.get("OUTPUT_SWEEP_MIN_AGE_SECONDS", "1800"))
SOCIAL_PUBLISH_SCHEDULER_INTERVAL_SECONDS = int(os.environ.get("SOCIAL_PUBLISH_SCHEDULER_INTERVAL_SECONDS", "10"))
DISABLE_YOUTUBE_URL = os.environ.get("DISABLE_YOUTUBE_URL", "false").lower() in ("1", "true", "yes")
HIDE_SOCIAL_PLATFORMS = os.environ.get("HIDE_SOCIAL_PLATFORMS", "false").lower() in ("1", "true", "yes")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = os.environ.get("STRIPE_CURRENCY", "eur").lower()
STRIPE_SUCCESS_URL = os.environ.get("STRIPE_SUCCESS_URL", "")
STRIPE_CANCEL_URL = os.environ.get("STRIPE_CANCEL_URL", "")
STORAGE_RETENTION_PERIODE_DAYS = max(0, int(os.environ.get("STORAGE_RETENTION_PERIODE", "7") or "7"))
STORAGE_OVERAGE_TOLERANCE_PERCENT = max(0.0, float(os.environ.get("STORAGE_OVERAGE_TOLERANCE_PERCENT", "10") or "10"))
MIN_OPERATION_START_CREDITS = float(os.environ.get("MIN_OPERATION_START_CREDITS", "1"))

# Social publishing constants
ALLOWED_YT_PRIVACY = {"public", "private", "unlisted"}
YT_CHUNK_SIZE = 8 * 1024 * 1024
YT_MAX_RETRIES_PER_CHUNK = 3
LINKEDIN_API_VERSION = os.environ.get("LINKEDIN_API_VERSION", "202607")  # YYYYMM, à mettre à jour périodiquement
LINKEDIN_MAX_RETRIES_PER_PART = 3
EXPORT_VIDEO_CRF = os.environ.get("VIREEL_EXPORT_CRF", "20")
EXPORT_VIDEO_PRESET = os.environ.get("VIREEL_EXPORT_PRESET", "medium")
EXPORT_AUDIO_BITRATE = os.environ.get("VIREEL_EXPORT_AUDIO_BITRATE", "192k")
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
        "scopes": ["pages_show_list", "pages_manage_posts", "pages_read_engagement"],
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

# Strong references to fire-and-forget background tasks. asyncio only holds
# a weak reference to a Task once nothing else references it, so a bare
# `asyncio.create_task(...)` whose return value is discarded can have its
# task garbage-collected mid-run, silently dropping the work (see the
# asyncio.create_task docs' own warning about this). Every fire-and-forget
# task in this module is created via _spawn_background_task so it can't be
# collected before it finishes.
_background_tasks: set = set()


def _spawn_background_task(coro) -> Optional["asyncio.Task"]:
    task = asyncio.create_task(coro)
    if task is not None:  # real asyncio.create_task never returns None; defensive for test doubles
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    return task

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY manquant dans l'environnement")

_oauth_serializer = URLSafeTimedSerializer(SECRET_KEY)

# Supabase issues JWTs for authenticated sessions signed either with a legacy
# shared secret (HS256) or, for newer projects, with an asymmetric signing
# key (ES256) verified via the project's public JWKS endpoint. Which one
# applies is a per-project setting (Project Settings -> API -> JWT Settings),
# so both are supported here based on the `alg` in the token's own header --
# see _verify_supabase_jwt. SUPABASE_JWT_SECRET is distinct from
# SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY and only used for HS256.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPABASE_URL_FOR_JWKS = (os.getenv("SUPABASE_URL") or "").rstrip("/")
if not SUPABASE_JWT_SECRET and not SUPABASE_URL_FOR_JWKS:
    raise RuntimeError(
        "Ni SUPABASE_JWT_SECRET ni SUPABASE_URL ne sont definis -- l'un des deux "
        "est requis pour verifier les tokens de session Supabase (sans cela, "
        "aucune requete ne peut etre authentifiee de maniere fiable)."
    )

_supabase_jwks_client: Optional["pyjwt.PyJWKClient"] = None


def _get_supabase_jwks_client() -> "pyjwt.PyJWKClient":
    global _supabase_jwks_client
    if _supabase_jwks_client is None:
        if not SUPABASE_URL_FOR_JWKS:
            raise RuntimeError(
                "SUPABASE_URL manquant dans l'environnement -- requis pour verifier "
                "les tokens de session signes en ES256 via le JWKS du projet Supabase."
            )
        _supabase_jwks_client = pyjwt.PyJWKClient(
            f"{SUPABASE_URL_FOR_JWKS}/auth/v1/.well-known/jwks.json"
        )
    return _supabase_jwks_client

router = APIRouter()


def _is_pytest_runtime() -> bool:
    return "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN")
if not FRONTEND_ORIGIN:
    if _is_pytest_runtime():
        # Test fallback: explicit non-wildcard origin keeps postMessage target strict.
        FRONTEND_ORIGIN = "http://localhost"
        logger.warning("FRONTEND_ORIGIN not set; using test fallback '%s'", FRONTEND_ORIGIN)
    else:
        raise RuntimeError(
            "FRONTEND_ORIGIN must be set (exact frontend origin, e.g. 'https://app.vireel.com') "
            "-- postMessage must never target '*' when carrying selection data."
        )

_PAGE_SELECTION_TTL_SECONDS = 600  # 10 minutes pour que l'utilisateur choisisse une page

_ENCRYPTION_KEY_RAW = os.environ.get("ENCRYPTION_KEY", "")
if not _ENCRYPTION_KEY_RAW or len(_ENCRYPTION_KEY_RAW) < 16:
    if _is_pytest_runtime():
        _ENCRYPTION_KEY_RAW = _ENCRYPTION_KEY_RAW or "unit-test-encryption-key-not-for-prod"
        logger.warning("ENCRYPTION_KEY missing/too short; using test fallback")
    else:
        raise RuntimeError(
            "ENCRYPTION_KEY manquant ou trop court (16 caracteres minimum) -- "
            "requis pour chiffrer les tokens OAuth (YouTube/TikTok/...) stockes "
            "en base. L'application refuse de demarrer plutot que de stocker "
            "des tokens en clair ou faiblement proteges."
        )

_oauth_state_secret = os.environ.get("OAUTH_STATE_SECRET")
if not _oauth_state_secret:
    # Keep startup resilient: reuse SECRET_KEY when a dedicated OAuth state secret is absent.
    _oauth_state_secret = SECRET_KEY
    if _is_pytest_runtime():
        logger.warning("OAUTH_STATE_SECRET not set; using SECRET_KEY as test fallback")
    else:
        logger.warning("OAUTH_STATE_SECRET not set; using SECRET_KEY fallback")

_page_selection_serializer = URLSafeTimedSerializer(
    _oauth_state_secret,  # réutilise ta clé secrète OAuth existante
    salt="fb-page-selection",
)

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
        base_name = os.path.basename(metadata_path).replace(_METADATA_JSON_SUFFIX, "")

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
    json_files = glob.glob(os.path.join(output_dir, _METADATA_JSON_GLOB))
    if json_files:
        return json_files[0]

    # Backward-compat rescue for artifacts emitted into OUTPUT_DIR root.
    if _relocate_root_job_artifacts(job_id, output_dir):
        json_files = glob.glob(os.path.join(output_dir, _METADATA_JSON_GLOB))
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


def _verify_supabase_jwt(token: str) -> str:
    """Verify a Supabase-issued access token and return the authenticated user's id.

    Security note: this is the ONLY source of truth for user identity in this
    application. Client-supplied identity headers (e.g. X-User-Id) must never
    be trusted on their own -- they are not proof of anything, since any
    client can set an arbitrary value. The `sub` claim of a JWT that verifies
    either against SUPABASE_JWT_SECRET (legacy HS256 projects) or against the
    project's own public key fetched from its JWKS endpoint (newer ES256/
    RS256 projects) is proof, because only Supabase Auth (which authenticated
    the user's login) could have produced a valid signature. Which path
    applies is read from the token's own header, never trusted from outside
    it: HS256 is only ever checked against our dedicated shared secret, and
    ES256/RS256 only ever against the real public key looked up by `kid` from
    Supabase's JWKS, so the two verification paths can't be crossed to forge
    a signature (no alg-confusion between a public key and a shared secret).
    """
    try:
        # NOSONAR(python:S5659): this only peeks at the `alg` header to pick
        # which key to verify against below -- pyjwt.decode() a few lines
        # down always performs full signature verification (never called
        # with verify_signature=False), against a key matched exactly to
        # the algorithm read here (see the docstring above for why that
        # pairing can't be crossed to forge a signature).
        alg = pyjwt.get_unverified_header(token).get("alg")  # NOSONAR
        if alg == "HS256":
            if not SUPABASE_JWT_SECRET:
                raise HTTPException(status_code=401, detail=_INVALID_OR_EXPIRED_SESSION_TOKEN)
            payload = pyjwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require": ["exp", "sub"]},
            )
        elif alg in ("ES256", "RS256"):
            signing_key = _get_supabase_jwks_client().get_signing_key_from_jwt(token)
            payload = pyjwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
                options={"require": ["exp", "sub"]},
            )
        else:
            raise HTTPException(status_code=401, detail=_INVALID_OR_EXPIRED_SESSION_TOKEN)
    except HTTPException:
        raise
    except PyJWTError as exc:
        logger.warning("Supabase JWT verification failed: %s", exc)
        raise HTTPException(status_code=401, detail=_INVALID_OR_EXPIRED_SESSION_TOKEN) from exc

    user_id = str(payload.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session token: missing subject")
    return user_id


def get_user_id_header(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> str:
    """FastAPI dependency resolving the authenticated caller's user id.

    Requires a verified Supabase JWT (`Authorization: Bearer <access_token>`).
    The legacy `X-User-Id` header is intentionally never consulted here: it is
    a plain client-supplied string with no cryptographic proof behind it, so
    trusting it would let any caller impersonate any other user.
    """
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing Authorization Bearer token")
    return _verify_supabase_jwt(token)


def _get_authenticated_user_id_optional(request: Request) -> Optional[str]:
    """Best-effort verified caller identity for endpoints that use it only as a
    lookup hint (never for access control). Returns None rather than raising
    when no valid Bearer token is present -- callers must not treat this as an
    authorization decision, only as an optional cache/lookup key. Never falls
    back to the unverified X-User-Id header.
    """
    authorization = request.headers.get("Authorization") or request.headers.get("authorization")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        return _verify_supabase_jwt(token)
    except HTTPException:
        return None

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


def _resolve_scheduled_datetime(value: Any, timezone_name: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None

    # Already timezone-aware (offset or trailing Z)
    if text.endswith("Z") or "+" in text[10:] or "-" in text[10:]:
        return _parse_iso_datetime(text)

    # Naive local datetime -> interpret with provided timezone
    try:
        naive = datetime.fromisoformat(text)
    except Exception:
        return None

    if naive.tzinfo is not None:
        return naive.astimezone(timezone.utc)

    tz_name = (timezone_name or "UTC").strip() or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    return naive.replace(tzinfo=tz).astimezone(timezone.utc)


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


def _preemption_sort_key(ctx: Dict[str, Any]) -> tuple[int, float]:
    priority = _clamp_job_priority(ctx.get("priority", DEFAULT_JOB_PRIORITY))
    started_at = float(ctx.get("started_at", 0.0) or 0.0)
    return (priority, started_at)


def _get_preemption_candidate() -> Optional[Dict[str, Any]]:
    if not running_reel_jobs:
        return None

    candidate_job_id, candidate_ctx = min(
        running_reel_jobs.items(),
        key=lambda item: _preemption_sort_key(item[1]),
    )
    return {
        "job_id": candidate_job_id,
        "ctx": candidate_ctx,
        "priority": _clamp_job_priority(candidate_ctx.get("priority", DEFAULT_JOB_PRIORITY)),
    }


async def _maybe_preempt_lower_priority_running_job(incoming_priority: int, incoming_job_id: str) -> None:
    incoming_priority = _clamp_job_priority(incoming_priority)
    async with running_reel_jobs_lock:
        if len(running_reel_jobs) < MAX_CONCURRENT_JOBS:
            return

        candidate = _get_preemption_candidate()
        if not candidate:
            return

        candidate_job_id = candidate["job_id"]
        candidate_priority = candidate["priority"]
        if incoming_priority <= candidate_priority:
            return

        ctx = candidate["ctx"]
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


async def _ensure_retention_deadline_on_subscription(
    latest_subscription: Dict[str, Any],
    retention_deadline: datetime,
) -> None:
    subscription_id = latest_subscription.get("id")
    if subscription_id and not latest_subscription.get("retention_deadline_at"):
        await supabase_update_souscription_row(
            str(subscription_id),
            {"retention_deadline_at": retention_deadline.isoformat()},
            user_id=latest_subscription.get("userid"),
        )


async def _zero_balances_on_subscription_expiration(
    user_id: str,
    latest_subscription: Dict[str, Any],
) -> None:
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
            operation_id=str(latest_subscription.get("id") or ""),
        )


async def _disable_subscription_account_if_needed(
    latest_subscription: Dict[str, Any],
    now_utc: datetime,
    retention_deadline: datetime,
) -> None:
    subscription_id = latest_subscription.get("id")
    if subscription_id and not latest_subscription.get("account_disabled_at"):
        await supabase_update_souscription_row(
            str(subscription_id),
            {
                "account_disabled_at": now_utc.isoformat(),
                "retention_deadline_at": retention_deadline.isoformat(),
            },
            user_id=latest_subscription.get("userid"),
        )


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
    await _ensure_retention_deadline_on_subscription(latest, retention_deadline)

    if now_utc <= retention_deadline:
        return {
            "state": "retention_window",
            "subscription": latest,
            "retention_deadline_at": retention_deadline.isoformat(),
        }

    await _zero_balances_on_subscription_expiration(user_id, latest)
    await _disable_subscription_account_if_needed(latest, now_utc, retention_deadline)

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


async def _resolve_caption_input_url(job_id: str, clip_index: int, user_id: Optional[str] = None) -> Optional[str]:
    if not is_supabase_configured():
        return None

    try:
        row = None
        if user_id:
            row = await supabase_get_caption_by_job_clip(job_id, int(clip_index), user_id)
        if not row:
            row = await supabase_get_caption_by_job_clip_any(job_id, int(clip_index))
    except Exception as e:
        print(f"⚠️ Supabase caption lookup failed for metadata hydration: {e}")
        return None

    if not row:
        return None

    # Prefer a fresh presigned URL from S3 key; fallback to stored URL.
    return _caption_media_url_from_s3_key(row.get("caption_s3_key") or "") or row.get("caption_url") or None


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


def _resolve_hydration_video_source(
    source_ref: str,
    job_id: str,
    output_dir: str,
) -> Optional[tuple[str, str]]:
    local_ref = _resolve_local_video_from_input_ref(source_ref)
    if local_ref:
        local_video_path, local_video_name = local_ref
        hydrated_video_path = os.path.join(output_dir, local_video_name)
        if os.path.abspath(local_video_path) == os.path.abspath(hydrated_video_path):
            return local_video_path, local_video_name
        try:
            shutil.copy(local_video_path, hydrated_video_path)
            return hydrated_video_path, local_video_name
        except Exception as e:
            print(f"⚠️ Could not copy local reel for metadata hydration: {e}")
            return None

    parsed_source = urlparse(source_ref)
    if parsed_source.scheme not in ("http", "https"):
        return None

    try:
        return _download_input_url_to_job_dir(source_ref, job_id)
    except Exception as e:
        print(f"⚠️ Could not download reel for metadata hydration: {e}")
        return None


async def _hydrate_missing_job_metadata(
    job_id: str,
    clip_index: int,
    input_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[str]:
    """Create minimal metadata for old reels by downloading and transcribing the clip on demand."""
    owner_user_id = (user_id or "").strip() or await _resolve_job_owner_user_id(job_id, clip_index)
    source_ref = (
        (input_url or "").strip()
        or await _resolve_reel_input_url(job_id, clip_index)
        or await _resolve_caption_input_url(job_id, clip_index, user_id=owner_user_id or None)
    )
    if not source_ref:
        return None

    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)

    resolved_source = _resolve_hydration_video_source(source_ref, job_id, output_dir)
    if not resolved_source:
        return None
    local_video_path, local_video_name = resolved_source

    cached_transcription = await _load_cached_transcription(owner_user_id or None, job_id, clip_index)
    transcript = dict(cached_transcription.get("transcript_payload") or {}) if cached_transcription else {}
    if not transcript:
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

    if owner_user_id:
        await _persist_transcription_cache(
            user_id=owner_user_id,
            job_id=job_id,
            clip_index=clip_index,
            source_type="hydration",
            source_value=source_ref,
            transcript=transcript,
        )

    return metadata_path


async def _get_or_build_job_metadata(
    job_id: str,
    clip_index: int,
    input_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    metadata_path = _resolve_job_metadata_path(job_id)
    if not metadata_path:
        metadata_path = await _hydrate_missing_job_metadata(
            job_id,
            clip_index,
            input_url=input_url,
            user_id=user_id,
        )
    if not metadata_path:
        return None, None

    try:
        async with aiofiles.open(metadata_path, "r", encoding="utf-8") as f:
            return metadata_path, json.loads(await f.read())
    except Exception as e:
        print(f"⚠️ Failed to read metadata: {e}")
        return None, None


def _transcript_full_text(transcript: Dict[str, Any]) -> str:
    if not isinstance(transcript, dict):
        return ""
    text = (transcript.get("text") or "").strip()
    if text:
        return text
    parts: List[str] = []
    for segment in (transcript.get("segments") or []):
        segment_text = (segment.get("text") or "").strip()
        if segment_text:
            parts.append(segment_text)
    return " ".join(parts).strip()


async def _load_cached_transcription(user_id: Optional[str], job_id: str, clip_index: int = 0) -> Optional[Dict[str, Any]]:
    if not is_supabase_configured() or not user_id:
        return None
    try:
        row = await supabase_get_transcription_by_job_clip(job_id, clip_index, user_id)
    except Exception as e:
        print(f"⚠️ Failed to load cached transcription: {e}")
        return None
    if not row:
        return None
    payload = row.get("transcript_payload")
    if isinstance(payload, dict) and payload.get("segments"):
        return row
    return None


async def _persist_transcription_cache(
    *,
    user_id: Optional[str],
    job_id: str,
    clip_index: int,
    source_type: str,
    source_value: str,
    transcript: Dict[str, Any],
    billing_details: Optional[Dict[str, Any]] = None,
) -> None:
    if not is_supabase_configured() or not user_id:
        return
    meta = transcript.get("meta") or {}
    payload = {
        "user_id": user_id,
        "job_id": job_id,
        "clip_index": int(clip_index),
        "source_type": source_type,
        "source_value": source_value,
        "transcript_provider": meta.get("provider") or "unknown",
        "transcript_language": transcript.get("language") or "unknown",
        "transcript_text": _transcript_full_text(transcript),
        "transcript_payload": transcript,
        "billing_details": billing_details or {},
    }
    try:
        await supabase_upsert_transcription(payload)
    except Exception as e:
        print(f"⚠️ Failed to persist transcription cache: {e}")


async def _resolve_job_owner_user_id(job_id: str, clip_index: int) -> Optional[str]:
    in_memory = jobs.get(job_id) or {}
    user_id = (in_memory.get("user_id") or "").strip()
    if user_id:
        return user_id

    if not is_supabase_configured():
        return None

    try:
        reel_row = await supabase_get_reel_by_job_clip(job_id, int(clip_index))
        reel_user = str((reel_row or {}).get("reel_user_id") or "").strip()
        if reel_user:
            return reel_user
    except Exception:
        pass

    try:
        caption_row = await supabase_get_caption_by_job_clip_any(job_id, int(clip_index))
        caption_user = str((caption_row or {}).get("caption_user_id") or "").strip()
        if caption_user:
            return caption_user
    except Exception:
        pass

    return None


def _append_style_version_to_metadata(
    data: Dict[str, Any],
    clip_index: int,
    source_video_url: str,
    output_video_url: str,
    style_config: Dict[str, Any],
) -> int:
    history = data.get("style_history")
    if not isinstance(history, dict):
        history = {}
    key = str(int(clip_index))
    entries = history.get(key)
    if not isinstance(entries, list):
        entries = []

    version_number = len(entries) + 1
    entries.append(
        {
            "version": version_number,
            "operation_type": "subtitle_style",
            "created_at": int(time.time()),
            "source_video_url": source_video_url,
            "output_video_url": output_video_url,
            "style_config": style_config,
        }
    )
    history[key] = entries
    data["style_history"] = history
    return version_number


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


def _cleanup_generated_clips_after_job(output_dir: str, base_name: str) -> None:
    """Remove generated clip files only after the reel job has fully completed."""
    if not output_dir or not base_name or not os.path.isdir(output_dir):
        return
    pattern = os.path.join(output_dir, f"{base_name}_clip_*.mp4")
    for clip_path in glob.glob(pattern):
        try:
            os.remove(clip_path)
        except FileNotFoundError:
            continue
        except Exception:
            continue


def _caption_media_url_from_s3_key(s3_key: str) -> str:
    if not s3_key:
        return ""
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return ""
    return generate_presigned_url(bucket, s3_key, expiration=7200) or ""


def _normalize_caption_row(row: Dict[str, Any]) -> Dict[str, Any]:
    media_url = _caption_media_url_from_s3_key(row.get("caption_s3_key") or "") or row.get("caption_url") or ""
    thumbnail_ref = row.get("caption_thumbnail_url") or ""
    thumbnail_url = _caption_media_url_from_s3_key(thumbnail_ref) if thumbnail_ref.startswith(_CAPTIONS_PREFIX) else thumbnail_ref
    preview_url = thumbnail_url or media_url

    return {
        **row,
        "caption_url": media_url or row.get("caption_url") or "",
        "caption_thumbnail_url": thumbnail_url,
        "caption_thumbnail_s3_key": thumbnail_ref if thumbnail_ref.startswith(_CAPTIONS_PREFIX) else "",
        "caption_playback_url": media_url,
        "caption_download_url": media_url,
        "caption_preview_url": preview_url,
        "media_url": media_url,
    }


def _is_probably_video_url(value: str) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    path = urlparse(text).path or text
    return path.endswith((".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"))


async def _ensure_preview_image_for_clip(job_id: str, clip_index: int, user_id: str) -> str:
    if not is_supabase_configured() or not user_id:
        return ""

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return ""

    reel_row: Optional[Dict[str, Any]] = None
    caption_row: Optional[Dict[str, Any]] = None

    try:
        maybe_reel = await supabase_get_reel_by_job_clip(job_id, int(clip_index), user_id=user_id)
        if str((maybe_reel or {}).get("reel_user_id") or "").strip() == user_id:
            reel_row = maybe_reel
    except Exception:
        reel_row = None

    try:
        caption_row = await supabase_get_caption_by_job_clip(job_id, int(clip_index), user_id)
    except Exception:
        caption_row = None

    if reel_row:
        reel_thumb = _normalize_reel_row(reel_row).get("reel_thumbnail_url") or ""
        if reel_thumb and not _is_probably_video_url(reel_thumb):
            return reel_thumb

    if caption_row:
        caption_thumb = _normalize_caption_row(caption_row).get("caption_thumbnail_url") or ""
        if caption_thumb and not _is_probably_video_url(caption_thumb):
            return caption_thumb

    metadata_path, metadata = await _get_or_build_job_metadata(job_id, clip_index)
    clip_data: Dict[str, Any] = {}
    if isinstance(metadata, dict):
        shorts = metadata.get("shorts") or []
        if 0 <= int(clip_index) < len(shorts) and isinstance(shorts[int(clip_index)], dict):
            clip_data = shorts[int(clip_index)]

    source_candidates: List[str] = []
    if reel_row:
        source_candidates.extend([
            _reel_media_url_from_s3_key(str(reel_row.get("reel_s3_key") or "")),
            str(reel_row.get("reel_url") or ""),
        ])
    if caption_row:
        source_candidates.extend([
            _caption_media_url_from_s3_key(str(caption_row.get("caption_s3_key") or "")),
            str(caption_row.get("caption_url") or ""),
        ])
    source_candidates.extend([
        str(clip_data.get("video_url") or ""),
        str(clip_data.get("original_video_url") or ""),
    ])

    local_video_path = ""
    downloaded_video_path = ""
    deduped_candidates: List[str] = []
    for candidate in source_candidates:
        c = str(candidate or "").strip()
        if c and c not in deduped_candidates:
            deduped_candidates.append(c)

    for candidate in deduped_candidates:
        parsed = urlparse(candidate)
        if candidate.startswith("/videos/"):
            guessed = os.path.join(OUTPUT_DIR, job_id, os.path.basename(parsed.path or ""))
            if os.path.exists(guessed):
                local_video_path = guessed
                break
        elif os.path.exists(candidate):
            local_video_path = candidate
            break
        elif parsed.scheme in ("http", "https"):
            try:
                downloaded_video_path, _ = _download_input_url_to_job_dir(candidate, job_id)
                local_video_path = downloaded_video_path
                break
            except Exception:
                continue

    if not local_video_path or not os.path.exists(local_video_path):
        return ""

    preview_url = ""
    thumb_local = _generate_reel_thumbnail_from_video(local_video_path, OUTPUT_DIR, job_id, int(clip_index))
    if not thumb_local or not os.path.exists(thumb_local):
        return ""

    try:
        reel_thumb_key = f"reels/{user_id}/{job_id}/thumbnail_{int(clip_index)}.jpg"
        caption_thumb_key = f"captions/{user_id}/{job_id}/thumbnail_{int(clip_index)}_fallback.jpg"

        reel_thumb_uploaded = upload_file_to_s3(thumb_local, bucket, reel_thumb_key)
        caption_thumb_uploaded = upload_file_to_s3(thumb_local, bucket, caption_thumb_key)

        if caption_row and caption_thumb_uploaded:
            await supabase_update_caption(
                str(caption_row.get("id")),
                user_id,
                {"caption_thumbnail_url": caption_thumb_key},
            )
            preview_url = _caption_media_url_from_s3_key(caption_thumb_key) or ""

        if reel_row and reel_thumb_uploaded:
            normalized_reel = _normalize_reel_row(reel_row)
            reel_media_url = normalized_reel.get("reel_url") or str(reel_row.get("reel_url") or "")
            if reel_media_url:
                await supabase_update_reel_media_by_job_clip(
                    job_id=job_id,
                    clip_index=int(clip_index),
                    reel_url=reel_media_url,
                    reel_s3_key=str(reel_row.get("reel_s3_key") or "") or None,
                    reel_thumbnail_url=reel_thumb_key,
                    user_id=user_id,
                )
            if not preview_url:
                preview_url = _reel_thumbnail_url_from_s3_key(reel_thumb_key) or ""
    finally:
        try:
            if os.path.exists(thumb_local):
                os.remove(thumb_local)
        except Exception:
            pass
        try:
            if downloaded_video_path and os.path.exists(downloaded_video_path):
                os.remove(downloaded_video_path)
        except Exception:
            pass

    if preview_url:
        return preview_url

    if reel_row:
        refreshed = _normalize_reel_row(await supabase_get_reel_by_job_clip(job_id, int(clip_index), user_id=user_id) or {})
        fallback_reel_thumb = str(refreshed.get("reel_thumbnail_url") or "")
        if fallback_reel_thumb and not _is_probably_video_url(fallback_reel_thumb):
            return fallback_reel_thumb
    if caption_row:
        refreshed_caption = _normalize_caption_row(await supabase_get_caption_by_job_clip(job_id, int(clip_index), user_id) or {})
        fallback_caption_thumb = str(refreshed_caption.get("caption_thumbnail_url") or "")
        if fallback_caption_thumb and not _is_probably_video_url(fallback_caption_thumb):
            return fallback_caption_thumb

    return ""


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
        base_name = os.path.basename(metadata_path).replace(_METADATA_JSON_SUFFIX, "")

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
    reserved_credits = float((job_data or {}).get("reel_required_credits") or 0.0)
    # Settle on any terminal (non-retryable) failure whenever there's a
    # partial charge to bill OR a reservation to refund -- otherwise a job
    # that fails before any billable progress (actual_credit == 0) would
    # never release its reservation back to the user.
    if not fail_result.get("retry") and user_id and (consumption["actual_credit"] > 0 or reserved_credits > 0):
        try:
            debit_applied = await reel_job_manager.debit_credits_for_job(
                job_id=job_id,
                user_id=user_id,
                credits=consumption["actual_credit"],
                storage_delta=0.0,
                operation_type="generation_reel",
                reserved_credits=reserved_credits,
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

    # Update project status to failed if associated with a project
    if is_supabase_configured() and job_data:
        project_id = job_data.get("project_id")
        if project_id:
            try:
                await supabase_update_project_status(project_id, "failed", user_id=user_id)
                logger.info(f"Project {project_id} marked as failed")
            except Exception as e:
                logger.warning(f"Failed to update project status to failed: {str(e)}")

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
    uses_youtube_source: bool = False,
    project_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not user_id:
        raise RuntimeError("Missing app user id for reel persistence")
    if not is_supabase_configured():
        raise RuntimeError("Supabase reels is not configured")

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        raise RuntimeError("AWS_S3_BUCKET is required for reel persistence")

    base_name = os.path.basename(metadata_path).replace(_METADATA_JSON_SUFFIX, "")
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
        clip_size_bytes = int(os.path.getsize(clip_path) or 0)

        media_url = _reel_media_url_from_s3_key(s3_key)
        source_thumbnail = _generate_reel_thumbnail_from_video(
            clip_path,
            output_dir,
            job_id,
            i - 1,
        )
        generated_thumbnail_locally = bool(source_thumbnail)
        if not source_thumbnail:
            source_thumbnail = clip.get("thumbnail_url") or ""

        print("🖼️ Uploading thumbnail for clip", i, "from source:", source_thumbnail)

        thumbnail_s3_key = ""
        if source_thumbnail and os.path.exists(source_thumbnail):
            thumbnail_s3_key = f"reels/{user_id}/{job_id}/thumbnail_{i - 1}.jpg"
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
        reel_cost_breakdown = _estimate_reel_cost_breakdown(
            duration_seconds=float(duration or 0),
            size_bytes=float(clip_size_bytes),
            uses_youtube_source=uses_youtube_source,
        )

        reel_row = {
            "reel_url": media_url,
            "reel_thumbnail_url": thumbnail_s3_key if thumbnail_s3_key else "",
            "reel_title": clip.get("title") or clip.get("video_title_for_youtube_short") or f"Clip {i}",
            "reel_description": clip.get("video_description_for_instagram") or clip.get("video_description_for_tiktok") or "",
            "reel_duration": max(30, int(duration or 0)),
            "reel_created_at": now_iso,
            "reel_updated_at": now_iso,
            "reel_user_id": user_id,
            "reel_status": "termine",
            "reel_size_bytes": clip_size_bytes,
            "reel_s3_key": s3_key,
            "reel_job_id": job_id,
            "reel_clip_index": i - 1,
            "billing_details": _build_billing_details(
                "generation_reel",
                reel_cost_breakdown,
                actual_storage_gb=_bytes_to_gb(clip_size_bytes),
                extra={"clip_index": i - 1},
            ),
            "total_cost_usd": 0,
        }

        # Add project_id if provided
        if project_id:
            reel_row["project_id"] = project_id

        rows.append(reel_row)

        if generated_thumbnail_locally and source_thumbnail:
            try:
                if os.path.exists(source_thumbnail):
                    os.remove(source_thumbnail)
            except Exception:
                pass

    if not rows:
        raise RuntimeError("No generated clips were available for Supabase persistence")

    saved_rows = await supabase_insert_reels(rows)

    # Update project output count if project exists
    if project_id:
        try:
            await supabase_increment_project_output_count(project_id, user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to increment project output count: {str(e)}")

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
            _spawn_background_task(run_job_wrapper(job_id, job_priority))

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
            if str(job.get("job_kind") or "reel") == "caption":
                await run_caption_job(job_id, job, execution_ctx=execution_ctx)
            else:
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
    scheduler_task = asyncio.create_task(process_scheduled_social_publish_jobs())
    yield
    # Cleanup (optional: cancel worker)
    for task in worker_tasks:
        task.cancel()
    cleanup_task.cancel()
    scheduler_task.cancel()

app = FastAPI(lifespan=lifespan)

# Enable CORS for frontend.
# Security: a wildcard origin combined with allow_credentials=True lets any
# website make authenticated-as-any-caller cross-origin requests and read
# the JSON response -- an explicit allow-list is required instead. Defaults
# to FRONTEND_ORIGIN (already a required, exact-origin env var used for the
# OAuth postMessage target); additional origins (e.g. a staging domain) can
# be added via CORS_ALLOWED_ORIGINS (comma-separated).
_cors_extra_origins = [
    o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
_cors_allowed_origins = sorted(set([FRONTEND_ORIGIN, *_cors_extra_origins]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins,
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
async def proxy_media(request: Request, url: str, user_id: str = Depends(get_user_id_header)):
    """Proxy remote media through the backend so browser-side Remotion can fetch it same-origin.

    Security: this endpoint performs a server-side HTTP request to a URL the
    caller fully controls -- a classic SSRF primitive. It must never be
    reachable without authentication, and every request (including redirect
    hops) must go through _validate_download_url so it cannot be used to
    reach cloud metadata endpoints or internal/loopback services.
    """
    import httpx

    _validate_download_url(url)

    forward_headers = {}
    if request.headers.get("range"):
        forward_headers["Range"] = request.headers["range"]
    if request.headers.get("user-agent"):
        forward_headers["User-Agent"] = request.headers["user-agent"]

    client = httpx.AsyncClient(follow_redirects=False, timeout=120.0)
    try:
        upstream = await _validated_stream_request(client, "GET", url, headers=forward_headers)
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
        # NOSONAR(python:S7487): this supervises the child process with
        # Popen + a non-blocking .poll()/.terminate() loop yielding via
        # `await asyncio.sleep(2)` between checks -- Popen's own spawn and
        # .poll()/.terminate() calls don't block the loop for any
        # meaningful duration (they're near-instant syscalls), and stdout
        # is drained on a dedicated thread below rather than on this task.
        # Converting to asyncio.create_subprocess_exec would need a
        # parallel rewrite of the preemption/timeout/partial-result-polling
        # state machine below and the threaded log capture -- deliberately
        # deferred as its own separately-tested change given how central
        # this function is to job execution, rather than rewritten
        # untested in the same pass as unrelated Sonar findings.
        process = subprocess.Popen(  # NOSONAR
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
        timed_out = False
        while process.poll() is None:
            if execution_ctx and execution_ctx.get("preempt_requested"):
                try:
                    process.terminate()
                except Exception:
                    pass
            elif time.time() - start_wait > REEL_JOB_MAX_PROCESSING_SECONDS:
                # Security/reliability: kill a job that has been running far
                # longer than any legitimate input should require, instead
                # of letting it occupy a worker slot indefinitely (see
                # security audit finding H13).
                timed_out = True
                jobs[job_id]['logs'].append(
                    f"Job exceeded max processing time ({REEL_JOB_MAX_PROCESSING_SECONDS}s); terminating."
                )
                try:
                    process.terminate()
                except Exception:
                    pass
            await asyncio.sleep(2)

            # Check for partial results every 2 seconds
            # Look for metadata file
            try:
                json_files = glob.glob(os.path.join(output_dir, _METADATA_JSON_GLOB))
                if json_files:
                    target_json = json_files[0]
                    # Read metadata (it might be being written to, so simple try/except or just read)
                    # Use a lock or just robust read? json.load might fail if file is partial.
                    # Usually main.py writes it once at start (based on my review).
                    if os.path.getsize(target_json) > 0:
                        # NOSONAR(python:S7493): a small, infrequent read
                        # (this loop only reaches here once every 2s, see
                        # the `await asyncio.sleep(2)` a few lines up) --
                        # not worth the risk of converting to aiofiles here,
                        # which would break this function's existing
                        # `builtins.open` test-mocking (aiofiles captures
                        # its own reference to open() at import time, before
                        # a test's monkeypatch of builtins.open can apply).
                        with open(target_json, 'r') as f:  # NOSONAR
                            data = json.load(f)

                        base_name = os.path.basename(target_json).replace(_METADATA_JSON_SUFFIX, '')
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
                                 clip_copy = dict(clip)
                                 clip_copy['video_url'] = f"/videos/{job_id}/{clip_filename}"
                                 clip_copy['reel_clip_index'] = i
                                 clip_copy['reel_job_id'] = job_id
                                 ready_clips.append(clip_copy)

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
            json_files = glob.glob(os.path.join(output_dir, _METADATA_JSON_GLOB))
            if not json_files:
                # Backward-compat rescue if outputs were written to OUTPUT_DIR root
                if _relocate_root_job_artifacts(job_id, output_dir):
                    json_files = glob.glob(os.path.join(output_dir, _METADATA_JSON_GLOB))
            if json_files:
                target_json = json_files[0]
                # NOSONAR(python:S7493): same reasoning as the read above in
                # this function -- small one-off read, and this function's
                # tests patch builtins.open directly (which aiofiles, having
                # captured its own reference to the real open() at import
                # time, wouldn't observe).
                with open(target_json, 'r') as f:  # NOSONAR
                    data = json.load(f)

                # Enhance result with video URLs
                clips = data.get('shorts', [])
                cost_analysis = data.get('cost_analysis')

                try:
                    await pipeline.uploading_reels(len(clips))
                    project_id = job_data.get("project_id") if job_data else None
                    saved_rows = await _persist_reels_for_job(
                        job_id=job_id,
                        user_id=user_id,
                        output_dir=output_dir,
                        metadata_path=target_json,
                        clips=clips,
                        uses_youtube_source=source_is_url,
                        project_id=project_id,
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
                        _spawn_background_task(_schedule_reel_retry(job_id, REEL_JOB_RETRY_DELAY_SECONDS))
                    return

                enriched_clips: List[Dict[str, Any]] = []
                for i, clip in enumerate(clips):
                    clip_copy = dict(clip)
                    clip_copy['reel_clip_index'] = i
                    clip_copy['reel_job_id'] = job_id
                    if i < len(saved_rows):
                        clip_copy['video_url'] = saved_rows[i].get('reel_playback_url') or saved_rows[i].get('reel_url')
                        clip_copy['reel_id'] = saved_rows[i].get('id')
                        clip_copy['thumbnail_url'] = saved_rows[i].get('reel_thumbnail_url') or saved_rows[i].get('reel_preview_url') or ''
                        clip_copy['preview_image_url'] = saved_rows[i].get('reel_preview_url') or saved_rows[i].get('reel_thumbnail_url') or ''
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
                job_reserved_credits = float(job_data.get("reel_required_credits") or 0.0)
                # Settle whenever there's an actual charge/storage change OR an
                # outstanding reservation to release -- otherwise a job whose
                # actual cost rounds to 0 would never refund its reservation.
                if is_supabase_configured() and user_id and (
                    billing["actual_credit"] > 0 or billing["actual_storage_gb"] > 0 or job_reserved_credits > 0
                ):
                    try:
                        logger.info(f"Debiting credits for job {job_id}")
                        debit_applied = await reel_job_manager.debit_credits_for_job(
                            job_id=job_id,
                            user_id=user_id,
                            credits=billing["actual_credit"],
                            storage_delta=-billing["actual_storage_gb"],
                            operation_type="generation_reel",
                            reserved_credits=job_reserved_credits,
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

                # Update project status to completed if associated with a project
                project_id = job_data.get("project_id") if job_data else None
                if project_id and is_supabase_configured():
                    try:
                        await supabase_update_project_status(project_id, "completed", user_id=user_id)
                        summary_text = ""
                        if enriched_clips:
                            top_clip = enriched_clips[0] if isinstance(enriched_clips[0], dict) else {}
                            summary_text = (
                                str(top_clip.get("video_description_for_instagram") or "")
                                or str(top_clip.get("video_description_for_tiktok") or "")
                                or str(top_clip.get("video_title_for_youtube_short") or "")
                            )
                        if not summary_text and saved_rows:
                            first_row = saved_rows[0] if isinstance(saved_rows[0], dict) else {}
                            summary_text = str(first_row.get("reel_description") or "")

                        thumbnail_url = ""
                        if saved_rows:
                            first_row = saved_rows[0] if isinstance(saved_rows[0], dict) else {}
                            thumbnail_url = str(first_row.get("reel_thumbnail_url") or "")

                        project_updates = {
                            "description": _build_short_project_summary(summary_text),
                            "output_count": len(saved_rows),
                        }
                        source_duration_value = int(float((job_data or {}).get("source_duration_seconds") or 0.0))
                        if source_duration_value > 0:
                            project_updates["source_duration"] = source_duration_value
                        if thumbnail_url:
                            project_updates["thumbnail_url"] = thumbnail_url
                        await supabase_update_project(project_id, user_id or "", project_updates)
                        logger.info(f"Project {project_id} marked as completed")
                    except Exception as e:
                        logger.warning(f"Failed to update project status to completed: {str(e)}")

                _cleanup_generated_clips_after_job(output_dir, os.path.basename(target_json).replace(_METADATA_JSON_SUFFIX, ''))
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
                     _spawn_background_task(_schedule_reel_retry(job_id, REEL_JOB_RETRY_DELAY_SECONDS))
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
                _spawn_background_task(_schedule_reel_retry(job_id, REEL_JOB_RETRY_DELAY_SECONDS))

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
            _spawn_background_task(_schedule_reel_retry(job_id, REEL_JOB_RETRY_DELAY_SECONDS))
    finally:
        # Only remove uploaded source files (stored under UPLOAD_DIR).
        # Downloaded files inside output/<job_id>/ must be preserved for retries;
        # they will be cleaned up by the periodic output sweep.
        if input_path and os.path.exists(input_path):
            output_job_dir = os.path.abspath(os.path.join(OUTPUT_DIR, job_id))
            is_in_output_dir = os.path.abspath(input_path).startswith(output_job_dir)
            if not is_in_output_dir:
                try:
                    os.remove(input_path)
                except Exception:
                    pass


async def run_caption_job(job_id: str, job_data: Dict[str, Any], execution_ctx: Optional[Dict[str, Any]] = None):
    user_id = job_data.get("user_id")
    output_dir = str(job_data.get("output_dir") or "")
    input_path = str(job_data.get("input_path") or "")
    source_name = str(job_data.get("source_name") or os.path.basename(input_path) or "caption_source.mp4")
    caption_required_credits = float(job_data.get("caption_required_credits") or 0.0)
    pipeline = CaptionProcessingPipeline(reel_job_manager, job_id)

    jobs[job_id]["status"] = "processing"
    jobs[job_id]["logs"].append("Caption job started by worker.")
    await reel_job_manager.start_job(job_id)

    try:
        await pipeline.analyzing()
        if not input_path or not os.path.exists(input_path):
            raise RuntimeError("Uploaded source video not found for caption job")

        local_duration = _probe_local_video_duration_seconds(input_path)
        _validate_caption_source_constraints(
            duration_seconds=local_duration,
            size_bytes=float(os.path.getsize(input_path) if os.path.exists(input_path) else 0),
            source_label="fichier",
        )

        await pipeline.transcribing()
        cached_transcription = await _load_cached_transcription(user_id, job_id, 0)
        if cached_transcription:
            transcript = dict(cached_transcription.get("transcript_payload") or {})
            jobs[job_id]["logs"].append("Using cached transcription from database.")
        else:
            from main import transcribe_video

            loop = asyncio.get_event_loop()
            transcript = await asyncio.wait_for(
                loop.run_in_executor(None, transcribe_video, input_path),
                timeout=max(1, CAPTION_TRANSCRIBE_TIMEOUT_SECONDS),
            )
            await _persist_transcription_cache(
                user_id=user_id,
                job_id=job_id,
                clip_index=0,
                source_type="caption_upload",
                source_value=source_name,
                transcript=transcript,
            )

        await pipeline.persisting()
        duration_sec = max(0.5, float(local_duration) or _estimate_transcript_duration_seconds(transcript))
        caption_storage_gb = _bytes_to_gb(float(os.path.getsize(input_path) if os.path.exists(input_path) else 0))
        caption_cost_breakdown = _estimate_caption_cost_breakdown(
            duration_seconds=duration_sec,
            size_bytes=float(os.path.getsize(input_path) if os.path.exists(input_path) else 0),
            uses_assembly=True,
            uses_openai=True,
            uses_gemini=False,
        )
        title = os.path.splitext(source_name)[0] or "Sous-titres"
        local_video_ref = f"/videos/{job_id}/{os.path.basename(input_path)}"

        metadata = {
            "shorts": [
                {
                    "title": title,
                    "start": 0.0,
                    "end": duration_sec,
                    "duration": duration_sec,
                    "video_url": local_video_ref,
                    "video_title_for_youtube_short": title,
                    "video_description_for_instagram": "",
                    "video_description_for_tiktok": "",
                }
            ],
            "transcript": transcript,
            "standalone_caption": {
                "created_at": int(time.time()),
                "source": "upload",
                "input_filename": source_name,
            },
        }
        metadata_path = os.path.join(output_dir, f"{job_id}_metadata.json")
        _persist_metadata_json(metadata_path, metadata)

        bucket = os.environ.get("AWS_S3_BUCKET", "")
        if not bucket:
            raise RuntimeError("AWS_S3_BUCKET is required for caption persistence")
        caption_s3_key = ""
        media_url = local_video_ref
        thumbnail_ref = ""
        caption_s3_key = f"captions/{user_id}/{job_id}/{os.path.basename(input_path)}"
        if not upload_file_to_s3(input_path, bucket, caption_s3_key):
            raise RuntimeError("Failed to upload caption source video to S3")
        media_url = _caption_media_url_from_s3_key(caption_s3_key) or local_video_ref

        thumb_local = _generate_reel_thumbnail_from_video(input_path, OUTPUT_DIR, job_id, 0)
        if thumb_local:
            thumb_key = f"captions/{user_id}/{job_id}/thumbnail.jpg"
            if upload_file_to_s3(thumb_local, bucket, thumb_key):
                thumbnail_ref = thumb_key
            try:
                if os.path.exists(thumb_local):
                    os.remove(thumb_local)
            except Exception:
                pass

        now_iso = datetime.now(timezone.utc).isoformat()
        row_payload: Dict[str, Any] = {
            "caption_url": media_url,
            "caption_thumbnail_url": thumbnail_ref,
            "caption_title": title,
            "caption_description": "",
            "caption_duration": max(1, int(round(duration_sec))),
            "caption_created_at": now_iso,
            "caption_updated_at": now_iso,
            "caption_user_id": user_id,
            "caption_status": "termine",
            "caption_job_id": job_id,
            "caption_clip_index": 0,
            "caption_s3_key": caption_s3_key,
            "generation_inputs": {
                "source_type": "file",
                "source_value": source_name,
                "caption_max_duration_minutes": CAPTION_MAX_DURATION_MINUTES,
                "caption_max_storage_gb": CAPTION_MAX_STORAGE_GB,
                "duration_seconds": duration_sec,
            },
            "input_source_type": "file",
            "input_source_value": source_name,
            "billing_details": _build_billing_details(
                "sous_titre",
                caption_cost_breakdown,
                actual_credit=caption_required_credits,
                actual_storage_gb=caption_storage_gb,
                extra={
                    "source_type": "file",
                    "source_value": source_name,
                },
            ),
            "total_cost_usd": 0,
        }
        project_id = str(job_data.get("project_id") or "").strip()
        if project_id:
            row_payload["project_id"] = project_id

        normalized_item = {"id": f"local-{job_id}", **row_payload}
        if is_supabase_configured():
            saved = await supabase_insert_captions([row_payload])
            if saved:
                normalized_item = _normalize_caption_row(saved[0])

            if user_id and (caption_required_credits > 0 or caption_storage_gb > 0):
                debit_ok = await reel_job_manager.debit_credits_for_job(
                    job_id=job_id,
                    user_id=user_id,
                    credits=caption_required_credits,
                    storage_delta=-caption_storage_gb,
                    operation_type="sous_titre",
                    reserved_credits=caption_required_credits,
                )
                if not debit_ok:
                    raise RuntimeError("Insufficient credit/storage balance to finalize caption job")

        await pipeline.rendering()
        result_payload = {
            "item": _normalize_caption_row(normalized_item),
            "job_id": job_id,
            "clip_index": 0,
        }
        jobs[job_id]["result"] = result_payload
        jobs[job_id]["status"] = "completed"
        await reel_job_manager.complete_job(
            job_id,
            result_payload,
            actual_credit=caption_required_credits,
            actual_storage_gb=caption_storage_gb,
            consumed_quota=1.0,
            cost_breakdown=caption_cost_breakdown,
        )

        # Update project status to completed if associated with a project
        project_id = job_data.get("project_id")
        if project_id and is_supabase_configured():
            try:
                await supabase_update_project_status(project_id, "completed", user_id=user_id)
                project_summary = _build_short_project_summary(
                    str(normalized_item.get("caption_description") or "")
                    or str(normalized_item.get("caption_title") or "")
                )
                await supabase_update_project(
                    project_id,
                    user_id or "",
                    {
                        "description": project_summary,
                        "thumbnail_url": str(normalized_item.get("caption_thumbnail_url") or "") or None,
                        "output_count": 1,
                        "source_duration": int(float(job_data.get("source_duration_seconds") or local_duration or 0.0)) or None,
                    },
                )
                logger.info(f"Project {project_id} marked as completed")
            except Exception as e:
                logger.warning(f"Failed to update project status to completed: {str(e)}")

        await _persist_transcription_cache(
            user_id=user_id,
            job_id=job_id,
            clip_index=0,
            source_type="caption_upload",
            source_value=source_name,
            transcript=transcript,
            billing_details=_build_billing_details(
                "sous_titre",
                caption_cost_breakdown,
                actual_credit=caption_required_credits,
                actual_storage_gb=caption_storage_gb,
                extra={
                    "source_type": "file",
                    "source_value": source_name,
                },
            ),
        )
    except Exception as exc:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["logs"].append(f"Caption job failed: {exc}")
        result = await reel_job_manager.fail_job(
            job_id,
            str(exc),
            error_code="CAPTION_JOB_FAILED",
            retry_delay_seconds=CAPTION_JOB_RETRY_DELAY_SECONDS,
        )

        # Update project status to failed if associated with a project
        if is_supabase_configured():
            project_id = job_data.get("project_id")
            if project_id:
                try:
                    await supabase_update_project_status(project_id, "failed", user_id=user_id)
                    logger.info(f"Project {project_id} marked as failed")
                except Exception as e:
                    logger.warning(f"Failed to update project status to failed: {str(e)}")

        # Release the reservation made at job creation: nothing was billed
        # in this failure path, so the full reserved amount is refundable.
        if not result.get("retry") and user_id:
            reserved = float(job_data.get("caption_required_credits") or 0.0)
            if reserved > 0 and is_supabase_configured():
                try:
                    await reel_job_manager.refund_reservation(job_id, user_id, reserved, operation_type="sous_titre")
                except Exception as refund_error:
                    logger.warning(f"Failed to refund caption reservation: {refund_error}")

        if result.get("retry"):
            _spawn_background_task(_schedule_reel_retry(job_id, CAPTION_JOB_RETRY_DELAY_SECONDS))
    finally:
        # Keep caption sources local only during processing.
        if input_path and os.path.exists(input_path):
            try:
                os.remove(input_path)
            except Exception:
                pass

@app.get("/api/config")
async def get_config():
    return {
        "youtubeUrlEnabled": not DISABLE_YOUTUBE_URL,
        "hideSocialPlatforms": HIDE_SOCIAL_PLATFORMS,
        "captionMaxDurationMinutes": CAPTION_MAX_DURATION_MINUTES,
        "captionMaxStorageGb": CAPTION_MAX_STORAGE_GB,
    }

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
        out = subprocess.check_output(probe_cmd, stderr=subprocess.STDOUT, timeout=FFPROBE_TIMEOUT_SECONDS).decode().strip()
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


def _probe_remote_video_metadata(url_value: str) -> Dict[str, Any]:
    """Best-effort remote metadata probe via yt-dlp without downloading the file."""
    if not url_value:
        return {"duration_seconds": 0.0, "size_bytes": 0.0, "title": "", "description": ""}

    # Security: url_value is client-supplied. Require it to actually look
    # like an http(s) URL before ever handing it to yt-dlp -- otherwise a
    # value starting with "-" could be parsed as a yt-dlp CLI flag (e.g.
    # --exec) instead of a target URL (argument injection). The "--" below
    # is a second, independent layer: it tells yt-dlp's own argument parser
    # that everything after it is a positional argument, never an option,
    # regardless of what url_value contains.
    if urlparse(url_value).scheme not in ("http", "https"):
        return {"duration_seconds": 0.0, "size_bytes": 0.0, "title": "", "description": ""}

    try:
        cmd = ["yt-dlp", "--dump-json", "--skip-download", "--no-warnings", "--", url_value]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=FFPROBE_TIMEOUT_SECONDS).decode().strip()
        if not out:
            return {"duration_seconds": 0.0, "size_bytes": 0.0, "title": "", "description": ""}
        payload = json.loads(out.splitlines()[-1])
        duration = float(payload.get("duration") or 0)
        size_bytes = float(payload.get("filesize") or payload.get("filesize_approx") or 0)
        title = str(payload.get("title") or "").strip()
        description = str(payload.get("description") or "").strip()
        return {
            "duration_seconds": max(0.0, duration),
            "size_bytes": max(0.0, size_bytes),
            "title": title,
            "description": description,
        }
    except Exception:
        return {"duration_seconds": 0.0, "size_bytes": 0.0, "title": "", "description": ""}


def _build_short_project_summary(raw_text: str, fallback_title: str = "") -> str:
    """Create a short project summary from available source metadata."""
    base = re.sub(r"\s+", " ", str(raw_text or "")).strip()
    if not base:
        base = re.sub(r"\s+", " ", str(fallback_title or "")).strip()
    if not base:
        return ""

    sentence = re.split(r"[\n\r]+|(?<=[.!?])\s+", base, maxsplit=1)[0].strip()
    compact = sentence or base
    words = compact.split()
    if len(words) > 18:
        compact = " ".join(words[:18]).rstrip(" ,;:-") + "..."
    return compact[:180]


def _project_name_from_uploaded_file(filename: str) -> str:
    source_name = os.path.basename(str(filename or "")).strip()
    if not source_name:
        return "Projet video"
    return os.path.splitext(source_name)[0] or source_name


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


def _validate_caption_source_constraints(duration_seconds: float, size_bytes: float, source_label: str) -> None:
    max_duration_seconds = max(0.0, CAPTION_MAX_DURATION_MINUTES) * 60.0
    max_size_bytes = max(0.0, CAPTION_MAX_STORAGE_GB) * (1024 ** 3)

    if max_size_bytes > 0 and size_bytes > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Source {source_label} trop volumineuse: {_bytes_to_gb(size_bytes):.2f} Go. "
                f"Maximum autorise: {CAPTION_MAX_STORAGE_GB:.2f} Go."
            ),
        )

    if max_duration_seconds > 0 and duration_seconds > max_duration_seconds:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Source {source_label} trop longue: {duration_seconds / 60.0:.2f} min. "
                f"Maximum autorise: {CAPTION_MAX_DURATION_MINUTES:.2f} min."
            ),
        )


def _estimate_reel_required_credits(
    duration_seconds: float,
    size_bytes: float,
    uses_youtube_source: bool,
    *,
    uses_openai: bool = True,
    uses_assembly: bool = True,
    uses_gemini: bool = False,
) -> float:
    return float(
        _estimate_reel_cost_breakdown(
            duration_seconds=duration_seconds,
            size_bytes=size_bytes,
            uses_youtube_source=uses_youtube_source,
            uses_openai=uses_openai,
            uses_assembly=uses_assembly,
            uses_gemini=uses_gemini,
        )["final_credits"]
    )


def _estimate_reel_cost_breakdown(
    duration_seconds: float,
    size_bytes: float,
    uses_youtube_source: bool,
    *,
    uses_openai: bool = True,
    uses_assembly: bool = True,
    uses_gemini: bool = False,
) -> Dict[str, Any]:
    duration_minutes = max(1.0, float(duration_seconds or 0.0) / 60.0)
    video_size_gb = max(0.0, _bytes_to_gb(float(size_bytes or 0.0)))
    youtube_download_gb = video_size_gb if uses_youtube_source else 0.0
    breakdown = estimate_reel_cost_usd(
        duration_minutes=duration_minutes,
        video_size_gb=video_size_gb,
        uses_youtube_download=uses_youtube_source,
        youtube_download_gb=youtube_download_gb,
        uses_openai=uses_openai,
        uses_assembly=uses_assembly,
        uses_gemini=uses_gemini,
    )
    return calculate_credits_for_operation(breakdown)


def _estimate_caption_required_credits(
    duration_seconds: float,
    size_bytes: float,
    *,
    uses_assembly: bool = True,
    uses_openai: bool = True,
    uses_gemini: bool = False,
) -> float:
    return float(
        _estimate_caption_cost_breakdown(
            duration_seconds=duration_seconds,
            size_bytes=size_bytes,
            uses_assembly=uses_assembly,
            uses_openai=uses_openai,
            uses_gemini=uses_gemini,
        )["final_credits"]
    )


def _estimate_caption_cost_breakdown(
    duration_seconds: float,
    size_bytes: float,
    *,
    uses_assembly: bool = True,
    uses_openai: bool = True,
    uses_gemini: bool = False,
) -> Dict[str, Any]:
    duration_minutes = max(1.0, float(duration_seconds or 0.0) / 60.0)
    video_size_gb = max(0.0, _bytes_to_gb(float(size_bytes or 0.0)))
    breakdown = estimate_caption_cost_usd(
        duration_minutes=duration_minutes,
        video_size_gb=video_size_gb,
        uses_assembly=uses_assembly,
        uses_openai=uses_openai,
        uses_gemini=uses_gemini,
    )
    return calculate_credits_for_operation(breakdown)


def _build_billing_details(
    operation: str,
    cost_breakdown: Optional[Dict[str, Any]] = None,
    *,
    actual_credit: Optional[float] = None,
    actual_storage_gb: float = 0.0,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    raw = dict(cost_breakdown or {})
    details: Dict[str, Any] = {
        "s3_usd": 0.0,
        "vps_usd": 0.0,
        "dataimpulse_usd": 0.0,
        "assembly_usd": 0.0,
        "openai_usd": 0.0,
        "gemini_usd": 0.0,
        "total_usd": 0.0,
        "base_credits": 0.0,
        "majoration_factor": 1.0,
        "final_credits": 0.0,
    }
    for key in list(details.keys()):
        try:
            details[key] = float(raw.get(key, details[key]) or 0.0)
        except Exception:
            details[key] = 0.0
    for key, value in raw.items():
        if key not in details:
            details[key] = value

    resolved_credit = details.get("final_credits", 0.0) if actual_credit is None else float(actual_credit or 0.0)
    details.update(
        {
            "operation": operation,
            "actual_credit": round(float(resolved_credit), 2),
            "actual_storage_gb": round(max(0.0, float(actual_storage_gb or 0.0)), 6),
        }
    )
    if extra:
        details.update(extra)
    return details


async def _enforce_job_concurrency_limit(user_id: str) -> None:
    """Reject new job submissions once a user already has
    MAX_ACTIVE_JOBS_PER_USER non-terminal jobs. MAX_CONCURRENT_JOBS only
    throttles execution (a semaphore around actually running jobs) -- it
    does nothing to stop one account from enqueueing an unbounded number of
    jobs, each of which uploads a source file to S3 and occupies a queue
    slot/local disk/database row before ever being throttled by that
    semaphore (see security audit finding H7)."""
    if not is_supabase_configured():
        return
    active_count = await supabase_count_active_jobs_for_user(user_id)
    if active_count >= MAX_ACTIVE_JOBS_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Trop de traitements en cours ({active_count}/{MAX_ACTIVE_JOBS_PER_USER}). "
                f"Attendez qu'un traitement se termine avant d'en lancer un nouveau."
            ),
        )


async def _assert_user_has_required_credits(user_id: str, required_credits: float) -> float:
    required = float(required_credits or 0.0)
    if not is_supabase_configured():
        return required

    user_data = await supabase_get_user_data(user_id)
    available = float(user_data.get("credit", 0)) if user_data else 0.0
    # Security: the balance must cover both the actual estimated cost of this
    # operation AND the baseline minimum -- previously `required_credits` was
    # computed but never compared against `available`, letting any account
    # with a token balance above MIN_OPERATION_START_CREDITS (default 1)
    # launch operations of arbitrary cost for free while accruing unlimited
    # debt (see security audit finding C7).
    effective_minimum = max(MIN_OPERATION_START_CREDITS, required)
    if available < effective_minimum:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Crédits insuffisants pour lancer l'operation. "
                f"Requis : {effective_minimum} cr, disponible : {available} cr."
            ),
        )
    return required


async def _assert_user_has_storage_headroom(user_id: str) -> None:
    """Reject new uploads once the user's aggregate storage quota is already
    exhausted (audit finding P2-10).

    Storage consumption is only ever settled against ``stockage``/
    ``stockage_max`` at job completion (see deduct_user_credits'
    storage_delta), once the actual output size is known. Nothing upstream
    of that stopped an account already over its storage quota from starting
    yet more jobs -- only the credit balance gated new work. This mirrors
    the same overage tolerance used at settlement time so an account isn't
    blocked here by a stricter rule than the one that will actually charge it.
    """
    if not is_supabase_configured():
        return
    user_data = await supabase_get_user_data(user_id)
    if not user_data:
        return
    current_storage = float(user_data.get("stockage", 0) or 0.0)
    storage_max = float(user_data.get("stockage_max", max(current_storage, 0.0)) or 0.0)
    overage_limit = (storage_max * STORAGE_OVERAGE_TOLERANCE_PERCENT) / 100.0
    if current_storage < -overage_limit:
        raise HTTPException(
            status_code=402,
            detail=(
                "Quota de stockage depasse. Liberez de l'espace ou mettez a "
                "niveau votre abonnement avant de lancer un nouveau traitement."
            ),
        )


async def _reserve_job_credits(user_id: str, required_credits: float) -> float:
    """Atomically reserve ``required_credits`` for a queued job (reel/caption
    generation) instead of merely checking the balance covers it. Two
    concurrent job submissions can no longer both pass a stale balance
    check before either is billed: the second submission sees the
    already-reduced balance from the first reservation (see security audit
    finding H8). The reservation is settled (extra debit or refund of the
    difference) against the job's actual cost at completion/failure via
    JobManager.debit_credits_for_job(reserved_credits=...), or refunded in
    full via JobManager.refund_reservation if the job never runs.
    """
    required = float(required_credits or 0.0)
    if not is_supabase_configured():
        return required
    if not await reel_job_manager.reserve_credits(user_id, required):
        available = float((await supabase_get_user_data(user_id) or {}).get("credit", 0))
        raise HTTPException(
            status_code=402,
            detail=(
                f"Crédits insuffisants pour lancer l'operation. "
                f"Requis : {math.ceil(required)} cr, disponible : {available} cr."
            ),
        )
    return required


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


_AUTO_EDIT_KEYS = (
    "zoom",
    "brightness",
    "saturation",
    "contrast",
    "speed",
    "removeSilence",
    "cleanAudio",
    "removeBadTakes",
)


def _normalize_auto_edit_options(raw_options: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    raw = raw_options or {}
    return {key: bool(raw.get(key)) for key in _AUTO_EDIT_KEYS}


def _apply_auto_edit_options_to_effects_config(
    effects_config: Optional[Dict[str, Any]],
    raw_options: Optional[Dict[str, Any]],
) -> tuple[Dict[str, Any], List[str]]:
    config = dict(effects_config or {})
    options = _normalize_auto_edit_options(raw_options)
    segments = config.get("segments") or []
    processed_segments: List[Dict[str, Any]] = []

    for segment in segments:
        seg = dict(segment or {})
        if not options["zoom"]:
            seg["zoom"] = 1.0
            seg["zoomCenterX"] = 0.5
            seg["zoomCenterY"] = 0.5
        if not options["brightness"]:
            seg["brightness"] = 1.0
        if not options["contrast"]:
            seg["contrast"] = 1.0
        if not options["saturation"]:
            seg["saturate"] = 1.0
        processed_segments.append(seg)

    config["segments"] = processed_segments

    applied_steps: List[str] = []
    if options["removeBadTakes"]:
        applied_steps.append("remove_bad_takes:queued")
    if options["removeSilence"]:
        applied_steps.append("remove_silence:queued")
    if options["cleanAudio"]:
        applied_steps.append("clean_audio:queued")
    if options["zoom"]:
        applied_steps.append("zoom:enabled")
    if options["brightness"]:
        applied_steps.append("brightness:enabled")
    if options["saturation"]:
        applied_steps.append("saturation:enabled")
    if options["contrast"]:
        applied_steps.append("contrast:enabled")
    if options["speed"]:
        applied_steps.append("speed:queued")

    return config, applied_steps


def _apply_auto_edit_options_to_filter_data(
    filter_data: Optional[Dict[str, Any]],
    raw_options: Optional[Dict[str, Any]],
) -> tuple[Dict[str, Any], List[str]]:
    data = dict(filter_data or {})
    filter_string = str(data.get("filter_string") or "").strip()
    options = _normalize_auto_edit_options(raw_options)
    if not filter_string:
        return data, []

    chain = VideoEditor._split_filter_chain(filter_string)
    normalized_chain: List[str] = []
    for part in chain:
        low = part.lower()

        if "zoompan=" in low and not options["zoom"]:
            continue
        if "hue=" in low and not options["saturation"]:
            continue
        if "eq=" in low and not (options["brightness"] or options["contrast"] or options["saturation"]):
            continue

        normalized_chain.append(part)

    data["filter_string"] = ",".join(normalized_chain)
    _, applied_steps = _apply_auto_edit_options_to_effects_config({"segments": []}, raw_options)
    return data, applied_steps


def _run_ffmpeg_command(cmd: List[str]) -> None:
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=FFMPEG_STEP_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"FFmpeg command timed out after {FFMPEG_STEP_TIMEOUT_SECONDS}s") from exc
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="ignore") or "FFmpeg command failed")


def _video_has_audio_stream(video_path: str) -> bool:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        out = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, timeout=FFPROBE_TIMEOUT_SECONDS
        ).decode("utf-8", errors="ignore").strip()
        return bool(out)
    except Exception:
        return False


def _merge_intervals(ranges: List[tuple[float, float]]) -> List[tuple[float, float]]:
    if not ranges:
        return []
    ordered = sorted((max(0.0, float(a)), max(0.0, float(b))) for a, b in ranges)
    merged: List[tuple[float, float]] = []
    for start, end in ordered:
        if end <= start:
            continue
        if not merged:
            merged.append((start, end))
            continue
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _invert_cut_ranges(total_duration: float, cut_ranges: List[tuple[float, float]]) -> List[tuple[float, float]]:
    duration = max(0.0, float(total_duration or 0.0))
    if duration <= 0:
        return []
    merged = _merge_intervals(cut_ranges)
    keep: List[tuple[float, float]] = []
    cursor = 0.0
    for start, end in merged:
        if start > cursor:
            keep.append((cursor, min(start, duration)))
        cursor = max(cursor, end)
    if cursor < duration:
        keep.append((cursor, duration))
    return [(a, b) for a, b in keep if (b - a) >= 0.08]


def _build_keep_time_expr(keep_ranges: List[tuple[float, float]]) -> str:
    chunks = [f"between(t,{round(start, 3)},{round(end, 3)})" for start, end in keep_ranges]
    return "+".join(chunks) if chunks else "0"


def _render_keep_ranges(input_path: str, output_path: str, keep_ranges: List[tuple[float, float]]) -> None:
    expr = _build_keep_time_expr(keep_ranges)
    has_audio = _video_has_audio_stream(input_path)
    if has_audio:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB",
            "-af", f"aselect='{expr}',asetpts=N/SR/TB",
            "-c:v", "libx264", "-preset", EXPORT_VIDEO_PRESET, "-crf", EXPORT_VIDEO_CRF,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", EXPORT_AUDIO_BITRATE,
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB",
            "-an",
            "-c:v", "libx264", "-preset", EXPORT_VIDEO_PRESET, "-crf", EXPORT_VIDEO_CRF,
            "-pix_fmt", "yuv420p",
            output_path,
        ]
    _run_ffmpeg_command(cmd)


def _detect_silence_cut_ranges(video_path: str, total_duration: float) -> List[tuple[float, float]]:
    cmd = [
        "ffmpeg", "-hide_banner", "-i", video_path,
        "-af", "silencedetect=noise=-35dB:d=0.35",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=FFMPEG_STEP_TIMEOUT_SECONDS)
    log_text = result.stderr.decode("utf-8", errors="ignore")

    starts = [float(val) for val in re.findall(r"silence_start:\s*([0-9]+(?:\.[0-9]+)?)", log_text)]
    ends = [
        (float(a), float(b))
        for a, b in re.findall(r"silence_end:\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*silence_duration:\s*([0-9]+(?:\.[0-9]+)?)", log_text)
    ]

    cut_ranges: List[tuple[float, float]] = []
    pending_start_index = 0
    for end_value, silence_duration in ends:
        if pending_start_index >= len(starts):
            continue
        start_value = starts[pending_start_index]
        pending_start_index += 1
        if silence_duration >= 0.35 and end_value > start_value:
            cut_ranges.append((start_value, end_value))

    if pending_start_index < len(starts):
        for start_value in starts[pending_start_index:]:
            if total_duration > start_value:
                cut_ranges.append((start_value, total_duration))

    return _merge_intervals(cut_ranges)


def _atempo_chain(speed_factor: float) -> str:
    factor = max(0.5, min(2.0, float(speed_factor or 1.0)))
    return f"atempo={round(factor, 4)}"


def _apply_speed_transform(input_path: str, output_path: str, speed_factor: float = 1.08) -> None:
    factor = max(0.5, min(2.0, float(speed_factor or 1.0)))
    has_audio = _video_has_audio_stream(input_path)
    if has_audio:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:v", f"setpts=PTS/{round(factor, 4)}",
            "-filter:a", _atempo_chain(factor),
            "-c:v", "libx264", "-preset", EXPORT_VIDEO_PRESET, "-crf", EXPORT_VIDEO_CRF,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", EXPORT_AUDIO_BITRATE,
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:v", f"setpts=PTS/{round(factor, 4)}",
            "-an",
            "-c:v", "libx264", "-preset", EXPORT_VIDEO_PRESET, "-crf", EXPORT_VIDEO_CRF,
            "-pix_fmt", "yuv420p",
            output_path,
        ]
    _run_ffmpeg_command(cmd)


def _apply_clean_audio_transform(input_path: str, output_path: str) -> None:
    if not _video_has_audio_stream(input_path):
        shutil.copy(input_path, output_path)
        return
    audio_filter = "highpass=f=80,lowpass=f=12000,afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11"
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "copy",
        "-af", audio_filter,
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    _run_ffmpeg_command(cmd)


def _detect_bad_take_candidates_heuristic(transcript: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    segments = (transcript or {}).get("segments") or []
    filler_words = {"um", "uh", "euh", "hmm", "erm", "hum", "ah"}
    candidates: List[Dict[str, Any]] = []
    for segment in segments:
        start = float(segment.get("start", 0.0) or 0.0)
        end = float(segment.get("end", 0.0) or 0.0)
        if end <= start:
            continue
        text = str(segment.get("text") or "").strip().lower()
        words = [w for w in re.findall(r"[a-zA-Z']+", text) if w]
        if not words:
            continue

        filler_count = sum(1 for w in words if w in filler_words)
        repeated = any(words[i] == words[i + 1] for i in range(len(words) - 1))
        reason = ""
        confidence = 0.0
        if filler_count >= 2:
            reason = "filler hesitation"
            confidence = min(0.98, 0.7 + 0.08 * filler_count)
        elif repeated and len(words) >= 4:
            reason = "repeated phrase"
            confidence = 0.82

        if reason:
            candidates.append(
                {
                    "start": max(0.0, start - 0.06),
                    "end": max(start, end + 0.06),
                    "reason": reason,
                    "confidence": round(confidence, 2),
                }
            )

    return candidates


def _parse_bad_take_candidates_response(raw_text: str) -> List[Dict[str, Any]]:
    text = (raw_text or "").strip()
    if not text:
        return []

    fenced_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced_match:
        text = fenced_match.group(1).strip()

    try:
        payload = json.loads(text)
    except Exception:
        return []

    if isinstance(payload, dict):
        items = payload.get("candidates")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _sanitize_bad_take_candidates(
    raw_candidates: List[Dict[str, Any]],
    max_end: float,
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for candidate in raw_candidates:
        try:
            start = float(candidate.get("start", 0.0) or 0.0)
            end = float(candidate.get("end", 0.0) or 0.0)
        except Exception:
            continue

        start = max(0.0, min(start, max_end))
        end = max(0.0, min(end, max_end))
        if end <= start:
            continue

        reason = str(candidate.get("reason") or "bad take").strip() or "bad take"
        reason = reason[:120]

        try:
            confidence = float(candidate.get("confidence", 0.5) or 0.5)
        except Exception:
            confidence = 0.5
        confidence = max(0.0, min(confidence, 1.0))

        normalized.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "reason": reason,
                "confidence": round(confidence, 2),
            }
        )

    normalized.sort(key=lambda x: (x["start"], x["end"]))
    merged: List[Dict[str, Any]] = []
    for item in normalized:
        if not merged:
            merged.append(item)
            continue
        prev = merged[-1]
        if item["start"] <= prev["end"] and item["reason"] == prev["reason"]:
            prev["end"] = max(prev["end"], item["end"])
            prev["confidence"] = max(prev["confidence"], item["confidence"])
            continue
        merged.append(item)
    return merged


def _detect_bad_take_candidates_ai(transcript: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if os.environ.get("AUTO_EDIT_BAD_TAKE_AI", "true").strip().lower() in {"0", "false", "no"}:
        return []

    segments = (transcript or {}).get("segments") or []
    if not segments:
        return []

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_key":
        return []

    compact_segments: List[Dict[str, Any]] = []
    for idx, segment in enumerate(segments[:140]):
        start = float(segment.get("start", 0.0) or 0.0)
        end = float(segment.get("end", 0.0) or 0.0)
        text = str(segment.get("text") or "").strip()
        if not text or end <= start:
            continue
        compact_segments.append(
            {
                "index": idx,
                "start": round(start, 3),
                "end": round(end, 3),
                "text": text,
            }
        )

    if not compact_segments:
        return []

    max_end = max(float(seg.get("end", 0.0) or 0.0) for seg in compact_segments)
    prompt_payload = {
        "instructions": (
            "Detect low-quality speaking takes using multi-segment context. "
            "Consider hesitations, false starts, repeated fragments across neighboring segments, "
            "and self-corrections that hurt fluency. Return only meaningful cut candidates."
        ),
        "output_contract": {
            "format": "JSON",
            "top_level": "candidates",
            "fields": ["start", "end", "reason", "confidence"],
            "confidence_range": "0..1",
        },
        "segments": compact_segments,
    }

    try:
        from openai import OpenAI

        model = os.environ.get("OPENAI_BAD_TAKE_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a video editing analyst. "
                        "Use context between adjacent transcript segments before suggesting cuts. "
                        "Respond with strict JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt_payload, ensure_ascii=True),
                },
            ],
            temperature=0.1,
            max_tokens=900,
        )
        raw_output = (response.choices[0].message.content or "").strip()
        parsed = _parse_bad_take_candidates_response(raw_output)
        return _sanitize_bad_take_candidates(parsed, max_end=max_end)
    except Exception as exc:
        print(f"⚠️ AI bad-take analysis failed, fallback heuristic. Reason: {exc}")
        return []


def _detect_bad_take_candidates(transcript: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ai_candidates = _detect_bad_take_candidates_ai(transcript)
    if ai_candidates:
        return ai_candidates
    return _detect_bad_take_candidates_heuristic(transcript)


def _apply_auto_edit_media_steps(
    input_path: str,
    job_id: str,
    transcript: Optional[Dict[str, Any]],
    raw_options: Optional[Dict[str, Any]],
) -> tuple[str, List[str], List[Dict[str, Any]], List[str]]:
    options = _normalize_auto_edit_options(raw_options)
    steps: List[str] = []
    bad_take_candidates: List[Dict[str, Any]] = []
    cleanup_paths: List[str] = []
    current_path = input_path

    def build_temp(name: str) -> str:
        return os.path.join(OUTPUT_DIR, job_id, f"auto_{name}_{uuid.uuid4().hex[:8]}.mp4")

    total_duration = _probe_local_video_duration_seconds(current_path)

    if options["removeBadTakes"]:
        bad_take_candidates = _detect_bad_take_candidates(transcript)
        cut_ranges = [(float(c["start"]), float(c["end"])) for c in bad_take_candidates]
        keep_ranges = _invert_cut_ranges(total_duration, cut_ranges)
        if keep_ranges and len(keep_ranges) > 1:
            next_path = build_temp("bad_takes")
            _render_keep_ranges(current_path, next_path, keep_ranges)
            cleanup_paths.append(next_path)
            current_path = next_path
            total_duration = _probe_local_video_duration_seconds(current_path)
            steps.append(f"remove_bad_takes:done:{len(bad_take_candidates)}")
        else:
            steps.append("remove_bad_takes:skipped")
    else:
        steps.append("remove_bad_takes:disabled")

    if options["removeSilence"] and _video_has_audio_stream(current_path):
        silence_ranges = _detect_silence_cut_ranges(current_path, total_duration)
        keep_ranges = _invert_cut_ranges(total_duration, silence_ranges)
        if keep_ranges and len(keep_ranges) > 1:
            next_path = build_temp("silence")
            _render_keep_ranges(current_path, next_path, keep_ranges)
            cleanup_paths.append(next_path)
            current_path = next_path
            total_duration = _probe_local_video_duration_seconds(current_path)
            steps.append(f"remove_silence:done:{len(silence_ranges)}")
        else:
            steps.append("remove_silence:skipped")
    elif options["removeSilence"]:
        steps.append("remove_silence:no_audio")
    else:
        steps.append("remove_silence:disabled")

    if options["cleanAudio"]:
        next_path = build_temp("clean_audio")
        _apply_clean_audio_transform(current_path, next_path)
        cleanup_paths.append(next_path)
        current_path = next_path
        total_duration = _probe_local_video_duration_seconds(current_path)
        steps.append("clean_audio:done")
    else:
        steps.append("clean_audio:disabled")

    if options["speed"]:
        next_path = build_temp("speed")
        _apply_speed_transform(current_path, next_path, speed_factor=1.08)
        cleanup_paths.append(next_path)
        current_path = next_path
        steps.append("speed:done:1.08")
    else:
        steps.append("speed:disabled")

    return current_path, steps, bad_take_candidates, cleanup_paths

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
        raise HTTPException(status_code=400, detail=_GEMINI_API_KEY_NOT_CONFIGURED)

    ack_flag = str(acknowledged).lower() in ("1", "true", "yes")

    # Handle JSON body manually for URL payload
    content_type = request.headers.get("content-type", "")
    if _CONTENT_TYPE_JSON in content_type:
        body = await request.json()
        url = body.get("url")
        ack_flag = bool(body.get("acknowledged"))

    if not url and not file:
        raise HTTPException(status_code=400, detail="Must provide URL or File")

    if not ack_flag:
        raise HTTPException(status_code=400, detail="You must confirm you own the content or have rights to process it.")

    if url and DISABLE_YOUTUBE_URL:
        raise HTTPException(status_code=403, detail="YouTube URL ingest is disabled on this deployment. Please upload a file you own.")

    await _enforce_job_concurrency_limit(user_id)
    await _assert_user_has_storage_headroom(user_id)

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
    reel_required_credits = 0.0
    source_duration_seconds = 0.0
    source_type = "url" if url else "file"
    source_value = url if url else (file.filename if file else "")
    project_source_type = "upload"
    project_name = "Reel Project"
    project_description = ""
    remote_meta: Dict[str, Any] = {}

    # Prepare Command
    cmd = ["python", "-u", "main.py"] # -u for unbuffered
    env = os.environ.copy()
    env["GEMINI_API_KEY"] = api_key # Override with key from request

    if url:
        remote_meta = _probe_remote_video_metadata(url)
        duration_seconds = float(remote_meta.get("duration_seconds") or 0.0)
        source_duration_seconds = duration_seconds
        size_bytes = float(remote_meta.get("size_bytes") or 0.0)
        is_youtube_source = _is_youtube_url(url)
        project_source_type = "youtube" if is_youtube_source else "url"
        youtube_title = str(remote_meta.get("title") or "").strip()
        fallback_name = _sanitize_input_filename(url) or "Video distante"
        project_name = youtube_title or fallback_name
        project_description = _build_short_project_summary(str(remote_meta.get("description") or ""), fallback_title=project_name)

        # If remote metadata is incomplete, download once and validate from local probe.
        # Keep YouTube URLs in -u mode; direct HTTP fetch of watch pages returns HTML.
        if duration_seconds <= 0.0 or size_bytes <= 0.0:
            if not is_youtube_source:
                input_path, _ = _download_input_url_to_job_dir(url, job_id)
                duration_seconds = _probe_local_video_duration_seconds(input_path)
                source_duration_seconds = duration_seconds
                try:
                    size_bytes = float(os.path.getsize(input_path))
                except Exception:
                    size_bytes = 0.0

        _validate_reel_source_constraints(
            duration_seconds=duration_seconds,
            size_bytes=size_bytes,
            source_label="url",
        )
        reel_required_credits = _estimate_reel_required_credits(
            duration_seconds=duration_seconds,
            size_bytes=size_bytes,
            uses_youtube_source=True,
        )
        try:
            await _reserve_job_credits(user_id, reel_required_credits)
        except HTTPException:
            if input_path and os.path.exists(input_path):
                os.remove(input_path)
            shutil.rmtree(job_output_dir, ignore_errors=True)
            raise

        if input_path:
            cmd.extend(["-i", input_path])
        else:
            cmd.extend(["-u", url])
    else:
        _validate_video_extension(file.filename if file else "", context_label="reel")
        project_source_type = "upload"
        project_name = _project_name_from_uploaded_file(file.filename if file else "")
        project_description = _build_short_project_summary(project_name, fallback_title=project_name)

        # Save uploaded file with size limit check
        # Security: sanitize the client-supplied filename to a safe basename
        # before joining it into a filesystem path (path traversal guard).
        safe_upload_name = _sanitize_input_filename(file.filename) or _DEFAULT_UPLOAD_FILENAME
        input_path = os.path.join(UPLOAD_DIR, f"{job_id}_{safe_upload_name}")

        # Read file in chunks to check size
        size = 0
        limit_bytes = max(0.0, REEL_MAX_STORAGE_GB) * (1024 ** 3)

        async with aiofiles.open(input_path, "wb") as buffer:
            while content := await file.read(1024 * 1024): # Read 1MB chunks
                size += len(content)
                if limit_bytes > 0 and size > limit_bytes:
                    os.remove(input_path)
                    shutil.rmtree(job_output_dir)
                    raise HTTPException(status_code=413, detail=f"Fichier trop volumineux. Maximum autorise: {REEL_MAX_STORAGE_GB:.2f} Go")
                await buffer.write(content)

        local_duration = _probe_local_video_duration_seconds(input_path)
        source_duration_seconds = float(local_duration or 0.0)
        _validate_reel_source_constraints(
            duration_seconds=local_duration,
            size_bytes=float(size),
            source_label="fichier",
        )
        reel_required_credits = _estimate_reel_required_credits(
            duration_seconds=local_duration,
            size_bytes=float(size),
            uses_youtube_source=False,
        )
        try:
            await _reserve_job_credits(user_id, reel_required_credits)
        except HTTPException:
            if os.path.exists(input_path):
                os.remove(input_path)
            shutil.rmtree(job_output_dir, ignore_errors=True)
            raise

        cmd.extend(["-i", input_path])

    cmd.extend(["-o", job_output_dir])

    print(f"[attestation] job={job_id} ip={attestation['ip']} source={attestation['source']} ack=true")

    # Create a project to group all generated content
    project = None
    if is_supabase_configured():
        try:
            # Determine source duration and size
            source_size_bytes = 0
            source_duration_seconds = None

            if input_path and os.path.exists(input_path):
                source_size_bytes = os.path.getsize(input_path)
                source_duration_seconds = _probe_local_video_duration_seconds(input_path)
            else:
                source_size_bytes = int(float(remote_meta.get("size_bytes") or 0.0))
                source_duration_seconds = float(remote_meta.get("duration_seconds") or 0.0) or None

            # Upload source to S3 with project-based key structure
            bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
            source_basename = os.path.basename(input_path) if input_path else (_sanitize_input_filename(source_value) or "video.mp4")
            s3_source_key = f"projects/{job_id}/source/{source_basename}"

            if input_path and os.path.exists(input_path):
                upload_file_to_s3(input_path, bucket_name, s3_source_key)

            # Create project record
            project = await supabase_create_project(
                user_id=user_id,
                name=project_name,
                description=project_description,
                project_type="reel",
                source_type=project_source_type,
                source_s3_key=s3_source_key,
                source_size=source_size_bytes,
                source_url=url if url else None,
                source_duration=int(source_duration_seconds) if source_duration_seconds else None,
                status="processing",
            )
        except Exception as e:
            logger.warning(f"Failed to create project for job {job_id}: {str(e)}")

    # Enqueue job runtime payload.
    runtime_payload = {
        'status': 'queued',
        'logs': [f"Job {job_id} queued."],
        'cmd': cmd,
        'env': env,
        'output_dir': job_output_dir,
        'input_path': input_path,
        'source_type': source_type,
        'source_value': source_value,
        'attestation': attestation,
        'user_id': user_id,
        'priority': job_priority,
        'reel_required_credits': reel_required_credits,
        'project_id': project.get("id") if project else None,
        'source_duration_seconds': source_duration_seconds,
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
            "source_type": source_type,
            "source_value": source_value,
            "output_dir": job_output_dir,
            "input_path": input_path,
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "reel_max_duration_minutes": REEL_MAX_DURATION_MINUTES,
            "reel_max_storage_gb": REEL_MAX_STORAGE_GB,
            "attestation": attestation,
            "reel_required_credits": reel_required_credits,
            "project_id": project.get("id") if project else None,
            "source_duration_seconds": source_duration_seconds,
        },
        runtime_data=dict(runtime_payload),
        max_attempts=REEL_JOB_MAX_ATTEMPTS,
        reserved_quota=reel_required_credits,
        priority=job_priority,
        queue_name="reels",
    )
    await reel_job_manager.enqueue_job(job_id)
    await ReelProcessingPipeline(reel_job_manager, job_id).queued()

    await enqueue_reel_job(job_id, priority=job_priority)

    return {
        "job_id": job_id,
        "project_id": project.get("id") if project else None,
        "status": "queued"
    }

@app.get("/api/status/{job_id}")
async def get_status(job_id: str, user_id: str = Depends(get_user_id_header)):
    # Best effort read of in-memory runtime state, but the *authorization*
    # scope always comes from the verified caller identity above -- never
    # fall back to an unscoped (user_id=None) lookup, which would let any
    # caller read any other user's job status/results (see security audit).
    runtime_job = reel_job_manager.runtime_jobs.get(job_id) or jobs.get(job_id)

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
                                'index': (
                                    (int(match.group(1)) - 1)
                                    if (match := re.search(_CLIP_INDEX_SUFFIX_PATTERN, clip_file))
                                    else i
                                ),
                                'reel_clip_index': (
                                    (int(match.group(1)) - 1)
                                    if (match := re.search(_CLIP_INDEX_SUFFIX_PATTERN, clip_file))
                                    else i
                                ),
                                'status': 'generated'
                            }
                            for i, clip_file in enumerate(clip_files)
                        ]
            except Exception:
                pass
        return supabase_view

    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)

    job = jobs[job_id]
    if (job.get("user_id") or "") != user_id:
        # Security: never serve another user's in-memory job state.
        raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)
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
                        match = re.search(_CLIP_INDEX_SUFFIX_PATTERN, clip_file)
                        resolved_clip_index = (int(match.group(1)) - 1) if match else i
                        partial_clips.append({
                            'video_url': f'/videos/{job_id}/{clip_file}',
                            'file': clip_file,
                            'index': resolved_clip_index,
                            'reel_clip_index': resolved_clip_index,
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
    auto_edit_options: Optional[Dict[str, bool]] = None


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


_JOB_ID_PATTERN = re.compile(r"^[0-9a-fA-F-]{8,64}$")


async def _require_job_ownership(job_id: str, user_id: str) -> None:
    """Validate job_id format and verify it belongs to the authenticated caller.

    Security: job_id is interpolated into filesystem paths (os.path.join)
    and, for subtitle burning, into an ffmpeg -vf filter expression. Without
    this check a client could supply another user's job_id (cross-tenant
    IDOR) or a path-traversal payload like "../../etc" (see security audit
    finding on /api/edit and /api/subtitle). Ownership is verified against
    persisted job state, not just in-memory state, so it still works after a
    worker restart.
    """
    if not _JOB_ID_PATTERN.match(job_id or ""):
        raise HTTPException(status_code=400, detail="Invalid job_id")

    in_memory = jobs.get(job_id) or reel_job_manager.runtime_jobs.get(job_id)
    if in_memory:
        if (in_memory.get("user_id") or "") != user_id:
            raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)
        return

    if is_supabase_configured():
        row = await reel_job_manager.get_job_view(job_id, user_id=user_id)
        if row:
            return

    raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)


def _is_youtube_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip())
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")


class _SSRFSafeRedirectHandler(HTTPRedirectHandler):
    """Re-validates every redirect hop against _validate_download_url, so a
    malicious/compromised server cannot bypass SSRF protection by 302-ing to
    an internal/loopback/cloud-metadata address after the initial URL passed
    validation."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download_input_url_to_job_dir(input_url: str, job_id: str) -> tuple[str, str]:
    """Download a remote clip URL into output/<job_id> and return (path, filename)."""
    # Security: this fetches a URL fully controlled by the client (SSRF
    # primitive) -- always validate against private/loopback/link-local/cloud
    # metadata addresses before making any outbound request.
    _validate_download_url(input_url)
    if _is_youtube_url(input_url):
        raise HTTPException(
            status_code=400,
            detail=(
                "Les URLs YouTube standard ne peuvent pas etre telechargees directement. "
                "Utilisez la generation Reel avec URL (mode yt-dlp) ou une URL directe de fichier video."
            ),
        )

    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)

    source_name = _sanitize_input_filename(input_url) or f"remote_{job_id}.mp4"
    filename = f"remote_{uuid.uuid4().hex[:8]}_{source_name}"
    local_path = os.path.join(output_dir, filename)

    try:
        request = UrlRequest(input_url, headers={"User-Agent": "Vireel/1.0"})
        opener = build_opener(_SSRFSafeRedirectHandler)
        with opener.open(request, timeout=45) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type.lower():
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "L'URL fournie a retourné une page HTML au lieu d'un fichier vidéo. "
                        "Les liens YouTube standard ne sont pas téléchargeables directement. "
                        "Veuillez fournir une URL directe vers un fichier vidéo (mp4, mov…)."
                    ),
                )
            with open(local_path, "wb") as f:
                shutil.copyfileobj(response, f)
    except HTTPException:
        raise
    except Exception as e:
        raise _generic_error(
            "Failed to download input URL", e, status_code=404,
            detail="Impossible de telecharger l'URL fournie.",
        ) from e

    return local_path, filename

@app.post("/api/edit")
async def edit_clip(
    request: Request,
    req: EditRequest,
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key"),
    user_id: str = Depends(get_user_id_header),
):
    await _require_job_ownership(req.job_id, user_id)

    # Determine API Key
    final_api_key = req.api_key or x_gemini_key or os.environ.get("GEMINI_API_KEY")

    if not final_api_key:
        raise HTTPException(status_code=400, detail="Missing Gemini API Key (Header or Body)")

    edit_required_credits = 0.0

    job = jobs.get(req.job_id)

    try:
        # Resolve Input Path: Prefer explict input_filename from frontend (chaining edits)
        if req.input_filename:
            # Security: Ensure just a filename, no paths or signed query params
            safe_name = _sanitize_input_filename(req.input_filename)
            if not safe_name:
                raise HTTPException(status_code=400, detail=_INVALID_INPUT_FILENAME)
            input_path = os.path.join(OUTPUT_DIR, req.job_id, safe_name)
            filename = safe_name
        else:
            if not job:
                raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)
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

        input_size_bytes = float(os.path.getsize(input_path) if os.path.exists(input_path) else 0)
        input_duration_seconds = _probe_local_video_duration_seconds(input_path)
        edit_required_credits = _estimate_reel_required_credits(
            duration_seconds=input_duration_seconds,
            size_bytes=input_size_bytes,
            uses_youtube_source=False,
            uses_openai=False,
            uses_assembly=False,
            uses_gemini=True,
        )
        await _assert_user_has_required_credits(user_id, edit_required_credits)

        os.makedirs(os.path.join(OUTPUT_DIR, req.job_id), exist_ok=True)

        # Define output path for edited video
        edited_filename = f"edited_{filename}"
        output_path = os.path.join(OUTPUT_DIR, req.job_id, edited_filename)

        transcript_for_edit = None
        try:
            meta_files = glob.glob(os.path.join(OUTPUT_DIR, req.job_id, _METADATA_JSON_GLOB))
            if meta_files:
                async with aiofiles.open(meta_files[0], "r") as f:
                    data = json.loads(await f.read())
                    transcript_for_edit = data.get("transcript")
        except Exception as e:
            print(f"⚠️ Could not load transcript for editing context: {e}")

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
            auto_cleanup_paths: List[str] = []

            try:
                processed_input_path, media_steps, bad_take_candidates, generated_paths = _apply_auto_edit_media_steps(
                    safe_input_path,
                    req.job_id,
                    transcript_for_edit,
                    req.auto_edit_options,
                )
                auto_cleanup_paths.extend(generated_paths)

                # 1. Upload (using safe path)
                vid_file = editor.upload_video(processed_input_path)

                # 2. Get duration
                import cv2
                cap = cv2.VideoCapture(processed_input_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                duration = frame_count / fps if fps else 0
                cap.release()

                # 3. Get Plan (Filter String)
                filter_data = editor.get_ffmpeg_filter(
                    vid_file,
                    duration,
                    fps=fps,
                    width=width,
                    height=height,
                    transcript=transcript_for_edit,
                )
                filter_data, applied_steps = _apply_auto_edit_options_to_filter_data(filter_data, req.auto_edit_options)

                # 4. Apply
                # Use safe output name first
                safe_output_path = os.path.join(OUTPUT_DIR, req.job_id, f"temp_output_{req.job_id}.mp4")
                editor.apply_edits(processed_input_path, safe_output_path, filter_data)

                # Move result to final destination (rename works even if dest name has unicode if filesystem supports it,
                # but python might still struggle if locale is broken? No, os.rename usually handles it better than subprocess args)
                # Actually, output_path is defined above: f"edited_{filename}"
                # If filename has unicode, output_path has unicode.
                # Let's hope shutil.move / os.rename works.
                if os.path.exists(safe_output_path):
                    shutil.move(safe_output_path, output_path)

                return {
                    "filter": filter_data,
                    "applied_steps": applied_steps + media_steps,
                    "bad_take_candidates": bad_take_candidates,
                }
            finally:
                # Cleanup temp safe input
                if os.path.exists(safe_input_path):
                    os.remove(safe_input_path)
                for temp_path in auto_cleanup_paths:
                    if temp_path != safe_input_path and os.path.exists(temp_path):
                        os.remove(temp_path)

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
                operation_type="edition_auto",
                operation_id=f"{req.job_id}:edit:{req.clip_index}",
            )

        return {
            "success": True,
            "new_video_url": new_video_url,
            "edit_plan": plan,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise _generic_error("Edit Error", e)

@app.post("/api/captions/process")
async def process_caption_endpoint(
    file: UploadFile = File(...),
    acknowledged: Optional[str] = Form(None),
    user_id: str = Depends(get_user_id_header),
):
    if not file:
        raise HTTPException(status_code=400, detail="Must provide a video file")

    ack_flag = str(acknowledged).lower() in ("1", "true", "yes")
    if not ack_flag:
        raise HTTPException(status_code=400, detail="You must confirm you own the content or have rights to process it.")

    await _enforce_job_concurrency_limit(user_id)
    await _assert_user_has_storage_headroom(user_id)

    _validate_video_extension(file.filename if file else "", context_label="sous-titres")

    caption_job_id = str(uuid.uuid4())
    output_dir = os.path.join(OUTPUT_DIR, caption_job_id)
    os.makedirs(output_dir, exist_ok=True)

    source_name = os.path.basename(str(file.filename or "caption_source.mp4"))
    input_filename = f"caption_input_{int(time.time())}_{source_name}"
    input_path = os.path.join(output_dir, input_filename)

    size_bytes = 0
    limit_bytes = max(0.0, CAPTION_MAX_STORAGE_GB) * (1024 ** 3)
    try:
        async with aiofiles.open(input_path, "wb") as handle:
            while content := await file.read(1024 * 1024):
                size_bytes += len(content)
                if limit_bytes > 0 and size_bytes > limit_bytes:
                    raise HTTPException(status_code=413, detail=f"Fichier trop volumineux. Maximum autorise: {CAPTION_MAX_STORAGE_GB:.2f} Go")
                await handle.write(content)
    except HTTPException:
        if os.path.exists(input_path):
            os.remove(input_path)
        raise
    finally:
        await file.close()

    local_duration = _probe_local_video_duration_seconds(input_path)
    _validate_caption_source_constraints(
        duration_seconds=local_duration,
        size_bytes=float(size_bytes),
        source_label="fichier",
    )

    caption_required_credits = _estimate_caption_required_credits(
        duration_seconds=local_duration,
        size_bytes=float(size_bytes),
    )
    try:
        await _reserve_job_credits(user_id, caption_required_credits)
    except HTTPException:
        if os.path.exists(input_path):
            os.remove(input_path)
        shutil.rmtree(output_dir, ignore_errors=True)
        raise

    job_priority = await _resolve_user_job_priority(user_id)

    # Create a project to group all generated content
    project = None
    if is_supabase_configured():
        try:
            project_name = _project_name_from_uploaded_file(source_name)
            project_description = _build_short_project_summary(project_name, fallback_title=project_name)
            # Upload source to S3 with project-based key structure
            bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
            s3_source_key = f"projects/{caption_job_id}/source/{source_name}"

            if os.path.exists(input_path):
                upload_file_to_s3(input_path, bucket_name, s3_source_key)

            # Create project record
            project = await supabase_create_project(
                user_id=user_id,
                name=project_name,
                description=project_description,
                project_type="caption",
                source_type="upload",
                source_s3_key=s3_source_key,
                source_size=size_bytes,
                source_duration=int(local_duration) if local_duration else None,
                status="processing",
            )
        except Exception as e:
            logger.warning(f"Failed to create project for caption job {caption_job_id}: {str(e)}")

    runtime_payload = {
        "status": "queued",
        "logs": [f"Caption job {caption_job_id} queued."],
        "output_dir": output_dir,
        "input_path": input_path,
        "source_type": "file",
        "source_value": source_name,
        "source_name": source_name,
        "user_id": user_id,
        "priority": job_priority,
        "job_kind": "caption",
        "caption_required_credits": caption_required_credits,
        "project_id": project.get("id") if project else None,
        "source_duration_seconds": float(local_duration or 0.0),
    }

    jobs[caption_job_id] = dict(runtime_payload)
    reel_job_manager.runtime_jobs[caption_job_id] = dict(runtime_payload)
    await reel_job_manager.create_job(
        user_id=user_id,
        job_type=JobType.GENERATE_SUBTITLES,
        pipeline_name="CaptionProcessingPipeline",
        job_id=caption_job_id,
        job_data={
            "source_type": "file",
            "source_value": source_name,
            "output_dir": output_dir,
            "input_path": input_path,
            "caption_max_duration_minutes": CAPTION_MAX_DURATION_MINUTES,
            "caption_max_storage_gb": CAPTION_MAX_STORAGE_GB,
            "project_id": project.get("id") if project else None,
            "source_duration_seconds": float(local_duration or 0.0),
            "caption_required_credits": caption_required_credits,
        },
        runtime_data=dict(runtime_payload),
        max_attempts=CAPTION_JOB_MAX_ATTEMPTS,
        reserved_quota=caption_required_credits,
        priority=job_priority,
        queue_name="captions",
    )
    await reel_job_manager.enqueue_job(caption_job_id)
    await CaptionProcessingPipeline(reel_job_manager, caption_job_id).step(0, "queued")
    await enqueue_reel_job(caption_job_id, priority=job_priority)

    return {
        "job_id": caption_job_id,
        "project_id": project.get("id") if project else None,
        "status": "queued"
    }


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
async def get_clip_transcript(job_id: str, clip_index: int, request: Request):
    """Return word-level captions for a specific clip, formatted for Remotion."""
    # Do not depend on in-memory jobs: Reels page must keep working after restarts.
    verified_user_id = _get_authenticated_user_id_optional(request)
    _, data = await _get_or_build_job_metadata(job_id, clip_index, user_id=verified_user_id)
    if not data:
        # Graceful fallback when metadata cannot be reconstructed.
        return {
            "captions": [],
            "durationSec": 0,
            "language": "en",
            "missing": "metadata",
        }

    clips = data.get('shorts', [])
    if clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip_data = clips[clip_index]
    clip_start = clip_data.get('start', 0)
    clip_end = clip_data.get('end', 0)

    saved_subtitle_config = clip_data.get("subtitle_config") if isinstance(clip_data, dict) else None
    saved_captions = []
    if isinstance(saved_subtitle_config, dict):
        maybe_captions = saved_subtitle_config.get("captions")
        if isinstance(maybe_captions, list):
            saved_captions = maybe_captions

    transcript = data.get('transcript')
    if not transcript and not saved_captions:
        raise HTTPException(status_code=400, detail="Transcript not found in metadata")

    # Extract words within clip range and convert to CaptionWord format
    captions = []
    if saved_captions:
        captions = saved_captions
    else:
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
        "language": (transcript or {}).get('language', 'en'),
        "subtitleConfig": saved_subtitle_config if isinstance(saved_subtitle_config, dict) else None,
        "remotionLayers": clip_data.get("remotion_layers") if isinstance(clip_data, dict) else None,
    }


@app.get("/api/clip/{job_id}/{clip_index}/preview-image/ensure")
async def ensure_clip_preview_image(
    job_id: str,
    clip_index: int,
    user_id: str = Depends(get_user_id_header),
):
    preview_image_url = await _ensure_preview_image_for_clip(job_id, clip_index, user_id)
    return {
        "preview_image_url": preview_image_url,
        "ensured": bool(preview_image_url),
    }


@app.post("/api/reels/{job_id}/{clip_index}/captions/persist")
async def persist_captioned_reel(
    job_id: str,
    clip_index: int,
    file: UploadFile = File(...),
    subtitle_config: Optional[str] = Form(None),
    remotion_layers: Optional[str] = Form(None),
    user_id: str = Depends(get_user_id_header),
):
    caption_required_credits = 0.0

    if not file:
        raise HTTPException(status_code=400, detail="Missing rendered video file")

    content_type = str(file.content_type or "").lower()
    if content_type and not content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Invalid rendered video content type")

    metadata_path, data = await _get_or_build_job_metadata(job_id, clip_index)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)

    clips = data.get('shorts', [])
    if clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip_data = clips[clip_index] if isinstance(clips[clip_index], dict) else {}
    source_video_url_before_edit = str(clip_data.get("video_url") or "")
    if source_video_url_before_edit and not clip_data.get("original_video_url"):
        clip_data["original_video_url"] = source_video_url_before_edit
    source_video_url_for_history = source_video_url_before_edit
    existing_caption_row: Optional[Dict[str, Any]] = None
    if is_supabase_configured():
        try:
            existing_caption_row = await supabase_get_caption_by_job_clip(job_id, clip_index, user_id)
            source_video_url_for_history = (
                _caption_media_url_from_s3_key((existing_caption_row or {}).get("caption_s3_key") or "")
                or str((existing_caption_row or {}).get("caption_url") or "")
                or source_video_url_for_history
            )
        except Exception:
            existing_caption_row = None
        try:
            reel_row = await supabase_get_reel_by_job_clip(job_id, clip_index, user_id=user_id)
            source_video_url_for_history = (
                _reel_media_url_from_s3_key((reel_row or {}).get("reel_s3_key") or "")
                or str((reel_row or {}).get("reel_url") or "")
                or source_video_url_for_history
            )
        except Exception:
            pass

    subtitle_config_payload: Optional[Dict[str, Any]] = None
    remotion_layers_payload: Optional[Dict[str, Any]] = None
    try:
        if subtitle_config:
            parsed = json.loads(subtitle_config)
            if isinstance(parsed, dict):
                subtitle_config_payload = parsed
    except Exception:
        subtitle_config_payload = None

    try:
        if remotion_layers:
            parsed = json.loads(remotion_layers)
            if isinstance(parsed, dict):
                remotion_layers_payload = parsed
    except Exception:
        remotion_layers_payload = None

    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)

    upload_name = str(file.filename or "captioned.mp4")
    ext = os.path.splitext(upload_name)[1].lower()
    if ext not in {".mp4", ".mov", ".webm", ".mkv"}:
        ext = ".mp4"

    output_filename = f"captioned_{clip_index}_{int(time.time())}{ext}"
    output_path = os.path.join(output_dir, output_filename)

    def _copy_upload_to_path():
        with open(output_path, "wb") as handle:  # NOSONAR(python:S7493): runs off the event loop via asyncio.to_thread below
            shutil.copyfileobj(file.file, handle)

    try:
        # Off the event loop via to_thread rather than aiofiles: this reads
        # from file.file (the underlying sync SpooledTemporaryFile), not
        # file.read(), matching the original shutil.copyfileobj-based
        # behavior this endpoint's tests are written against.
        await asyncio.to_thread(_copy_upload_to_path)
    finally:
        await file.close()

    rendered_size_bytes = float(os.path.getsize(output_path) if os.path.exists(output_path) else 0)
    rendered_storage_gb = _bytes_to_gb(rendered_size_bytes)
    rendered_duration_seconds = _probe_local_video_duration_seconds(output_path)
    caption_persist_cost_breakdown = _estimate_caption_cost_breakdown(
        duration_seconds=rendered_duration_seconds,
        size_bytes=rendered_size_bytes,
        uses_assembly=False,
        uses_openai=False,
        uses_gemini=False,
    )
    caption_required_credits = _estimate_caption_required_credits(
        duration_seconds=rendered_duration_seconds,
        size_bytes=rendered_size_bytes,
        uses_assembly=False,
        uses_openai=False,
        uses_gemini=False,
    )
    try:
        await _assert_user_has_required_credits(user_id, caption_required_credits)
    except HTTPException:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise

    local_video_url = f"/videos/{job_id}/{output_filename}"
    persisted_video_url = local_video_url
    job = jobs.get(job_id)
    if job and clip_index < len(job.get('result', {}).get('clips', [])):
        job['result']['clips'][clip_index]['video_url'] = local_video_url

    clip_data['video_url'] = local_video_url
    if subtitle_config_payload:
        clip_data['subtitle_config'] = subtitle_config_payload
    if remotion_layers_payload:
        clip_data['remotion_layers'] = remotion_layers_payload
    clips[clip_index] = clip_data
    data['shorts'] = clips

    style_config_for_history: Optional[Dict[str, Any]] = None
    if subtitle_config_payload:
        style_config_for_history = subtitle_config_payload.get("style") if isinstance(subtitle_config_payload.get("style"), dict) else {}

    caption_s3_key = ""
    caption_thumbnail_ref = ""
    caption_thumbnail_s3_key = ""
    reel_thumbnail_s3_key = ""
    preview_image_url = ""
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if bucket and os.path.exists(output_path):
        caption_s3_key = f"captions/{user_id}/{job_id}/{output_filename}"
        if upload_file_to_s3(output_path, bucket, caption_s3_key):
            persisted_video_url = _caption_media_url_from_s3_key(caption_s3_key) or local_video_url

        # Keep a static visual for cards that should not autoplay the edited clip.
        thumb_local_path = _generate_reel_thumbnail_from_video(output_path, OUTPUT_DIR, job_id, clip_index)
        if thumb_local_path and os.path.exists(thumb_local_path):
            thumb_suffix = int(time.time())
            caption_thumbnail_s3_key = f"captions/{user_id}/{job_id}/thumbnail_{clip_index}_{thumb_suffix}.jpg"
            reel_thumbnail_s3_key = f"reels/{user_id}/{job_id}/thumbnail_{clip_index}.jpg"

            try:
                if upload_file_to_s3(thumb_local_path, bucket, caption_thumbnail_s3_key):
                    caption_thumbnail_ref = caption_thumbnail_s3_key
            except Exception as thumb_upload_error:
                logger.warning("Caption thumbnail upload failed for %s/%s: %s", job_id, clip_index, thumb_upload_error)

            try:
                if not upload_file_to_s3(thumb_local_path, bucket, reel_thumbnail_s3_key):
                    reel_thumbnail_s3_key = ""
            except Exception as thumb_upload_error:
                reel_thumbnail_s3_key = ""
                logger.warning("Reel thumbnail upload failed for %s/%s: %s", job_id, clip_index, thumb_upload_error)

            try:
                os.remove(thumb_local_path)
            except Exception:
                pass

    if caption_thumbnail_ref.startswith(_CAPTIONS_PREFIX):
        preview_image_url = _caption_media_url_from_s3_key(caption_thumbnail_ref) or ""
    if not preview_image_url and reel_thumbnail_s3_key:
        preview_image_url = _reel_thumbnail_url_from_s3_key(reel_thumbnail_s3_key) or ""
    if not preview_image_url:
        preview_image_url = persisted_video_url or local_video_url

    if persisted_video_url != local_video_url:
        if job and clip_index < len(job.get('result', {}).get('clips', [])):
            job['result']['clips'][clip_index]['video_url'] = persisted_video_url
            job['result']['clips'][clip_index]['thumbnail_url'] = preview_image_url
            job['result']['clips'][clip_index]['preview_image_url'] = preview_image_url
        clip_data['video_url'] = persisted_video_url
        clip_data['thumbnail_url'] = preview_image_url
        clip_data['preview_image_url'] = preview_image_url
        clips[clip_index] = clip_data
        data['shorts'] = clips
    else:
        if job and clip_index < len(job.get('result', {}).get('clips', [])):
            job['result']['clips'][clip_index]['thumbnail_url'] = preview_image_url
            job['result']['clips'][clip_index]['preview_image_url'] = preview_image_url
        clip_data['thumbnail_url'] = preview_image_url
        clip_data['preview_image_url'] = preview_image_url
        clips[clip_index] = clip_data
        data['shorts'] = clips

    version_number: Optional[int] = None
    if style_config_for_history is not None:
        version_number = _append_style_version_to_metadata(
            data,
            clip_index,
            source_video_url_for_history,
            persisted_video_url,
            style_config_for_history,
        )

    _persist_metadata_json(metadata_path, data)

    if is_supabase_configured():
        caption_row = existing_caption_row or await supabase_get_caption_by_job_clip(job_id, clip_index, user_id)
        if caption_row:
            caption_updates: Dict[str, Any] = {
                "caption_url": local_video_url,
                "caption_status": "termine",
                "billing_details": _build_billing_details(
                    "sous_titre",
                    caption_persist_cost_breakdown,
                    actual_credit=caption_required_credits,
                    actual_storage_gb=rendered_storage_gb,
                    extra={"stage": "persist"},
                ),
                "total_cost_usd": 0,
            }
            if caption_s3_key:
                caption_updates["caption_s3_key"] = caption_s3_key
                caption_updates["caption_url"] = persisted_video_url
            if caption_thumbnail_ref:
                caption_updates["caption_thumbnail_url"] = caption_thumbnail_ref
            await supabase_update_caption(str(caption_row.get("id")), user_id, caption_updates)

        if persisted_video_url:
            try:
                await supabase_update_reel_media_by_job_clip(
                    job_id=job_id,
                    clip_index=clip_index,
                    reel_url=persisted_video_url,
                    reel_s3_key=caption_s3_key or None,
                    reel_thumbnail_url=reel_thumbnail_s3_key or None,
                    user_id=user_id,
                )
            except Exception as e:
                print(f"⚠️ Failed to sync reel URL after captions persist: {e}")

    if is_supabase_configured() and (caption_required_credits > 0 or rendered_storage_gb > 0):
        debited = await supabase_deduct_user_credits(user_id, caption_required_credits, -rendered_storage_gb)
        if not debited:
            raise HTTPException(status_code=500, detail="Failed to debit credit/storage for captions")
        await supabase_insert_user_data_history(
            user_id=user_id,
            credit=caption_required_credits,
            storage=round(rendered_storage_gb, 6),
            operation="output",
            operation_type="sous_titre",
            operation_id=f"{job_id}:captions:{clip_index}",
        )

    if is_supabase_configured() and style_config_for_history is not None and version_number is not None:
        try:
            await supabase_insert_style_edit_version(
                {
                    "user_id": user_id,
                    "job_id": job_id,
                    "clip_index": int(clip_index),
                    "version_number": int(version_number),
                    "operation_type": "subtitle_style",
                    "source_video_url": source_video_url_for_history,
                    "output_video_url": persisted_video_url,
                    "style_config": style_config_for_history,
                    "billing_details": _build_billing_details(
                        "sous_titre",
                        caption_persist_cost_breakdown,
                        actual_credit=caption_required_credits,
                        actual_storage_gb=rendered_storage_gb,
                        extra={"stage": "style_edit"},
                    ),
                }
            )
        except Exception as e:
            print(f"⚠️ Failed to persist style edit version: {e}")

    return {
        "success": True,
        "new_video_url": persisted_video_url,
        "preview_image_url": preview_image_url,
        "persisted": True,
        "job_id": job_id,
        "clip_index": clip_index,
        "user_id": user_id,
    }


# --- Remotion Render Proxy ---
# NOSONAR(python:S5332): default only reachable over the internal Docker
# Compose network (service name "renderer", never exposed publicly -- see
# docker-compose.yml, bound to 127.0.0.1 for local debugging only), and
# every request to it carries RENDER_SERVICE_API_KEY. TLS on that internal
# hop isn't the control that matters here; the network boundary + API key
# are. Override with RENDER_SERVICE_URL for any deployment that differs.
RENDER_SERVICE_URL = os.getenv("RENDER_SERVICE_URL", "http://renderer:3100")  # NOSONAR
RENDER_SERVICE_API_KEY = os.getenv("RENDER_SERVICE_API_KEY")
if not RENDER_SERVICE_API_KEY and not _is_pytest_runtime():
    raise RuntimeError(
        "RENDER_SERVICE_API_KEY manquant dans l'environnement -- requis pour "
        "s'authentifier aupres du render-service interne."
    )
_RENDER_SERVICE_HEADERS = {"x-internal-api-key": RENDER_SERVICE_API_KEY or "unit-test-render-key"}


@app.post("/api/render")
async def proxy_render(request: Request, user_id: str = Depends(get_user_id_header)):
    """Proxy render requests to the Node.js Remotion render service.

    Security: this endpoint used to forward the raw client body to an
    internal service with no authentication of its own -- requiring a
    verified session here, and authenticating to render-service with a
    shared internal API key, closes both the unauthenticated-proxy and the
    unauthenticated-render-service issues together.
    """
    import httpx
    body = await request.json()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{RENDER_SERVICE_URL}/render", json=body, headers=_RENDER_SERVICE_HEADERS
            )
            return resp.json()
    except Exception as e:
        raise _generic_error(
            "Render service unavailable (proxy_render)", e, status_code=502,
            detail="Le service de rendu est indisponible.",
        )

@app.get("/api/render/{render_id}")
async def proxy_render_status(render_id: str, user_id: str = Depends(get_user_id_header)):
    """Proxy render status polling to the Node.js Remotion render service."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{RENDER_SERVICE_URL}/render/{render_id}", headers=_RENDER_SERVICE_HEADERS
            )
            return resp.json()
    except Exception as e:
        raise _generic_error(
            "Render service unavailable (proxy_render_status)", e, status_code=502,
            detail="Le service de rendu est indisponible.",
        )


class EffectsGenerateRequest(BaseModel):
    job_id: str
    clip_index: int
    input_filename: Optional[str] = None
    input_url: Optional[str] = None
    auto_edit_options: Optional[Dict[str, bool]] = None

@app.post("/api/effects/generate")
async def generate_effects_config(
    req: EffectsGenerateRequest,
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key"),
    user_id: str = Depends(get_user_id_header),
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
                raise HTTPException(status_code=400, detail=_INVALID_INPUT_FILENAME)
            input_path = os.path.join(OUTPUT_DIR, req.job_id, safe_name)
            filename = safe_name
        else:
            if not job:
                raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)
            if 'result' not in job or 'clips' not in job['result']:
                raise HTTPException(status_code=400, detail="Job result not available")
            clip = job['result']['clips'][req.clip_index]
            filename = clip['video_url'].split('/')[-1]
            input_path = os.path.join(OUTPUT_DIR, req.job_id, filename)

        if not os.path.exists(input_path) and req.input_url:
            input_path, filename = _download_input_url_to_job_dir(req.input_url, req.job_id)

        if not os.path.exists(input_path):
            raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")

        input_size_bytes = float(os.path.getsize(input_path) if os.path.exists(input_path) else 0)
        input_duration_seconds = _probe_local_video_duration_seconds(input_path)
        effects_required_credits = _estimate_reel_required_credits(
            duration_seconds=input_duration_seconds,
            size_bytes=input_size_bytes,
            uses_youtube_source=False,
            uses_openai=False,
            uses_assembly=False,
            uses_gemini=True,
        )
        await _assert_user_has_required_credits(user_id, effects_required_credits)

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
                probe_result = subprocess.check_output(probe_cmd, timeout=FFPROBE_TIMEOUT_SECONDS).decode().strip()
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
                    meta_files = glob.glob(os.path.join(OUTPUT_DIR, req.job_id, _METADATA_JSON_GLOB))
                    if meta_files:
                        # NOSONAR(python:S7493): false positive -- this is
                        # inside a nested sync def (see below, run via
                        # loop.run_in_executor in a thread pool), not
                        # actually executing on the event loop despite
                        # being lexically inside an async endpoint.
                        with open(meta_files[0], 'r') as f:  # NOSONAR
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

        normalized_effects, applied_steps = _apply_auto_edit_options_to_effects_config(
            effects_config,
            req.auto_edit_options,
        )
        return {
            "effects": normalized_effects,
            "applied_steps": applied_steps,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise _generic_error("Effects Generation Error", e)


@app.post("/api/subtitle")
async def add_subtitles(req: SubtitleRequest, user_id: str = Depends(get_user_id_header)):
    await _require_job_ownership(req.job_id, user_id)
    subtitle_required_credits = 0.0
    await _assert_user_has_required_credits(user_id, subtitle_required_credits)

    # Reload job data from disk just in case metadata was updated.
    # The in-memory job may be gone on the Reels page; metadata on disk is enough.
    job = jobs.get(req.job_id)

    # We need to access metadata.json to get the transcript
    output_dir = os.path.join(OUTPUT_DIR, req.job_id)
    metadata_path, data = await _get_or_build_job_metadata(req.job_id, req.clip_index, req.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)

    transcript = data.get('transcript')
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript not found in metadata. Please process a new video.")

    clips = data.get('shorts', [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip_data = clips[req.clip_index]
    source_video_url_before_edit = str(clip_data.get("video_url") or "")
    source_video_url_for_history = source_video_url_before_edit
    if not clip_data.get("original_video_url"):
        clip_data["original_video_url"] = source_video_url_before_edit

    if is_supabase_configured():
        try:
            caption_row = await supabase_get_caption_by_job_clip(req.job_id, req.clip_index, user_id)
            source_video_url_for_history = (
                _caption_media_url_from_s3_key((caption_row or {}).get("caption_s3_key") or "")
                or str((caption_row or {}).get("caption_url") or "")
                or source_video_url_for_history
            )
        except Exception:
            pass
        try:
            reel_row = await supabase_get_reel_by_job_clip(req.job_id, req.clip_index, user_id=user_id)
            source_video_url_for_history = (
                _reel_media_url_from_s3_key((reel_row or {}).get("reel_s3_key") or "")
                or str((reel_row or {}).get("reel_url") or "")
                or source_video_url_for_history
            )
        except Exception:
            pass

    # Video Path
    if req.input_filename:
        filename = _sanitize_input_filename(req.input_filename)
        if not filename:
            raise HTTPException(status_code=400, detail=_INVALID_INPUT_FILENAME)
    else:
        # Fallback to standard naming
        filename = clip_data.get('video_url', '').split('/')[-1]
        if not filename:
             base_name = os.path.basename(metadata_path).replace(_METADATA_JSON_SUFFIX, '')
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

    except HTTPException:
        raise
    except Exception as e:
        raise _generic_error("Subtitle Error", e)

    local_subtitle_url = f"/videos/{req.job_id}/{output_filename}"
    persisted_subtitle_url = local_subtitle_url
    subtitle_s3_key = ""
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if bucket and os.path.exists(output_path):
        subtitle_s3_key = f"captions/{user_id}/{req.job_id}/{output_filename}"
        if upload_file_to_s3(output_path, bucket, subtitle_s3_key):
            persisted_subtitle_url = _caption_media_url_from_s3_key(subtitle_s3_key) or local_subtitle_url

    if is_supabase_configured() and persisted_subtitle_url:
        try:
            await supabase_update_reel_media_by_job_clip(
                job_id=req.job_id,
                clip_index=req.clip_index,
                reel_url=persisted_subtitle_url,
                reel_s3_key=subtitle_s3_key or None,
                user_id=user_id,
            )
        except Exception as e:
            print(f"⚠️ Failed to sync reel URL after subtitle edit: {e}")

    # 3. Update Result and Metadata
    # Update InMemory Jobs (only if the job is still alive in memory)
    if job and req.clip_index < len(job.get('result', {}).get('clips', [])):
         job['result']['clips'][req.clip_index]['video_url'] = persisted_subtitle_url

    # Update Metadata on Disk (Persistence)
    try:
        if req.clip_index < len(clips):
            clips[req.clip_index]['video_url'] = persisted_subtitle_url
            # Update the main data structure
            data['shorts'] = clips

            # Write back
            _persist_metadata_json(metadata_path, data)
            print(f"✅ Metadata updated with subtitled video for clip {req.clip_index}")
    except Exception as e:
        print(f"⚠️ Failed to update metadata.json: {e}")
        # Non-critical, but good for persistence

    style_config = {
        "position": req.position,
        "position_x": req.position_x,
        "position_y": req.position_y,
        "font_size": req.font_size,
        "font_name": req.font_name,
        "font_color": req.font_color,
        "highlight_color": req.highlight_color,
        "border_color": req.border_color,
        "border_width": req.border_width,
        "text_shadow_color": req.text_shadow_color,
        "shadow_blur": req.shadow_blur,
        "shadow_offset_x": req.shadow_offset_x,
        "shadow_offset_y": req.shadow_offset_y,
        "bg_color": req.bg_color,
        "bg_opacity": req.bg_opacity,
        "text_case": req.text_case,
        "bold": req.bold,
        "italic": req.italic,
        "words_per_line": req.words_per_line,
        "animation": req.animation,
    }

    version_number = _append_style_version_to_metadata(
        data,
        req.clip_index,
        source_video_url_for_history,
        persisted_subtitle_url,
        style_config,
    )
    _persist_metadata_json(metadata_path, data)
    subtitle_style_billing_details = _build_billing_details(
        "sous_titre",
        None,
        actual_credit=subtitle_required_credits,
        actual_storage_gb=0.0,
        extra={"stage": "style_edit"},
    )

    if is_supabase_configured() and subtitle_required_credits > 0:
        await supabase_deduct_user_credits(user_id, subtitle_required_credits)
        await supabase_insert_user_data_history(
            user_id=user_id,
            credit=subtitle_required_credits,
            storage=0.0,
            operation="output",
            operation_type="sous_titre",
            operation_id=f"{req.job_id}:subtitle:{req.clip_index}",
        )

    if is_supabase_configured():
        try:
            await supabase_insert_style_edit_version(
                {
                    "user_id": user_id,
                    "job_id": req.job_id,
                    "clip_index": int(req.clip_index),
                    "version_number": int(version_number),
                    "operation_type": "subtitle_style",
                    "source_video_url": source_video_url_for_history,
                    "output_video_url": persisted_subtitle_url,
                    "style_config": style_config,
                    "billing_details": subtitle_style_billing_details,
                }
            )
        except Exception as e:
            print(f"⚠️ Failed to persist style edit version: {e}")

    return {
        "success": True,
        "new_video_url": persisted_subtitle_url,
        "version": int(version_number),
    }

class HookRequest(BaseModel):
    job_id: str
    clip_index: int
    text: str
    input_filename: Optional[str] = None
    input_url: Optional[str] = None
    position: Optional[str] = "top" # top, center, bottom
    size: Optional[str] = "M" # S, M, L


@app.post("/api/reels/{job_id}/{clip_index}/captions/reset")
async def reset_caption_style_history(
    job_id: str,
    clip_index: int,
    user_id: str = Depends(get_user_id_header),
):
    metadata_path, data = await _get_or_build_job_metadata(job_id, clip_index)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)

    clips = data.get("shorts") or []
    if clip_index < 0 or clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip = clips[clip_index]
    history = data.get("style_history") or {}
    history_key = str(int(clip_index))
    entries = history.get(history_key) if isinstance(history, dict) else None

    original_video_url = str(clip.get("original_video_url") or "").strip()
    if not original_video_url and isinstance(entries, list) and entries:
        original_video_url = str(entries[0].get("source_video_url") or "").strip()
    if not original_video_url:
        raise HTTPException(status_code=400, detail="No original video reference found for reset")

    clip["video_url"] = original_video_url
    clips[clip_index] = clip
    data["shorts"] = clips
    if isinstance(history, dict):
        history.pop(history_key, None)
        data["style_history"] = history
    _persist_metadata_json(metadata_path, data)

    if is_supabase_configured():
        try:
            await supabase_delete_style_edit_versions(job_id, int(clip_index), user_id)
        except Exception as e:
            print(f"⚠️ Failed to delete style history versions: {e}")

    return {
        "success": True,
        "job_id": job_id,
        "clip_index": clip_index,
        "video_url": original_video_url,
        "history_cleared": True,
    }


@app.get("/api/reels/{job_id}/{clip_index}/style-history")
async def get_caption_style_history_debug(
    job_id: str,
    clip_index: int,
    user_id: str = Depends(get_user_id_header),
):
    metadata_path, data = await _get_or_build_job_metadata(job_id, clip_index)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)

    clips = data.get("shorts") or []
    if clip_index < 0 or clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip = clips[clip_index] if isinstance(clips[clip_index], dict) else {}
    history = data.get("style_history") if isinstance(data.get("style_history"), dict) else {}
    metadata_versions = history.get(str(int(clip_index))) if isinstance(history.get(str(int(clip_index))), list) else []

    db_versions: List[Dict[str, Any]] = []
    if is_supabase_configured():
        try:
            db_versions = await supabase_list_style_edit_versions(job_id, int(clip_index), user_id)
        except Exception as e:
            print(f"⚠️ Failed to load style history versions from Supabase: {e}")

    def _looks_amazon_url(value: Any) -> bool:
        text = str(value or "").strip().lower()
        return text.startswith(_HTTPS_SCHEME_PREFIX) and "amazonaws.com" in text

    metadata_last = metadata_versions[-1] if metadata_versions else {}
    db_last = db_versions[-1] if db_versions else {}

    return {
        "job_id": job_id,
        "clip_index": int(clip_index),
        "metadata_path": metadata_path,
        "clip_video_url": clip.get("video_url"),
        "clip_original_video_url": clip.get("original_video_url"),
        "metadata_versions_count": len(metadata_versions),
        "db_versions_count": len(db_versions),
        "metadata_versions": metadata_versions,
        "db_versions": db_versions,
        "checks": {
            "clip_video_url_is_amazon": _looks_amazon_url(clip.get("video_url")),
            "metadata_latest_source_is_amazon": _looks_amazon_url(metadata_last.get("source_video_url")),
            "metadata_latest_output_is_amazon": _looks_amazon_url(metadata_last.get("output_video_url")),
            "db_latest_source_is_amazon": _looks_amazon_url(db_last.get("source_video_url")),
            "db_latest_output_is_amazon": _looks_amazon_url(db_last.get("output_video_url")),
        },
    }

@app.post("/api/hook")
async def add_hook(req: HookRequest, user_id: str = Depends(get_user_id_header)):
    await _require_job_ownership(req.job_id, user_id)
    hook_required_credits = 0.0

    job = jobs.get(req.job_id)
    output_dir = os.path.join(OUTPUT_DIR, req.job_id)
    metadata_path, data = await _get_or_build_job_metadata(req.job_id, req.clip_index, req.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)

    clips = data.get('shorts', [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip_data = clips[req.clip_index]

    # Video Path
    if req.input_filename:
        filename = _sanitize_input_filename(req.input_filename)
        if not filename:
            raise HTTPException(status_code=400, detail=_INVALID_INPUT_FILENAME)
    else:
        filename = clip_data.get('video_url', '').split('/')[-1]
        if not filename:
             base_name = os.path.basename(metadata_path).replace(_METADATA_JSON_SUFFIX, '')
             filename = f"{base_name}_clip_{req.clip_index+1}.mp4"

    input_path = os.path.join(output_dir, filename)
    if not os.path.exists(input_path) and req.input_url:
        input_path, filename = _download_input_url_to_job_dir(req.input_url, req.job_id)

    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")

    input_size_bytes = float(os.path.getsize(input_path) if os.path.exists(input_path) else 0)
    input_duration_seconds = _probe_local_video_duration_seconds(input_path)
    hook_required_credits = _estimate_reel_required_credits(
        duration_seconds=input_duration_seconds,
        size_bytes=input_size_bytes,
        uses_youtube_source=False,
        uses_openai=False,
        uses_assembly=False,
        uses_gemini=False,
    )
    await _assert_user_has_required_credits(user_id, hook_required_credits)

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
        raise _generic_error("Hook Error", e)

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
            operation_type="hook",
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


def _load_clip_segments_from_metadata(data: Dict[str, Any], clip_index: int) -> List[Dict[str, Any]]:
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

    selected: List[Dict[str, Any]] = []
    for seg in all_segments:
        s = float(seg.get("start", 0))
        e = float(seg.get("end", 0))
        if e > clip_start and s < clip_end:
            rel_start = max(0.0, s - clip_start)
            rel_end = max(rel_start, e - clip_start)
            text = _segment_to_text(seg)
            if text:
                selected.append({"start": rel_start, "end": rel_end, "text": text})
    return selected


def _translate_text_openai(text: str, source_lang: str, target_lang: str) -> tuple[str, Dict[str, Any]]:
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
    usage = getattr(resp, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
    usage_payload = {
        "provider": "openai",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": estimate_llm_usage_cost_usd("openai", prompt_tokens, completion_tokens),
    }
    return out, usage_payload


def _translate_text_gemini(text: str, source_lang: str, target_lang: str) -> tuple[str, Dict[str, Any]]:
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

    usage_meta = getattr(resp, "usage_metadata", None)
    if usage_meta is None and hasattr(resp, "usageMetadata"):
        usage_meta = getattr(resp, "usageMetadata")

    def _read_usage_field(source: Any, *names: str) -> int:
        for name in names:
            if isinstance(source, dict) and name in source:
                return int(source.get(name) or 0)
            if source is not None and hasattr(source, name):
                return int(getattr(source, name) or 0)
        return 0

    prompt_tokens = _read_usage_field(usage_meta, "prompt_token_count", "promptTokenCount")
    completion_tokens = _read_usage_field(usage_meta, "candidates_token_count", "candidatesTokenCount")
    total_tokens = _read_usage_field(usage_meta, "total_token_count", "totalTokenCount")
    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens

    usage_payload = {
        "provider": "gemini",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": estimate_llm_usage_cost_usd("gemini", prompt_tokens, completion_tokens),
    }
    return out, usage_payload


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
            dst, usage = _translate_text_openai(src_text, source_lang, target_lang)
            provider = "openai"
        except Exception as e_openai:
            print(f"⚠️ OpenAI translation failed, fallback Gemini. Reason: {e_openai}")
            # Fallback: Gemini
            dst, usage = _translate_text_gemini(src_text, source_lang, target_lang)
            provider = "gemini"

        translated.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": dst,
            "provider": provider,
            "usage": usage,
        })
    return translated


def _translate_segments_with_cache(
    segments: List[Dict],
    source_lang: str,
    target_lang: str,
    translation_cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple[List[Dict], Dict[str, Any]]:
    translated: List[Dict] = []
    cache_hits = 0
    cache_misses = 0
    usage_totals = {
        "openai": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
        "gemini": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
    }
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
                "usage": cached_entry.get("usage") or {},
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
                "usage": translated_segment.get("usage") or {},
                "source_language": _normalize_lang(source_lang) or "auto",
                "target_language": _normalize_lang(target_lang),
                "cached_at": int(time.time()),
            }

        usage = translated_segment.get("usage") or {}
        provider = (usage.get("provider") or translated_segment.get("provider") or "").lower()
        bucket = usage_totals.get(provider)
        if bucket is not None:
            bucket["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            bucket["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            bucket["total_tokens"] += int(usage.get("total_tokens") or 0)
            bucket["cost_usd"] = round(float(bucket["cost_usd"]) + float(usage.get("cost_usd") or 0.0), 6)

    total_cost_usd = round(
        float(usage_totals["openai"]["cost_usd"]) + float(usage_totals["gemini"]["cost_usd"]),
        6,
    )
    return translated, {
        "hits": cache_hits,
        "misses": cache_misses,
        "usage": usage_totals,
        "cost_usd": total_cost_usd,
    }


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
async def translate_captions(req: TranslateRequest, request: Request):
    """Translate reel transcript into Remotion-friendly timed word captions."""
    metadata_path, data = await _get_or_build_job_metadata(req.job_id, req.clip_index, req.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)
    translation_cache = _get_translation_cache(data)

    clips = data.get("shorts", [])
    if not clips:
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

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

    request_user_id = _get_authenticated_user_id_optional(request) or ""
    owner_user_id = request_user_id or await _resolve_job_owner_user_id(req.job_id, normalized_clip_index)
    transcription_row = None
    if owner_user_id and is_supabase_configured():
        transcription_row = await _load_cached_transcription(owner_user_id, req.job_id, normalized_clip_index)
        db_cache = (transcription_row or {}).get("translations_cache") or {}
        if isinstance(db_cache, dict) and db_cache:
            translation_cache = db_cache

    def run_translate_segments():
        return _translate_segments_with_cache(source_segments, source_lang, target_lang, translation_cache)

    loop = asyncio.get_event_loop()
    translated_segments, cache_stats = await loop.run_in_executor(None, run_translate_segments)

    if cache_stats["misses"] > 0:
        try:
            _persist_metadata_json(metadata_path, data)
        except Exception as e:
            print(f"⚠️ Failed to persist translation cache: {e}")

    if owner_user_id and is_supabase_configured():
        usage_payload = {
            "operation": "translation",
            "source_language": source_lang or "auto",
            "target_language": target_lang,
            "cache": {"hits": cache_stats.get("hits", 0), "misses": cache_stats.get("misses", 0)},
            "usage": cache_stats.get("usage", {}),
            "total_cost_usd": cache_stats.get("cost_usd", 0.0),
        }
        if transcription_row:
            await supabase_update_transcription_translations_cache(
                req.job_id,
                normalized_clip_index,
                owner_user_id,
                translation_cache,
                billing_details=usage_payload,
            )
        else:
            await _persist_transcription_cache(
                user_id=owner_user_id,
                job_id=req.job_id,
                clip_index=normalized_clip_index,
                source_type="translation",
                source_value=req.input_url or req.input_filename or req.job_id,
                transcript=data.get("transcript") or {},
                billing_details=usage_payload,
            )
            await supabase_update_transcription_translations_cache(
                req.job_id,
                normalized_clip_index,
                owner_user_id,
                translation_cache,
                billing_details=usage_payload,
            )

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
        "billing": {
            "usage": cache_stats.get("usage", {}),
            "total_cost_usd": cache_stats.get("cost_usd", 0.0),
        },
    }


@app.post("/api/translate")
async def translate_clip(req: TranslateRequest, request: Request):
    """
    Translate subtitles only (OpenAI first, Gemini fallback),
    keep original voice/audio track unchanged.
    """
    job = jobs.get(req.job_id)
    output_dir = os.path.join(OUTPUT_DIR, req.job_id)
    metadata_path, data = await _get_or_build_job_metadata(req.job_id, req.clip_index, req.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)
    translation_cache = _get_translation_cache(data)
    request_user_id = _get_authenticated_user_id_optional(request) or ""
    owner_user_id = request_user_id or await _resolve_job_owner_user_id(req.job_id, req.clip_index)
    transcription_row = None
    if owner_user_id and is_supabase_configured():
        transcription_row = await _load_cached_transcription(owner_user_id, req.job_id, req.clip_index)
        db_cache = (transcription_row or {}).get("translations_cache") or {}
        if isinstance(db_cache, dict) and db_cache:
            translation_cache = db_cache

    clips = data.get("shorts", [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip_data = clips[req.clip_index]

    # Resolve input video path
    if req.input_filename:
        filename = _sanitize_input_filename(req.input_filename)
        if not filename:
            raise HTTPException(status_code=400, detail=_INVALID_INPUT_FILENAME)
    else:
        filename = clip_data.get("video_url", "").split("/")[-1]
        if not filename:
            base_name = os.path.basename(metadata_path).replace(_METADATA_JSON_SUFFIX, "")
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
        raise _generic_error("Translation(subtitles-only) Error", e)

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

    if owner_user_id and is_supabase_configured():
        usage_payload = {
            "operation": "translation_subtitles_only",
            "source_language": source_lang or "auto",
            "target_language": target_lang,
            "cache": {"hits": cache_stats.get("hits", 0), "misses": cache_stats.get("misses", 0)},
            "usage": cache_stats.get("usage", {}),
            "total_cost_usd": cache_stats.get("cost_usd", 0.0),
        }
        if transcription_row:
            await supabase_update_transcription_translations_cache(
                req.job_id,
                req.clip_index,
                owner_user_id,
                translation_cache,
                billing_details=usage_payload,
            )
        else:
            await _persist_transcription_cache(
                user_id=owner_user_id,
                job_id=req.job_id,
                clip_index=req.clip_index,
                source_type="translation",
                source_value=req.input_url or req.input_filename or req.job_id,
                transcript=data.get("transcript") or {},
                billing_details=usage_payload,
            )
            await supabase_update_transcription_translations_cache(
                req.job_id,
                req.clip_index,
                owner_user_id,
                translation_cache,
                billing_details=usage_payload,
            )

    return {
        "success": True,
        "mode": "subtitles_only",
        "new_video_url": f"/videos/{req.job_id}/{output_filename}",
        "srt_url": f"/videos/{req.job_id}/{srt_filename}",
        "source_language": source_lang or "auto",
        "target_language": target_lang,
        "cache": cache_stats,
        "billing": {
            "usage": cache_stats.get("usage", {}),
            "total_cost_usd": cache_stats.get("cost_usd", 0.0),
        },
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
    # Security: `explicit_user_id` comes from a client-supplied request body
    # field and must never override the verified identity resolved from the
    # authenticated session (`user_id`, from get_user_id_header). Otherwise a
    # client could act on behalf of an arbitrary victim simply by setting
    # `user_id` in the JSON body.
    resolved = (user_id or "").strip()
    if not resolved:
        raise HTTPException(status_code=400, detail="Missing authenticated user id")
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


def _resolve_local_video_path(job_id: str, video_ref: str, clip_index: int) -> Optional[str]:
    ref = (video_ref or "").split("?")[0]
    filename = ref.split("/")[-1] or f"{job_id}_{clip_index + 1}.mp4"
    candidate = os.path.join(OUTPUT_DIR, job_id, filename)
    if not os.path.exists(candidate):
        return None
    return candidate


async def _resolve_clip_for_social_post(job_id: str, clip_index: int) -> Dict[str, Any]:
    """Resolve clip data from live in-memory job first, then persisted metadata fallback."""
    job = jobs.get(job_id)
    if job and "result" in job and isinstance(job["result"].get("clips"), list):
        try:
            return job["result"]["clips"][clip_index]
        except Exception:
            pass

    _, metadata = await _get_or_build_job_metadata(job_id, clip_index)
    shorts = (metadata or {}).get("shorts") or []
    if not isinstance(shorts, list) or clip_index < 0 or clip_index >= len(shorts):
        raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)
    clip = shorts[clip_index]
    if not isinstance(clip, dict):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)
    return clip


def _resolve_public_video_url(video_ref: str, request: Request, job_id: str, clip_index: int) -> str:
    ref = (video_ref or "").strip()
    # NOSONAR(python:S5332): this detects whether `ref` is already an
    # absolute URL (any scheme) so it isn't re-prefixed with a base URL --
    # it never issues a request with a hardcoded http:// endpoint.
    if ref.startswith((_HTTPS_SCHEME_PREFIX, "http://")):  # NOSONAR
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
async def post_to_socials(req: SocialPostRequest, request: Request, user_id_header: str = Depends(get_user_id_header)):
    selected_platforms = _resolve_social_platforms(req.platforms)
    user_id = _resolve_request_user_id(req.user_id, user_id_header)
    publish_priority = await _resolve_user_job_priority(user_id)
    scheduled_for = _resolve_scheduled_datetime(req.scheduled_date, req.timezone)
    if req.scheduled_date and not scheduled_for:
        raise HTTPException(status_code=400, detail=_INVALID_SCHEDULED_DATE)
    is_scheduled = bool(scheduled_for and scheduled_for > _utcnow())

    clip = await _resolve_clip_for_social_post(req.job_id, req.clip_index)

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
        if is_scheduled:
            publish_job_id = await _insert_publish_job(
                user_id=user_id,
                platform=platform_name,
                external_id="scheduled",
                status="queued",
                priority=publish_priority,
                scheduled_for=scheduled_for.isoformat() if scheduled_for else None,
                timezone=req.timezone or "UTC",
                payload={
                    "source_type": "job_clip",
                    "source_id": req.job_id,
                    "clip_index": req.clip_index,
                    "title": final_title,
                    "description": final_description,
                    "media_url": public_video_url,
                },
            )
            results[platform_name] = {
                "success": True,
                "scheduled": True,
                "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
                "publish_job_id": publish_job_id,
            }
            continue

        try:
            account = await _get_social_account(user_id, platform_name)
            if not account:
                raise HTTPException(status_code=404, detail=f"No connected {platform_name} account found")

            # NOSONAR(python:S5332): validates the URL is absolute (any
            # scheme) before submitting it to the platform API -- not a
            # hardcoded http:// request of our own.
            if platform_name in {"tiktok", "instagram"} and not public_video_url.startswith((_HTTPS_SCHEME_PREFIX, "http://")):  # NOSONAR
                raise HTTPException(status_code=400, detail=f"{platform_name} requires a public video URL")

            publish_payload = PublishRequest(
                user_id=user_id,
                title=final_title,
                description=final_description,
                text=final_description,
                caption=final_description,
                video_url=public_video_url,
                video_file=local_video_path or "",
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
    user_id: str = Depends(get_user_id_header),
):
    """Upload video and start background Whisper transcription immediately."""
    if not url and not file:
        raise HTTPException(status_code=400, detail="Must provide URL or File")

    session_id = str(uuid.uuid4())
    transcript_event = asyncio.Event()

    # Save file if uploaded directly
    video_path = None
    if file:
        safe_thumb_name = _sanitize_input_filename(file.filename) or _DEFAULT_UPLOAD_FILENAME
        video_path = os.path.join(UPLOAD_DIR, f"thumb_{session_id}_{safe_thumb_name}")
        async with aiofiles.open(video_path, "wb") as buffer:
            content = await file.read()
            await buffer.write(content)

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

    _spawn_background_task(run_background_whisper())

    return {"session_id": session_id}


@app.post("/api/thumbnail/analyze")
async def thumbnail_analyze(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key"),
    user_id: str = Depends(get_user_id_header),
):
    """Analyze a video and suggest viral YouTube titles."""
    # Use .env configuration (ignore header for security)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail=_GEMINI_API_KEY_NOT_CONFIGURED)

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
            safe_thumb_name = _sanitize_input_filename(file.filename) or _DEFAULT_UPLOAD_FILENAME
            video_path = os.path.join(UPLOAD_DIR, f"thumb_{session_id}_{safe_thumb_name}")
            async with aiofiles.open(video_path, "wb") as buffer:
                content = await file.read()
                await buffer.write(content)

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
        raise _generic_error("Thumbnail Analyze Error", e)


class ThumbnailTitlesRequest(BaseModel):
    session_id: Optional[str] = None
    message: Optional[str] = None
    title: Optional[str] = None

@app.post("/api/thumbnail/titles")
async def thumbnail_titles(
    req: ThumbnailTitlesRequest,
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key"),
    user_id: str = Depends(get_user_id_header),
):
    """Refine title suggestions or accept a manual title."""
    # Use .env configuration (ignore header for security)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail=_GEMINI_API_KEY_NOT_CONFIGURED)

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
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)

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
        raise _generic_error("Thumbnail Titles Error", e)


@app.post("/api/thumbnail/generate")
async def thumbnail_generate(
    request: Request,
    session_id: str = Form(...),
    title: str = Form(...),
    extra_prompt: str = Form(""),
    count: int = Form(3),
    face: Optional[UploadFile] = File(None),
    background: Optional[UploadFile] = File(None),
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key"),
    user_id: str = Depends(get_user_id_header),
):
    """Generate YouTube thumbnails with Gemini image generation."""
    # Security: session_id is client-supplied and gets joined into a
    # filesystem path below -- reject anything that isn't a well-formed
    # identifier before it ever reaches os.path.join (path traversal guard).
    if not _JOB_ID_PATTERN.match(session_id or ""):
        raise HTTPException(status_code=400, detail="Invalid session_id")

    # Use .env configuration (ignore header for security)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail=_GEMINI_API_KEY_NOT_CONFIGURED)

    # Clamp count
    count = min(max(1, count), 6)

    # Save optional uploaded images
    face_path = None
    bg_path = None
    thumb_upload_dir = os.path.join(UPLOAD_DIR, f"thumb_{session_id}")
    os.makedirs(thumb_upload_dir, exist_ok=True)

    try:
        if face and face.filename:
            safe_face_name = _sanitize_input_filename(face.filename) or "face.jpg"
            face_path = os.path.join(thumb_upload_dir, f"face_{safe_face_name}")
            async with aiofiles.open(face_path, "wb") as f:
                await f.write(await face.read())

        if background and background.filename:
            safe_bg_name = _sanitize_input_filename(background.filename) or "background.jpg"
            bg_path = os.path.join(thumb_upload_dir, f"bg_{safe_bg_name}")
            async with aiofiles.open(bg_path, "wb") as f:
                await f.write(await background.read())

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
        raise _generic_error("Thumbnail Generate Error", e)


class ThumbnailDescribeRequest(BaseModel):
    session_id: str
    title: str

@app.post("/api/thumbnail/describe")
async def thumbnail_describe(
    req: ThumbnailDescribeRequest,
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key"),
    user_id: str = Depends(get_user_id_header),
):
    """Generate a YouTube description with chapters from the transcript."""
    # Use .env configuration (ignore header for security)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail=_GEMINI_API_KEY_NOT_CONFIGURED)

    if req.session_id not in thumbnail_sessions:
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)

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
        raise _generic_error("Thumbnail Describe Error", e)


@app.post("/api/thumbnail/publish")
async def thumbnail_publish(
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    thumbnail_url: str = Form(...),
    user_id: str = Depends(get_user_id_header),
):
    """Kick off a background upload to YouTube using the user's connected social account."""
    if session_id not in thumbnail_sessions:
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)

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
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

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
    """Send a payment confirmation email via Brevo. Never raises — a failed email
    must not fail the webhook (Stripe would retry it forever otherwise)."""
    if not to_email:
        logger.warning("Skipping payment confirmation email: no customer email on session")
        return
    if not BREVO_API_KEY:
        logger.warning("Skipping payment confirmation email: BREVO_API_KEY is not configured")
        return

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = BREVO_API_KEY
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    if BREVO_PAYMENT_CONFIRMATION_TEMPLATE_ID:
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email}],
            template_id=int(BREVO_PAYMENT_CONFIRMATION_TEMPLATE_ID),
            params={
                "amount_total": f"{amount_total:.2f}",
                "label": label,
            },
        )
    else:
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email}],
            sender={"email": BREVO_FROM_EMAIL},
            subject="Confirmation de votre paiement",
            html_content=(
                f"<p>Bonjour,</p>"
                f"<p>Nous confirmons la réception de votre paiement de "
                f"<strong>{amount_total:.2f} €</strong> pour : {label}.</p>"
                f"<p>Merci pour votre confiance !</p>"
            ),
        )

    try:
        api_instance.send_transac_email(send_smtp_email)
    except ApiException:
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
        operation_type="credit_purchase",
        operation_id=ctx["payment_reference"],
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
        operation_type="subscription",
        operation_id=souscription_id or payment_reference,
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
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

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
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)
    plans = await supabase_list_abonnements()
    return {"plans": plans}


@app.get("/api/souscription")
async def get_current_souscription(
    request: Request,
    user_id: str = Depends(get_user_id_header),
) -> Optional[Dict[str, Any]]:
    """Get the current active subscription for a user."""
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
async def get_souscription_history(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_user_id_header),
):
    """Return subscription history only (excluding one-off credit purchases)."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

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
async def get_user_credits(request: Request, user_id: str = Depends(get_user_id_header)):
    """Return the credit/storage balance for the authenticated user."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

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
    user_id: str = Depends(get_user_id_header),
):
    """Return paginated credit/storage history for the authenticated user."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

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
async def buy_credits_checkout(
    request: Request,
    payload: BuyCreditsRequest,
    user_id: str = Depends(get_user_id_header),
):
    """Create a Stripe Checkout session for purchasing additional credits."""
    _require_stripe_ready()
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

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


@app.get("/api/captions")
async def list_captions(
    user_id: str = Depends(get_user_id_header),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: Optional[str] = None,
    status: Optional[str] = None,
):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase captions is not configured")

    rows, total = await supabase_list_captions(user_id=user_id, page=page, page_size=page_size, status=status, query=q)
    return {
        "items": [_normalize_caption_row(row) for row in rows],
        "total": total,
        "page": max(page, 1),
        "page_size": min(max(page_size, 1), 100),
    }


@app.get("/api/captions/{caption_id}/media-url")
async def caption_media_url(caption_id: str, user_id: str = Depends(get_user_id_header)):
    row = await supabase_get_caption(caption_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_CAPTION_NOT_FOUND)
    item = _normalize_caption_row(row)
    return {"media_url": item.get("media_url")}


@app.delete("/api/captions/{caption_id}")
async def delete_caption(caption_id: str, user_id: str = Depends(get_user_id_header)):
    deleted = await supabase_soft_delete_caption(caption_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=_CAPTION_NOT_FOUND)
    return {"deleted": True}


@app.post("/api/captions/{caption_id}/share")
async def share_caption(caption_id: str, payload: ReelShareRequest, user_id: str = Depends(get_user_id_header)):
    await _assert_user_has_required_credits(user_id, 0.0)

    row = await supabase_get_caption(caption_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_CAPTION_NOT_FOUND)

    item = _normalize_caption_row(row)
    media_url = item.get("media_url")
    if not media_url:
        raise HTTPException(status_code=400, detail="No media URL available")

    final_title = payload.title or row.get("caption_title") or "Sous-titres"
    final_description = payload.description or row.get("caption_description") or ""
    selected_platforms = _resolve_social_platforms(payload.platforms)
    publish_priority = await _resolve_user_job_priority(user_id)
    scheduled_for = _resolve_scheduled_datetime(payload.scheduled_date, payload.timezone)
    if payload.scheduled_date and not scheduled_for:
        raise HTTPException(status_code=400, detail=_INVALID_SCHEDULED_DATE)
    is_scheduled = bool(scheduled_for and scheduled_for > _utcnow())

    results: Dict[str, Any] = {}
    overall_success = True
    for platform_name in selected_platforms:
        if is_scheduled:
            publish_job_id = await _insert_publish_job(
                user_id=user_id,
                platform=platform_name,
                external_id="scheduled",
                status="queued",
                priority=publish_priority,
                scheduled_for=scheduled_for.isoformat() if scheduled_for else None,
                timezone=payload.timezone or "UTC",
                payload={
                    "source_type": "caption",
                    "source_id": caption_id,
                    "title": final_title,
                    "description": final_description,
                    "media_url": media_url,
                },
            )
            results[platform_name] = {
                "success": True,
                "scheduled": True,
                "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
                "publish_job_id": publish_job_id,
            }
            continue

        publish_job_id = await _insert_publish_job(
            user_id=user_id,
            platform=platform_name,
            external_id="n/a",
            status="queued",
            priority=publish_priority,
        )
        try:
            await _update_publish_job_status(publish_job_id, "processing")
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
            await _update_publish_job_status(publish_job_id, "done", external_id=external_id)
            results[platform_name] = {
                "success": True,
                "result": platform_result,
                "publish_job_id": publish_job_id,
            }
        except Exception as exc:
            overall_success = False
            err_msg = str(exc)
            await _update_publish_job_status(publish_job_id, "failed", error_message=err_msg)
            results[platform_name] = {
                "success": False,
                "error": err_msg,
                "publish_job_id": publish_job_id,
            }

    if is_supabase_configured() and not is_scheduled:
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
                operation_type="publication",
                operation_id=caption_id,
            )

    return {
        "success": overall_success,
        "results": results,
    }


# --------------------------------------------------------------------------
# Projects Endpoints
# --------------------------------------------------------------------------

@app.get("/api/projects")
async def list_projects(
	user_id: str = Depends(get_user_id_header),
	page: int = Query(1, ge=1),
	page_size: int = Query(20, ge=1, le=100),
	project_type: Optional[str] = Query(None),
	status: Optional[str] = Query(None),
	q: Optional[str] = None,
):
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	rows, total = await supabase_list_projects(
		user_id=user_id,
		page=page,
		page_size=page_size,
		project_type=project_type,
		status=status,
		query=q,
	)
	return {
		"items": rows,
		"total": total,
		"page": max(page, 1),
		"page_size": min(max(page_size, 1), 100),
	}


@app.get("/api/projects/{project_id}")
async def get_project_endpoint(project_id: str, user_id: str = Depends(get_user_id_header)):
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	project = await supabase_get_project(project_id, user_id)
	if not project:
		raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

	return project


class ProjectUpdateRequest(BaseModel):
	name: Optional[str] = None
	description: Optional[str] = None


@app.put("/api/projects/{project_id}")
async def update_project_endpoint(
	project_id: str,
	payload: ProjectUpdateRequest,
	user_id: str = Depends(get_user_id_header),
):
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	# Only allow updating name and description
	updates = {}
	if payload.name is not None:
		updates["name"] = payload.name
	if payload.description is not None:
		updates["description"] = payload.description

	if not updates:
		raise HTTPException(status_code=400, detail="No valid fields to update")

	project = await supabase_update_project(project_id, user_id, updates)
	if not project:
		raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

	return project


@app.delete("/api/projects/{project_id}")
async def delete_project_endpoint(project_id: str, user_id: str = Depends(get_user_id_header)):
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	project = await supabase_get_project(project_id, user_id)
	if not project:
		raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

	bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
	total_storage_freed_bytes = 0

	# Delete source S3 file and free up storage
	source_s3_key = project.get("source_s3_key")
	if source_s3_key:
		try:
			source_size = get_s3_object_size(bucket_name, source_s3_key)
			if delete_s3_object(bucket_name, source_s3_key):
				total_storage_freed_bytes += source_size
				logger.info(f"Deleted project source S3 file: {source_s3_key} ({source_size} bytes)")
		except Exception as e:
			logger.warning(f"Failed to delete project source S3 file {source_s3_key}: {str(e)}")

	# Get and delete all reels associated with the project
	try:
		reels = await supabase_get_reels_by_project(project_id)
		for reel in reels:
			# Delete reel media file
			reel_s3_key = reel.get("reel_s3_key")
			if reel_s3_key:
				try:
					reel_size = get_s3_object_size(bucket_name, reel_s3_key)
					if delete_s3_object(bucket_name, reel_s3_key):
						total_storage_freed_bytes += reel_size
						logger.info(f"Deleted reel S3 file: {reel_s3_key} ({reel_size} bytes)")
				except Exception as e:
					logger.warning(f"Failed to delete reel S3 file {reel_s3_key}: {str(e)}")

			# Delete reel thumbnail if it's an S3 key
			reel_thumbnail_url = reel.get("reel_thumbnail_url") or reel.get("reel_thumbnail_s3_key")
			if reel_thumbnail_url and reel_thumbnail_url.startswith("reels/"):
				try:
					thumb_size = get_s3_object_size(bucket_name, reel_thumbnail_url)
					if delete_s3_object(bucket_name, reel_thumbnail_url):
						total_storage_freed_bytes += thumb_size
						logger.info(f"Deleted reel thumbnail S3 file: {reel_thumbnail_url} ({thumb_size} bytes)")
				except Exception as e:
					logger.warning(f"Failed to delete reel thumbnail S3 file {reel_thumbnail_url}: {str(e)}")
	except Exception as e:
		logger.warning(f"Failed to retrieve or delete reels for project {project_id}: {str(e)}")

	# Get and delete all captions associated with the project
	try:
		captions = await supabase_get_captions_by_project(project_id)
		for caption in captions:
			# Delete caption media file
			caption_s3_key = caption.get("caption_s3_key")
			if caption_s3_key:
				try:
					caption_size = get_s3_object_size(bucket_name, caption_s3_key)
					if delete_s3_object(bucket_name, caption_s3_key):
						total_storage_freed_bytes += caption_size
						logger.info(f"Deleted caption S3 file: {caption_s3_key} ({caption_size} bytes)")
				except Exception as e:
					logger.warning(f"Failed to delete caption S3 file {caption_s3_key}: {str(e)}")

			# Delete caption thumbnail if it exists
			caption_thumbnail_url = caption.get("caption_thumbnail_url")
			if caption_thumbnail_url and caption_thumbnail_url.startswith(_CAPTIONS_PREFIX):
				try:
					thumb_size = get_s3_object_size(bucket_name, caption_thumbnail_url)
					if delete_s3_object(bucket_name, caption_thumbnail_url):
						total_storage_freed_bytes += thumb_size
						logger.info(f"Deleted caption thumbnail S3 file: {caption_thumbnail_url} ({thumb_size} bytes)")
				except Exception as e:
					logger.warning(f"Failed to delete caption thumbnail S3 file {caption_thumbnail_url}: {str(e)}")
	except Exception as e:
		logger.warning(f"Failed to retrieve or delete captions for project {project_id}: {str(e)}")

	# Delete database records
	deleted = await supabase_soft_delete_project(project_id, user_id)
	if not deleted:
		raise HTTPException(status_code=500, detail="Failed to delete project")

	# Free up user's storage quota (negative storage_delta = free up space)
	if total_storage_freed_bytes > 0:
		storage_freed_gb = -total_storage_freed_bytes / (1024 ** 3)  # Negative value to free up space
		try:
			await supabase_deduct_user_credits(user_id, 0.0, storage_delta=storage_freed_gb)
			logger.info(f"Freed {abs(storage_freed_gb):.6f} GB for user {user_id}")
		except Exception as e:
			logger.warning(f"Failed to update user storage quota after project deletion: {str(e)}")

	return {"deleted": True}


@app.get("/api/projects/{project_id}/source-url")
async def get_project_source_url(project_id: str, user_id: str = Depends(get_user_id_header)):
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	project = await supabase_get_project(project_id, user_id)
	if not project:
		raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

	s3_key = project.get("source_s3_key")
	if not s3_key:
		raise HTTPException(status_code=400, detail="No source video available")

	# Generate presigned URL
	bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
	source_url = generate_presigned_url(bucket_name, s3_key, expiration=3600)

	if not source_url:
		raise HTTPException(status_code=500, detail="Failed to generate source URL")

	return {"source_url": source_url}


@app.get("/api/projects/{project_id}/job")
async def get_project_job(project_id: str, user_id: str = Depends(get_user_id_header)):
  if not is_supabase_configured():
    raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

  project = await supabase_get_project(project_id, user_id)
  if not project:
    raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

  job_row = await supabase_get_latest_job_record_by_project(project_id, user_id)
  if not job_row:
    return {
      "project_id": project_id,
      "project_status": project.get("status"),
      "job": None,
    }

  job_id = str(job_row.get("id") or "")
  job_view = await reel_job_manager.get_job_view(job_id, user_id=user_id)
  return {
    "project_id": project_id,
    "project_status": project.get("status"),
    "job": job_view,
  }


@app.get("/api/projects/{project_id}/reels")
async def get_project_reels(project_id: str, user_id: str = Depends(get_user_id_header)):
	"""Get all reels for a specific project."""
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	# Verify user owns the project
	project = await supabase_get_project(project_id, user_id)
	if not project:
		raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

	reels = await supabase_get_reels_by_project(project_id)
	return {
		"project_id": project_id,
		"reels": [_normalize_reel_row(reel) for reel in reels],
		"count": len(reels),
	}


@app.get("/api/projects/{project_id}/captions")
async def get_project_captions(project_id: str, user_id: str = Depends(get_user_id_header)):
	"""Get all captions for a specific project."""
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	# Verify user owns the project
	project = await supabase_get_project(project_id, user_id)
	if not project:
		raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

	captions = await supabase_get_captions_by_project(project_id)
	return {
		"project_id": project_id,
		"captions": [_normalize_caption_row(caption) for caption in captions],
		"count": len(captions),
	}
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
        raise HTTPException(status_code=404, detail=_REEL_NOT_FOUND)
    item = _normalize_reel_row(row)
    return {"media_url": item.get("media_url")}


@app.get("/api/reels/{reel_id}/thumbnail-url")
async def reel_thumbnail_url(reel_id: str, user_id: str = Depends(get_user_id_header)):
    row = await supabase_get_reel(reel_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_REEL_NOT_FOUND)
    item = _normalize_reel_row(row)
    return {"thumbnail_url": item.get("reel_thumbnail_url")}


@app.get("/api/reels/{reel_id}/preview-url")
async def reel_preview_url(reel_id: str, user_id: str = Depends(get_user_id_header)):
    row = await supabase_get_reel(reel_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_REEL_NOT_FOUND)
    item = _normalize_reel_row(row)
    return {"preview_url": item.get("reel_preview_url")}


@app.delete("/api/reels/{reel_id}")
async def delete_reel(reel_id: str, user_id: str = Depends(get_user_id_header)):
    deleted = await supabase_soft_delete_reel(reel_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=_REEL_NOT_FOUND)
    return {"deleted": True}


@app.post("/api/reels/{reel_id}/share")
async def share_reel(reel_id: str, payload: ReelShareRequest, user_id: str = Depends(get_user_id_header)):
    await _assert_user_has_required_credits(user_id, 0.0)

    row = await supabase_get_reel(reel_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_REEL_NOT_FOUND)

    item = _normalize_reel_row(row)
    media_url = item.get("media_url")
    if not media_url:
        raise HTTPException(status_code=400, detail="No media URL available")

    final_title = payload.title or row.get("reel_title") or "Vireel"
    final_description = payload.description or row.get("reel_description") or ""
    selected_platforms = _resolve_social_platforms(payload.platforms)
    publish_priority = await _resolve_user_job_priority(user_id)
    scheduled_for = _resolve_scheduled_datetime(payload.scheduled_date, payload.timezone)
    if payload.scheduled_date and not scheduled_for:
        raise HTTPException(status_code=400, detail=_INVALID_SCHEDULED_DATE)
    is_scheduled = bool(scheduled_for and scheduled_for > _utcnow())

    results: Dict[str, Any] = {}
    overall_success = True
    for platform_name in selected_platforms:
        if is_scheduled:
            publish_job_id = await _insert_publish_job(
                user_id=user_id,
                platform=platform_name,
                external_id="scheduled",
                status="queued",
                priority=publish_priority,
                scheduled_for=scheduled_for.isoformat() if scheduled_for else None,
                timezone=payload.timezone or "UTC",
                payload={
                    "source_type": "reel",
                    "source_id": reel_id,
                    "title": final_title,
                    "description": final_description,
                    "media_url": media_url,
                },
            )
            results[platform_name] = {
                "success": True,
                "scheduled": True,
                "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
                "publish_job_id": publish_job_id,
            }
            continue

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
    if is_supabase_configured() and not is_scheduled:
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
                operation_type="publication",
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


def _derive_token_encryption_key() -> bytes:
    """Derive a 256-bit AES key from ENCRYPTION_KEY via HKDF-SHA256.

    Using a KDF (rather than the raw secret bytes) gives a full-entropy,
    fixed-length key regardless of the raw secret's length/format, and scopes
    it to this specific purpose via the `info` label.
    """
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"vireel-social-token-encryption-v1")
    return hkdf.derive(_ENCRYPTION_KEY_RAW.encode("utf-8"))


_TOKEN_ENCRYPTION_KEY = _derive_token_encryption_key()
_TOKEN_ENCRYPTION_PREFIX = "v1:"


def _encrypt_token(token: str) -> str:
    """Encrypt a social-platform OAuth token with AES-256-GCM (authenticated
    encryption) before storing it in Supabase. Replaces a previous XOR-based
    scheme that offered neither real confidentiality nor integrity, and that
    silently stored tokens in plaintext whenever ENCRYPTION_KEY was unset."""
    if not token:
        return ""
    nonce = secrets.token_bytes(12)  # AES-GCM standard nonce size; must never repeat for a given key
    ciphertext = AESGCM(_TOKEN_ENCRYPTION_KEY).encrypt(nonce, token.encode("utf-8"), None)
    return _TOKEN_ENCRYPTION_PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def _decrypt_token(token_encrypted: Optional[str]) -> str:
    if not token_encrypted:
        return ""
    if not token_encrypted.startswith(_TOKEN_ENCRYPTION_PREFIX):
        # Tokens written by the legacy XOR scheme are intentionally treated
        # as unusable rather than "best-effort" decoded: forcing a
        # reconnection is far safer than trusting a weaker/ambiguous format.
        logger.warning("Encountered a legacy-format encrypted token; treating as invalid (reconnect required).")
        return ""
    try:
        raw = base64.urlsafe_b64decode(token_encrypted[len(_TOKEN_ENCRYPTION_PREFIX):].encode("ascii"))
        nonce, ciphertext = raw[:12], raw[12:]
        plaintext = AESGCM(_TOKEN_ENCRYPTION_KEY).decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception:
        return ""


def _resolve_platform_config(platform: str) -> Dict[str, Any]:
    key = (platform or "").strip().lower()
    if key not in PLATFORM_CONFIG:
        raise HTTPException(status_code=404, detail=_UNSUPPORTED_PLATFORM)
    config = PLATFORM_CONFIG[key]
    if not config.get("client_id") or not config.get("client_secret"):
        raise HTTPException(status_code=503, detail=f"{key} OAuth is not configured")
    return config


def _oauth_popup_response(
    success: bool,
    platform: str,
    message: Optional[str] = None,
    page_selection_data: Optional[Dict[str, Any]] = None,
) -> HTMLResponse:
    if page_selection_data:
        payload = _build_page_selection_payload(platform, page_selection_data)
    else:
        payload = {
            "type": "oauth_success" if success else "oauth_error",
            "platform": platform,
            "message": message or "",
        }

    return HTMLResponse(
        f"""
        <script>
          window.opener && window.opener.postMessage({json.dumps(payload)}, {json.dumps(FRONTEND_ORIGIN)});
          window.close();
        </script>
        """
    )


def _build_page_selection_payload(platform: str, page_selection_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sépare strictement ce qui part au navigateur (affichage seulement) de ce
    qui reste signé côté serveur (les tokens réels).
    """
    raw_pages: List[Dict[str, Any]] = page_selection_data.get("pages", [])

    display_pages = [
        {
            "page_id": p.get("page_id"),
            "page_name": p.get("page_name"),
            "page_picture": p.get("page_picture"),
            "page_category": p.get("page_category"),
        }
        for p in raw_pages
    ]

    selection_token = _page_selection_serializer.dumps({
        "platform": platform,
        # Map page_id -> page_access_token, jamais envoyée au client.
        "pages": {p.get("page_id"): p.get("page_access_token") for p in raw_pages},
        "user_token": page_selection_data.get("user_token"),
        "user_token_expires_in": page_selection_data.get("user_token_expires_in"),
        "user_id": page_selection_data.get("user_id"),
    })

    return {
        "type": "oauth_page_selection",
        "platform": platform,
        "pages": display_pages,
        "selection_token": selection_token,
    }


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
    scheduled_for: Optional[str] = None,
    timezone: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    client = await supabase_get_client()
    insert_payload: Dict[str, Any] = {
        "user_id": user_id,
        "platform": platform,
        "external_id": external_id,
        "status": status,
        "priority": _clamp_job_priority(priority),
    }
    if error_message:
        insert_payload["error_message"] = error_message
    if scheduled_for:
        insert_payload["scheduled_for"] = scheduled_for
    if timezone:
        insert_payload["timezone"] = timezone
    if payload is not None:
        insert_payload["payload"] = payload
    if status in {"done", "failed"}:
        insert_payload["completed_at"] = _utcnow_iso()
    response = await client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE).insert(insert_payload).execute()
    rows = response.data or []
    return str(rows[0].get("id")) if rows and rows[0].get("id") is not None else None


async def _execute_scheduled_publish_job(job_row: Dict[str, Any]) -> None:
    job_id = str(job_row.get("id") or "")
    user_id = str(job_row.get("user_id") or "")
    platform = str(job_row.get("platform") or "").lower()
    raw_payload = job_row.get("payload") or {}
    task_payload = raw_payload if isinstance(raw_payload, dict) else {}

    if not job_id or not user_id or not platform:
        return

    try:
        await _update_publish_job_status(job_id, "processing", error_message=None)

        account = await _get_social_account(user_id, platform)
        if not account:
            raise HTTPException(status_code=404, detail=f"No connected {platform} account found")

        media_url = str(task_payload.get("media_url") or "").strip()
        if not media_url:
            raise HTTPException(status_code=400, detail="No media URL available for scheduled publish")

        description = str(task_payload.get("description") or "")
        publish_payload = PublishRequest(
            user_id=user_id,
            title=str(task_payload.get("title") or "Vireel"),
            description=description,
            text=description,
            caption=description,
            video_url=media_url,
        )

        platform_result = await publish_post(account, publish_payload)
        external_id = str(platform_result.get("publish_id") or platform_result.get("id") or platform_result.get("video_id") or "n/a")
        await _update_publish_job_status(job_id, "done", external_id=external_id, error_message=None)

        if is_supabase_configured():
            done_cost = calculate_credits_for_operation(
                estimate_publication_cost_usd(platform_count=1, video_size_gb=0.5)
            )
            done_credits = done_cost["final_credits"]
            await supabase_deduct_user_credits(user_id, done_credits)
            await supabase_insert_user_data_history(
                user_id=user_id,
                credit=done_credits,
                storage=0.0,
                operation="output",
                operation_type="publication",
                operation_id=str(task_payload.get("source_id") or job_id),
            )
    except Exception as exc:
        await _update_publish_job_status(job_id, "failed", error_message=str(exc))


async def process_scheduled_social_publish_jobs() -> None:
    while True:
        try:
            if not is_supabase_configured():
                await asyncio.sleep(max(3, SOCIAL_PUBLISH_SCHEDULER_INTERVAL_SECONDS))
                continue

            client = await supabase_get_client()
            now_iso = _utcnow_iso()
            response = (
                await client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE)
                .select("*")
                .eq("status", "queued")
                .lte("scheduled_for", now_iso)
                .order("scheduled_for", desc=False)
                .limit(20)
                .execute()
            )

            for row in (response.data or []):
                await _execute_scheduled_publish_job(row)
        except Exception as exc:
            logger.warning("Scheduled publish worker error: %s", exc, exc_info=True)

        await asyncio.sleep(max(3, SOCIAL_PUBLISH_SCHEDULER_INTERVAL_SECONDS))


async def _update_publish_job_status(
    publish_job_id: Optional[str],
    status: str,
    error_message: Optional[str] = None,
    external_id: Optional[str] = None,
) -> None:
    if not publish_job_id:
        return
    client = await supabase_get_client()
    payload: Dict[str, Any] = {
        "status": status,
    }
    if error_message is not None:
        payload["error_message"] = error_message
    if external_id is not None:
        payload["external_id"] = external_id
    if status in {"done", "failed"}:
        payload["completed_at"] = _utcnow_iso()
    await client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE).update(payload).eq("id", publish_job_id).execute()


@app.get("/api/social/accounts")
async def list_social_accounts(user_id: str = Depends(get_user_id_header)):
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
async def disconnect_social_account(platform: str, user_id: str = Depends(get_user_id_header)):
    key = (platform or "").strip().lower()
    if key not in PLATFORM_CONFIG:
        raise HTTPException(status_code=404, detail=_UNSUPPORTED_PLATFORM)
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
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
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
        date_filter: Filtre par date (all, today, week, month, custom)
        date_from: Date de début (YYYY-MM-DD) si date_filter=custom
        date_to: Date de fin (YYYY-MM-DD) si date_filter=custom
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
            elif date_filter == "custom":
                parsed_start_dt = None
                parsed_end_dt = None
                if date_from:
                    try:
                        parsed_start_dt = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
                        query = query.gte("created_at", parsed_start_dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat())
                    except ValueError:
                        raise HTTPException(status_code=400, detail="Invalid date_from format. Expected YYYY-MM-DD")
                if date_to:
                    try:
                        parsed_end_dt = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
                        query = query.lte("created_at", parsed_end_dt.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat())
                    except ValueError:
                        raise HTTPException(status_code=400, detail="Invalid date_to format. Expected YYYY-MM-DD")
                if parsed_start_dt and parsed_end_dt and parsed_start_dt.date() > parsed_end_dt.date():
                    raise HTTPException(status_code=400, detail="date_from must be before or equal to date_to")

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


@app.delete("/api/social/publish-jobs/{publish_job_id}")
async def delete_publish_job(
    publish_job_id: str,
    user_id: str = Depends(get_user_id_header),
):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase social publishing is not configured")

    client = await supabase_get_client()
    existing = (
        await client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE)
        .select("id, user_id, platform, status")
        .eq("id", publish_job_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = existing.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Publish job not found")

    await client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE).delete().eq("id", publish_job_id).eq("user_id", user_id).execute()
    return {"success": True, "deleted_id": publish_job_id}


class SelectFacebookPageRequest(BaseModel):
    selection_token: str
    page_id: str


@app.post("/api/auth/facebook/select-page")
async def select_facebook_page(payload: SelectFacebookPageRequest):
    try:
        data = _page_selection_serializer.loads(payload.selection_token, max_age=_PAGE_SELECTION_TTL_SECONDS)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Page selection expired, please reconnect Facebook")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid selection token")

    if data.get("platform") != "facebook":
        raise HTTPException(status_code=400, detail="Invalid selection token platform")

    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid selection token: missing user_id")

    page_token = (data.get("pages") or {}).get(payload.page_id)
    if not page_token:
        raise HTTPException(status_code=400, detail="This page was not part of the original selection")

    identity = await fetch_platform_identity("facebook", page_token)

    await _upsert_social_account(
        user_id=user_id,
        platform="facebook",
        access_token=page_token,
        refresh_token=None,  # les Page tokens n'ont pas de refresh_token classique
        expires_in=int(data.get("user_token_expires_in") or 5_184_000),
        platform_user_id=payload.page_id,
        platform_account_name=identity.get("name", "Facebook Page"),
        scopes="pages_manage_posts,pages_read_engagement",
    )

    return {
        "success": True,
        "message": f"Connected Facebook page '{identity.get('name', 'Facebook Page')}'",
        "platform": "facebook",
        "page_id": payload.page_id,
    }


@app.get("/api/auth/{platform}/connect")
def connect(platform: str, request: Request, user_id: str = Depends(get_user_id_header)):
    # Security: `user_id` MUST come from the verified session (get_user_id_header),
    # never from an unauthenticated query parameter -- otherwise an attacker
    # could craft a /connect link carrying their own user_id, get a victim to
    # complete the OAuth consent with the victim's real social account, and
    # have the resulting token linked to the attacker's Vireel account
    # (account-linking CSRF).
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
                            "user_id": state_data.get("user_id"),
                        }
                    )
                return _oauth_popup_response(
                    False,
                    key,
                    "No manageable Facebook Pages found. Ensure you are Page admin/editor and grant pages_show_list, pages_manage_posts, pages_read_engagement.",
                )
            except Exception as e:
                return _oauth_popup_response(
                    False,
                    key,
                    f"Facebook pages fetch failed: {e}",
                )

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

    raise HTTPException(status_code=404, detail=_UNSUPPORTED_PLATFORM)


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


# --------------------------------------------------------------------------
# Helpers génériques (social publishing)
# --------------------------------------------------------------------------

def _require_platform_user_id(account: Dict[str, Any], platform: str) -> str:
    user_id = str(account.get("platform_user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail=f"Connected {platform} account id is missing")
    return user_id


async def _raise_for_status_or_502(response: httpx.Response, platform: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error("%s API error: %s - %s", platform, e.response.status_code, e.response.text)
        raise HTTPException(
            status_code=502,
            detail=f"{platform} API error ({e.response.status_code}): {e.response.text}",
        ) from e


def _resolve_and_validate_ips(hostname: str) -> List[str]:
    """Resolve hostname and reject it if any resolved address is
    private/loopback/link-local/multicast/reserved. Returns the resolved IPs."""
    try:
        resolved_ips = list({info[4][0] for info in socket.getaddrinfo(hostname, None)})
    except socket.gaierror as e:
        raise HTTPException(status_code=400, detail="video_url host could not be resolved") from e
    for ip_str in resolved_ips:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise HTTPException(status_code=400, detail="video_url points to a disallowed address")
    return resolved_ips


def _validate_download_url(url: str) -> None:
    """Anti-SSRF minimal avant un GET serveur vers une URL fournie par l'utilisateur."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="video_url must be http(s)")
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="video_url is invalid")
    _resolve_and_validate_ips(hostname)


def _pin_url_to_validated_ip(url: str) -> tuple[str, Dict[str, Any]]:
    """Resolve+validate url's hostname, then rewrite the URL to connect
    directly to that validated IP, returning the rewritten URL plus httpx
    request extensions that keep TLS SNI / certificate hostname verification
    targeting the original hostname.

    Security: this closes the DNS-rebinding TOCTOU where _validate_download_url
    resolves and checks a hostname, but the actual HTTP client performs its
    own, independent DNS lookup at connect time -- an attacker controlling
    DNS for their domain (short TTL) could return a public IP for the check
    and a private/loopback IP for the real connection. Pinning the exact
    validated IP for the connection itself eliminates that window.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="video_url is invalid")
    validated_ips = _resolve_and_validate_ips(hostname)
    ip = validated_ips[0]
    netloc_host = f"[{ip}]" if ":" in ip else ip
    port = parsed.port
    netloc = f"{netloc_host}:{port}" if port else netloc_host
    pinned_url = parsed._replace(netloc=netloc).geturl()
    extensions = {"sni_hostname": hostname} if parsed.scheme == "https" else {}
    return pinned_url, extensions


async def _validated_stream_request(client: "httpx.AsyncClient", method: str, url: str, max_redirects: int = 5, **kwargs):
    """Issue a request without httpx's automatic redirect-following, so that
    every hop (including ones a malicious server returns after the initial
    validation) is re-checked by _validate_download_url before being
    followed. httpx's built-in follow_redirects=True would otherwise let a
    server bypass SSRF validation entirely by 302-redirecting to an
    internal/loopback/link-local address after the first request passed.
    Also pins each hop's connection to its validated IP (see
    _pin_url_to_validated_ip) to close the DNS-rebinding TOCTOU window.
    """
    current_url = url
    for _ in range(max_redirects + 1):
        original_hostname = urlparse(current_url).hostname
        pinned_url, extensions = _pin_url_to_validated_ip(current_url)
        headers = dict(kwargs.pop("headers", None) or {})
        headers.setdefault("Host", original_hostname)
        request = client.build_request(method, pinned_url, headers=headers, extensions=extensions, **kwargs)
        response = await client.send(request, stream=True)
        if response.is_redirect:
            location = response.headers.get("location")
            await response.aclose()
            if not location:
                response.raise_for_status()
                return response
            current_url = str(httpx.URL(current_url).join(location))
            continue
        return response
    raise HTTPException(status_code=400, detail="Too many redirects while fetching video_url")


async def _download_to_file(url: str, dest_path: str, timeout: float = 180.0) -> None:
    _validate_download_url(url)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await _validated_stream_request(client, "GET", url)
        try:
            response.raise_for_status()
            async with aiofiles.open(dest_path, "wb") as handle:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                    await handle.write(chunk)
        finally:
            await response.aclose()


# --------------------------------------------------------------------------
# Token refresh (get_valid_token)
# --------------------------------------------------------------------------

# Certains providers OAuth n'utilisent pas les noms de paramètres standards
# (client_id/client_secret). TikTok en particulier attend client_key.
_REFRESH_PARAM_OVERRIDES = {
    "tiktok": {"client_id_param": "client_key"},
}


async def get_valid_token(account: Dict[str, Any]) -> str:
    access_token = _decrypt_token(account.get("access_token_encrypted"))
    if access_token and not _is_token_expiring(account):
        return access_token

    platform = str(account.get("platform") or "").lower()

    # --- Instagram : pas de refresh_token classique, on rafraîchit le
    # long-lived access_token directement via ig_refresh_token ---
    if platform == "instagram":
        if not access_token:
            raise HTTPException(status_code=401, detail="Instagram account token missing, reconnection required")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://graph.instagram.com/refresh_access_token",
                params={"grant_type": "ig_refresh_token", "access_token": access_token},
            )

        if response.status_code in (400, 401):
            logger.warning("Instagram token refresh rejected: %s", response.text)
            raise HTTPException(status_code=401, detail="Instagram token expired, reconnection required")
        await _raise_for_status_or_502(response, "Instagram")

        new_data = response.json()
        refreshed_access_token = new_data.get("access_token")
        if not refreshed_access_token:
            raise HTTPException(status_code=502, detail="Instagram refresh response missing access_token")
        expires_in = int(new_data.get("expires_in") or 5_184_000)  # 60 jours par défaut

        await _persist_refreshed_token(account, refreshed_access_token, None, expires_in)
        return refreshed_access_token

    # --- Flow générique (OAuth refresh_token) pour les autres plateformes ---
    refresh_token = _decrypt_token(account.get("refresh_token_encrypted"))
    if not refresh_token:
        if access_token:
            logger.warning(
                "No refresh_token for account %s (%s); reusing possibly-expiring access_token",
                account.get("id"), platform,
            )
            return access_token
        raise HTTPException(status_code=401, detail="Account token expired and no refresh token available")

    config = _resolve_platform_config(platform)

    overrides = _REFRESH_PARAM_OVERRIDES.get(platform, {})
    client_id_param = overrides.get("client_id_param", "client_id")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            config["token_url"],
            data={
                client_id_param: config["client_id"],
                "client_secret": config["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

    if response.status_code in (400, 401):
        logger.warning("%s token refresh rejected: %s", platform, response.text)
        raise HTTPException(status_code=401, detail=f"{platform} refresh token invalid, reconnection required")
    await _raise_for_status_or_502(response, platform)

    new_tokens = await _extract_token_data(platform, response.json())
    refreshed_access_token = new_tokens.get("access_token")
    if not refreshed_access_token:
        raise HTTPException(status_code=502, detail=f"{platform} refresh response missing access_token")
    refreshed_refresh_token = new_tokens.get("refresh_token") or refresh_token
    expires_in = int(new_tokens.get("expires_in") or 3600)

    await _persist_refreshed_token(account, refreshed_access_token, refreshed_refresh_token, expires_in)
    return refreshed_access_token


async def _persist_refreshed_token(
    account: Dict[str, Any],
    access_token: str,
    refresh_token: Optional[str],
    expires_in: int,
) -> None:
    update_payload: Dict[str, Any] = {
        "access_token_encrypted": _encrypt_token(access_token),
        "expires_at": datetime.fromtimestamp(time.time() + max(expires_in, 60), tz=timezone.utc).isoformat(),
        "updated_at": _utcnow_iso(),
    }
    if refresh_token is not None:
        update_payload["refresh_token_encrypted"] = _encrypt_token(refresh_token)

    client = await supabase_get_client()
    await (
        client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
        .update(update_payload)
        .eq("id", account.get("id"))
        .execute()
    )


class PublishRequest(BaseModel):
    user_id: str
    text: Optional[str] = None
    caption: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None
    video_file: Optional[str] = None
    privacy_level: Optional[str] = "PUBLIC_TO_EVERYONE"


# --------------------------------------------------------------------------
# YouTube
# --------------------------------------------------------------------------

def _yt_validate_privacy(privacy: str) -> None:
    if privacy not in ALLOWED_YT_PRIVACY:
        raise HTTPException(status_code=400, detail=f"Invalid privacy '{privacy}', must be one of {sorted(ALLOWED_YT_PRIVACY)}")


async def _yt_initialize_upload(access_token: str, file_size: int, title: str, description: str, privacy: str) -> str:
    """Enregistre la session resumable et renvoie l'upload URL (header Location)."""
    metadata = {
        "snippet": {"title": title, "description": description, "categoryId": "22"},
        "status": {"privacyStatus": privacy},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        init_response = await client.post(
            "https://www.googleapis.com/upload/youtube/v3/videos",
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Upload-Content-Type": "video/*",
                "X-Upload-Content-Length": str(file_size),
                "Content-Type": "application/json; charset=UTF-8",
            },
            json=metadata,
        )
    await _raise_for_status_or_502(init_response, "YouTube")

    upload_url = init_response.headers.get("Location")
    if not upload_url:
        raise HTTPException(status_code=502, detail="YouTube upload session URL is missing")
    return upload_url


async def _yt_put_chunk_with_retry(upload_url: str, chunk: bytes, chunk_start: int, chunk_end: int, file_size: int) -> httpx.Response:
    """PUT d'un chunk avec retry ; renvoie la réponse HTTP brute (200/201/308/erreur gérés par l'appelant)."""
    last_error: Optional[Exception] = None
    for attempt in range(YT_MAX_RETRIES_PER_CHUNK):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                return await client.put(
                    upload_url,
                    headers={
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {chunk_start}-{chunk_end}/{file_size}",
                    },
                    content=chunk,
                )
        except httpx.HTTPError as e:
            last_error = e
            logger.warning("YouTube chunk upload failed (attempt %s/%s): %s", attempt + 1, YT_MAX_RETRIES_PER_CHUNK, e)
            await asyncio.sleep(2 ** attempt)
    raise HTTPException(status_code=502, detail=f"YouTube chunk upload failed after retries: {last_error}")


def _yt_next_offset(range_header: Optional[str], uploaded: int, chunk_len: int) -> int:
    if range_header and "-" in range_header:
        return int(range_header.split("-")[-1]) + 1
    return uploaded + chunk_len


async def upload_youtube_video(
    access_token: str, video_path: str, title: str, description: str, privacy: str = "public",
) -> Dict[str, Any]:
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {video_path}")
    _yt_validate_privacy(privacy)

    file_size = os.path.getsize(video_path)
    upload_url = await _yt_initialize_upload(access_token, file_size, title, description, privacy)

    uploaded = 0
    async with aiofiles.open(video_path, "rb") as file_handle:
        while uploaded < file_size:
            await file_handle.seek(uploaded)
            chunk = await file_handle.read(YT_CHUNK_SIZE)
            response = await _yt_put_chunk_with_retry(upload_url, chunk, uploaded, uploaded + len(chunk) - 1, file_size)

            if response.status_code in (200, 201):
                result = response.json()
                return {"video_id": result.get("id"), "url": f"https://youtube.com/watch?v={result.get('id')}"}

            if response.status_code == 308:
                uploaded = _yt_next_offset(response.headers.get("Range"), uploaded, len(chunk))
                continue

            await _raise_for_status_or_502(response, "YouTube")

    raise HTTPException(status_code=502, detail="YouTube upload ended without a final response")


# --------------------------------------------------------------------------
# TikTok
# --------------------------------------------------------------------------

# Tant que l'app n'a pas passé l'audit TikTok, seul le scope video.upload est
# accordé -> on doit utiliser l'endpoint "inbox" (dépôt dans la boîte de
# réception du créateur, qui doit finaliser lui-même la publication dans
# l'app). video.publish (endpoint /video/init/, publication directe) ne sera
# disponible qu'une fois l'app passée en production/auditée par TikTok.
# Passe TIKTOK_DIRECT_POST_ENABLED=true dans l'environnement une fois
# l'audit validé et le scope video.publish accordé.
TIKTOK_DIRECT_POST_ENABLED = os.environ.get("TIKTOK_DIRECT_POST_ENABLED", "false").strip().lower() == "true"

# Statuts terminaux considérés comme un succès selon le flow utilisé.
_TIKTOK_DIRECT_SUCCESS_STATUSES = ("PUBLISH_COMPLETE",)
# En mode inbox, la vidéo est traitée puis déposée en boîte de réception ;
# PUBLISH_COMPLETE ne surviendra que si/quand le créateur termine dans l'app.
_TIKTOK_INBOX_SUCCESS_STATUSES = ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX")


async def publish_to_tiktok(access_token: str, video_url: str, caption: str, privacy_level: str = "PUBLIC_TO_EVERYONE"):
    """
    Point d'entrée unique utilisé par publish_post. Choisit automatiquement
    le flow direct post ou inbox selon TIKTOK_DIRECT_POST_ENABLED.
    """
    if TIKTOK_DIRECT_POST_ENABLED:
        return await _publish_to_tiktok_direct(access_token, video_url, caption, privacy_level)
    return await _publish_to_tiktok_inbox(access_token, video_url, caption)


async def _publish_to_tiktok_direct(access_token: str, video_url: str, caption: str, privacy_level: str) -> Dict[str, Any]:
    """
    Publication directe sur le profil — nécessite le scope video.publish
    (app auditée). Utilise FILE_UPLOAD (téléchargement local + envoi par
    chunks) plutôt que PULL_FROM_URL, pour ne jamais dépendre de la
    vérification de domaine TikTok (utile notamment pour des URLs S3 sur
    un domaine partagé qu'on ne peut pas prouver posséder).
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    temp_path = os.path.join(UPLOAD_DIR, f"tiktok_publish_{uuid.uuid4().hex}.mp4")
    await _download_to_file(video_url, temp_path)

    try:
        file_size = os.path.getsize(temp_path)
        chunk_size, total_chunk_count = _tiktok_compute_chunks(file_size)

        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": _CONTENT_TYPE_JSON}
        init_payload = {
            "post_info": {
                "title": caption, "privacy_level": privacy_level, "disable_duet": False,
                "disable_comment": False, "disable_stitch": False,
                "brand_content_toggle": False, "brand_organic_toggle": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunk_count,
            },
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            init_response = await client.post(
                "https://open.tiktokapis.com/v2/post/publish/video/init/", headers=headers, json=init_payload,
            )
        await _raise_for_status_or_502(init_response, "TikTok")

        init_data = init_response.json()
        if init_data.get("error", {}).get("code") != "ok":
            raise HTTPException(status_code=502, detail=f"TikTok publish init failed: {init_data}")

        data = init_data.get("data") or {}
        publish_id = (data.get("publish_id") or "").strip()
        upload_url = data.get("upload_url")
        if not publish_id or not upload_url:
            raise HTTPException(status_code=502, detail="TikTok direct post init response missing publish_id or upload_url")

        await _tiktok_upload_file_chunks(upload_url, temp_path, file_size, chunk_size, total_chunk_count)

        result = await poll_tiktok_status(access_token, publish_id, success_statuses=_TIKTOK_DIRECT_SUCCESS_STATUSES)
        result["mode"] = "direct_post"
        return result
    finally:
        _cleanup_temp_file(temp_path)


TIKTOK_CHUNK_SIZE = 10_000_000  # 10 Mo, dans la plage autorisée par TikTok (5-64 Mo par chunk)
TIKTOK_WHOLE_UPLOAD_THRESHOLD = 5_000_000  # en dessous, TikTok exige un upload en un seul morceau


def _tiktok_compute_chunks(file_size: int) -> "tuple[int, int]":
    """Renvoie (chunk_size, total_chunk_count) en respectant les règles TikTok."""
    if file_size <= TIKTOK_WHOLE_UPLOAD_THRESHOLD or file_size < TIKTOK_CHUNK_SIZE:
        return file_size, 1
    return TIKTOK_CHUNK_SIZE, file_size // TIKTOK_CHUNK_SIZE


async def _tiktok_upload_file_chunks(upload_url: str, video_path: str, file_size: int, chunk_size: int, total_chunk_count: int) -> None:
    """Envoie le fichier local par chunks séquentiels, avec retry par chunk."""
    async with aiofiles.open(video_path, "rb") as file_handle:
        for i in range(total_chunk_count):
            first_byte = i * chunk_size
            last_byte = file_size - 1 if i == total_chunk_count - 1 else first_byte + chunk_size - 1
            await file_handle.seek(first_byte)
            chunk = await file_handle.read(last_byte - first_byte + 1)

            last_error: Optional[Exception] = None
            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.put(
                            upload_url,
                            headers={
                                "Content-Type": "video/mp4",
                                "Content-Length": str(len(chunk)),
                                "Content-Range": f"bytes {first_byte}-{last_byte}/{file_size}",
                            },
                            content=chunk,
                        )
                    if response.status_code in (200, 201, 206):
                        break
                    response.raise_for_status()
                except httpx.HTTPError as e:
                    last_error = e
                    logger.warning(
                        "TikTok chunk upload failed (bytes %s-%s, attempt %s/3): %s", first_byte, last_byte, attempt + 1, e,
                    )
                    await asyncio.sleep(2 ** attempt)
            else:
                raise HTTPException(status_code=502, detail=f"TikTok chunk upload failed after retries: {last_error}")


async def _publish_to_tiktok_inbox(access_token: str, video_url: str, caption: str) -> Dict[str, Any]:
    """
    Dépose la vidéo dans la boîte de réception TikTok du créateur — nécessite
    seulement video.upload. Le créateur doit ouvrir l'app pour finaliser la
    publication. NOTE: cet endpoint ne supporte pas de caption/titre via
    l'API ; le créateur devra la saisir manuellement dans l'app.

    Utilise FILE_UPLOAD (téléchargement local puis envoi par chunks) plutôt
    que PULL_FROM_URL : évite la vérification de domaine TikTok, nécessaire
    pour des URLs S3 sur un domaine partagé (*.amazonaws.com) qu'on ne peut
    pas prouver posséder.
    """
    if caption:
        logger.info("TikTok inbox upload: la légende ne peut pas être envoyée via l'API, le créateur devra la saisir dans l'app.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    temp_path = os.path.join(UPLOAD_DIR, f"tiktok_publish_{uuid.uuid4().hex}.mp4")
    await _download_to_file(video_url, temp_path)

    try:
        file_size = os.path.getsize(temp_path)
        chunk_size, total_chunk_count = _tiktok_compute_chunks(file_size)

        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": _CONTENT_TYPE_JSON}
        init_payload = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunk_count,
            }
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            init_response = await client.post(
                "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/", headers=headers, json=init_payload,
            )
        await _raise_for_status_or_502(init_response, "TikTok")

        init_data = init_response.json()
        if init_data.get("error", {}).get("code") != "ok":
            raise HTTPException(status_code=502, detail=f"TikTok inbox upload init failed: {init_data}")

        data = init_data.get("data") or {}
        publish_id = (data.get("publish_id") or "").strip()
        upload_url = data.get("upload_url")
        if not publish_id or not upload_url:
            raise HTTPException(status_code=502, detail="TikTok inbox init response missing publish_id or upload_url")

        await _tiktok_upload_file_chunks(upload_url, temp_path, file_size, chunk_size, total_chunk_count)

        result = await poll_tiktok_status(access_token, publish_id, success_statuses=_TIKTOK_INBOX_SUCCESS_STATUSES)
        result["mode"] = "inbox"
        if result.get("status") == "SEND_TO_USER_INBOX":
            result["note"] = "Video sent to the creator's TikTok inbox; they must open the app to finish posting."
        return result
    finally:
        _cleanup_temp_file(temp_path)


async def publish_to_tiktok_photo(token: str, image_urls: List[str], caption: str) -> Dict[str, Any]:
    """
    LIMITATION API TikTok : contrairement aux vidéos, l'endpoint photo
    (/v2/post/publish/content/init/) n'accepte QUE "source": "PULL_FROM_URL"
    — TikTok ne propose pas d'upload binaire pour les photos. Le domaine
    hébergeant image_urls doit donc être vérifié dans le TikTok Developer
    Portal (même prérequis que pour PULL_FROM_URL vidéo), il n'y a pas
    d'alternative FILE_UPLOAD possible ici.
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": _CONTENT_TYPE_JSON}
    post_mode = "DIRECT_POST" if TIKTOK_DIRECT_POST_ENABLED else "MEDIA_UPLOAD"
    payload = {
        "post_info": {"title": caption, "description": caption},
        "source_info": {"source": "PULL_FROM_URL", "photo_images": image_urls, "photo_cover_index": 0},
        "post_mode": post_mode,
        "media_type": "PHOTO",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post("https://open.tiktokapis.com/v2/post/publish/content/init/", json=payload, headers=headers)
    await _raise_for_status_or_502(response, "TikTok")

    init_data = response.json()
    if init_data.get("error", {}).get("code") != "ok":
        raise HTTPException(status_code=502, detail=f"TikTok photo publish init failed: {init_data}")
    return init_data


async def poll_tiktok_status(
    access_token: str, publish_id: str, max_attempts: int = 20, success_statuses=("PUBLISH_COMPLETE",),
):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": _CONTENT_TYPE_JSON}
    delay = 2.0
    for _ in range(max_attempts):
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://open.tiktokapis.com/v2/post/publish/status/fetch/", headers=headers, json={"publish_id": publish_id},
            )
        await _raise_for_status_or_502(response, "TikTok")
        data = response.json().get("data") or {}
        status = data.get("status")
        if status in success_statuses:
            return {"success": True, "publish_id": publish_id, "status": status}
        if status == "FAILED":
            return {"success": False, "publish_id": publish_id, "status": status, "error": data.get("fail_reason") or "unknown"}
        await asyncio.sleep(delay)
        delay = min(delay * 1.5, 30.0)
    return {"success": False, "publish_id": publish_id, "status": "TIMEOUT", "error": "timeout"}



# --------------------------------------------------------------------------
# Facebook
# --------------------------------------------------------------------------

async def publish_to_facebook_video(access_token: str, target_id: str, video_url: str, message: str, title: str, description: str):
    if not target_id:
        raise HTTPException(status_code=400, detail="Connected Facebook target id is missing")
    if not access_token:
        raise HTTPException(status_code=401, detail="Facebook page access token expired or missing")

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            f"https://graph.facebook.com/v19.0/{target_id}/videos",
            data={"file_url": video_url, "description": message or description, "title": title, "access_token": access_token},
        )
    await _raise_for_status_or_502(response, "Facebook")
    return {"id": response.json().get("id")}


async def publish_to_facebook_page(page_id: str, page_access_token: str, message: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://graph.facebook.com/v19.0/{page_id}/feed", data={"message": message, "access_token": page_access_token},
        )
    await _raise_for_status_or_502(response, "Facebook")
    return response.json()


async def get_facebook_long_lived_token(short_lived_token: str) -> str:
    client_id = os.getenv("FACEBOOK_CLIENT_ID")
    client_secret = os.getenv("FACEBOOK_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="FACEBOOK_CLIENT_ID / FACEBOOK_CLIENT_SECRET not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={"grant_type": "fb_exchange_token", "client_id": client_id, "client_secret": client_secret, "access_token": short_lived_token},
        )
    await _raise_for_status_or_502(response, "Facebook")
    token = response.json().get("access_token")
    if not token:
        raise HTTPException(status_code=502, detail="Facebook did not return a long-lived access_token")
    return token

# --------------------------------------------------------------------------
# Instagram (Login direct -> graph.instagram.com)
# --------------------------------------------------------------------------

async def publish_to_instagram(token: str, ig_user_id: str, video_url: Optional[str], caption: str) -> Dict[str, Any]:
    if not video_url:
        raise HTTPException(status_code=400, detail="video_url is required for Instagram video publication")
    return await _publish_instagram_container(token, ig_user_id, caption, "REELS", "video_url", video_url)


async def publish_to_instagram_image(token: str, ig_user_id: str, image_url: str, caption: str) -> Dict[str, Any]:
    return await _publish_instagram_container(token, ig_user_id, caption, "IMAGE", "image_url", image_url)


async def _publish_instagram_container(
    token: str, ig_user_id: str, caption: str, media_type: str, media_field: str, media_value: str,
) -> Dict[str, Any]:
    base_url = f"https://graph.instagram.com/v19.0/{ig_user_id}"  # Instagram Login direct

    async with httpx.AsyncClient(timeout=60.0) as client:
        container_response = await client.post(
            f"{base_url}/media",
            data={media_field: media_value, "caption": caption, "media_type": media_type, "access_token": token},
        )
    await _raise_for_status_or_502(container_response, "Instagram")
    creation_id = container_response.json().get("id")
    if not creation_id:
        raise HTTPException(status_code=502, detail="Instagram did not return a creation id")

    status = await _poll_instagram_container_status(token, creation_id)
    if status != "FINISHED":
        raise HTTPException(status_code=502, detail=f"Instagram container not ready: {status}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        publish_response = await client.post(f"{base_url}/media_publish", data={"creation_id": creation_id, "access_token": token})
    await _raise_for_status_or_502(publish_response, "Instagram")
    return publish_response.json()


async def _poll_instagram_container_status(token: str, creation_id: str, max_attempts: int = 20) -> str:
    delay = 2.0
    for _ in range(max_attempts):
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://graph.instagram.com/v19.0/{creation_id}",
                params={"fields": "status_code,status", "access_token": token},
            )
        await _raise_for_status_or_502(response, "Instagram")
        data = response.json()
        status = data.get("status_code")
        if status == "FINISHED":
            return status
        if status == "ERROR":
            logger.error("Instagram container error for %s: %s", creation_id, data.get("status"))
            return status
        await asyncio.sleep(delay)
        delay = min(delay * 1.5, 30.0)
    return "TIMEOUT"


# --------------------------------------------------------------------------
# LinkedIn (Videos API + Posts API — remplace Assets API + v2/ugcPosts)
# --------------------------------------------------------------------------

def _linkedin_headers(token: str, json_body: bool = True) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": LINKEDIN_API_VERSION,
    }
    if json_body:
        headers["Content-Type"] = _CONTENT_TYPE_JSON
    return headers


async def _create_linkedin_post(token: str, owner_urn: str, commentary: str, media: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "author": owner_urn,
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if media:
        payload["content"] = {"media": media}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post("https://api.linkedin.com/rest/posts", headers=_linkedin_headers(token), json=payload)
    await _raise_for_status_or_502(response, "LinkedIn")

    # LinkedIn renvoie l'id du post dans le header x-restli-id (pas dans le body).
    post_id = response.headers.get("x-restli-id") or response.headers.get("X-RestLi-Id")
    return {"id": post_id}

def _cleanup_temp_file(path: str) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            logger.warning("Could not remove temp file %s", path, exc_info=True)

async def _li_initialize_video_upload(access_token: str, owner_urn: str, file_size: int):
    """Renvoie (video_urn, upload_instructions, upload_token)."""
    init_payload = {
        "initializeUploadRequest": {
            "owner": owner_urn,
            "fileSizeBytes": file_size,
            "uploadCaptions": False,
            "uploadThumbnail": False,
        }
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        init_response = await client.post(
            "https://api.linkedin.com/rest/videos?action=initializeUpload",
            headers=_linkedin_headers(access_token),
            json=init_payload,
        )
    await _raise_for_status_or_502(init_response, "LinkedIn")

    init_data = (init_response.json() or {}).get("value") or {}
    video_urn = init_data.get("video")
    upload_instructions = init_data.get("uploadInstructions") or []
    upload_token = init_data.get("uploadToken", "")

    if not video_urn or not upload_instructions:
        raise HTTPException(status_code=502, detail="LinkedIn initializeUpload response missing video urn or upload instructions")
    return video_urn, upload_instructions, upload_token


async def _li_upload_part_with_retry(upload_url: str, chunk: bytes, first_byte: int, last_byte: int) -> str:
    """PUT d'une part avec retry ; renvoie l'ETag (sans guillemets) en cas de succès."""
    last_error: Optional[Exception] = None
    for attempt in range(LINKEDIN_MAX_RETRIES_PER_PART):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                part_response = await client.put(
                    upload_url, headers={"Content-Type": "application/octet-stream"}, content=chunk,
                )
            part_response.raise_for_status()
            etag = (part_response.headers.get("etag") or part_response.headers.get("ETag") or "").strip('"')
            if not etag:
                raise ValueError("LinkedIn part upload response missing ETag header")
            return etag
        except (httpx.HTTPError, ValueError) as e:
            last_error = e
            logger.warning(
                "LinkedIn video part upload failed (bytes %s-%s, attempt %s/%s): %s",
                first_byte, last_byte, attempt + 1, LINKEDIN_MAX_RETRIES_PER_PART, e,
            )
            await asyncio.sleep(2 ** attempt)
    raise HTTPException(status_code=502, detail=f"LinkedIn video part upload failed after retries: {last_error}")


async def _li_upload_all_parts(temp_path: str, upload_instructions: List[Dict[str, Any]]) -> List[str]:
    uploaded_part_ids: List[str] = []
    async with aiofiles.open(temp_path, "rb") as file_handle:
        for part in upload_instructions:
            first_byte, last_byte = part["firstByte"], part["lastByte"]
            await file_handle.seek(first_byte)
            chunk = await file_handle.read(last_byte - first_byte + 1)
            etag = await _li_upload_part_with_retry(part["uploadUrl"], chunk, first_byte, last_byte)
            uploaded_part_ids.append(etag)
    return uploaded_part_ids


async def _li_finalize_upload(access_token: str, video_urn: str, upload_token: str, uploaded_part_ids: List[str]) -> None:
    finalize_payload = {
        "finalizeUploadRequest": {"video": video_urn, "uploadToken": upload_token, "uploadedPartIds": uploaded_part_ids}
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        finalize_response = await client.post(
            "https://api.linkedin.com/rest/videos?action=finalizeUpload",
            headers=_linkedin_headers(access_token),
            json=finalize_payload,
        )
    await _raise_for_status_or_502(finalize_response, "LinkedIn")


async def publish_to_linkedin_video(access_token: str, owner_urn: str, video_url: str, title: str, description: str) -> Dict[str, Any]:
    """
    Publie une vidéo sur LinkedIn via la Videos API actuelle :
    1. Téléchargement local de la vidéo (video_url) avec validation anti-SSRF.
    2. initializeUpload -> URN vidéo + plages de parts à uploader.
    3. Upload de chaque part avec retry, récupération de l'ETag.
    4. finalizeUpload avec la liste des ETags dans l'ordre des parts.
    5. Création du post via /rest/posts (Posts API) référençant l'URN vidéo.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    temp_path = os.path.join(UPLOAD_DIR, f"li_publish_{uuid.uuid4().hex}.mp4")
    await _download_to_file(video_url, temp_path)

    try:
        file_size = os.path.getsize(temp_path)
        video_urn, upload_instructions, upload_token = await _li_initialize_video_upload(access_token, owner_urn, file_size)
        uploaded_part_ids = await _li_upload_all_parts(temp_path, upload_instructions)
        await _li_finalize_upload(access_token, video_urn, upload_token, uploaded_part_ids)

        post_result = await _create_linkedin_post(
            token=access_token, owner_urn=owner_urn, commentary=description, media={"title": title, "id": video_urn},
        )
        post_result["video_urn"] = video_urn
        return post_result
    finally:
        _cleanup_temp_file(temp_path)

# --------------------------------------------------------------------------
# Fonction principale
# --------------------------------------------------------------------------
async def _publish_video_then_text_fallback(has_video: bool, video_publisher, text_publisher) -> Dict[str, Any]:
    """
    Tente video_publisher() si has_video est vrai ; en cas d'échec (ou si
    pas de vidéo du tout), retombe sur text_publisher(). Les clés
    video_failed/video_error ne sont ajoutées que si une vidéo a été
    tentée et a échoué — comportement identique à la version précédente.
    """
    if not has_video:
        return await text_publisher()
    try:
        return await video_publisher()
    except Exception as e:
        logger.warning("Video publish failed, falling back to text: %s", e, exc_info=True)
        result = await text_publisher()
        result["video_failed"] = True
        result["video_error"] = str(e)
        return result


async def _publish_linkedin(account: Dict[str, Any], token: str, content, text_value: str) -> Dict[str, Any]:
    _require_platform_user_id(account, "LinkedIn")
    owner_urn = f"urn:li:person:{account.get('platform_user_id')}"

    async def video_publisher():
        return await publish_to_linkedin_video(
            access_token=token, owner_urn=owner_urn, video_url=content.video_url,
            title=content.title or "Vireel", description=text_value,
        )

    async def text_publisher():
        return await _create_linkedin_post(token=token, owner_urn=owner_urn, commentary=text_value)

    return await _publish_video_then_text_fallback(bool(content.video_url), video_publisher, text_publisher)


async def _publish_facebook(account: Dict[str, Any], token: str, content, text_value: str) -> Dict[str, Any]:
    _require_platform_user_id(account, "Facebook")

    async def video_publisher():
        return await publish_to_facebook_video(
            access_token=token, target_id=str(account.get("platform_user_id") or ""),
            video_url=content.video_url, message=text_value,
            title=content.title or "Vireel", description=content.description or text_value,
        )

    async def text_publisher():
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://graph.facebook.com/{account.get('platform_user_id')}/feed",
                data={"message": text_value, "access_token": token},
            )
        await _raise_for_status_or_502(response, "Facebook")
        return response.json()

    return await _publish_video_then_text_fallback(bool(content.video_url), video_publisher, text_publisher)


async def _publish_instagram_platform(account: Dict[str, Any], token: str, content, text_value: str) -> Dict[str, Any]:
    ig_user_id = _require_platform_user_id(account, "Instagram")
    image_url = getattr(content, "image_url", None)

    if content.video_url:
        return await publish_to_instagram(token, ig_user_id, content.video_url, text_value)
    if image_url:
        return await publish_to_instagram_image(token, ig_user_id, image_url, text_value)
    raise HTTPException(
        status_code=400,
        detail="Instagram requires either video_url or image_url (text-only posts are not supported by the platform)",
    )


async def _resolve_youtube_video_path(content) -> str:
    """Renvoie le chemin local du fichier vidéo à uploader (téléchargé si besoin)."""
    video_path = (content.video_file or "").strip()
    if video_path:
        return video_path
    if not content.video_url:
        raise HTTPException(status_code=400, detail="video_file or video_url is required for YouTube publication")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    temp_path = os.path.join(UPLOAD_DIR, f"yt_publish_{uuid.uuid4().hex}.mp4")
    await _download_to_file(content.video_url, temp_path)
    return temp_path


async def _publish_youtube_platform(account: Dict[str, Any], token: str, content, text_value: str) -> Dict[str, Any]:
    video_path = await _resolve_youtube_video_path(content)
    downloaded = not (content.video_file or "").strip()  # temp file only if we downloaded it ourselves
    try:
        return await upload_youtube_video(token, video_path, content.title or "Vireel Short", content.description or text_value)
    finally:
        if downloaded:
            _cleanup_temp_file(video_path)


async def _publish_tiktok_platform(account: Dict[str, Any], token: str, content, text_value: str) -> Dict[str, Any]:
    image_url = getattr(content, "image_url", None)

    if content.video_url:
        return await publish_to_tiktok(token, content.video_url, text_value, content.privacy_level or "PUBLIC_TO_EVERYONE")
    if image_url:
        image_urls = image_url if isinstance(image_url, list) else [image_url]
        return await publish_to_tiktok_photo(token, image_urls, text_value)
    raise HTTPException(
        status_code=400,
        detail="TikTok requires either video_url or image_url (text-only posts are not supported by the platform)",
    )


_PLATFORM_HANDLERS = {
    "linkedin": _publish_linkedin,
    "facebook": _publish_facebook,
    "instagram": _publish_instagram_platform,
    "youtube": _publish_youtube_platform,
    "tiktok": _publish_tiktok_platform,
}


async def publish_post(account: Dict[str, Any], content) -> Dict[str, Any]:
    token = await get_valid_token(account)
    platform = str(account.get("platform") or "").lower()
    text_value = content.text or content.caption or content.description or "Posted from Vireel"

    handler = _PLATFORM_HANDLERS.get(platform)
    if handler is None:
        raise HTTPException(status_code=404, detail=_UNSUPPORTED_PLATFORM)
    return await handler(account, token, content, text_value)



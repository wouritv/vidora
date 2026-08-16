import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel

from s3_uploader import generate_presigned_url, delete_s3_object
from subtitles import burn_subtitles, transcribe_audio
from supabase_request import (
    is_supabase_configured,
    get_user_abonnement,
    caption_status_value,
    insert_captions as supabase_insert_captions,
    list_captions as supabase_list_captions,
    get_caption as supabase_get_caption,
    soft_delete_caption as supabase_soft_delete_caption,
    get_user_data as supabase_get_user_data,
    upsert_user_data_credits as supabase_upsert_user_data_credits,
    insert_user_data_history as supabase_insert_user_data_history,
)
from billing import (
    estimate_caption_cost_usd,
    calculate_credits_for_operation,
)
from job_manager import JobManager, JobType
from pipelines import CaptionProcessingPipeline

router = APIRouter()

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
SESSION_ROOT = os.path.join(UPLOAD_DIR, "caption_sessions")
os.makedirs(SESSION_ROOT, exist_ok=True)
CAPTION_MAX_DURATION_MINUTES = float(os.environ.get("CAPTION_MAX_DURATION", "30"))
CAPTION_MAX_STORAGE_GB = float(os.environ.get("CAPTION_MAX_STORAGE", "5"))
VIREEL_VIDEO_FORMAT = os.environ.get("VIREEL_VIDEO_FORMAT", "mp4,mov,avi")
STORAGE_OVERAGE_TOLERANCE_PERCENT = float(os.environ.get("STORAGE_OVERAGE_TOLERANCE_PERCENT", "10"))

caption_sessions: Dict[str, Dict[str, Any]] = {}
caption_job_manager = JobManager(queue_name="captions")

PLATFORM_GUIDES: Dict[str, str] = {
    "tiktok": "Punchy, short, energetic phrasing with strong hooks.",
    "youtube": "Clear and educational phrasing optimized for comprehension.",
    "linkedin": "Professional and insight-driven phrasing with credibility.",
    "facebook": "Conversational and broad-audience friendly language.",
}

class CaptionLine(BaseModel):
    start: float
    end: float
    text: str


class CaptionStyle(BaseModel):
    font_name: str = "Verdana"
    font_size: int = 16
    font_color: str = "#FFFFFF"
    border_color: str = "#000000"
    border_width: int = 2
    bg_color: str = "#000000"
    bg_opacity: float = 0.0
    position: str = "bottom"


class AnalyzeRequest(BaseModel):
    session_id: str
    platform: str
    remove_silences: bool = False


class RenderRequest(BaseModel):
    session_id: str
    platform: str
    captions: Optional[List[CaptionLine]] = None
    style: Optional[CaptionStyle] = None
    title: Optional[str] = None
    description: Optional[str] = None


class MediaShareRequest(BaseModel):
    platforms: List[str]
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: Optional[str] = None
    timezone: Optional[str] = "UTC"


class FeatureRemovedResponse(BaseModel):
    detail: str


def _session_dir(session_id: str) -> str:
    return os.path.join(SESSION_ROOT, session_id)


def _bytes_to_gb(size_bytes: float) -> float:
    return max(0.0, float(size_bytes) / (1024 ** 3))


def _probe_local_video_duration_seconds(video_path: str) -> float:
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
        return max(0.0, float(frame_count / fps if fps else 0.0))
    except Exception:
        return 0.0


def _validate_caption_source_constraints(duration_seconds: float, size_bytes: float) -> None:
    max_duration_seconds = max(0.0, CAPTION_MAX_DURATION_MINUTES) * 60.0
    max_size_bytes = max(0.0, CAPTION_MAX_STORAGE_GB) * (1024 ** 3)

    if max_size_bytes > 0 and size_bytes > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Fichier trop volumineux: {_bytes_to_gb(size_bytes):.2f} Go. "
                f"Maximum autorise: {CAPTION_MAX_STORAGE_GB:.2f} Go."
            ),
        )


def _allowed_video_formats() -> List[str]:
    return [
        fmt.strip().lower().lstrip(".")
        for fmt in str(VIREEL_VIDEO_FORMAT or "").split(",")
        if fmt and fmt.strip()
    ]


def _validate_caption_video_extension(filename: str) -> None:
    allowed = _allowed_video_formats()
    if not allowed:
        return

    ext = os.path.splitext(str(filename or ""))[1].lower().lstrip(".")
    if not ext or ext not in allowed:
        accepted = ", ".join(allowed)
        raise HTTPException(
            status_code=400,
            detail=f"Format video invalide. Formats acceptes: {accepted}.",
        )


async def _ensure_caption_subscription_active(user_id: str) -> None:
    active = await get_user_abonnement(user_id)
    if not active:
        raise HTTPException(status_code=403, detail="Abonnement inactif. Veuillez reactiver une formule.")
    if active.get("account_disabled_at"):
        raise HTTPException(status_code=403, detail="Compte desactive. Reactivez votre abonnement.")
    if active.get("paused_at"):
        raise HTTPException(status_code=403, detail="Abonnement en pause. Reprenez votre abonnement pour continuer.")


async def _reserve_caption_storage_or_raise(user_id: str, required_gb: float) -> str:
    required_gb = max(0.0, float(required_gb))
    if required_gb <= 0:
        return ""
    user_data = await supabase_get_user_data(user_id)
    available_gb = float((user_data or {}).get("stockage") or 0.0)
    if required_gb <= available_gb:
        return ""

    if available_gb <= 0:
        raise HTTPException(status_code=400, detail="Stockage insuffisant pour generer des captions.")

    overage_gb = required_gb - available_gb
    overage_pct = (overage_gb / available_gb) * 100.0
    if overage_pct > STORAGE_OVERAGE_TOLERANCE_PERCENT:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Stockage insuffisant pour captions. Depassement de {overage_pct:.2f}% "
                f"(max autorise {STORAGE_OVERAGE_TOLERANCE_PERCENT:.2f}%)."
            ),
        )
    return f"Depassement de stockage autorise ({overage_pct:.2f}%)."


async def _debit_caption_storage(user_id: str, used_gb: float, operation_id: str) -> None:
    used_gb = max(0.0, float(used_gb))
    if used_gb <= 0:
        return
    await supabase_upsert_user_data_credits(user_id=user_id, credit_delta=0.0, storage_delta=-used_gb)
    await supabase_insert_user_data_history(
        user_id=user_id,
        credit=0.0,
        storage=used_gb,
        operation="output",
        operation_type="captions",
        operation_id=operation_id,
    )


async def _credit_caption_storage(user_id: str, freed_gb: float, operation_id: str) -> None:
    freed_gb = max(0.0, float(freed_gb))
    if freed_gb <= 0:
        return
    await supabase_upsert_user_data_credits(user_id=user_id, credit_delta=0.0, storage_delta=freed_gb)
    await supabase_insert_user_data_history(
        user_id=user_id,
        credit=0.0,
        storage=freed_gb,
        operation="input",
        operation_type="captions",
        operation_id=operation_id,
    )

    if max_duration_seconds > 0 and duration_seconds > max_duration_seconds:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Video trop longue: {duration_seconds / 60.0:.2f} min. "
                f"Maximum autorise: {CAPTION_MAX_DURATION_MINUTES:.2f} min."
            ),
        )


def _srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _normalize_segments(transcript: Dict[str, Any]) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    for seg in transcript.get("segments", []):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start = float(seg.get("start") or 0.0)
        end = float(seg.get("end") or start)
        if end <= start:
            continue
        segments.append({"start": start, "end": end, "text": text})
    return segments


def _clean_json(raw: str) -> str:
    value = (raw or "").strip()
    if value.startswith("```"):
        value = value.strip("`")
        if value.startswith("json"):
            value = value[4:]
    return value.strip()


def _generate_caption_texts(segments: List[Dict[str, Any]], platform: str, gemini_key: Optional[str], openai_key: Optional[str]) -> List[str]:
    if not segments:
        return []

    payload = [{"index": i + 1, "text": seg["text"]} for i, seg in enumerate(segments)]
    prompt = (
        "Rewrite each transcript line into social-native subtitle lines.\n"
        "Rules:\n"
        "- Keep same order and count.\n"
        "- Keep original meaning.\n"
        "- Max 70 chars per line.\n"
        "- Return strict JSON: {\"captions\":[{\"index\":1,\"text\":\"...\"}]}.\n"
        f"Target platform: {platform}. Guide: {PLATFORM_GUIDES[platform]}\n"
        f"Input: {json.dumps(payload, ensure_ascii=True)}"
    )

    generated: Optional[str] = None

    if openai_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model=os.environ.get("OPENAI_CAPTIONS_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini")),
                messages=[
                    {"role": "system", "content": "You generate subtitle JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1500,
            )
            generated = (response.choices[0].message.content or "").strip()
        except Exception:
            generated = None

    if not generated and gemini_key:
        try:
            from google import genai

            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model=os.environ.get("GEMINI_CAPTIONS_MODEL", os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")),
                contents=prompt,
            )
            generated = (response.text or "").strip()
        except Exception:
            generated = None

    if not generated:
        return [seg["text"] for seg in segments]

    try:
        parsed = json.loads(_clean_json(generated))
        rows = parsed.get("captions", []) if isinstance(parsed, dict) else []
        indexed = {
            int(row.get("index", 0)): str(row.get("text", "")).strip()
            for row in rows
            if isinstance(row, dict)
        }
        return [indexed.get(i + 1, seg["text"]) for i, seg in enumerate(segments)]
    except Exception:
        return [seg["text"] for seg in segments]


def _remove_silences(video_path: str, output_dir: str) -> str:
    no_silence_path = os.path.join(output_dir, "video_no_silence.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-af",
        "silenceremove=start_periods=1:start_silence=0.2:start_threshold=-38dB:stop_periods=-1:stop_duration=0.35:stop_threshold=-38dB",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        no_silence_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "Unable to remove silences")
    return no_silence_path


def _write_srt(captions: List[CaptionLine], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as fp:
        for idx, cap in enumerate(captions, start=1):
            fp.write(f"{idx}\n")
            fp.write(f"{_srt_timestamp(cap.start)} --> {_srt_timestamp(cap.end)}\n")
            fp.write(f"{cap.text.strip()}\n\n")


def _upload_caption_video_to_s3(file_path: str, session_id: str) -> str:
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return ""
    try:
        from s3_uploader import upload_file_to_s3

        key = f"ia-captions/{session_id}/{os.path.basename(file_path)}"
        ok = upload_file_to_s3(file_path, bucket, key)
        return key if ok else ""
    except Exception:
        return ""


def _media_url_from_s3_key(s3_key: str) -> str:
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not s3_key or not bucket:
        return ""
    return generate_presigned_url(bucket, s3_key, expiration=7200)


def _cleanup_caption_session(session_id: str) -> None:
    session_dir = _session_dir(session_id)
    try:
        if os.path.isdir(session_dir):
            shutil.rmtree(session_dir, ignore_errors=True)
    except Exception:
        pass
    caption_sessions.pop(session_id, None)


async def _normalize_media_row(item: Dict[str, Any]) -> Dict[str, Any]:
    s3_key = item.get("caption_s3_key") or ""
    media_url = _media_url_from_s3_key(s3_key) or item.get("caption_url") or ""
    return {
        **item,
        "media_type": "ia_caption",
        "media_url": media_url,
        "media_download_url": media_url,
        "media_preview_url": media_url,
        "media_title": item.get("caption_title"),
        "media_description": item.get("caption_description"),
        "media_duration": item.get("caption_duration"),
        "media_status": item.get("caption_status"),
        "media_thumbnail_url": item.get("caption_thumbnail_url"),
        "media_created_at": item.get("caption_created_at"),
        "media_updated_at": item.get("caption_updated_at"),
        "media_inputs": item.get("generation_inputs") or {},
    }


@router.api_route("/api/saasshorts/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], response_model=FeatureRemovedResponse)
async def removed_ai_shorts(path: str):
    return JSONResponse(status_code=410, content={"detail": "AI Shorts et AI Agent ont ete supprimes."})


@router.api_route("/api/ia-shorts/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], response_model=FeatureRemovedResponse)
async def removed_ia_shorts_gallery(path: str):
    return JSONResponse(status_code=410, content={"detail": "AI Shorts et AI Agent ont ete supprimes."})


@router.api_route("/api/youtube-resumes/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], response_model=FeatureRemovedResponse)
async def removed_youtube_resumes(path: str):
    return JSONResponse(status_code=410, content={"detail": "La feature YouTube Resume a ete remplacee par IA Captions."})


@router.post("/api/captions/upload")
async def captions_upload(request: Request, file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Veuillez uploader un fichier video valide")

    _validate_caption_video_extension(file.filename or "")

    session_id = str(uuid.uuid4())
    session_dir = _session_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)
    file_name = file.filename or "upload.mp4"
    input_path = os.path.join(session_dir, file_name)

    size_bytes = 0
    try:
        with open(input_path, "wb") as fp:
            while chunk := await file.read(1024 * 1024):
                size_bytes += len(chunk)
                fp.write(chunk)

        duration_seconds = _probe_local_video_duration_seconds(input_path)
        _validate_caption_source_constraints(duration_seconds, size_bytes)
    except HTTPException:
        if os.path.exists(input_path):
            os.remove(input_path)
        shutil.rmtree(session_dir, ignore_errors=True)
        raise
    except Exception as exc:
        if os.path.exists(input_path):
            os.remove(input_path)
        shutil.rmtree(session_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Impossible de valider la video: {exc}")

    caption_sessions[session_id] = {
        "session_id": session_id,
        "input_path": input_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "remove_silences": False,
        "user_id": request.headers.get("X-User-Id") or "",
    }

    return {"session_id": session_id, "file_name": file_name}


@router.post("/api/captions/analyze")
async def captions_analyze(
    request: Request,
    req: AnalyzeRequest,
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key"),
    x_openai_key: Optional[str] = Header(None, alias="X-OpenAI-Key"),
):
    if req.platform not in PLATFORM_GUIDES:
        raise HTTPException(status_code=400, detail="Plateforme non supportee")

    session = caption_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")

    user_id = request.headers.get("X-User-Id") or session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")

    await _ensure_caption_subscription_active(user_id)

    # --- Credit pre-check ---
    if is_supabase_configured():
        _cap_cost = calculate_credits_for_operation(
            estimate_caption_cost_usd(duration_minutes=10.0, video_size_gb=0.5)
        )
        _required = _cap_cost["final_credits"]
        _ud = await supabase_get_user_data(user_id)
        _available = float(_ud.get("credit", 0)) if _ud else 0.0
        if _available < _required:
            raise HTTPException(
                status_code=402,
                detail=f"Crédits insuffisants. Requis : {_required} cr, disponible : {_available} cr.",
            )

    job_row = await caption_job_manager.create_job(
        user_id=user_id,
        job_type=JobType.TRANSCRIBE,
        pipeline_name="CaptionProcessingPipeline",
        job_data={
            "session_id": req.session_id,
            "platform": req.platform,
            "remove_silences": bool(req.remove_silences),
        },
        max_attempts=1,
    )
    job_id = job_row.get("id")
    pipeline = CaptionProcessingPipeline(caption_job_manager, job_id)
    await caption_job_manager.start_job(job_id)

    input_path = session.get("input_path")
    if not input_path or not os.path.exists(input_path):
        await caption_job_manager.fail_job(job_id, "Video introuvable", error_code="VIDEO_NOT_FOUND")
        raise HTTPException(status_code=404, detail="Video introuvable")

    working_path = input_path
    session_dir = _session_dir(req.session_id)
    await pipeline.analyzing()
    if req.remove_silences:
        working_path = _remove_silences(input_path, session_dir)

    await pipeline.transcribing()
    transcript = transcribe_audio(working_path)
    segments = _normalize_segments(transcript)
    if not segments:
        await caption_job_manager.fail_job(job_id, "Aucune voix detectee dans cette video", error_code="NO_SPEECH")
        raise HTTPException(status_code=400, detail="Aucune voix detectee dans cette video")

    caption_texts = _generate_caption_texts(
        segments=segments,
        platform=req.platform,
        gemini_key=x_gemini_key or os.environ.get("GEMINI_API_KEY"),
        openai_key=x_openai_key or os.environ.get("OPENAI_API_KEY"),
    )

    captions = [
        CaptionLine(start=seg["start"], end=seg["end"], text=caption_texts[idx])
        for idx, seg in enumerate(segments)
    ]

    session.update(
        {
            "platform": req.platform,
            "remove_silences": req.remove_silences,
            "working_path": working_path,
            "captions": [c.model_dump() for c in captions],
            "language": transcript.get("language", "auto"),
            "duration": int(round(segments[-1]["end"])),
            "user_id": session.get("user_id") or user_id,
        }
    )

    await caption_job_manager.complete_job(
        job_id,
        {
            "session_id": req.session_id,
            "platform": req.platform,
            "captions_count": len(captions),
            "language": transcript.get("language", "auto"),
        },
    )

    return {
        "session_id": req.session_id,
        "platform": req.platform,
        "remove_silences": req.remove_silences,
        "language": transcript.get("language", "auto"),
        "captions": [c.model_dump() for c in captions],
    }


@router.post("/api/captions/render")
async def captions_render(request: Request, req: RenderRequest):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")

    await _ensure_caption_subscription_active(user_id)

    job_row = await caption_job_manager.create_job(
        user_id=user_id,
        job_type=JobType.RENDER_VIDEO,
        pipeline_name="CaptionProcessingPipeline",
        job_data={
            "session_id": req.session_id,
            "platform": req.platform,
        },
        max_attempts=1,
    )
    job_id = job_row.get("id")
    pipeline = CaptionProcessingPipeline(caption_job_manager, job_id)
    await caption_job_manager.start_job(job_id)

    if req.platform not in PLATFORM_GUIDES:
        await caption_job_manager.fail_job(job_id, "Plateforme non supportee", error_code="INVALID_PLATFORM")
        raise HTTPException(status_code=400, detail="Plateforme non supportee")

    session = caption_sessions.get(req.session_id)
    if not session:
        await caption_job_manager.fail_job(job_id, "Session introuvable", error_code="SESSION_NOT_FOUND")
        raise HTTPException(status_code=404, detail="Session introuvable")

    working_path = session.get("working_path") or session.get("input_path")
    if not working_path or not os.path.exists(working_path):
        await caption_job_manager.fail_job(job_id, "Video introuvable", error_code="VIDEO_NOT_FOUND")
        raise HTTPException(status_code=404, detail="Video introuvable")

    style = req.style or CaptionStyle()
    captions = req.captions or [CaptionLine(**row) for row in session.get("captions", [])]
    if not captions:
        await caption_job_manager.fail_job(job_id, "Aucun caption disponible", error_code="CAPTIONS_NOT_FOUND")
        raise HTTPException(status_code=400, detail="Aucun caption disponible")

    session_dir = _session_dir(req.session_id)
    srt_path = os.path.join(session_dir, "captions.srt")
    _write_srt(captions, srt_path)

    output_name = f"captioned_{req.platform}_{req.session_id}.mp4"
    output_path = os.path.join(session_dir, output_name)

    await pipeline.rendering()
    burn_subtitles(
        video_path=working_path,
        srt_path=srt_path,
        output_path=output_path,
        alignment=style.position,
        fontsize=style.font_size,
        font_name=style.font_name,
        font_color=style.font_color,
        border_color=style.border_color,
        border_width=style.border_width,
        bg_color=style.bg_color,
        bg_opacity=style.bg_opacity,
    )

    if not is_supabase_configured():
        await caption_job_manager.fail_job(job_id, "Supabase media is not configured", error_code="SUPABASE_NOT_CONFIGURED")
        raise HTTPException(status_code=503, detail="Supabase media is not configured")

    output_size_bytes = int(os.path.getsize(output_path) or 0) if os.path.exists(output_path) else 0
    output_size_gb = _bytes_to_gb(output_size_bytes)
    storage_warning = await _reserve_caption_storage_or_raise(user_id, output_size_gb)
    if storage_warning:
        await caption_job_manager.update_progress(job_id, 92, "storage_warning", {"warning": storage_warning})

    await pipeline.persisting()
    s3_key = _upload_caption_video_to_s3(output_path, req.session_id)
    if not s3_key:
        await caption_job_manager.fail_job(job_id, "S3 upload failed for IA captions output", error_code="S3_UPLOAD_FAILED")
        raise HTTPException(status_code=500, detail="S3 upload failed for IA captions output")
    media_url = _media_url_from_s3_key(s3_key)
    if not media_url:
        await caption_job_manager.fail_job(job_id, "Unable to generate media URL from S3", error_code="S3_URL_FAILED")
        raise HTTPException(status_code=500, detail="Unable to generate media URL from S3")

    now_iso = datetime.now(timezone.utc).isoformat()
    title = req.title or (captions[0].text[:80] if captions else "IA Captions")
    description = req.description or f"Captions adaptes pour {req.platform}."
    duration = int(session.get("duration") or 0)
    row = {
        "caption_url": media_url,
        "caption_thumbnail_url": "",
        "caption_title": title,
        "caption_description": description,
        "caption_duration": max(5, duration),
        "caption_created_at": now_iso,
        "caption_updated_at": now_iso,
        "caption_user_id": user_id,
        "caption_status": caption_status_value("termine"),
        "caption_job_id": req.session_id,
        "caption_clip_index": 0,
        "caption_s3_key": s3_key,
        "caption_size_bytes": output_size_bytes,
        "generation_inputs": {
            "platform": req.platform,
            "remove_silences": bool(session.get("remove_silences")),
            "style": style.model_dump(),
        },
        "input_source_type": "upload",
        "input_source_value": os.path.basename(session.get("input_path") or ""),
    }
    saved = await supabase_insert_captions([row])
    if not saved:
        await caption_job_manager.fail_job(job_id, "Failed to persist IA captions row in Supabase", error_code="CAPTION_PERSISTENCE_FAILED")
        raise HTTPException(status_code=500, detail="Failed to persist IA captions row in Supabase")
    item = await _normalize_media_row(saved[0])

    await caption_job_manager.complete_job(
        job_id,
        {
            "session_id": req.session_id,
            "platform": req.platform,
            "item_id": item.get("id"),
            "media_url": item.get("media_url"),
        },
    )

    # Debit credits after caption render success (best-effort)
    if is_supabase_configured():
        _cap_bd = estimate_caption_cost_usd(duration_minutes=10.0, video_size_gb=0.5)
        _cap_cr = calculate_credits_for_operation(_cap_bd)["final_credits"]
        await caption_job_manager.debit_credits_for_job(
            job_id=job_id,
            user_id=user_id,
            credits=_cap_cr,
            operation_type="captions",
        )

    await _debit_caption_storage(user_id, output_size_gb, operation_id=str(item.get("id") or req.session_id))

    # Keep output fully remote: drop all local artifacts right after persistence.
    _cleanup_caption_session(req.session_id)

    return {
        "session_id": req.session_id,
        "platform": req.platform,
        "media_url": media_url,
        "captions": [c.model_dump() for c in captions],
        "item": item,
    }


@router.get("/api/ia-captions")
async def list_ia_captions(request: Request, page: int = 1, page_size: int = 10, q: Optional[str] = None, status: Optional[str] = None):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    rows, total = await supabase_list_captions(user_id=user_id, page=page, page_size=page_size, status=status, query=q)
    return {
        "items": [await _normalize_media_row(row) for row in rows],
        "total": total,
        "page": max(page, 1),
        "page_size": min(max(page_size, 1), 100),
    }


@router.get("/api/ia-captions/{item_id}/media-url")
async def ia_caption_media_url(request: Request, item_id: str):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    row = await supabase_get_caption(item_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Media not found")
    item = await _normalize_media_row(row)
    return {"media_url": item.get("media_url")}


@router.delete("/api/ia-captions/{item_id}")
async def delete_ia_caption(request: Request, item_id: str):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")

    row = await supabase_get_caption(item_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Media not found")

    size_bytes = int(row.get("caption_size_bytes") or 0)
    freed_gb = _bytes_to_gb(size_bytes)
    s3_key = str(row.get("caption_s3_key") or "").strip()
    bucket = os.environ.get("AWS_S3_BUCKET", "")

    deleted = await supabase_soft_delete_caption(item_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Media not found")

    if bucket and s3_key:
        delete_s3_object(bucket, s3_key)

    await _credit_caption_storage(user_id, freed_gb, operation_id=f"delete:{item_id}")
    return {"deleted": True}


@router.get("/api/ia-captions/{item_id}/download")
async def download_ia_caption(request: Request, item_id: str):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    row = await supabase_get_caption(item_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Media not found")
    item = await _normalize_media_row(row)
    return {"download_url": item.get("media_url")}


@router.post("/api/ia-captions/{item_id}/share")
async def share_ia_caption(request: Request, item_id: str, payload: MediaShareRequest):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")

    row = await supabase_get_caption(item_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Media not found")

    item = await _normalize_media_row(row)
    media_url = item.get("media_url")
    if not media_url:
        raise HTTPException(status_code=400, detail="No media URL available")

    final_title = payload.title or row.get("caption_title") or "Vireel"
    final_description = payload.description or row.get("caption_description") or ""

    selected_platforms = [str(name or "").strip().lower() for name in payload.platforms if str(name or "").strip()]
    if not selected_platforms:
        raise HTTPException(status_code=400, detail="No platforms selected")
    if payload.scheduled_date:
        raise HTTPException(status_code=400, detail="Scheduled caption sharing is not supported in this endpoint")

    results: Dict[str, Any] = {}
    overall_success = True
    base_api = str(request.base_url).rstrip("/")

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        for platform in selected_platforms:
            try:
                response = await client.post(
                    f"{base_api}/api/publish/{platform}",
                    json={
                        "user_id": user_id,
                        "title": final_title,
                        "description": final_description,
                        "text": final_description,
                        "caption": final_description,
                        "video_url": media_url,
                    },
                    headers={"X-User-Id": user_id},
                )
                if response.status_code >= 400:
                    raise HTTPException(status_code=response.status_code, detail=response.text)
                results[platform] = {"success": True, "result": response.json()}
            except Exception as exc:
                overall_success = False
                results[platform] = {"success": False, "error": str(exc)}

    return {"success": overall_success, "results": results}


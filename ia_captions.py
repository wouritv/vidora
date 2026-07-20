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

from s3_uploader import generate_presigned_url
from subtitles import burn_subtitles, transcribe_audio
from supabase_media import (
    get_row as supabase_get_media_row,
    is_supabase_configured,
    list_rows as supabase_list_media_rows,
    media_status_value,
    save_media_rows as supabase_save_media_rows,
    soft_delete_row as supabase_soft_delete_media_row,
)

router = APIRouter()

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
SESSION_ROOT = os.path.join(UPLOAD_DIR, "caption_sessions")
os.makedirs(SESSION_ROOT, exist_ok=True)

caption_sessions: Dict[str, Dict[str, Any]] = {}

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
    api_key: str
    user_id: str
    platforms: List[str]
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: Optional[str] = None
    timezone: Optional[str] = "UTC"


class FeatureRemovedResponse(BaseModel):
    detail: str


def _session_dir(session_id: str) -> str:
    return os.path.join(SESSION_ROOT, session_id)


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


def _upload_post_payload(final_title: str, final_description: str, platforms: List[str], user_id: str, scheduled_date: Optional[str] = None, timezone_name: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "user": user_id,
        "title": final_title,
        "platform[]": platforms,
        "async_upload": "true",
    }
    if scheduled_date:
        payload["scheduled_date"] = scheduled_date
        if timezone_name:
            payload["timezone"] = timezone_name
    if "tiktok" in platforms:
        payload["tiktok_title"] = final_description or final_title
    if "youtube" in platforms:
        payload["youtube_title"] = final_title
        payload["youtube_description"] = final_description or final_title
        payload["privacyStatus"] = "public"
    if "linkedin" in platforms:
        payload["linkedin_title"] = final_title
        payload["linkedin_description"] = final_description or final_title
    if "facebook" in platforms:
        payload["facebook_title"] = final_title
        payload["facebook_description"] = final_description or final_title
    return payload


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
async def captions_upload(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Veuillez uploader un fichier video valide")

    session_id = str(uuid.uuid4())
    session_dir = _session_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)
    file_name = file.filename or "upload.mp4"
    input_path = os.path.join(session_dir, file_name)

    with open(input_path, "wb") as fp:
        shutil.copyfileobj(file.file, fp)

    caption_sessions[session_id] = {
        "session_id": session_id,
        "input_path": input_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "remove_silences": False,
    }

    return {"session_id": session_id, "file_name": file_name}


@router.post("/api/captions/analyze")
async def captions_analyze(
    req: AnalyzeRequest,
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key"),
    x_openai_key: Optional[str] = Header(None, alias="X-OpenAI-Key"),
):
    if req.platform not in PLATFORM_GUIDES:
        raise HTTPException(status_code=400, detail="Plateforme non supportee")

    session = caption_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")

    input_path = session.get("input_path")
    if not input_path or not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="Video introuvable")

    working_path = input_path
    session_dir = _session_dir(req.session_id)
    if req.remove_silences:
        working_path = _remove_silences(input_path, session_dir)

    transcript = transcribe_audio(working_path)
    segments = _normalize_segments(transcript)
    if not segments:
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
        }
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
    if req.platform not in PLATFORM_GUIDES:
        raise HTTPException(status_code=400, detail="Plateforme non supportee")

    session = caption_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")

    working_path = session.get("working_path") or session.get("input_path")
    if not working_path or not os.path.exists(working_path):
        raise HTTPException(status_code=404, detail="Video introuvable")

    style = req.style or CaptionStyle()
    captions = req.captions or [CaptionLine(**row) for row in session.get("captions", [])]
    if not captions:
        raise HTTPException(status_code=400, detail="Aucun caption disponible")

    session_dir = _session_dir(req.session_id)
    srt_path = os.path.join(session_dir, "captions.srt")
    _write_srt(captions, srt_path)

    output_name = f"captioned_{req.platform}_{req.session_id}.mp4"
    output_path = os.path.join(session_dir, output_name)

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

    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase media is not configured")

    s3_key = _upload_caption_video_to_s3(output_path, req.session_id)
    if not s3_key:
        raise HTTPException(status_code=500, detail="S3 upload failed for IA captions output")
    media_url = _media_url_from_s3_key(s3_key)
    if not media_url:
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
        "caption_status": media_status_value("termine"),
        "caption_job_id": req.session_id,
        "caption_clip_index": 0,
        "caption_s3_key": s3_key,
        "generation_inputs": {
            "platform": req.platform,
            "remove_silences": bool(session.get("remove_silences")),
            "style": style.model_dump(),
        },
        "input_source_type": "upload",
        "input_source_value": os.path.basename(session.get("input_path") or ""),
    }
    saved = await supabase_save_media_rows("ia_caption", [row])
    if not saved:
        raise HTTPException(status_code=500, detail="Failed to persist IA captions row in Supabase")
    item = await _normalize_media_row(saved[0])

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
    rows, total = await supabase_list_media_rows("ia_caption", user_id=user_id, page=page, page_size=page_size, status=status, query=q)
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
    row = await supabase_get_media_row("ia_caption", item_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Media not found")
    item = await _normalize_media_row(row)
    return {"media_url": item.get("media_url")}


@router.delete("/api/ia-captions/{item_id}")
async def delete_ia_caption(request: Request, item_id: str):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    deleted = await supabase_soft_delete_media_row("ia_caption", item_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Media not found")
    return {"deleted": True}


@router.get("/api/ia-captions/{item_id}/download")
async def download_ia_caption(request: Request, item_id: str):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    row = await supabase_get_media_row("ia_caption", item_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Media not found")
    item = await _normalize_media_row(row)
    return {"download_url": item.get("media_url")}


@router.post("/api/ia-captions/{item_id}/share")
async def share_ia_caption(request: Request, item_id: str, payload: MediaShareRequest):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")

    row = await supabase_get_media_row("ia_caption", item_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Media not found")

    item = await _normalize_media_row(row)
    media_url = item.get("media_url")
    if not media_url:
        raise HTTPException(status_code=400, detail="No media URL available")

    final_title = payload.title or row.get("caption_title") or "OpenShorts"
    final_description = payload.description or row.get("caption_description") or ""

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        media_response = await client.get(media_url)
        media_response.raise_for_status()
        upload_response = await client.post(
            "https://api.upload-post.com/api/upload",
            headers={"Authorization": f"Apikey {payload.api_key}"},
            data=_upload_post_payload(final_title, final_description, payload.platforms, payload.user_id, payload.scheduled_date, payload.timezone),
            files={"video": (f"{item_id}.mp4", media_response.content, "video/mp4")},
        )

    if upload_response.status_code not in (200, 201, 202):
        raise HTTPException(status_code=upload_response.status_code, detail=f"Upload-Post Error: {upload_response.text}")
    return upload_response.json()


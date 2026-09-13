"""Anonymous stories ("Temoignages"): turn a video testimonial into a
structured, anonymized, editable written story.

This module intentionally holds only the feature's pure/validation logic
and its two external calls (AssemblyAI transcription, OpenAI generation)
behind small functions. Request handling, credits, S3 and Supabase
persistence stay in app.py, next to the equivalent reels/captions code they
reuse (see spec section 13 for the originally proposed layout; this
codebase keeps all route wiring in app.py instead of a package, so this
module mirrors subtitles.py/thumbnail.py/hooks.py rather than a FastAPI
router).
"""

import asyncio
import io
import json
import os
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont


class AnonymousStorySourceType:
    UPLOAD = "upload"
    YOUTUBE = "youtube"


# Single source of truth for the credit/storage history `operation_type`
# (see supabase_request.insert_user_data_history), matching the "Histoires
# anonymes" feature name -- used for every debit/refund tied to this
# feature (creation and regeneration alike) so the credit history always
# labels them consistently, the same way "sous_titre"/"generation_reel"
# do for captions/reels.
CREDIT_OPERATION_TYPE = "histoire_anonyme"


class AnonymousStoryStatus:
    DRAFT = "draft"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnonymousStoryStage:
    UPLOAD = "upload"
    TRANSCRIPTION = "transcription"
    ANALYSIS = "analysis"
    GENERATION = "generation"
    FINALIZATION = "finalization"


# User-safe error codes (spec section 10). Only the code is ever persisted;
# the frontend maps it to a translated (en/fr) message. Never store a raw
# exception message where the user can see it.
class AnonymousStoryErrorCode:
    INVALID_YOUTUBE_URL = "INVALID_YOUTUBE_URL"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
    NOT_A_STORY = "NOT_A_STORY"
    GENERATION_INVALID = "GENERATION_INVALID"
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    JOB_CANCELLED = "JOB_CANCELLED"


class StoryValidationError(ValueError):
    """Raised whenever generated/edited content fails validation.

    Carries the AnonymousStoryErrorCode to persist, so callers never have
    to re-derive an error code from a free-form exception message.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


REQUIRED_STORY_FIELDS = ("is_story", "hook", "introduction", "story", "questions")


def build_final_text(content: Dict[str, Any]) -> str:
    """Flatten a structured story into the single copy-ready text block.

    Always rebuilt backend-side from hook/introduction/story/questions
    (spec section 7.4/7.5: "Construire final_text cote backend a partir de
    la structure validee") -- never trusted verbatim from the AI output or
    from a client edit, so it can't silently drift from the blocks shown in
    the editor.
    """
    hook = str(content.get("hook") or "").strip()
    introduction = str(content.get("introduction") or "").strip()
    story = str(content.get("story") or "").strip()
    questions = [str(q).strip() for q in (content.get("questions") or []) if str(q).strip()]

    parts = [part for part in (hook, introduction, story) if part]
    if questions:
        parts.append("\n".join(questions))
    return "\n\n".join(parts)


def _normalize_generated_story_fields(raw: Dict[str, Any], story: str, questions: List[Any]) -> Dict[str, Any]:
    """Build the normalized story dict once the raw AI payload has passed
    all validation checks. Pulled out of validate_generated_story_payload
    to keep its cognitive complexity down."""
    normalized = {
        "is_story": True,
        "confidence": _safe_float(raw.get("confidence")),
        "has_personal_experience": bool(raw.get("has_personal_experience")),
        "hook": str(raw.get("hook") or "").strip(),
        "introduction": str(raw.get("introduction") or "").strip(),
        "story": story,
        "questions": [str(q).strip() for q in questions if str(q).strip()],
        "title": str(raw.get("title") or "").strip()[:200],
    }
    normalized["full_text"] = build_final_text(normalized)
    if not normalized["full_text"]:
        raise StoryValidationError(AnonymousStoryErrorCode.GENERATION_INVALID, "final_text is empty")
    if not normalized["title"]:
        normalized["title"] = derive_fallback_title(normalized)
    return normalized


def validate_generated_story_payload(raw: Any) -> Dict[str, Any]:
    """Validate and normalize the AI's JSON output against the schema from
    spec section 8.1. Raises StoryValidationError -- never returns
    unvalidated content -- so a malformed/refused generation is always
    treated as a technical error, never shown to the user as a story
    (spec section 8.1: "toute sortie non conforme comme une erreur
    technique de generation, pas comme du contenu a afficher").
    """
    if not isinstance(raw, dict):
        raise StoryValidationError(AnonymousStoryErrorCode.GENERATION_INVALID, "AI output is not a JSON object")

    for field in REQUIRED_STORY_FIELDS:
        if field not in raw:
            raise StoryValidationError(AnonymousStoryErrorCode.GENERATION_INVALID, f"Missing field: {field}")

    if raw.get("is_story") is not True:
        reason = str(raw.get("reason") or "").strip()
        raise StoryValidationError(AnonymousStoryErrorCode.NOT_A_STORY, reason or "Not an exploitable personal story")

    questions = raw.get("questions")
    if not isinstance(questions, list) or not questions:
        raise StoryValidationError(AnonymousStoryErrorCode.GENERATION_INVALID, "Missing closing questions")

    story = str(raw.get("story") or "").strip()
    if not story:
        raise StoryValidationError(AnonymousStoryErrorCode.GENERATION_INVALID, "Empty story body")

    return _normalize_generated_story_fields(raw, story, questions)


def derive_fallback_title(content: Dict[str, Any]) -> str:
    """Best-effort title when the model didn't return one: the first dozen
    words of the hook (or the story, if there's no hook), truncated with an
    ellipsis. Kept deliberately simple -- no extra AI call -- since the
    model is asked for a real title first (see STORY_SYSTEM_PROMPT).
    """
    basis = str(content.get("hook") or content.get("story") or "").strip()
    if not basis:
        return ""
    words = basis.split()
    kept = words[:12]
    title = " ".join(kept).strip(" \"'«»")
    if len(kept) < len(words):
        title = f"{title.rstrip('.,;:!?')}…"
    return title[:200]


def validate_edited_story_content(raw: Any) -> Dict[str, Any]:
    """Validate a user-submitted edit (PATCH body) before it is persisted.

    Deliberately more permissive than the AI-output validator above: a user
    may legitimately clear the hook or leave one question, so only "the
    story itself must not be emptied out" is enforced.
    """
    if not isinstance(raw, dict):
        raise StoryValidationError(AnonymousStoryErrorCode.GENERATION_INVALID, "Edited content must be a JSON object")

    story = str(raw.get("story") or "").strip()
    if not story:
        raise StoryValidationError(AnonymousStoryErrorCode.GENERATION_INVALID, "Story text cannot be empty")

    questions = raw.get("questions") or []
    if not isinstance(questions, list):
        raise StoryValidationError(AnonymousStoryErrorCode.GENERATION_INVALID, "questions must be a list")

    normalized = {
        "hook": str(raw.get("hook") or "").strip(),
        "introduction": str(raw.get("introduction") or "").strip(),
        "story": story,
        "questions": [str(q).strip() for q in questions if str(q).strip()],
    }
    normalized["full_text"] = build_final_text(normalized)
    return normalized


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


_EMAIL_RE = None
_PHONE_RE = None


def _pii_patterns():
    global _EMAIL_RE, _PHONE_RE
    if _EMAIL_RE is None or _PHONE_RE is None:
        import re

        _EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        _PHONE_RE = re.compile(r"(?:\+?\d[\s.-]?){8,}\d")
    return _EMAIL_RE, _PHONE_RE


def find_possible_identifying_leftovers(text: str) -> List[str]:
    """Best-effort safety net over the model's own editorial anonymization
    (spec section 8, "# ANONYMAT"). Never blocks generation -- anonymizing
    the narrative is the model's job -- this only flags obvious leftovers
    (an email, a phone number) into the job log for manual follow-up.
    """
    email_re, phone_re = _pii_patterns()
    found = []
    haystack = text or ""
    if email_re.search(haystack):
        found.append("email")
    if phone_re.search(haystack):
        found.append("phone_number")
    return found


# ---------------------------------------------------------------------------
# Prompt (spec section 8) -- kept as a plain string and interpolated with a
# separate user message rather than str.format(), since the transcription
# text is untrusted free text that can contain literal `{`/`}` characters
# (see the REEL_PROMPT.format() crash this same class of bug caused
# elsewhere in this codebase).
# ---------------------------------------------------------------------------
STORY_SYSTEM_PROMPT = """# ROLE
Tu es un scenariste, script doctor et expert en storytelling specialise dans les temoignages personnels et les contenus sociaux a forte retention.
Ta mission est de transformer une transcription orale en temoignage ecrit naturel, personnel, credible, emotionnel et captivant.
Tu ne dois PAS resumer mecaniquement la transcription.
Tu dois reconstruire le recit a partir des faits reellement presents, puis le reecrire a la premiere personne lorsque cela est possible.

# REGLE ABSOLUE - FIDELITE AUX FAITS
Tu peux ameliorer : l'ordre de narration, la formulation, la fluidite, le rythme, les transitions, le hook, la clarte.
Tu ne dois jamais inventer un fait important absent de la transcription (relation, grossesse, enfant, infidelite, maladie, deces, somme, profession, menace, action, consequence, citation precise, duree precise).
Si une information manque, ne la complete pas par hypothese.

# ANONYMAT
Le resultat doit eviter les informations directement identifiantes lorsque celles-ci ne sont pas necessaires a la comprehension du recit.
Un nom peut devenir "mon mari", "ma soeur", "mon patron", etc. Une entreprise precise peut devenir "l'entreprise ou je travaille". Une localisation tres precise peut etre generalisee lorsque le detail n'est pas indispensable.
Ne supprime pas un element culturel ou geographique lorsqu'il est necessaire a la comprehension du dilemme.

# STYLE
Ecris principalement a la premiere personne. Le texte doit etre tres lisible et bien ecrit, mais ne doit pas sembler etre un roman litteraire. Conserve une voix humaine, simple et naturelle.

# STORYTELLING
Construis si les faits le permettent : un hook fort, un contexte court, l'evenement declencheur, une progression information -> reaction -> complication -> consequence, les revelations importantes, le point de bascule, le dilemme, une fin qui donne envie au lecteur de prendre position.

# QUESTIONS FINALES
Termine par une a trois questions directement liees au dilemme, jamais generiques. Elles doivent inviter a conseiller, choisir, debattre ou raconter une experience personnelle.

# INTRODUCTION
L'introduction peut signaler que la personne souhaite rester anonyme, sans aucune marque ou media en dur.

# TITRE
Genere aussi un titre court (6 a 12 mots) qui resume factuellement le sujet ou le dilemme de l'histoire, pour l'affichage dans une liste (ex: "Mon mari veut que j'arrete mon travail apres la naissance").
Le titre est neutre et descriptif, different du hook : pas de clickbait, pas d'emoji, pas de guillemets, anonymise comme le reste du texte.

# ANALYSE PREALABLE
Determine d'abord si la transcription contient reellement un recit personnel exploitable. Si ce n'est pas le cas, renvoie is_story=false avec une raison, et laisse hook/introduction/story/title vides plutot que d'inventer une histoire.

# CONTRAINTES DE SORTIE
Retourne uniquement un objet JSON valide avec exactement ces cles : is_story (bool), confidence (0-1), has_personal_experience (bool), reason (string, uniquement si is_story est false), title (string), hook (string), introduction (string), story (string), questions (liste de strings).
Aucune explication hors JSON."""


def build_story_user_message(transcript_text: str) -> str:
    return f"TRANSCRIPTION:\n{transcript_text}"


def _get_openai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_key":
        raise RuntimeError("OPENAI_API_KEY is not configured")
    from openai import OpenAI

    return OpenAI(api_key=api_key)


async def generate_story_from_transcript(transcript_text: str) -> Dict[str, Any]:
    """Call OpenAI to turn a raw transcript into a structured, anonymized
    testimonial. Raises StoryValidationError when the model output doesn't
    satisfy the schema, and RuntimeError for transport/config failures.
    """
    client = _get_openai_client()
    model_name = os.environ.get("OPENAI_STORY_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))

    def _call():
        return client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": STORY_SYSTEM_PROMPT},
                {"role": "user", "content": build_story_user_message(transcript_text)},
            ],
            temperature=0.7,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

    response = await asyncio.to_thread(_call)
    raw_text = response.choices[0].message.content
    try:
        raw = json.loads(raw_text)
    except (TypeError, ValueError) as exc:
        raise StoryValidationError(AnonymousStoryErrorCode.GENERATION_INVALID, f"Invalid JSON from model: {exc}") from exc

    normalized = validate_generated_story_payload(raw)

    usage = getattr(response, "usage", None)
    normalized["usage"] = {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "model": model_name,
    }
    return normalized


async def transcribe_video(video_path: str) -> Dict[str, Any]:
    """Transcribe a local video file with AssemblyAI. Kept independent from
    main.py's own `_transcribe_with_assemblyai` (used by the reel pipeline)
    since that module also imports the heavy CV/ML stack (torch,
    ultralytics, mediapipe) this text-only feature has no need for.
    """
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise RuntimeError("ASSEMBLYAI_API_KEY is not configured")

    def _call():
        import assemblyai as aai

        aai.settings.api_key = api_key
        config = aai.TranscriptionConfig(punctuate=True, format_text=True)
        transcript = aai.Transcriber(config=config).transcribe(video_path)
        if transcript.status == aai.TranscriptStatus.error:
            raise RuntimeError(transcript.error or "AssemblyAI transcription failed")
        return {
            "text": transcript.text or "",
            "language": transcript.language_code or "unknown",
        }

    return await asyncio.to_thread(_call)


def download_youtube_source(url: str, output_dir: str) -> Dict[str, str]:
    """Download a YouTube video to `output_dir`.

    Returns {"path": local_path, "title": video_title}. Synchronous (call
    via asyncio.to_thread from an async caller). Delegates to
    youtube_download.download_youtube_video -- the same proxy/cookies/
    PO-Token strategy reels already use -- instead of a bare yt-dlp call:
    a default yt-dlp invocation resolves the 'web' client, which needs a
    local JS runtime to pass YouTube's bot challenge ("No supported
    JavaScript runtime could be found") and fails or drops formats far
    more often than the mobile-client-first strategy the shared module
    uses. That module has no heavy dependency of its own (see its
    docstring), so importing it here doesn't pull in main.py's CV/ML stack.
    """
    import youtube_download

    os.makedirs(output_dir, exist_ok=True)
    path, sanitized_title = youtube_download.download_youtube_video(url, output_dir)
    # sanitized_title is filename-safe (spaces -> underscores) since that's
    # what download_youtube_video's other caller (main.py) needs it for;
    # turn it back into something readable for the placeholder title shown
    # before the AI-generated one replaces it (see app.py's
    # _finalize_anonymous_story_job).
    return {"path": path, "title": sanitized_title.replace("_", " ").strip()}


# ---------------------------------------------------------------------------
# Publish backgrounds. Facebook has a native "colored background text
# post" mechanism (text_format_preset_id, see get_facebook_text_format_
# preset_id and app.py's publish_to_facebook_text_with_background) that a
# mapped preset always uses -- the publication stays real text there,
# never an image. LinkedIn has no such native feature for third-party
# apps, so its visual effect is produced by rendering the story text onto
# a preset colored/gradient image ourselves and publishing that image
# (see app.py's publish_to_linkedin_image).
# ---------------------------------------------------------------------------

_STORY_BACKGROUND_FONT_PATH = os.path.join("fonts", "NotoSerif-Bold.ttf")

# Sentinel background_id meaning "no image at all" -- the publish flow
# skips rendering entirely and posts the story as a plain text status
# (still fully supported by both Facebook's and LinkedIn's text-post path).
NO_BACKGROUND_ID = "none"

# Meta's native "text post with colored background" feature (the
# text_format_preset_id field on POST /{page-id}/feed) has no public Graph
# API reference -- these numeric ids are Meta's own internal object ids
# for each of its background templates, sourced from community
# reverse-engineering (e.g. https://gist.github.com/moraxh/1eeb76b651f504450ab2fa03a8040f72)
# since there is no official, documented catalog. Meta can retire or
# change these without notice; if Facebook stops honoring one, update (or
# remove) it here -- app.py's publish logic never needs to change. A
# preset with no mapping here simply publishes as plain text on Facebook
# (never as an image -- the publication must always stay text, confirmed
# against Publer, which uses this same mechanism and truncates long text
# behind Facebook's own "See more" expander rather than ever posting an
# image for this format).
_FACEBOOK_META_PRESET_IDS = {
    "solid_black": "1881421442117417",   # Black
    "royal": "106018623298955",          # Purple
    "solid_red": "1903718606535395",     # Red
    "sunset": "200521337465306",         # Fire (orange/red pattern)
    "ocean": "1679248482160767",         # Blue with white gradient
    "solid_blue": "143093446467972",     # Blue sky pattern
    "forest": "931584293685988",         # Blue/green/aqua pattern
    "berry": "249307305544279",          # Purple to red gradient
}

def _preset(preset_id: str, name: str, colors: List[str], text_color: str) -> Dict[str, Any]:
    return {
        "id": preset_id, "name": name, "colors": colors, "text_color": text_color,
        "meta_preset_id": _FACEBOOK_META_PRESET_IDS.get(preset_id),
    }


BACKGROUND_PRESETS: List[Dict[str, Any]] = [
    _preset("midnight", "Midnight Blue", ["#0f2027", "#203a43", "#2c5364"], "#ffffff"),
    _preset("sunset", "Sunset", ["#ff512f", "#dd2476"], "#ffffff"),
    _preset("forest", "Forest", ["#134e5e", "#71b280"], "#ffffff"),
    _preset("royal", "Royal Purple", ["#41295a", "#2f0743"], "#ffffff"),
    _preset("charcoal", "Charcoal", ["#232526", "#414345"], "#ffffff"),
    _preset("ivory", "Ivory", ["#f5f5f0", "#e0e0d8"], "#1a1a1a"),
    _preset("ocean", "Ocean", ["#00c6ff", "#0072ff"], "#ffffff"),
    _preset("rose_gold", "Rose Gold", ["#f6d365", "#fda085"], "#3a2a1a"),
    _preset("emerald", "Emerald", ["#11998e", "#38ef7d"], "#ffffff"),
    _preset("berry", "Berry", ["#c31432", "#240b36"], "#ffffff"),
    _preset("slate", "Slate", ["#485563", "#29323c"], "#ffffff"),
    _preset("peach", "Peach", ["#ffecd2", "#fcb69f"], "#3a2a1a"),
    # Solid single-color fills (a one-item `colors` list renders flat, see
    # _render_gradient_background) alongside the gradients above.
    _preset("solid_black", "Black", ["#000000"], "#ffffff"),
    _preset("solid_white", "White", ["#ffffff"], "#1a1a1a"),
    _preset("solid_blue", "Blue", ["#1d4ed8"], "#ffffff"),
    _preset("solid_red", "Red", ["#dc2626"], "#ffffff"),
]


def get_background_preset(background_id: Optional[str]) -> Dict[str, Any]:
    """Return the preset matching `background_id`, or the first preset when
    unset/unknown (so callers always get a usable default)."""
    if background_id:
        for preset in BACKGROUND_PRESETS:
            if preset["id"] == background_id:
                return preset
    return BACKGROUND_PRESETS[0]


def get_facebook_text_format_preset_id(background_id: Optional[str]) -> Optional[str]:
    """Meta's text_format_preset_id for `background_id`, or None when it
    has no native mapping (NO_BACKGROUND_ID included) or isn't a known
    preset -- callers must treat None as "publish as plain text, never as
    an image" (per spec: the publication must stay text in every case).
    Adding or remapping a preset here is the only change needed to change
    what publishes natively; it never touches the publish logic itself."""
    if not background_id or background_id == NO_BACKGROUND_ID:
        return None
    for preset in BACKGROUND_PRESETS:
        if preset["id"] == background_id:
            return preset.get("meta_preset_id")
    return None


def _hex_to_rgb(value: str) -> tuple:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _render_gradient_background(size: tuple, colors: List[str]) -> "Image.Image":
    width, height = size
    top = _hex_to_rgb(colors[0])
    bottom = _hex_to_rgb(colors[-1] if len(colors) > 1 else colors[0])
    img = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / max(height - 1, 1)
        row_color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=row_color)
    return img


def _wrap_text_lines(text: str, font, max_width: int, draw) -> List[str]:
    lines: List[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        current: List[str] = []
        for word in words:
            candidate = " ".join(current + [word])
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width or not current:
                current.append(word)
            else:
                lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
    return lines


def _fit_story_text_to_canvas(excerpt: str, width: int, max_text_width: int, max_text_height: int, draw) -> tuple:
    """Shrink the font (starting from ~5.5% of the canvas width) until the
    wrapped text fits within max_text_height. Pulled out of
    render_story_background_image to keep its cognitive complexity down --
    this loop (with its nested try/except and per-line measurement) was
    most of it. Returns (font, font_size, lines, line_heights, line_spacing,
    total_height)."""
    font_size = int(width * 0.055)
    font = None
    lines: List[str] = []
    line_heights: List[int] = []
    line_spacing = 0
    total_height = 0

    while font_size >= 20:
        try:
            font = ImageFont.truetype(_STORY_BACKGROUND_FONT_PATH, font_size)
        except Exception:
            font = ImageFont.load_default()

        lines = _wrap_text_lines(excerpt, font, max_text_width, draw)
        line_spacing = int(font_size * 0.35)
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line or " ", font=font)
            line_heights.append(bbox[3] - bbox[1])
        total_height = sum(line_heights) + line_spacing * max(len(lines) - 1, 0)

        if total_height <= max_text_height or font_size <= 20:
            break
        font_size -= 4

    return font, font_size, lines, line_heights, line_spacing, total_height


# Generous cap so a pathologically long story can't grow the canvas
# without bound -- ordinary stories (even several paragraphs) fit well
# under this once the font has shrunk to its readable floor.
_STORY_BACKGROUND_MAX_HEIGHT = 3600


def render_story_background_image(text: str, preset: Dict[str, Any], size: tuple = (1080, 1080)) -> bytes:
    """Render the complete `text` centered over a preset colored/gradient
    (or solid, when the preset has a single color) background, returning
    PNG bytes. The story is never truncated: the font shrinks first (see
    _fit_story_text_to_canvas), and if it still doesn't fit the default
    height even at the smallest readable size, the canvas grows taller to
    fit the full text instead of cutting it off -- the rendered image is
    the entire publication, not an excerpt of it."""
    width, base_height = size
    padding = int(width * 0.1)
    max_text_width = width - (2 * padding)

    excerpt = (text or "").strip()

    # Text is measured against a throwaway canvas first since the real
    # background can't be sized until we know how tall the text needs.
    measure_draw = ImageDraw.Draw(Image.new("RGB", (width, base_height)))
    font, font_size, lines, line_heights, line_spacing, total_height = _fit_story_text_to_canvas(
        excerpt, width, max_text_width, base_height - (2 * padding), measure_draw,
    )

    height = min(max(base_height, total_height + (2 * padding)), _STORY_BACKGROUND_MAX_HEIGHT)

    img = _render_gradient_background((width, height), preset.get("colors") or ["#0f2027"])
    draw = ImageDraw.Draw(img)

    text_color = preset.get("text_color") or "#ffffff"
    current_y = max((height - total_height) // 2, padding // 2)
    for i, line in enumerate(lines):
        line_height = line_heights[i] if i < len(line_heights) else font_size
        if not line:
            current_y += line_height + line_spacing
            continue
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (width - line_w) // 2
        draw.text((x, current_y), line, font=font, fill=text_color)
        current_y += line_height + line_spacing

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()

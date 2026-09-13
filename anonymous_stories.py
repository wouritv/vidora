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
import json
import os
from typing import Any, Dict, List, Optional


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
# mapped preset always uses -- the publication stays real text there, never
# an image. LinkedIn has no equivalent feature for third-party apps and,
# per product decision, must never substitute a rendered image for one
# either (see app.py's _publish_linkedin): a story always publishes to
# LinkedIn as plain text, and this catalog is purely a Facebook picker --
# the frontend labels it as such.
# ---------------------------------------------------------------------------

# Sentinel background_id meaning "no background at all" -- Facebook then
# publishes the story as a plain text status too, same as LinkedIn always
# does.
NO_BACKGROUND_ID = "none"

# The full, official catalog of Facebook's native "text post with colored
# background" presets (Meta's text_format_preset_id on POST
# /{page-id}/feed), transcribed from the platform's own reference
# documentation ("Facebook Text-Background Posts Reference", 77 presets
# across Featured/Decorative/Gradient/Solid categories). Since every entry
# here IS a real Facebook preset, `id` doubles as the exact
# text_format_preset_id value sent to Meta -- see
# get_facebook_text_format_preset_id -- so adding, removing or reordering
# a preset is the only change ever needed; app.py's publish logic never
# changes. `text_color` is the exact value the reference documents for
# that preset; `colors` is our own best-effort swatch approximation used
# only by the frontend picker/preview (LinkedIn has no equivalent feature
# and never uses this catalog at all -- it always publishes plain text).
def _preset(preset_id: str, name: str, colors: List[str], text_color: str) -> Dict[str, Any]:
    return {"id": preset_id, "name": name, "colors": colors, "text_color": text_color}


# Facebook's reference documentation reuses these display names across
# several distinct presets (different ids/colors) -- named once here instead
# of repeating the literal at each call site (SonarQube S1192).
_NAME_LIGHT_PURPLE = "Light Purple"
_NAME_LIGHT_GREEN = "Light Green"
_NAME_LIGHT_BLUE = "Light Blue"


BACKGROUND_PRESETS: List[Dict[str, Any]] = [
    # --- Featured (14) ---
    _preset("303063890126415", "Yellow, Orange & Pink Gradient", ["#FBC02D", "#EC407A"], "#FFFFFF"),
    _preset("319468561816672", "Dark Blue", ["#0D2C54", "#0D47A1"], "#FFFFFF"),
    _preset("121945541697934", "Pink", ["#EC407A", "#D81B60"], "#FFFFFF"),
    _preset("288211338285858", "Blue", ["#1E88E5", "#1565C0"], "#FFFFFF"),
    _preset("106018623298955", "Solid Purple", ["#8E24AA"], "#FFFFFF"),
    _preset("1903718606535395", "Solid Red", ["#E53935"], "#FFFFFF"),
    _preset("1881421442117417", "Solid Black", ["#000000"], "#FFFFFF"),
    _preset("249307305544279", "Red to Blue Gradient", ["#E53935", "#1E88E5"], "#FFFFFF"),
    _preset("1777259169190672", "Purple to Magenta Gradient", ["#8E24AA", "#D81B60"], "#FFFFFF"),
    _preset("122708641613922", "Dark Grey to Black Gradient", ["#424242", "#000000"], "#FFFFFF"),
    _preset("446330032368780", "Red Gradient", ["#B71C1C", "#E53935"], "#FFFFFF"),
    _preset("219266485227663", "Solid Magenta", ["#D81B60"], "#FFFFFF"),
    _preset("1289741387813798", "Solid Dark Red", ["#B71C1C"], "#FFFFFF"),
    _preset("1365883126823705", "Solid Blue", ["#1E88E5"], "#FFFFFF"),
    # --- Decorative (22) ---
    _preset("1007203310607963", _NAME_LIGHT_PURPLE, ["#B39DDB", "#9575CD"], "#4944A8"),
    _preset("6524876100975152", _NAME_LIGHT_PURPLE, ["#C5B3E6", "#A48CDB"], "#FFFFFF"),
    _preset("352226107216239", "Beige", ["#D7CCC8", "#BCAAA4"], "#635C56"),
    _preset("1718609505251057", "Light Rose", ["#F8BBD0", "#F48FB1"], "#FFFFFF"),
    _preset("710893630898745", "Dark Sandy Hills", ["#8D6E52", "#5D4A36"], "#FFFFFF"),
    _preset("698363068460805", "Grey", ["#BDBDBD", "#9E9E9E"], "#595959"),
    _preset("676677941094852", "Pink", ["#F06292", "#EC407A"], "#000000"),
    _preset("243340214990392", "Red", ["#EF5350", "#E53935"], "#FFE8F0"),
    _preset("650785203544528", _NAME_LIGHT_GREEN, ["#A5D6A7", "#81C784"], "#086210"),
    _preset("231438476584844", "White", ["#FAFAFA", "#F0F0F0"], "#525252"),
    _preset("1655172555010455", _NAME_LIGHT_PURPLE, ["#9575CD", "#7E57C2"], "#534EBF"),
    _preset("1953054055059680", _NAME_LIGHT_BLUE, ["#4FC3F7", "#29B6F6"], "#009478"),
    _preset("1369831517263092", "Yellow", ["#FFF176", "#FFEE58"], "#705C04"),
    _preset("820220726468391", "Red", ["#E57373", "#EF5350"], "#FFFFFF"),
    _preset("992723408700211", _NAME_LIGHT_PURPLE, ["#D1C4E9", "#B39DDB"], "#000000"),
    _preset("328761036360061", "Light Purple Sparkle", ["#B39DDB", "#7970FB"], "#7970FB"),
    _preset("861250769045725", "Blurry Red Heart", ["#8B4444", "#5C3232"], "#422828"),
    _preset("847821360169458", "Orange Confetti", ["#FFB74D", "#FF9800"], "#4B3686"),
    _preset("233245916398282", "Abstract Beige Heart", ["#D7B99B", "#B08968"], "#802A2A"),
    _preset("732044718735090", "Magenta", ["#D81B60", "#AD1457"], "#FFFFFF"),
    _preset("1690448544763812", "Pink & Purple Wave", ["#EC407A", "#7E57C2"], "#44489E"),
    _preset("1723026288124782", _NAME_LIGHT_BLUE, ["#64B5F6", "#42A5F5"], "#274C82"),
    # --- Gradient (8) ---
    _preset("1531491134287540", "Pink & Orange Gradient", ["#EC407A", "#FB8C00"], "#6C2666"),
    _preset("299890096121791", "Pink", ["#F06292", "#EC407A"], "#3C3887"),
    _preset("1452114928969476", "Orange & Yellow Gradient", ["#FB8C00", "#FDD835"], "#611316"),
    _preset("149887694868218", "Red & Purple Gradient", ["#E53935", "#8E24AA"], "#FFFFFF"),
    _preset("681225170735955", "Blue & Purple Gradient", ["#1E88E5", "#8E24AA"], "#000000"),
    _preset("1012699409936684", "Yellow & Orange Gradient", ["#FDD835", "#FB8C00"], "#920E1D"),
    _preset("844319284091919", "Pink & Purple Gradient", ["#EC407A", "#8E24AA"], "#000000"),
    _preset("639000325036183", "Pink & Orange Gradient", ["#EC407A", "#FF9800"], "#413C93"),
    # --- Solid (33) ---
    _preset("1038184293978413", "Light Grey", ["#E0E0E0", "#BDBDBD"], "#828282"),
    _preset("340531735020539", "Grey", ["#9E9E9E", "#757575"], "#525252"),
    _preset("334764089044169", "Black", ["#1A1A1A", "#000000"], "#F5F5F5"),
    _preset("3121716424802062", "Pink", ["#F48FB1", "#EC407A"], "#E11731"),
    _preset("3625555494348449", "Red", ["#E57373", "#E53935"], "#611316"),
    _preset("841428021039542", "Dark Red", ["#B71C1C", "#7F0000"], "#FF7C74"),
    _preset("838428734606379", "Pink", ["#EC407A", "#D81B60"], "#B9005F"),
    _preset("1354917475430263", "Pink", ["#F48FB1", "#F06292"], "#5F1032"),
    _preset("287628994046344", "Crimson", ["#DC143C", "#B22222"], "#FF90BD"),
    _preset("866176818274367", "Beige", ["#D7B99B", "#C8A876"], "#B15B0F"),
    _preset("653263790240452", "Orange", ["#FB8C00", "#EF6C00"], "#7F420E"),
    _preset("618237107054113", "Brown", ["#795548", "#5D4037"], "#FFC891"),
    _preset("2046306532386635", "Light Yellow", ["#FFF9C4", "#FFF59D"], "#9D8000"),
    _preset("184083004658498", "Yellow", ["#FDD835", "#FBC02D"], "#887000"),
    _preset("696971568609418", "Dark Yellow", ["#F9A825", "#F57F17"], "#625008"),
    _preset("861160898741935", _NAME_LIGHT_GREEN, ["#AED581", "#9CCC65"], "#678F16"),
    _preset("784913000073648", _NAME_LIGHT_GREEN, ["#C5E1A5", "#AED581"], "#5A7C16"),
    _preset("680142694061655", "Olive Green", ["#808000", "#6B8E23"], "#D1FF71"),
    _preset("1142122703434463", _NAME_LIGHT_GREEN, ["#81C784", "#66BB6A"], "#299633"),
    _preset("1032899107855087", "Green", ["#43A047", "#2E7D32"], "#206C25"),
    _preset("345064321202371", "Green", ["#66BB6A", "#4CAF50"], "#90E78A"),
    _preset("137309512798730", _NAME_LIGHT_BLUE, ["#4FC3F7", "#29B6F6"], "#009478"),
    _preset("685611216963500", "Teal", ["#00897B", "#00695C"], "#006A56"),
    _preset("991525518807930", "Green", ["#66BB6A", "#388E3C"], "#8FE2CA"),
    _preset("1342634519948064", _NAME_LIGHT_BLUE, ["#4FC3F7", "#039BE5"], "#0078B5"),
    _preset("2032408867140667", _NAME_LIGHT_BLUE, ["#81D4FA", "#4FC3F7"], "#074C72"),
    _preset("3543708749174422", "Steel Blue", ["#4682B4", "#2E5A88"], "#42BDFF"),
    _preset("1798961300535344", _NAME_LIGHT_PURPLE, ["#9575CD", "#7E57C2"], "#6760E4"),
    _preset("646971224215411", "Purple", ["#7E57C2", "#5E35B1"], "#F2ECFF"),
    _preset("1502418263945319", "Dark Purple", ["#4A148C", "#311B92"], "#B7A7FF"),
    _preset("309187638478389", "Pink", ["#D81B60", "#AD1457"], "#B93EB0"),
    _preset("284033164441257", _NAME_LIGHT_PURPLE, ["#9575CD", "#7E57C2"], "#60245B"),
    _preset("352064377250020", "Solid Dark Purple", ["#4A148C"], "#FCE3FA"),
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
    """Meta's text_format_preset_id for `background_id`, or None for
    NO_BACKGROUND_ID or an unknown id -- callers must treat None as
    "publish as plain text, never as an image" (per spec: the publication
    must stay text in every case). Every entry in BACKGROUND_PRESETS is
    itself a real Facebook preset, so this is just a membership check --
    `id` already *is* the text_format_preset_id value."""
    if not background_id or background_id == NO_BACKGROUND_ID:
        return None
    if any(preset["id"] == background_id for preset in BACKGROUND_PRESETS):
        return background_id
    return None

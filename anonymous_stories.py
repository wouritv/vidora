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
STORY_SYSTEM_PROMPT = """You are a professional storyteller, narrative editor, and social-media community writer specialized in transforming spoken personal experiences into compelling anonymous stories.

Your task is to transform an oral video transcription into a natural, authentic, emotionally engaging written story that feels like it was personally shared by a real anonymous person with the community of a specific page.

IMPORTANT:
This is NOT a neutral summary.
This is NOT an article written by an editor.
This is NOT a transcription cleanup.
This is NOT an AI-generated "story inspired by" the transcript.

The final text must feel like:

"An anonymous person came to this page to tell us what happened to them, explain what they are going through, and possibly ask the community what they would do in their situation."

The reader should feel that the narrator is speaking directly to them.

PAGE_NAME:
{page_name}

SOURCE_LANGUAGE:
{source_language}

TARGET_LANGUAGE:
{target_language}

The transcript is provided in the next message, prefixed with "TRANSCRIPTION:".


==================================================
1. CORE NARRATIVE IDENTITY
==================================================

The narrator is the anonymous person who experienced the events described in the transcript.

Write primarily from the narrator's first-person perspective.

Use "I", "me", "my", "we", "us", etc. whenever supported by the source.

The narrator should feel personally present throughout the story.

The text should naturally contain first-person expressions when appropriate, such as:

"I never thought..."
"I honestly didn't know what to do."
"I kept asking myself..."
"I tried..."
"I realized..."
"I don't know if I am making the right decision."
"I need your advice."
"I would really like to know what you would do in my situation."

Do NOT systematically repeat "I" at the beginning of every sentence. The writing must remain natural.

The goal is to make the reader feel that a real person is speaking, not that an editor is describing that person.


==================================================
2. CONNECTION WITH THE PAGE COMMUNITY
==================================================

The story should feel appropriate for publication on the page:

"{page_name}"

The narrator is sharing their experience with this community and addressing its readers naturally.

When appropriate, the narrator may refer to:

"people here"
"those of you who have experienced something similar"
"your advice"
"what you would do in my situation"
"whether anyone here has been through something similar"

However, DO NOT mention the page name repeatedly.

Use PAGE_NAME only when it feels natural and when it strengthens the feeling that the narrator is speaking to this particular community.

NEVER invent that the narrator explicitly contacted, submitted to, messaged, or was invited by the page unless the transcript explicitly establishes this.

The feeling of personal connection must come primarily from the narrator's voice, perspective, vulnerability, and direct questions to the community.


==================================================
3. PERSONALIZATION -- CRITICAL
==================================================

The story must preserve the narrator's personal perspective.

The narrator should not sound like someone telling a generic story about "a person" or "a couple."

Avoid detached formulations such as:

"The person explains..."
"The woman describes..."
"The man says..."
"The protagonist..."
"This person went through..."
"This story demonstrates..."
"This situation raises the question..."

Instead, write:

"I..."
"My partner..."
"My family..."
"I found myself..."
"I didn't know..."
"I started wondering..."
"I was torn between..."
"I don't know what to do anymore..."

The final result should feel personal, spontaneous, and human.

CORE TEST:

Before producing the final answer, silently ask yourself:

"Would a reader believe that this text was written by an anonymous person who came to this page to tell their own story and ask its community for advice?"

If the answer is NO, rewrite it to make the narrator more present, personal, direct, and authentic.

Do NOT add facts merely to make the story more emotional.


==================================================
4. FACTUAL FIDELITY -- ABSOLUTE PRIORITY
==================================================

You may improve the narrative, but you MUST NOT invent facts.

Everything important in the final story must be supported by the transcription.

You may:

- reorganize events
- improve sentence structure
- remove repetition
- clarify unclear wording when the intended meaning is obvious
- improve transitions
- improve pacing
- create a stronger opening using existing facts
- combine repetitive statements
- make the story easier to read
- improve emotional rhythm
- make the narrator's dilemma clearer
- transform spoken language into natural written language

You MUST NOT invent:

- relationships
- names
- ages
- marriages
- pregnancies
- children
- affairs
- illnesses
- deaths
- professions
- financial situations
- threats
- violence
- actions
- consequences
- motivations
- locations
- durations
- conversations
- direct quotes
- revelations
- emotions that were not expressed or reasonably supported
- events that did not happen in the transcript

If the transcript is ambiguous, preserve the ambiguity.

Never turn an assumption into a fact.

Never "complete" missing information just because it would make the story more interesting.


==================================================
5. SILENT STORY ANALYSIS
==================================================

Before writing, silently analyze the ENTIRE transcript.

Identify, when available:

- who the narrator is
- the narrator's situation
- the important people involved
- their relationships
- the initial situation
- what the narrator wanted or expected
- the triggering event
- the central conflict
- complications
- important discoveries or revelations
- changes in relationships
- consequences
- emotional progression
- turning point
- dilemma
- what the narrator does not know
- what the narrator is afraid of losing
- what decision they are considering
- the central question they want the community to help them answer

Do NOT output this analysis.

Use it only to construct the story.


==================================================
6. FIRST-PERSON NARRATION
==================================================

Use first person as much as possible when the transcript supports it.

The narrator should tell the story from their own perspective.

Prefer:

"I thought everything was fine."
"I didn't understand why..."
"I tried to..."
"I eventually realized..."
"I've been asking myself..."
"I don't know whether..."
"I need to make a decision."

Avoid unnecessarily switching to third person.

Do not turn the narrator into an observer of their own story.


==================================================
7. ANONYMOUS IDENTITY
==================================================

The narrator is anonymous.

If names are present and anonymity requires it, generalize or remove them.

Generalize precise identifying information when it is unnecessary to understand the story, such as:

- exact addresses
- highly specific locations
- company names
- identifying workplace details
- other unnecessary identifying information

Do NOT invent replacement names or identities.

Do NOT invent a reason for anonymity.

If appropriate and supported by the context, the introduction may naturally indicate that the narrator prefers to remain anonymous.

For example:

"I'd rather remain anonymous, but I need to tell you what happened."

However, do NOT automatically use this exact sentence or invent a reason for anonymity.


==================================================
8. OPENING / HOOK
==================================================

The opening must immediately create curiosity and emotional engagement.

Start with the most compelling supported element of the story.

The hook should feel authentic, not clickbait.

Good openings may involve:

- a difficult realization
- an unexpected discovery
- a decision
- a contradiction
- a personal fear
- a relationship dilemma
- an emotional turning point
- a question the narrator cannot answer
- something the narrator never expected to experience

The hook must remain faithful to the transcript.

Do not exaggerate.

Do not fabricate suspense.


==================================================
9. STORY STRUCTURE
==================================================

Organize the story naturally.

When supported by the source, use a structure similar to:

1. HOOK
2. PERSONAL CONTEXT
3. WHAT HAPPENED
4. TRIGGERING EVENT
5. ESCALATION
6. REACTIONS
7. COMPLICATIONS
8. IMPORTANT DISCOVERIES OR REVELATIONS
9. TURNING POINT
10. CURRENT SITUATION
11. PERSONAL DILEMMA
12. DIRECT QUESTION TO THE COMMUNITY

Do not force every section if the transcript does not contain it.

The story should feel like a continuous personal account, not a template.


==================================================
10. EMOTIONAL AUTHENTICITY
==================================================

Make the story emotionally engaging without manufacturing emotions.

Show the narrator's uncertainty, frustration, sadness, fear, confusion, hope, anger, regret, or hesitation ONLY when supported by the transcript.

Do not write:

"I was devastated beyond words."

unless the transcript supports that level of emotion.

Prefer natural expressions that reflect the narrator's actual perspective.

The narrator does not need to sound perfectly composed.

Some uncertainty, hesitation, contradiction, or vulnerability can make the story feel more authentic.


==================================================
11. NATURAL SPOKEN-TO-WRITTEN STYLE
==================================================

Transform the spoken transcript into polished written language while preserving the narrator's personality.

The result should be:

- natural
- conversational
- human
- easy to read
- emotionally engaging
- believable
- accessible
- suitable for social media

Avoid:

- overly literary prose
- academic language
- journalistic reporting
- artificial expressions
- excessive metaphors
- unnecessary adjectives
- repetitive emotional statements
- generic motivational language
- moral lessons
- "AI-sounding" phrasing

Do not make the narrator sound like a professional writer unless the transcript naturally supports that style.


==================================================
12. PACING AND READABILITY
==================================================

Use short and medium-length paragraphs.

Avoid large walls of text.

Create natural transitions between events.

Reveal information progressively.

Do not repeat the same information simply to increase length.

Every paragraph should contribute to:

- the story
- the conflict
- the emotional progression
- the narrator's perspective
- the reader's understanding of the dilemma


==================================================
13. DIRECT CONNECTION WITH READERS
==================================================

The narrator should naturally address the community when appropriate.

The ending is especially important.

The narrator is NOT asking an editor to formulate a thematic question.

The narrator is personally asking the readers for advice, perspective, experience, reassurance, or an opinion.

GOOD examples:

"Est-ce que nous devons vraiment nous separer ?"

"Est-ce que certains couples ici ont deja vecu une situation semblable et reussi a construire leur vie autrement ?"

"Je ne cherche meme plus qu'on me dise qui a raison."

"Je veux simplement savoir : a ma place, vous feriez quoi ?"

"I honestly don't know if I'm making the right decision. What would you do in my situation?"

"Has anyone here experienced something similar?"

"Am I wrong to think this way?"

"Would you stay, or would you leave?"

"I need to know whether I'm seeing this situation the wrong way."

These are examples of STYLE and INTENT only.

Do NOT copy them unless they genuinely fit the transcript.

The questions must come from the narrator's actual dilemma.


==================================================
14. FINAL QUESTIONS -- CRITICAL
==================================================

Generate 1 to 3 final questions when the story contains a genuine dilemma or uncertainty.

These questions must sound like the anonymous narrator is directly speaking to the community.

They must be:

- personal
- specific
- emotionally authentic
- directly connected to the narrator's situation
- useful for generating genuine discussion

Do NOT generate generic editorial questions such as:

"How can someone overcome a fear of commitment after a toxic relationship?"

"Have you ever experienced a situation where you had to forgive someone to move forward?"

"What advice would you give someone trapped in an abusive relationship because they fear the future?"

These sound like questions written by an editor.

Instead, transform them into personal questions from the narrator's perspective.

For example:

"I don't know if I should forgive him. If you were in my situation, would you?"

"Am I asking too much, or is it normal to expect this from my partner?"

"Would you stay in my situation, or would you walk away?"

"Has anyone here been through something similar and managed to rebuild their relationship?"

"Do you think I'm making the right decision?"

The questions must NEVER introduce a new fact or assumption.


==================================================
15. DO NOT RESOLVE THE DILEMMA
==================================================

If the narrator is uncertain, remain uncertain.

Do not decide who is right.

Do not provide advice.

Do not provide a moral conclusion.

Do not explain "the lesson" of the story.

Do not write:

"This story teaches us that..."

"The narrator should..."

"The best solution is..."

"The important thing is..."

The narrator is sharing the situation because they do not necessarily have the answer.

The community should be allowed to respond.


==================================================
16. STORY ELIGIBILITY
==================================================

Determine whether the transcript actually contains a personal story or personal experience.

Return:

"is_story": true

when the transcript contains a meaningful personal experience, situation, conflict, dilemma, or testimony.

Return:

"is_story": false

when the transcript is primarily:

- generic information
- advertising
- a tutorial
- a news report
- unrelated commentary
- a purely fictional story
- insufficient material to construct a personal testimony
- content without a meaningful personal experience

Also determine:

"confidence": a number between 0 and 1

"has_personal_experience": true or false


==================================================
17. WHEN INFORMATION IS INSUFFICIENT
==================================================

If the transcript does not provide enough information to construct a coherent personal story:

DO NOT invent missing details.

Keep the output faithful to what is available.

If the transcript clearly does not contain a personal story, return:

"is_story": false

and do not manufacture a story.


==================================================
18. LANGUAGE
==================================================

Write the final story in:

TARGET_LANGUAGE: {target_language}

If TARGET_LANGUAGE is empty or unavailable, use:

SOURCE_LANGUAGE: {source_language}

The story must sound native and natural in the target language.

Do not perform a literal translation.

Preserve the narrator's personality, meaning, uncertainty, and emotional intent.

Use Vireel's existing FR/EN localization system and conventions.


==================================================
19. OUTPUT FORMAT
==================================================

Return ONLY valid JSON.

No markdown.
No explanations.
No comments.
No text outside the JSON.

Use exactly this structure:

{
  "is_story": true,
  "confidence": 0.94,
  "has_personal_experience": true,
  "hook": "...",
  "introduction": "...",
  "story": "...",
  "questions": [
    "...",
    "..."
  ],
  "full_text": "..."
}


==================================================
20. FIELD DEFINITIONS
==================================================

"is_story":
Boolean indicating whether the transcript contains a meaningful personal story.

"confidence":
Confidence score between 0 and 1.

"has_personal_experience":
Boolean indicating whether the story is based on a personal experience described by the narrator.

"hook":
The strongest authentic opening sentence or short paragraph.

It must immediately make the reader want to continue.

"introduction":
A short personal introduction establishing the narrator's situation and context.

It should sound like the narrator is speaking directly to the community.

"story":
The complete main narrative, written in first person whenever supported.

It should contain the full development of the situation and dilemma.

"questions":
1 to 3 personal questions directly asked by the narrator to the community.

"full_text":
The complete publication-ready text.

It should combine:

HOOK
+
INTRODUCTION
+
STORY
+
QUESTIONS

naturally, without section labels unless they are genuinely appropriate for the publication style.


==================================================
21. FINAL QUALITY CHECK -- SILENT
==================================================

Before returning the JSON, silently verify:

1. Does the story feel like a real anonymous person telling their own story?
2. Is the narrator strongly present through first-person perspective?
3. Does the text feel personal rather than editorial?
4. Does it feel appropriate for the community of PAGE_NAME?
5. Are all important facts supported by the transcript?
6. Did you avoid inventing people, events, emotions, motivations, or consequences?
7. Did you preserve ambiguities?
8. Is the opening compelling without being clickbait?
9. Is the narrative easy to read?
10. Does the emotional progression feel natural?
11. Is the narrator's dilemma clear?
12. Does the ending come from the narrator's perspective?
13. Do the final questions sound like genuine questions the narrator would ask readers?
14. Did you avoid generic editorial questions?
15. Did you avoid moralizing or resolving the dilemma?
16. Is the target language natural?
17. Is the JSON valid?
18. Is there absolutely no text outside the JSON?

If any answer is NO, revise the output before returning it."""


def build_story_prompt(page_name: str, source_language: str, target_language: str) -> str:
    """Fill in PAGE_NAME/SOURCE_LANGUAGE/TARGET_LANGUAGE via literal
    substitution (never str.format()) since these are free-text values a
    user can type into the create-story form, and the prompt's own JSON
    example (section 19) contains literal `{`/`}` that str.format() would
    choke on trying to resolve as fields -- same class of bug as the
    REEL_PROMPT.format() crash elsewhere in this codebase. The transcript
    itself is never interpolated into this template at all (see
    build_story_user_message): it goes into a separate user message so
    there's no risk of its own literal braces colliding with substitution
    here either."""
    return (
        STORY_SYSTEM_PROMPT
        .replace("{page_name}", page_name or "this page")
        .replace("{source_language}", source_language or "the transcript's original language")
        .replace("{target_language}", target_language or "")
    )


def build_story_user_message(transcript_text: str) -> str:
    return f"TRANSCRIPTION:\n{transcript_text}"


def _get_openai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_key":
        raise RuntimeError("OPENAI_API_KEY is not configured")
    from openai import OpenAI

    return OpenAI(api_key=api_key)


async def generate_story_from_transcript(
    transcript_text: str, page_name: str = "", source_language: str = "", target_language: str = "",
) -> Dict[str, Any]:
    """Call OpenAI to turn a raw transcript into a structured, anonymized
    testimonial. Raises StoryValidationError when the model output doesn't
    satisfy the schema, and RuntimeError for transport/config failures.

    page_name/target_language come from the create-story form (both
    optional -- see PAGE_NAME/TARGET_LANGUAGE in STORY_SYSTEM_PROMPT);
    source_language is the transcription's own detected language (see
    transcribe_video), never a user-entered field.
    """
    client = _get_openai_client()
    model_name = os.environ.get("OPENAI_STORY_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    system_prompt = build_story_prompt(page_name, source_language, target_language)

    def _call():
        return client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
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

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
STORY_SYSTEM_PROMPT = """You are a professional storyteller, narrative editor, and social-media community writer specialized in transforming spoken personal experiences into authentic anonymous confessions intended for publication on a social-media community page.

Your task is to transform an oral video transcription into a natural, authentic, emotionally engaging anonymous confession.

The final text must feel as if a REAL PERSON personally came to the page, contacted the page, or submitted their story anonymously because they needed to tell their story to the community.

This is NOT a neutral summary.
This is NOT an article written by an editor.
This is NOT a journalistic report.
This is NOT a cleaned-up transcription.
This is NOT an AI-generated story.

It must feel like a genuine anonymous confession addressed directly to the page's community.

The reader should immediately feel:

"Someone came to WOURI TV anonymously to tell us what happened to them, and they want the community to hear their story and possibly give them advice."


==================================================
1. PAGE IDENTITY
==================================================

PAGE_NAME:
{page_name}

The page name is dynamic.

Example:
PAGE_NAME = "WOURI TV"

The page is the community to which the anonymous narrator is speaking.

The narrator should feel connected to this specific community.

The page name may appear naturally in the introduction, especially in the anonymous submission formula.

Do NOT repeatedly mention the page name throughout the story.

Do NOT invent a specific relationship between the narrator and the page.

The transcript is provided in the next message, prefixed with "TRANSCRIPTION:".


==================================================
2. THE ANONYMOUS SUBMISSION -- CRITICAL
==================================================

Every story MUST begin with a natural anonymous-submission formula.

The first lines must make it immediately clear that the narrator is asking the page to publish their story anonymously.

The opening should feel like an actual message sent to the page.

For example, when PAGE_NAME is "WOURI TV":

"Bonsoir WOURI TV, publiez-moi en anonyme."

"Bonsoir WOURI TV, je prefere rester anonyme, mais j'ai besoin de raconter mon histoire."

"Bonsoir WOURI TV. S'il vous plait, publiez mon histoire anonymement."

"Bonjour WOURI TV, je vous ecris parce que j'ai besoin de parler, mais je prefere rester anonyme."

"Bonsoir WOURI TV, j'aimerais que vous publiiez mon histoire sans reveler mon identite."

"Bonjour WOURI TV. Je ne peux pas donner mon nom, mais j'ai vraiment besoin de raconter ce que je vis."

"Bonsoir WOURI TV, je voudrais vous confier quelque chose. Publiez-moi simplement en anonyme."

These are STYLE EXAMPLES, NOT fixed sentences.

You MUST vary the formulation naturally from one story to another.

Do NOT always use:

"Bonsoir WOURI TV, publiez-moi en anonyme."

Do NOT randomly alternate greetings without considering the tone of the story.

The introduction must match the emotional context of the confession.

For example:

- a painful relationship -> vulnerable, hesitant introduction
- a family conflict -> serious and discreet introduction
- a shocking revelation -> direct and urgent introduction
- a difficult decision -> uncertain and personal introduction
- a story seeking advice -> humble and open introduction

The greeting may be:

- Bonjour
- Bonsoir
- Salut
- or another natural greeting appropriate to the target language and context.

Do not force "Bonjour" or "Bonsoir" if the language or publication context suggests another natural formulation.

IMPORTANT:
The anonymous-submission formula is part of the identity of the feature.

It should NOT feel like an editorial heading.

It should feel like the beginning of a real message sent by an anonymous person to the page.


==================================================
3. NEVER INVENT THE REASON FOR ANONYMITY
==================================================

The narrator is anonymous, but you MUST NOT invent why they want to remain anonymous.

You may naturally say:

"Je prefere rester anonyme."

"Je ne souhaite pas donner mon nom."

"Publiez-moi en anonyme."

when appropriate to establish the submission format.

But do NOT invent reasons such as:

"I am afraid my family will find out."

"I am afraid my husband will recognize me."

"My employer follows this page."

unless the transcript explicitly supports those facts.

The anonymity itself is part of the publication format.

The reason for anonymity must not be fabricated.


==================================================
4. THE NARRATOR IS SPEAKING DIRECTLY TO THE COMMUNITY
==================================================

The narrator must sound like a real person speaking directly to the readers of PAGE_NAME.

Use first-person narration extensively.

Prefer:

"I..."
"I never thought..."
"I didn't know..."
"I tried..."
"I kept asking myself..."
"I realized..."
"I was afraid..."
"I don't know what to do anymore."
"I need your advice."
"I want to know what you would do in my situation."

Avoid detached narration such as:

"The woman explains..."
"The man tells..."
"The person describes..."
"The protagonist..."
"This person experienced..."
"This story demonstrates..."

The narrator must remain at the center of their own story.


==================================================
5. PERSONAL CONFESSION -- CRITICAL
==================================================

The story must feel like a CONFESSION, not simply a narrative.

The narrator should reveal their experience progressively.

The writing should convey the feeling that the person has finally decided to tell people what happened.

The narrator may express:

- uncertainty
- hesitation
- regret
- confusion
- frustration
- fear
- disappointment
- hope
- emotional conflict
- the need to understand what to do next

ONLY when supported by the transcript.

Do not manufacture emotions.

The narrator does not need to sound perfectly polished.

Natural vulnerability is encouraged.

The story can contain phrases such as:

"I honestly don't know what to do anymore."

"I have been keeping this to myself for a long time."

"I never imagined I would find myself in this situation."

"I keep asking myself whether I am making the right decision."

"I don't know if I am wrong."

"I need to hear from people who may have experienced something similar."

These are examples of STYLE only.

Never insert them if the transcript does not support the underlying meaning.


==================================================
6. CORE EDITORIAL TEST
==================================================

Before returning the final story, silently ask:

"Does this sound like an anonymous person who personally came to PAGE_NAME to confess what happened to them and speak to the community?"

If the answer is NO:

- strengthen the first-person voice
- make the introduction feel more like an anonymous submission
- make the narrator more present
- make the narrator's personal dilemma clearer
- make the connection with the community more natural
- rewrite the ending so the narrator is directly asking the community

Do NOT add facts to achieve this effect.


==================================================
7. FACTUAL FIDELITY -- ABSOLUTE
==================================================

You may improve the narrative, but you MUST NOT invent facts.

You may:

- reorganize events
- improve sentence structure
- remove repetition
- clarify obvious meaning
- improve transitions
- improve pacing
- create a stronger opening using existing facts
- combine repetitive statements
- improve readability
- make the dilemma clearer
- improve emotional rhythm

You MUST NOT invent:

- names
- ages
- relationships
- marriages
- pregnancies
- children
- affairs
- illnesses
- deaths
- professions
- financial circumstances
- locations
- threats
- violence
- actions
- consequences
- motivations
- conversations
- direct quotes
- revelations
- emotions
- intentions
- events

If something is ambiguous in the transcript, preserve the ambiguity.

Never convert an assumption into a fact.

Never fill missing information simply because it would make the story more interesting.


==================================================
8. SILENT STORY ANALYSIS
==================================================

Before writing, analyze the ENTIRE transcript silently.

Identify, when available:

- narrator
- important people
- relationships
- initial situation
- narrator's expectations
- narrator's objective
- triggering event
- central conflict
- complications
- discoveries
- revelations
- consequences
- emotional progression
- turning point
- current situation
- dilemma
- what the narrator is unsure about
- what the narrator wants the community to help them understand

Do NOT output this analysis.


==================================================
9. FIRST-PERSON VOICE
==================================================

Use first person as much as possible when supported by the transcript.

The narrator should tell the story from their own perspective.

Prefer:

"I thought..."
"I believed..."
"I tried..."
"I realized..."
"I didn't understand..."
"I asked myself..."
"I was torn..."
"I don't know..."
"I need to know..."

Avoid unnecessary third-person narration.

Do not turn the narrator into an observer of their own life.


==================================================
10. STORY STRUCTURE
==================================================

Use the following conceptual structure when supported by the transcript:

1. ANONYMOUS SUBMISSION / GREETING
2. PERSONAL INTRODUCTION
3. HOOK
4. CONTEXT
5. WHAT HAPPENED
6. TRIGGERING EVENT
7. ESCALATION
8. REACTIONS
9. COMPLICATIONS
10. DISCOVERIES / REVELATIONS
11. TURNING POINT
12. CURRENT SITUATION
13. PERSONAL DILEMMA
14. DIRECT QUESTION TO THE COMMUNITY

Do NOT add sections or headings.

The final result must read as one continuous personal confession.

Do not make it look like a structured article.


==================================================
11. INTRODUCTION -- HIGH PRIORITY
==================================================

The introduction must contain TWO functions:

A. Establish the anonymous submission to PAGE_NAME.
B. Quickly establish why the narrator needs to tell this story.

The introduction should naturally combine:

- greeting
- page name
- anonymous publication request
- personal reason for telling the story, when supported
- beginning of the story

Example style:

"Bonsoir WOURI TV, publiez-moi en anonyme. Je ne pensais jamais avoir a raconter une histoire pareille, mais aujourd'hui je ne sais vraiment plus quoi faire."

Another possible style:

"Bonsoir WOURI TV. Je prefere rester anonyme, mais j'ai besoin de vous raconter ce qui m'arrive, parce que je suis completement perdu face a la decision que je dois prendre."

Another:

"Bonjour WOURI TV, s'il vous plait publiez mon histoire anonymement. Je garde cette situation pour moi depuis un moment et je ne sais plus vers qui me tourner."

These examples demonstrate the desired FEELING.

Do NOT copy them mechanically.

The introduction must be generated from the actual story.

Do not invent "I have been keeping this for months" unless the transcript says or strongly supports it.

Do not invent "I don't know who to turn to" unless supported.

The introduction must feel like a genuine message to the page, not a generic template.


==================================================
12. HOOK
==================================================

After the anonymous submission formula, move quickly into the strongest supported aspect of the story.

The hook can be:

- a shocking realization
- an unexpected discovery
- a difficult decision
- a contradiction
- a relationship problem
- a personal fear
- an emotional turning point
- an unanswered question

The hook must be authentic.

Never use fake clickbait.

Never exaggerate.


==================================================
13. EMOTIONAL AUTHENTICITY
==================================================

Make the story engaging without manufacturing emotions.

Show emotions only when supported by:

- what the narrator explicitly says
- their actions
- their reactions
- their words
- the situation itself when the emotional implication is clear

Do not add dramatic language simply to make the story more viral.


==================================================
14. NATURAL SOCIAL-MEDIA STYLE
==================================================

The final text must be easy to read on a social-media page.

Use:

- short paragraphs
- medium-length paragraphs
- natural transitions
- conversational language
- clear chronology
- progressive disclosure

Avoid:

- academic language
- journalistic tone
- literary over-writing
- excessive metaphors
- artificial suspense
- motivational cliches
- generic life lessons
- AI-sounding expressions
- unnecessary repetition


==================================================
15. THE ENDING MUST REMAIN PERSONAL
==================================================

The ending should return to the narrator's present situation.

The narrator should explain, when supported:

- what they are currently struggling with
- what decision they are facing
- what they don't understand
- what they want from the community

Do not resolve the dilemma.

Do not tell the narrator what they should do.

Do not add a moral lesson.

Do not write:

"This story teaches us that..."
"The narrator should..."
"The best solution is..."

Instead, let the narrator ask the community.


==================================================
16. FINAL QUESTIONS -- NARRATOR'S QUESTIONS
==================================================

Generate 1 to 3 questions when the narrator has a genuine dilemma or uncertainty.

These questions MUST sound like the anonymous person is personally asking the readers.

They are NOT editorial questions.

They are NOT psychological discussion questions.

They are NOT generic advice questions.

BAD:

"How can someone overcome a fear of commitment after a toxic relationship?"

"Have you ever experienced a situation where you had to forgive someone to move forward?"

"What advice would you give someone who is afraid of the future?"

These sound like an editor wrote them.

GOOD STYLE:

"Est-ce que nous devons vraiment nous separer ?"

"Est-ce que certains couples ici ont deja vecu une situation semblable et reussi a construire leur vie autrement ?"

"Je ne cherche meme plus qu'on me dise qui a raison. Je veux simplement savoir : a ma place, vous feriez quoi ?"

"Est-ce que je suis en train de faire le mauvais choix ?"

"Si vous etiez a ma place, vous resteriez ou vous partiriez ?"

"Est-ce que certains d'entre vous ont vecu quelque chose de similaire ?"

These are STYLE examples only.

Generate questions based strictly on the narrator's actual situation.

The questions must feel like something this particular person would genuinely ask.


==================================================
17. DO NOT TURN QUESTIONS INTO A MORAL LESSON
==================================================

Never end with:

"What can we learn from this story?"
"What would society say?"
"What are the lessons of this situation?"
"How should people deal with relationships?"

The ending must remain personal.

The narrator is asking:

"What would YOU do if you were ME?"


==================================================
18. ANONYMIZATION
==================================================

If identifying information is present:

- generalize unnecessary precise locations
- remove unnecessary company names
- remove unnecessary workplace identifiers
- anonymize names when necessary

Do NOT invent replacement identities.

Do NOT add fictional details.


==================================================
19. STORY ELIGIBILITY
==================================================

Determine whether the transcript contains a genuine personal experience.

Return:

"is_story": true

when the transcript contains a meaningful personal experience, testimony, conflict, dilemma, or personal situation.

Return:

"is_story": false

when the transcript is primarily:

- generic information
- advertising
- a tutorial
- unrelated commentary
- a news report
- fictional content without being presented as a personal experience
- insufficient material for a personal confession

Also determine:

"confidence": a number between 0 and 1

"has_personal_experience": true or false


==================================================
20. WHEN INFORMATION IS INSUFFICIENT
==================================================

Never invent missing information.

If the transcript does not contain enough information to construct a coherent personal confession, remain faithful to what is available.

If it clearly does not contain a personal experience, return:

"is_story": false


==================================================
21. LANGUAGE
==================================================

SOURCE_LANGUAGE:
{source_language}

TARGET_LANGUAGE:
{target_language}

Write the final story in TARGET_LANGUAGE.

If TARGET_LANGUAGE is unavailable, use SOURCE_LANGUAGE.

The result must sound like a native speaker personally telling their story.

Do NOT perform a literal translation.

Preserve:

- personality
- meaning
- uncertainty
- emotional intent
- personal voice


==================================================
22. OUTPUT FORMAT
==================================================

Return ONLY valid JSON.

No markdown.
No comments.
No explanations.
No text outside the JSON.

Use exactly:

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
23. FIELD DEFINITIONS
==================================================

"is_story":
Boolean indicating whether the transcript contains a genuine personal story.

"confidence":
Confidence score between 0 and 1.

"has_personal_experience":
Boolean indicating whether the narrator describes a personal experience.

"hook":
The strongest authentic opening after or integrated with the anonymous submission formula.

"introduction":
The complete opening of the confession.

It MUST establish the anonymous submission to PAGE_NAME and transition naturally into the narrator's story.

It should feel like a real message sent to the page.

"story":
The complete personal narrative.

It must remain in first person whenever supported.

"questions":
1 to 3 questions personally asked by the narrator to the community.

"full_text":
The complete publication-ready confession.

It must naturally combine:

- anonymous submission
- introduction
- hook
- story
- current dilemma
- questions to the community

Do NOT add section labels such as "Introduction", "Story", or "Questions".


==================================================
24. FINAL SILENT QUALITY CONTROL
==================================================

Before returning the JSON, silently verify ALL of the following:

1. Does the text immediately feel like an anonymous submission to PAGE_NAME?
2. Does the introduction contain a natural anonymous-publication formula?
3. Does it feel like a real person came to the page to confess?
4. Is the narrator strongly present?
5. Is first-person narration used extensively where supported?
6. Does the narrator speak directly to the community?
7. Does the story feel personal rather than editorial?
8. Does the story remain faithful to the transcript?
9. Did you avoid inventing facts?
10. Did you preserve ambiguity?
11. Is the hook compelling but authentic?
12. Is the writing natural and conversational?
13. Does the emotional progression feel believable?
14. Is the narrator's dilemma clear?
15. Do the final questions sound like the narrator's own questions?
16. Are the questions specific to the actual situation?
17. Did you avoid generic editorial questions?
18. Did you avoid moralizing?
19. Did you avoid resolving the narrator's dilemma?
20. Does the final text sound like something a real anonymous person would send to PAGE_NAME?
21. Is the target language natural?
22. Is the JSON valid?
23. Is there absolutely no text outside the JSON?

If ANY answer is NO, revise the output before returning it."""


def build_story_prompt(page_name: str, source_language: str, target_language: str) -> str:
    """Fill in PAGE_NAME/SOURCE_LANGUAGE/TARGET_LANGUAGE via literal
    substitution (never str.format()) since these are free-text values a
    user can type into the create-story form, and the prompt's own JSON
    example (section 22) contains literal `{`/`}` that str.format() would
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

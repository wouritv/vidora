// Shared helpers for the anonymous stories ("Temoignages") feature pages.

export function normalizeStoryJobStatus(status) {
    if (status === "completed") return "complete";
    if (status === "failed") return "error";
    if (status === "queued" || status === "created" || status === "retry_wait") return "processing";
    return status || "idle";
}

/**
 * Map a backend error_code (e.g. "NOT_A_STORY") to its i18n key
 * ("anonymousStories.errorNotAStory"). Falls back to `fallback` when no
 * code is given -- the caller's `t()` call handles a missing translation.
 */
export function errorMessageForCode(t, code, fallback) {
    if (!code) return fallback;
    const camel = String(code).toLowerCase().replace(/_([a-z0-9])/g, (_match, c) => c.toUpperCase());
    const key = `anonymousStories.error${camel.charAt(0).toUpperCase()}${camel.slice(1)}`;
    return t(key, fallback);
}

// Meta's documented rejection text when a text-background post exceeds its
// length limit (see app.py's publish_to_facebook_text_with_background,
// surfaced verbatim from the Graph API error body) -- matched loosely since
// it arrives wrapped in "502: Facebook API error (400): ...".
const FACEBOOK_TEXT_BACKGROUND_LENGTH_ERROR_MARKER = "limited to 130 characters";

/**
 * Turn a per-platform publish failure (results[platform].error, a raw
 * exception string) into a message safe to show the user: Meta's specific
 * "too long for a background preset" rejection gets a translated, friendly
 * message; anything else falls back to the raw error (still better than
 * hiding the failure) or the generic fallback.
 */
export function describePlatformPublishError(t, rawError) {
    if (typeof rawError === "string" && rawError.includes(FACEBOOK_TEXT_BACKGROUND_LENGTH_ERROR_MARKER)) {
        return t(
            "anonymousStories.errorFacebookTextBackgroundTooLong",
            "Facebook a refuse cette publication avec arriere-plan car le texte est trop long."
        );
    }
    return rawError || t("anonymousStories.genericError", "Une erreur est survenue.");
}

/**
 * Client-side mirror of the backend's build_final_text (anonymous_stories.py):
 * flattens hook/introduction/story/questions into the single copy-ready
 * text shown in the preview pane, before the user hits Save. The backend
 * always rebuilds this same text server-side on save -- this copy is only
 * for instant feedback while editing.
 */
export function buildFullText(hook, introduction, story, questions) {
    const parts = [hook, introduction, story].map((part) => (part || "").trim()).filter(Boolean);
    const cleanQuestions = (questions || []).map((q) => q.trim()).filter(Boolean);
    if (cleanQuestions.length) parts.push(cleanQuestions.join("\n"));
    return parts.join("\n\n");
}

// Backend stages reported via /api/status/{job_id}'s current_step (see
// job_manager.update_progress calls in app.py's anonymous-story pipeline:
// 20% "transcription", 55% "generation", 85% "finalization", 100% done).
// "upload" has no backend stage of its own -- the source video is already
// fully received/downloaded by the time a job_id exists at all (it happens
// synchronously in the POST handler), so it's always shown done once we're
// polling a job.
const STORY_STAGE_ORDER = ["transcription", "generation", "finalization"];

/**
 * State of a single step given the job's overall status, which stage index
 * is currently reported (-1 when none has been reported yet), and this
 * step's own index. Pulled out of buildAnonymousStoryProcessSteps (and
 * flattened to early returns) to keep cognitive complexity low -- a nested
 * closure with the same branching counts every branch twice (once for its
 * own nesting, once for being inside the outer function).
 */
function resolveStoryStepState(status, stageIndex, index) {
    if (status === "complete") return "done";
    if (index < stageIndex) return "done";

    const isCurrentStep = index === stageIndex || (stageIndex === -1 && index === 0);
    if (!isCurrentStep) return "pending";
    return status === "error" ? "error" : "active";
}

/**
 * Build the step list for the "Suivi du processus" progress card, in the
 * same shape/visual role as App.jsx's buildProcessingSteps for reels
 * (label + description + state per step) so both features present
 * generation progress the same way.
 */
export function buildAnonymousStoryProcessSteps({ status, currentStep, t }) {
    const stageIndex = STORY_STAGE_ORDER.indexOf(currentStep);
    const stateFor = (index) => resolveStoryStepState(status, stageIndex, index);

    return [
        {
            key: "upload",
            label: t("anonymousStories.stepUpload", "Reception de la video source"),
            description: t("anonymousStories.stepUploadDesc", "La source est prete pour le traitement."),
            state: "done",
        },
        {
            key: "transcription",
            label: t("anonymousStories.stepTranscription", "Transcription de l'audio"),
            description: t("anonymousStories.stepTranscriptionDesc", "Extraction du texte parle depuis la video."),
            state: stateFor(0),
        },
        {
            key: "generation",
            label: t("anonymousStories.stepGeneration", "Redaction de l'histoire"),
            description: t("anonymousStories.stepGenerationDesc", "Verification que l'histoire est exploitable, puis redaction anonymisee."),
            state: stateFor(1),
        },
        {
            key: "finalization",
            label: t("anonymousStories.stepFinalization", "Finalisation"),
            description: t("anonymousStories.stepFinalizationDesc", "Enregistrement du resultat et cloture du traitement."),
            state: stateFor(2),
        },
    ];
}

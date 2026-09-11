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

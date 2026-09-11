import { useEffect, useState } from "react";
import { AlertCircle, ArrowLeft, Check, Copy, Loader2, RefreshCw, Save } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { getApiUrl } from "../config";
import { getAuthHeaders } from "../lib/apiAuth";
import { useAuth } from "../state/AuthContext";
import { useTranslation } from "../state/LanguageContext";
import { buildFullText, errorMessageForCode } from "../lib/anonymousStories";

export default function AnonymousStoryEditorPage() {
    const { storyId } = useParams();
    const { user } = useAuth();
    const { t } = useTranslation();
    const navigate = useNavigate();

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [saving, setSaving] = useState(false);
    const [regenerating, setRegenerating] = useState(false);
    const [copied, setCopied] = useState(false);
    const [savedFlash, setSavedFlash] = useState(false);

    const [title, setTitle] = useState("");
    const [hook, setHook] = useState("");
    const [introduction, setIntroduction] = useState("");
    const [story, setStory] = useState("");
    const [questions, setQuestions] = useState([""]);

    const loadStory = async () => {
        if (!storyId || !user?.id) return;
        setLoading(true);
        setError("");
        try {
            const response = await fetch(getApiUrl(`/api/anonymous-stories/${storyId}`), {
                headers: getAuthHeaders(user.id),
            });
            const data = await response.json();
            if (!response.ok) {
                setError(errorMessageForCode(t, data?.detail, data?.detail || t("anonymousStories.genericError", "Une erreur est survenue.")));
                return;
            }
            const content = data.edited_content && Object.keys(data.edited_content).length ? data.edited_content : data.generated_content || {};
            setTitle(data.title || "");
            setHook(content.hook || "");
            setIntroduction(content.introduction || "");
            setStory(content.story || "");
            setQuestions(content.questions && content.questions.length ? content.questions : [""]);
        } catch (err) {
            setError(err.message || t("anonymousStories.genericError", "Une erreur est survenue."));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadStory();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [storyId, user?.id]);

    const fullText = buildFullText(hook, introduction, story, questions);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(fullText);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            setError(t("anonymousStories.genericError", "Une erreur est survenue."));
        }
    };

    const handleSave = async () => {
        if (!user?.id) return;
        setSaving(true);
        setError("");
        try {
            const response = await fetch(getApiUrl(`/api/anonymous-stories/${storyId}`), {
                method: "PATCH",
                headers: { "Content-Type": "application/json", ...getAuthHeaders(user.id) },
                body: JSON.stringify({
                    title,
                    hook,
                    introduction,
                    story,
                    questions: questions.filter((q) => q.trim()),
                }),
            });
            const data = await response.json();
            if (!response.ok) {
                setError(errorMessageForCode(t, data?.detail, data?.detail || t("anonymousStories.genericError", "Une erreur est survenue.")));
                return;
            }
            setSavedFlash(true);
            setTimeout(() => setSavedFlash(false), 2000);
        } catch (err) {
            setError(err.message || t("anonymousStories.genericError", "Une erreur est survenue."));
        } finally {
            setSaving(false);
        }
    };

    const handleRegenerate = async () => {
        if (!user?.id) return;
        setRegenerating(true);
        setError("");
        try {
            const response = await fetch(getApiUrl(`/api/anonymous-stories/${storyId}/regenerate`), {
                method: "POST",
                headers: getAuthHeaders(user.id),
            });
            const data = await response.json();
            if (!response.ok) {
                setError(errorMessageForCode(t, data?.detail, data?.detail || t("anonymousStories.genericError", "Une erreur est survenue.")));
                return;
            }
            const content = data.edited_content || data.generated_content || {};
            setHook(content.hook || "");
            setIntroduction(content.introduction || "");
            setStory(content.story || "");
            setQuestions(content.questions && content.questions.length ? content.questions : [""]);
        } catch (err) {
            setError(err.message || t("anonymousStories.genericError", "Une erreur est survenue."));
        } finally {
            setRegenerating(false);
        }
    };

    const updateQuestion = (index, value) => {
        setQuestions((prev) => prev.map((q, i) => (i === index ? value : q)));
    };

    if (loading) {
        return (
            <div className="flex-1 flex items-center justify-center p-8">
                <span className="inline-flex items-center gap-2 text-slate-500 dark:text-zinc-400">
                    <Loader2 size={16} className="animate-spin" /> {t("reels.loading", "Loading...")}
                </span>
            </div>
        );
    }

    return (
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                    <input
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder={t("anonymousStories.editorTitle", "Temoignage")}
                        className="w-full bg-transparent text-3xl font-black tracking-tight text-slate-900 dark:text-white focus:outline-none"
                    />
                </div>
                <button
                    type="button"
                    onClick={() => navigate("/dashboard/anonymous-stories")}
                    className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                >
                    <ArrowLeft size={14} />
                    {t("anonymousStories.backToList", "Retour aux temoignages")}
                </button>
            </div>

            {error ? (
                <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                    <AlertCircle size={14} />
                    {error}
                </div>
            ) : null}

            <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
                <section className="space-y-4">
                    <div className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-2">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                            {t("anonymousStories.hookLabel", "Accroche")}
                        </label>
                        <textarea
                            value={hook}
                            onChange={(e) => setHook(e.target.value)}
                            rows={2}
                            className="w-full resize-y rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 p-3 text-sm text-white focus:outline-none focus:border-primary/60"
                        />
                    </div>

                    <div className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-2">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                            {t("anonymousStories.introductionLabel", "Introduction")}
                        </label>
                        <textarea
                            value={introduction}
                            onChange={(e) => setIntroduction(e.target.value)}
                            rows={3}
                            className="w-full resize-y rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 p-3 text-sm text-white focus:outline-none focus:border-primary/60"
                        />
                    </div>

                    <div className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-2">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                            {t("anonymousStories.storyLabel", "Histoire")}
                        </label>
                        <textarea
                            value={story}
                            onChange={(e) => setStory(e.target.value)}
                            rows={12}
                            className="w-full resize-y rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 p-3 text-sm text-white focus:outline-none focus:border-primary/60"
                        />
                    </div>

                    <div className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-2">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                            {t("anonymousStories.questionsLabel", "Questions finales")}
                        </label>
                        <div className="space-y-2">
                            {questions.map((question, index) => (
                                <input
                                    // eslint-disable-next-line react/no-array-index-key
                                    key={index}
                                    value={question}
                                    onChange={(e) => updateQuestion(index, e.target.value)}
                                    className="w-full rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 p-3 text-sm text-white focus:outline-none focus:border-primary/60"
                                />
                            ))}
                        </div>
                    </div>
                </section>

                <aside className="space-y-4">
                    <div className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-3">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                            {t("anonymousStories.fullPreviewLabel", "Texte complet")}
                        </label>
                        <div className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 p-3 text-sm text-zinc-200">
                            {fullText}
                        </div>

                        <button
                            type="button"
                            onClick={handleCopy}
                            className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-500"
                        >
                            {copied ? <Check size={16} /> : <Copy size={16} />}
                            {copied ? t("anonymousStories.copiedConfirmation", "Copie dans le presse-papiers") : t("anonymousStories.copyButton", "Copier")}
                        </button>
                    </div>

                    <div className="flex flex-col gap-2">
                        <button
                            type="button"
                            onClick={handleSave}
                            disabled={saving}
                            className="flex items-center justify-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-zinc-200 transition hover:bg-white/10 disabled:opacity-50"
                        >
                            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                            {savedFlash ? t("anonymousStories.savedConfirmation", "Modifications enregistrees") : t("anonymousStories.saveButton", "Enregistrer")}
                        </button>
                        <button
                            type="button"
                            onClick={handleRegenerate}
                            disabled={regenerating}
                            className="flex items-center justify-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-zinc-200 transition hover:bg-white/10 disabled:opacity-50"
                        >
                            {regenerating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                            {t("anonymousStories.regenerateButton", "Regenerer")}
                        </button>
                    </div>
                </aside>
            </div>
        </div>
    );
}

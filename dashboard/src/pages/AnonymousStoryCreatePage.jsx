import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowLeft, CheckCircle2, Clock3, Loader2 } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { getApiUrl } from "../config";
import { getAuthHeaders } from "../lib/apiAuth";
import { useAuth } from "../state/AuthContext";
import { useUserCredits } from "../state/UserCreditsContext";
import { useTranslation } from "../state/LanguageContext";
import MediaInput from "../components/MediaInput";
import { errorMessageForCode, normalizeStoryJobStatus as normalizeStatus } from "../lib/anonymousStories";

export default function AnonymousStoryCreatePage() {
    const { user } = useAuth();
    const { credits } = useUserCredits();
    const { t } = useTranslation();
    const navigate = useNavigate();
    const location = useLocation();
    const projectIdFromUrl = useMemo(() => new URLSearchParams(location.search || "").get("project_id") || "", [location.search]);

    const [projectId, setProjectId] = useState(projectIdFromUrl);
    const [jobId, setJobId] = useState("");
    const [status, setStatus] = useState(projectIdFromUrl ? "processing" : "idle");
    const [error, setError] = useState("");
    const [projectJobLoading, setProjectJobLoading] = useState(false);
    const pollFailureCountRef = useRef(0);

    const hasCredits = Number(credits || 0) > 0;

    const processSteps = useMemo(() => {
        const s = normalizeStatus(status);
        return [
            { key: "upload", label: t("anonymousStories.stepUpload", "Reception de la video"), state: s === "idle" ? "pending" : "done" },
            { key: "transcription", label: t("anonymousStories.stepTranscription", "Transcription de l'audio"), state: s === "complete" || s === "processing" ? "done" : "pending" },
            { key: "analysis", label: t("anonymousStories.stepAnalysis", "Verification de l'histoire"), state: s === "complete" ? "done" : s === "processing" ? "active" : s === "error" ? "error" : "pending" },
            { key: "generation", label: t("anonymousStories.stepGeneration", "Redaction du temoignage"), state: s === "complete" ? "done" : s === "error" ? "error" : "pending" },
        ];
    }, [status, t]);

    // Resume an in-progress (or just-failed) project opened back from the
    // projects list -- same recovery flow as NewCaptionPage.
    useEffect(() => {
        if (!projectIdFromUrl || !user?.id) return undefined;
        let cancelled = false;
        const restoreProjectJob = async () => {
            setProjectJobLoading(true);
            try {
                const response = await fetch(getApiUrl(`/api/projects/${projectIdFromUrl}/job`), {
                    headers: getAuthHeaders(user.id),
                });
                const payload = await response.json().catch(() => ({}));
                if (cancelled) return;
                if (!response.ok) {
                    setStatus("error");
                    setError(payload?.detail || t("anonymousStories.genericError", "Une erreur est survenue."));
                    return;
                }
                const linkedJob = payload?.job;
                if (linkedJob?.id) {
                    setJobId(String(linkedJob.id));
                    setStatus(normalizeStatus(linkedJob.status || payload?.project_status || "processing"));
                    if (linkedJob.status === "failed") {
                        setError(errorMessageForCode(t, linkedJob?.error?.code, linkedJob?.error?.message || t("anonymousStories.genericError", "Une erreur est survenue.")));
                    }
                    return;
                }
                const projectStatus = normalizeStatus(payload?.project_status || "processing");
                if (projectStatus === "complete") {
                    navigate(`/dashboard/anonymous-stories/projects/${projectIdFromUrl}`);
                    return;
                }
                setStatus(projectStatus === "error" ? "error" : "processing");
            } catch {
                if (!cancelled) {
                    setStatus("error");
                    setError(t("anonymousStories.genericError", "Une erreur est survenue."));
                }
            } finally {
                if (!cancelled) setProjectJobLoading(false);
            }
        };
        restoreProjectJob();
        return () => {
            cancelled = true;
        };
    }, [projectIdFromUrl, user?.id, navigate, t]);

    useEffect(() => {
        if (!jobId) return undefined;
        let timerId = null;
        let cancelled = false;

        const poll = async () => {
            try {
                const response = await fetch(getApiUrl(`/api/status/${jobId}`), { headers: getAuthHeaders(user?.id) });
                if (!response.ok) {
                    pollFailureCountRef.current += 1;
                    if (pollFailureCountRef.current >= 3) {
                        setError(t("anonymousStories.genericError", "Une erreur est survenue."));
                    }
                    return;
                }
                const data = await response.json();
                if (cancelled) return;
                pollFailureCountRef.current = 0;
                setStatus(normalizeStatus(data.status));

                if (data.status === "failed") {
                    setError(errorMessageForCode(t, data?.error?.code, data?.error?.message || t("anonymousStories.genericError", "Une erreur est survenue.")));
                }

                if (data.status === "completed") {
                    const resultProjectId = data?.result?.project_id || projectId;
                    setTimeout(() => {
                        if (resultProjectId) {
                            navigate(`/dashboard/anonymous-stories/projects/${resultProjectId}`);
                        } else {
                            navigate("/dashboard/anonymous-stories");
                        }
                    }, 500);
                }
            } catch {
                // Keep polling on transient network errors.
            }
        };

        poll();
        timerId = globalThis.setInterval(poll, 2500);
        return () => {
            cancelled = true;
            if (timerId) globalThis.clearInterval(timerId);
        };
    }, [jobId, user?.id, navigate, projectId, t]);

    const handleProcess = async (data) => {
        if (!user?.id) {
            setError("Authentication required. Please reconnect your session.");
            return;
        }
        if (!hasCredits) {
            const message = t("common.insufficientCreditsStart", "Credits insuffisants pour initier cette operation.");
            setError(message);
            globalThis.alert(message);
            return;
        }

        setError("");
        setStatus("processing");
        try {
            const headers = getAuthHeaders(user.id);
            let body;
            if (data.type === "url") {
                headers["Content-Type"] = "application/json";
                body = JSON.stringify({ url: data.payload, acknowledged: !!data.acknowledged });
            } else {
                body = new FormData();
                body.append("file", data.payload);
                body.append("acknowledged", data.acknowledged ? "true" : "false");
            }

            const response = await fetch(getApiUrl("/api/anonymous-stories"), {
                method: "POST",
                headers,
                body,
            });

            if (!response.ok) {
                const raw = await response.text();
                let detail = raw;
                try {
                    detail = JSON.parse(raw)?.detail || raw;
                } catch {
                    // Keep raw server detail.
                }
                setStatus("error");
                setError(detail || t("anonymousStories.genericError", "Une erreur est survenue."));
                if (response.status === 402) {
                    globalThis.alert(detail || t("anonymousStories.errorInsufficientCredits", "Credits insuffisants."));
                }
                return;
            }

            const payload = await response.json();
            setJobId(payload.job_id || "");
            setProjectId(payload.project_id || "");
            setStatus("processing");
        } catch (err) {
            setStatus("error");
            setError(err.message || t("anonymousStories.genericError", "Une erreur est survenue."));
        }
    };

    const isProcessing = normalizeStatus(status) === "processing";

    return (
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight">{t("anonymousStories.createTitle", "Creer une histoire anonyme")}</h1>
                    <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">{t("anonymousStories.createSubtitle", "Importe une video ou colle un lien YouTube.")}</p>
                </div>
                <button
                    type="button"
                    onClick={() => navigate("/dashboard/anonymous-stories")}
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                >
                    <ArrowLeft size={14} />
                    {t("anonymousStories.backToList", "Retour aux histoires anonymes")}
                </button>
            </div>

            {!jobId && !projectIdFromUrl ? (
                <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                    {error ? (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</div>
                    ) : null}
                    <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-500 dark:text-zinc-400">
                        {t("anonymousStories.facebookNotice", "Une video Facebook doit d'abord etre telechargee, puis importee ici comme fichier.")}
                    </div>
                    {!hasCredits ? (
                        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                            {t("common.insufficientCreditsStart", "Credits insuffisants pour initier cette operation.")}
                        </div>
                    ) : null}

                    <MediaInput
                        onProcess={handleProcess}
                        isProcessing={isProcessing}
                        isCreditBlocked={!hasCredits}
                        disableActions={!hasCredits}
                        creditWarning={!hasCredits ? t("common.insufficientCreditsStart", "Credits insuffisants pour initier cette operation.") : ""}
                        submitLabel={t("anonymousStories.generateCta", "Generer l'histoire")}
                        processingLabel={t("mediaInput.processing", "Processing Video...")}
                    />
                </section>
            ) : (
                <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                    <div className="flex items-center justify-between">
                        <p className="text-sm text-slate-400">{t("anonymousStories.processingTitle", "Generation de ton histoire")}</p>
                        <div className="inline-flex items-center gap-2 rounded-full border border-slate-300 dark:border-white/10 bg-black/30 px-3 py-1 text-xs text-zinc-300">
                            <Activity size={14} className={isProcessing ? "animate-pulse text-primary" : "text-slate-400"} />
                            {projectJobLoading ? t("app.loading", "Chargement...") : normalizeStatus(status)}
                        </div>
                    </div>

                    {error ? (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</div>
                    ) : null}

                    <div className="space-y-2">
                        {processSteps.map((step) => (
                            <div key={step.key} className="flex items-center gap-2 rounded-lg border border-slate-300 dark:border-white/10 bg-black/30 px-3 py-2 text-sm text-zinc-300">
                                {step.state === "done" ? <CheckCircle2 size={14} className="text-green-400" /> : null}
                                {step.state === "active" ? <Loader2 size={14} className="animate-spin text-primary" /> : null}
                                {step.state === "pending" ? <Clock3 size={14} className="text-slate-500" /> : null}
                                {step.state === "error" ? <Clock3 size={14} className="text-red-400" /> : null}
                                <span>{step.label}</span>
                            </div>
                        ))}
                    </div>
                </section>
            )}
        </div>
    );
}

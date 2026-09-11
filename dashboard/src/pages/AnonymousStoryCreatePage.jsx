import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, AlertCircle, ArrowLeft, CheckCircle2, Clock3, Loader2 } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { getApiUrl } from "../config";
import { getAuthHeaders } from "../lib/apiAuth";
import { useAuth } from "../state/AuthContext";
import { useUserCredits } from "../state/UserCreditsContext";
import { useTranslation } from "../state/LanguageContext";
import MediaInput from "../components/MediaInput";
import {
    buildAnonymousStoryProcessSteps,
    errorMessageForCode,
    normalizeStoryJobStatus as normalizeStatus,
} from "../lib/anonymousStories";

// Same "Suivi du processus" card (eyebrow + title + status pill, progress
// bar, step cards with icon/label/description) as App.jsx's
// ProcessingChecklist for reels -- kept as its own small component here
// since ProcessingChecklist itself is wired to reel-specific data
// (visibleClips/processingMedia), but the visual presentation matches.
function StepStatusIcon({ state }) {
    if (state === "done") return <CheckCircle2 size={16} className="text-green-400" />;
    if (state === "active") return <Loader2 size={16} className="text-primary animate-spin" />;
    if (state === "error") return <AlertCircle size={16} className="text-red-400" />;
    return <Clock3 size={16} className="text-slate-400 dark:text-zinc-500" />;
}

function ProcessingChecklist({ status, currentStep, isLoadingStatus, t }) {
    const steps = useMemo(() => buildAnonymousStoryProcessSteps({ status, currentStep, t }), [status, currentStep, t]);
    const doneCount = steps.filter((step) => step.state === "done").length;
    const totalCount = steps.length;
    const progressPercent = Math.round((doneCount / totalCount) * 100);

    return (
        <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/[0.03] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                        {t("reels.processFollowup", "Suivi du processus")}
                    </p>
                    <h3 className="title-contrast mt-1 text-lg font-bold">{t("anonymousStories.processingTitle", "Generation de ton histoire")}</h3>
                </div>
                <div className="flex items-center gap-2 rounded-full border border-slate-300 dark:border-white/10 bg-black/20 px-3 py-1.5 text-xs text-slate-700 dark:text-zinc-300">
                    <Activity size={14} className={status === "processing" ? "text-primary animate-pulse" : "text-slate-500 dark:text-zinc-400"} />
                    <span>{isLoadingStatus ? t("app.loading", "Chargement...") : status}</span>
                </div>
            </div>

            <div className="mt-4 rounded-xl border border-slate-300 dark:border-white/10 bg-black/20 p-3">
                <div className="mb-2 flex items-center justify-between text-xs">
                    <span className="text-slate-500 dark:text-zinc-400">{t("reels.progress", "Progression")}</span>
                    <span className="font-medium text-zinc-200">{doneCount}/{totalCount} {t("reel.step", "etapes")} ({progressPercent}%)</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                        className="h-full rounded-full bg-primary transition-all duration-500"
                        style={{ width: `${progressPercent}%` }}
                    />
                </div>
            </div>

            <div className="mt-5 space-y-3">
                {steps.map((step) => (
                    <div key={step.key} className="flex items-start gap-3 rounded-xl border border-slate-200 dark:border-white/5 bg-black/20 px-4 py-3">
                        <div className="mt-0.5 shrink-0">
                            <StepStatusIcon state={step.state} />
                        </div>
                        <div className="min-w-0">
                            <p className="text-sm font-semibold text-white">{step.label}</p>
                            <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-zinc-400">{step.description}</p>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}

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
    const [currentStep, setCurrentStep] = useState("");
    const [error, setError] = useState("");
    const [projectJobLoading, setProjectJobLoading] = useState(false);
    const pollFailureCountRef = useRef(0);

    const hasCredits = Number(credits || 0) > 0;

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
                    setCurrentStep(String(linkedJob.current_step || ""));
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
                setCurrentStep(String(data.current_step || ""));

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
        setCurrentStep("");
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
                <div className="space-y-4">
                    {error ? (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</div>
                    ) : null}

                    <ProcessingChecklist
                        status={normalizeStatus(status)}
                        currentStep={currentStep}
                        isLoadingStatus={projectJobLoading}
                        t={t}
                    />
                </div>
            )}
        </div>
    );
}

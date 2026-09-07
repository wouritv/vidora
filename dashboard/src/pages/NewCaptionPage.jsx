import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowLeft, CheckCircle2, Clock3, Loader2 } from "lucide-react";
import { getApiUrl } from "../config";
import { useAuth } from "../state/AuthContext";
import { useUserCredits } from "../state/UserCreditsContext";
import { useLocation, useNavigate } from "react-router-dom";
import MediaInput from "../components/MediaInput";
import { useTranslation } from "../state/LanguageContext";

function normalizeStatus(status) {
    if (status === "completed") return "complete";
    if (status === "failed") return "error";
    if (status === "queued" || status === "created" || status === "retry_wait") return "processing";
    return status || "idle";
}

export default function NewCaptionPage() {
    const { user } = useAuth();
    const { credits } = useUserCredits();
    const { t } = useTranslation();
    const navigate = useNavigate();
    const location = useLocation();
    const projectId = useMemo(() => new URLSearchParams(location.search || "").get("project_id") || "", [location.search]);

    const [jobId, setJobId] = useState("");
    const [status, setStatus] = useState("idle");
    const [error, setError] = useState("");
    const [projectJobLoading, setProjectJobLoading] = useState(false);
    const lastLoggedCountRef = useRef(0);
    const pollFailureCountRef = useRef(0);

    const hasCreditsForCaption = Number(credits || 0) > 0;

    useEffect(() => {
        if (!projectId || !user?.id) return;
        let cancelled = false;
        const restoreProjectJob = async () => {
            setProjectJobLoading(true);
            try {
                const response = await fetch(getApiUrl(`/api/projects/${projectId}/job`), {
                    headers: { "X-User-Id": user.id },
                });
                const payload = await response.json().catch(() => ({}));
                if (cancelled) return;
                if (!response.ok) {
                    // Fallback for older backend versions where /projects/{id}/job may not exist yet.
                    const projectResp = await fetch(getApiUrl(`/api/projects/${projectId}`), {
                        headers: { "X-User-Id": user.id },
                    });
                    const projectPayload = await projectResp.json().catch(() => ({}));
                    if (cancelled) return;
                    if (!projectResp.ok) {
                        setStatus("error");
                        setError(projectPayload?.detail || payload?.detail || "Project not found");
                        return;
                    }

                    const projectStatus = normalizeStatus(projectPayload?.status || "processing");
                    if (projectStatus === "complete") {
                        navigate(`/dashboard/captions/projects/${projectId}?autoplay=1`);
                        return;
                    }
                    if (projectStatus === "error") {
                        setStatus("error");
                        setError("Ce projet a rencontre une erreur pendant le traitement.");
                    } else {
                        setStatus("processing");
                        setError("");
                    }
                    return;
                }
                const linkedJob = payload?.job;
                if (linkedJob?.id) {
                    setJobId(String(linkedJob.id));
                    setStatus(normalizeStatus(linkedJob.status || payload?.project_status || "processing"));
                    if (linkedJob.status === "failed") {
                        const msg = linkedJob?.error?.message || "Caption generation failed";
                        setError(String(msg));
                    }
                    return;
                }

                const projectStatus = normalizeStatus(payload?.project_status || "processing");
                if (projectStatus === "complete") {
                    navigate(`/dashboard/captions/projects/${projectId}?autoplay=1`);
                    return;
                }

                if (projectStatus === "error") {
                    setStatus("error");
                    setError("Ce projet a rencontre une erreur pendant le traitement.");
                } else {
                    setStatus("processing");
                }
            } catch {
                if (!cancelled) {
                    setStatus("error");
                    setError("Unable to recover this project job state.");
                }
            } finally {
                if (!cancelled) setProjectJobLoading(false);
            }
        };
        restoreProjectJob();
        return () => {
            cancelled = true;
        };
    }, [projectId, user?.id, navigate]);

    const processSteps = useMemo(() => {
        const s = normalizeStatus(status);
        return [
            {
                key: "queued",
                label: t("common.processStarted", "Processus demarre"),
                state: s === "idle" ? "pending" : "done",
            },
            {
                key: "analyzing",
                label: "Analyse de la video",
                state: s === "processing" || s === "complete" || s === "error" ? "done" : "pending",
            },
            {
                key: "transcribing",
                label: "Transcription audio",
                state: s === "complete" ? "done" : s === "processing" ? "active" : s === "error" ? "error" : "pending",
            },
            {
                key: "complete",
                label: "Sous-titres prets",
                state: s === "complete" ? "done" : s === "error" ? "error" : "pending",
            },
        ];
    }, [status, t]);

    useEffect(() => {
        if (!jobId) return;
        let timerId = null;
        let cancelled = false;

        const poll = async () => {
            try {
                const response = await fetch(getApiUrl(`/api/status/${jobId}`), {
                    headers: user?.id ? { "X-User-Id": user.id } : undefined,
                });
                if (!response.ok) {
                    pollFailureCountRef.current += 1;
                    if (pollFailureCountRef.current >= 3) {
                        setError("Unable to retrieve processing status. Please refresh or reopen this page.");
                    }
                    return;
                }
                const data = await response.json();
                if (cancelled) return;
                pollFailureCountRef.current = 0;

                setStatus(normalizeStatus(data.status));
                const backendLogs = Array.isArray(data.logs) ? data.logs : [];
                if (backendLogs.length > lastLoggedCountRef.current) {
                    const unseenLogs = backendLogs.slice(lastLoggedCountRef.current);
                    unseenLogs.forEach((line) => {
                        // Keep backend logs visible in dev tools only, not in the UI.
                        console.debug("[captions-job]", line);
                    });
                    lastLoggedCountRef.current = backendLogs.length;
                }
                if (data.status === "failed") {
                    const msg = data?.error?.message || data?.error || "Caption generation failed";
                    setError(String(msg));
                }

                if (data.status === "completed") {
                    const target = projectId
                        ? `/dashboard/captions/projects/${projectId}?autoplay=1`
                        : "/dashboard/captions";
                    setTimeout(() => navigate(target), 600);
                }
            } catch {
                // Keep polling on transient errors.
            }
        };

        poll();
        timerId = globalThis.setInterval(poll, 2000);
        return () => {
            cancelled = true;
            if (timerId) globalThis.clearInterval(timerId);
        };
    }, [jobId, navigate, user?.id, projectId]);

    const handleProcess = async (data) => {
        if (!user?.id) {
            setError("Authentication required. Please reconnect your session.");
            return;
        }
        if (!hasCreditsForCaption) {
            const message = t("common.insufficientCreditsStart", "Crédits insuffisants pour initier cette opération.");
            setError(message);
            globalThis.alert(message);
            return;
        }
        if (data.type !== "file") {
            setError("Upload local uniquement pour les sous-titres.");
            return;
        }

        setError("");
        lastLoggedCountRef.current = 0;
        pollFailureCountRef.current = 0;
        setStatus("processing");
        try {
            const formData = new FormData();
            formData.append("file", data.payload);
            formData.append("acknowledged", data.acknowledged ? "true" : "false");

            const response = await fetch(getApiUrl("/api/captions/process"), {
                method: "POST",
                headers: { "X-User-Id": user.id },
                body: formData,
            });

            if (!response.ok) {
                const raw = await response.text();
                let detail = raw;
                try {
                    const parsed = JSON.parse(raw);
                    detail = parsed?.detail || raw;
                } catch {
                    // Keep raw server detail.
                }
                setError(detail || "Subtitle generation failed");
                setStatus("error");
                if (response.status === 402) {
                    globalThis.alert(detail || "Credits insuffisants pour initier cette opération.");
                }
                return;
            }

            const payload = await response.json();
            setJobId(payload.job_id || "");
            setStatus("processing");
        } catch (err) {
            setError(err.message || "Subtitle generation failed");
            setStatus("error");
        }
    };

    const isProcessing = normalizeStatus(status) === "processing";

    return (
        <div className="captions-page-shell flex-1 overflow-y-auto overflow-x-hidden md:overflow-x-visible p-8 space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight">{t("common.subtitles", "Sous-titres")}</h1>
                    <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">Upload local uniquement puis generation via la file de jobs.</p>
                </div>

                <button
                    type="button"
                    onClick={() => navigate("/dashboard/captions")}
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                >
                    <ArrowLeft size={14} />
                    {t("app.backToList", "Back to list")}
                </button>
            </div>

            {!projectId ? (
                <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                    {error ? (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                            {error}
                        </div>
                    ) : null}
                    {!hasCreditsForCaption ? (
                        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                            {t("common.insufficientCreditsStart", "Insufficient credits to start this operation.")}
                        </div>
                    ) : null}

                    <MediaInput
                        onProcess={handleProcess}
                        isProcessing={isProcessing}
                        isCreditBlocked={!hasCreditsForCaption}
                        disableActions={!hasCreditsForCaption}
                        creditWarning={!hasCreditsForCaption ? t("common.insufficientCreditsStart", "Crédits insuffisants pour initier cette opération.") : ""}
                        localOnly
                        submitLabel={t("captionsModal.generateSubtitles", "Generate subtitles")}
                        processingLabel={t("mediaInput.processing", "Processing Video...")}
                    />
                </section>
            ) : (
                <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5">
                    <div className="inline-flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
                        <Loader2 size={14} className={projectJobLoading ? "animate-spin" : ""} />
                        {projectJobLoading ? "Chargement du projet..." : "Suivi du projet en cours..."}
                    </div>
                    {error ? (
                        <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                            {error}
                        </div>
                    ) : null}
                </section>
            )}

            {jobId || projectId ? (
                <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                    <div className="flex items-center justify-between">
                        <p className="text-sm text-slate-400">{t("common.processingProgress", "Progression du traitement")}</p>
                        <div className="inline-flex items-center gap-2 rounded-full border border-slate-300 dark:border-white/10 bg-black/30 px-3 py-1 text-xs text-zinc-300">
                            <Activity size={14} className={isProcessing ? "animate-pulse text-primary" : "text-slate-400"} />
                            {normalizeStatus(status)}
                        </div>
                    </div>

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
            ) : null}
        </div>
    );
}


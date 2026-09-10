import { ArrowRight, MessageSquareText, Sparkles } from "lucide-react";
import { useAuth } from "../state/AuthContext";
import { useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { getApiUrl } from "../config";
import { normalizeFrontendStatus, statusMeta } from "../lib/status";
import { readGenerationSession, SESSION_KEY } from "../lib/session";
import { useTranslation } from "../state/LanguageContext";
import { getAuthHeaders } from "../lib/apiAuth";

export default function Dashboard() {

    const { user } = useAuth();
    const navigate = useNavigate();
    const { t } = useTranslation();
    const [generationSession, setGenerationSession] = useState(() => readGenerationSession());

    const displayName =
        user?.user_metadata?.full_name ||
        user?.user_metadata?.name ||
        user?.email?.split("@")[0] ||
        "Utilisateur";

    useEffect(() => {
        const syncSession = () => setGenerationSession(readGenerationSession());
        syncSession();

        const interval = globalThis.setInterval(syncSession, 2000);
        return () => globalThis.clearInterval(interval);
    }, []);

    useEffect(() => {
        if (!generationSession?.jobId || generationSession.status !== "processing") return undefined;

        let cancelled = false;
        const pollStatus = async () => {
            try {
                const response = await fetch(getApiUrl(`/api/status/${generationSession.jobId}`), {
                    headers: getAuthHeaders(user?.id),
                });
                if (!response.ok) return;
                const data = await response.json();
                if (cancelled) return;

                const nextSession = {
                    ...generationSession,
                    status: normalizeFrontendStatus(data.status),
                    results: data.result ?? generationSession.results ?? null,
                    timestamp: Date.now(),
                };
                globalThis.localStorage.setItem(SESSION_KEY, JSON.stringify(nextSession));
                setGenerationSession(nextSession);
            } catch {
                // Silent background poll for dashboard summary only.
            }
        };

        pollStatus();
        const interval = globalThis.setInterval(pollStatus, 3000);
        return () => {
            cancelled = true;
            globalThis.clearInterval(interval);
        };
    }, [generationSession?.jobId, generationSession?.status]);

    const generationSummary = useMemo(() => {
        if (!generationSession?.status || generationSession.status === "idle") return null;
        return {
            ...generationSession,
            clipCount: generationSession.results?.clips?.length || 0,
            ...statusMeta(generationSession.status),
        };
    }, [generationSession]);

    let generationSummaryText = "";
    if (generationSummary?.status === "processing") {
        generationSummaryText = t("dashboard.generationInProgress", "Une generation est toujours en cours. Tu peux rouvrir la page de generation pour suivre les etapes et voir les reels deja prets.");
    } else if (generationSummary?.status === "complete") {
        generationSummaryText = t("dashboard.generationComplete", { count: generationSummary.clipCount });
    } else if (generationSummary) {
        generationSummaryText = t("dashboard.generationFailed", "La derniere generation a echoue. Rouvre les details pour verifier l’avancement et relancer une operation.");
    }

    return (
        <div className="flex-1 overflow-y-auto p-8 space-y-10">
            <section className="flex flex-col gap-4 rounded-3xl border border-slate-300 dark:border-white/10 bg-gradient-to-br from-primary/15 via-violet-500/10 to-transparent p-6 md:flex-row md:items-end md:justify-between">
                <div className="max-w-2xl space-y-3">
                    <p className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
                        <Sparkles size={14} />
                        {t("dashboard.welcomeBack", "Bienvenue de retour")}
                    </p>
                    <h2 className="text-3xl font-black tracking-tight">{t("dashboard.hello", "Bonjour")} {displayName}</h2>
                    <p className="text-sm leading-6 text-slate-700 dark:text-zinc-300">
                        {t("dashboard.startWorkflow", "Lance un workflow puis retrouve tous les resultats dans les galeries de services.")}
                    </p>
                </div>
            </section>

            {generationSummary && (
                <section className="rounded-3xl border border-slate-300 dark:border-white/10 bg-white/[0.03] p-6">
                    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                        <div className="space-y-2">
                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">{t("app.reelGenerator","Génération de réels")}</p>
                            <div className="flex flex-wrap items-center gap-3">
                                <h3 className="title-contrast text-xl font-bold">{t("dashboard.memoryWorkflow","Workflow en mémoire")}</h3>
                                <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${generationSummary.className}`}>
                                    <generationSummary.icon size={14} />
                                    {generationSummary.label}
                                </span>
                            </div>
                            <p className="text-sm leading-6 text-slate-500 dark:text-zinc-400">
                                {generationSummaryText}
                            </p>
                        </div>

                        <div className="flex flex-wrap gap-3">
                            <button
                                onClick={() => navigate("/dashboard/reel-generator")}
                                className="inline-flex items-center gap-2 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 px-4 py-3 text-sm text-white transition hover:bg-white/10"
                            >
                                <ArrowRight size={16} />
                                {t("dashboard.details","Ouvrir les details")}
                            </button>
                            <button
                                onClick={() => navigate("/dashboard/reels")}
                                className="inline-flex items-center gap-2 rounded-2xl bg-primary px-4 py-3 text-sm font-medium text-white transition hover:bg-blue-500"
                            >
                                {t("dashboard.gallery","Voir la galerie")}
                            </button>
                        </div>
                    </div>
                </section>
            )}

            <section className="space-y-6">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">{t("dashboard.startAction","Demarrer une action")}</p>
                    <h3 className="mt-2 text-xl font-bold">{t("dashboard.generationJourney","Parcours de generation")}</h3>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                    <button
                        onClick={() => navigate("/dashboard/reel-generator")}
                        className="group rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-5 text-left hover:bg-white/10 transition"
                    >
                        <div className="flex items-center justify-between">
                            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/10 text-violet-400">
                                <Sparkles size={18} />
                            </span>
                            <ArrowRight size={16} className="text-slate-400 dark:text-zinc-500 group-hover:text-white" />
                        </div>
                        <h4 className="title-contrast mt-5 text-lg font-semibold">{t("dashboard.reelgenerator","Générer des reels")}</h4>
                        <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-zinc-400">{t("dashboard.reelgeneratorSubtitle","Upload une video et laisse le systeme boosté à l'IA extraire les moments réels.")}</p>
                    </button>

                    <button
                        onClick={() => navigate("/dashboard/captions/new")}
                        className="group rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-5 text-left hover:bg-white/10 transition"
                    >
                        <div className="flex items-center justify-between">
                            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400">
                                <MessageSquareText size={18} />
                            </span>
                            <ArrowRight size={16} className="text-slate-400 dark:text-zinc-500 group-hover:text-white" />
                        </div>
                        <h4 className="title-contrast mt-5 text-lg font-semibold">{t("dashboard.captionGenerator","Générer des sous-titres")}</h4>
                        <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-zinc-400">{t("dashboard.captionGeneratorSubtitle","Upload une vidéo locale puis génère automatiquement les sous-titres.")}</p>
                    </button>


                </div>


            </section>


        </div>

    );
}
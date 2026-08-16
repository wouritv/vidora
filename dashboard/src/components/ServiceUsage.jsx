import React from "react";
import { CreditCardIcon, Loader2, RefreshCw, AlertTriangle } from "lucide-react";
import { useUserCredits } from "../state/UserCreditsContext";
import { useNavigate } from "react-router-dom";

function ProgressBar({ value, max, color = "green", label, unit = "" }) {
    const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
    const colors = {
        green:  "bg-green-500",
        blue:   "bg-blue-500",
        red:    "bg-red-500",
        purple: "bg-purple-500",
        zinc:   "bg-zinc-400",
        amber:  "bg-amber-400",
    };
    const barColor = pct < 20 ? "red" : pct < 50 ? "amber" : color;

    return (
        <div className="mb-4">
            <div className="flex justify-between text-xs text-slate-500 dark:text-zinc-400 mb-1">
                <span>{label}</span>
                <span className="font-mono">
                    {value.toLocaleString()}{unit} / {max.toLocaleString()}{unit}
                </span>
            </div>
            <div className="w-full bg-zinc-700/40 rounded-full overflow-hidden h-3">
                <div
                    className={`h-full ${colors[barColor] || colors.green} transition-all duration-500 ease-out rounded-full`}
                    style={{ width: `${pct}%` }}
                />
            </div>
        </div>
    );
}

export default function ServiceUsage() {
    const { credits, storage, hasCredits, aboCosts, loading, error, refresh } = useUserCredits();
    const navigate = useNavigate();

    // Estimate a "max" credit pool for display.
    // We take 10× the reel cost as the reference maximum (so users see a meaningful bar).
    const aboCredit       = aboCosts?.credit        ?? 1;
    const aboStorage   = aboCosts?.storage        ?? 1;

    if (loading && credits === 0) {
        return (
            <div className="p-4 flex items-center gap-2 text-slate-500 dark:text-zinc-400 text-sm">
                <Loader2 size={16} className="animate-spin" /> Chargement du solde...
            </div>
        );
    }

    return (
        <div className="p-4">
            {error && (
                <div className="mb-3 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                    <AlertTriangle size={14} />
                    <span>{error}</span>
                    <button onClick={refresh} className="ml-auto text-red-300 hover:text-white">
                        <RefreshCw size={13} />
                    </button>
                </div>
            )}

            {/* Credit balance bar */}
            <ProgressBar
                label="Crédits disponibles"
                value={credits}
                max={aboCredit}
                color="blue"
                unit=" cr"
            />

            {/* Storage bar (GB) */}
            <ProgressBar
                label="Stockage disponibles"
                value={parseFloat(storage.toFixed(2))}
                max={aboStorage}
                color="purple"
                unit=" Go"
            />

            {/* Warning if low credits */}
            {hasCredits === false && (
                <div className="flex items-center justify-between gap-4 mt-2">
                    <div className="flex-1 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                        <p className="text-xs text-amber-300 leading-relaxed">
                            Crédits insuffisants — rechargez votre compte pour continuer.
                        </p>
                    </div>

                    <button
                        onClick={() => navigate("/dashboard/abonnements")}
                        className="flex shrink-0 items-center justify-center gap-2 rounded-2xl border border-green-500/20 bg-green-500/10 px-4 py-3 text-sm font-semibold text-green-300 transition hover:bg-green-500/15"
                    >
                        <CreditCardIcon size={18} />
                        Gérer
                    </button>
                </div>
            )}


        </div>
    );
}
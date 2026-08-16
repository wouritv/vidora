/**
 * CreditGuard – wraps an action button with a credit check.
 *
 * If the user doesn't have enough credits the button is greyed out
 * and a warning tooltip/message is shown.
 *
 * Usage:
 *   <CreditGuard requiredCredits={reelCost}>
 *     <button onClick={...}>Générer</button>
 *   </CreditGuard>
 */
import React from "react";
import { AlertTriangle } from "lucide-react";
import { useUserCredits } from "../state/UserCreditsContext";
import { useNavigate } from "react-router-dom";

export default function CreditGuard({
    children,
    requiredCredits = 1,
    operationLabel = "cette opération",
}) {
    const { credits, hasCredits, loading } = useUserCredits();
    const navigate = useNavigate();

    // While credits haven't loaded yet we allow the action (optimistic).
    if (loading || hasCredits === null) return <>{children}</>;

    const sufficient = credits >= requiredCredits;

    if (sufficient) return <>{children}</>;

    return (
        <div className="flex flex-col gap-2">
            {/* Render children but disabled */}
            <div className="pointer-events-none opacity-40 select-none">
                {children}
            </div>

            <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                <AlertTriangle size={13} className="shrink-0" />
                <span>
                    Crédits insuffisants pour {operationLabel}.
                    Il vous faut au moins <strong>{requiredCredits.toLocaleString()} cr</strong>
                    {" "}(solde : <strong>{credits.toLocaleString()} cr</strong>).{" "}
                </span>
                <button
                    onClick={() => navigate("/dashboard/settings?buy=1")}
                    className="ml-auto whitespace-nowrap font-semibold underline hover:text-amber-200"
                >
                    Recharger
                </button>
            </div>
        </div>
    );
}


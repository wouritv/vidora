import { Activity, CheckCircle2, AlertCircle } from 'lucide-react';

// ── Backend → frontend status normalization ─────────────────────────────────

/**
 * Normalize a raw backend status string to the frontend canonical form.
 * "completed" → "complete"  |  "failed" → "error"
 */
export function normalizeFrontendStatus(status) {
    if (status === 'completed') return 'complete';
    if (status === 'failed') return 'error';
    return status;
}

// ── Reel / item status helpers (used by ReelsPage + GeneratedMediaPage) ─────

export function statusLabel(status) {
    if (status === 'termine') return 'Terminé';
    if (status === 'en_cours') return 'En cours';
    if (status === 'echec') return 'Échec';
    return status || '-';
}

export function statusClass(status) {
    if (status === 'termine') return 'bg-green-500/10 border-green-500/30 text-green-300';
    if (status === 'en_cours') return 'bg-blue-500/10 border-blue-500/30 text-blue-300';
    if (status === 'echec') return 'bg-red-500/10 border-red-500/30 text-red-300';
    return 'bg-white/5 border-slate-300 dark:border-white/10 text-slate-700 dark:text-zinc-300';
}

// ── Dashboard job status (includes Lucide icon reference) ───────────────────

/**
 * Returns { label, className, icon } for a given job status.
 * icon is a Lucide React component — skip asserting it in pure unit tests.
 */
export function statusMeta(status) {
    if (status === 'processing') {
        return {
            label: 'En cours',
            className: 'bg-primary/10 border-primary/20 text-primary',
            icon: Activity,
        };
    }
    if (status === 'complete') {
        return {
            label: 'Terminé',
            className: 'bg-green-500/10 border-green-500/20 text-green-400',
            icon: CheckCircle2,
        };
    }
    return {
        label: 'Erreur',
        className: 'bg-red-500/10 border-red-500/20 text-red-400',
        icon: AlertCircle,
    };
}


import { useEffect, useState } from "react";
import { Loader2, Search, Trash2, ExternalLink, Calendar, Filter } from "lucide-react";
import { getApiUrl } from "../config";
import { useAuth } from "../state/AuthContext";
import { useTranslation } from "../state/LanguageContext";

const PLATFORMS = [
    { value: "facebook", label: "Facebook" },
    { value: "instagram", label: "Instagram" },
    { value: "tiktok", label: "TikTok" },
    { value: "youtube", label: "YouTube" },
    { value: "linkedin", label: "LinkedIn" },
];


const getPlatformIcon = (platform) => {
    const icons = {
        facebook: "📘",
        instagram: "📷",
        tiktok: "🎵",
        youtube: "▶️",
        linkedin: "💼",
    };
    return icons[platform] || "📱";
};

const getStatusBadge = (status) => {
    const badges = {
        pending: { bg: "bg-yellow-500/10", border: "border-yellow-500/20", text: "text-yellow-400", label: "En attente" },
        processing: { bg: "bg-blue-500/10", border: "border-blue-500/20", text: "text-blue-400", label: "En cours" },
        done: { bg: "bg-green-500/10", border: "border-green-500/20", text: "text-green-400", label: "Publié" },
        failed: { bg: "bg-red-500/10", border: "border-red-500/20", text: "text-red-400", label: "Échoué" },
    };
    return badges[status] || badges.pending;
};

const formatDate = (date) => {
    if (!date) return "N/A";
    try {
        return new Date(date).toLocaleDateString("fr-FR", {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return "N/A";
    }
};

export default function SocialPublicationsPage() {
    const { user } = useAuth();
    const { t } = useTranslation();
    const [publications, setPublications] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [page, setPage] = useState(1);
    const [pageSize] = useState(20);
    const [total, setTotal] = useState(0);

    // Filtres
    const [platform, setPlatform] = useState("all");
    const [status, setStatus] = useState("all");
    const [dateFilter, setDateFilter] = useState("all"); // all, today, week, month
    const [searchInput, setSearchInput] = useState("");

    useEffect(() => {
        if (!user?.id) return;

        let cancelled = false;
        async function loadPublications() {
            setLoading(true);
            setError("");

            const params = new URLSearchParams({
                page: String(page),
                page_size: String(pageSize),
            });
            if (platform !== "all") params.set("platform", platform);
            if (status !== "all") params.set("status", status);
            if (dateFilter !== "all") params.set("date_filter", dateFilter);
            if (searchInput) params.set("search", searchInput);

            try {
                const response = await fetch(getApiUrl(`/api/social/publish-jobs?${params.toString()}`), {
                    headers: {
                        "X-User-Id": user.id,
                    },
                });

                if (!response.ok) {
                    const detail = await response.text();
                    setError(detail || "Erreur lors du chargement des publications");
                    setPublications([]);
                    return;
                }

                const data = await response.json();
                if (cancelled) return;

                setPublications(Array.isArray(data.items) ? data.items : []);
                setTotal(data.total || 0);
            } catch (err) {
                if (!cancelled) {
                    console.error("Error loading publications:", err);
                    setError(err.message || "Erreur réseau");
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        loadPublications();

        return () => {
            cancelled = true;
        };
    }, [user?.id, page, platform, status, dateFilter, searchInput, pageSize]);

    const totalPages = Math.max(1, Math.ceil(total / pageSize));

    const handleResetFilters = () => {
        setPlatform("all");
        setStatus("all");
        setDateFilter("all");
        setSearchInput("");
        setPage(1);
    };

    return (
        <div className="h-full flex flex-col bg-background overflow-hidden">
            {/* Header */}
            <div className="border-b border-slate-200 dark:border-white/5 bg-background/50 backdrop-blur-md px-6 py-4 shrink-0">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h1 className="text-3xl font-black tracking-tight">{t('social.socialPublications', 'Publications sociales')}</h1>
                        <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1">{t('social.realTimeTracking', 'Suivi en temps réel de vos publications')}</p>
                    </div>
                    {total > 0 && (
                        <div className="text-sm text-slate-500 dark:text-zinc-400">
                            <span className="font-semibold text-white">{total}</span> publication{total !== 1 ? "s" : ""}
                        </div>
                    )}
                </div>

                {/* Filtres */}
                <div className="flex flex-wrap gap-3 items-center">
                    {/* Recherche */}
                    <div className="flex-1 min-w-[200px] relative">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-zinc-500" />
                        <input
                            type="text"
                            placeholder="Rechercher..."
                            value={searchInput}
                            onChange={(e) => {
                                setSearchInput(e.target.value);
                                setPage(1);
                            }}
                            className="w-full pl-9 pr-3 py-2 rounded-lg bg-white/5 border border-slate-300 dark:border-white/10 text-sm text-white placeholder-zinc-500 focus:outline-none focus:bg-white/10 focus:border-primary/50"
                        />
                    </div>

                    {/* Plateforme */}
                    <select
                        value={platform}
                        onChange={(e) => {
                            setPlatform(e.target.value);
                            setPage(1);
                        }}
                        className="px-3 py-2 rounded-lg bg-white/5 border border-slate-300 dark:border-white/10 text-sm text-white focus:outline-none focus:bg-white/10 focus:border-primary/50"
                    >
                        <option value="all">{t("common.allPlatforms","Toutes les plateformes")}</option>
                        {PLATFORMS.map((p) => (
                            <option key={p.value} value={p.value}>
                                {p.label}
                            </option>
                        ))}
                    </select>

                    {/* Statut */}
                    <select
                        value={status}
                        onChange={(e) => {
                            setStatus(e.target.value);
                            setPage(1);
                        }}
                        className="px-3 py-2 rounded-lg bg-white/5 border border-slate-300 dark:border-white/10 text-sm text-white focus:outline-none focus:bg-white/10 focus:border-primary/50"
                    >
                        <option value="all">{t("common.allStatuses","Tous les statuts")}</option>
                        <option value="pending">{t("common.pending","En attente")}</option>
                        <option value="processing">{t("common.processing","En cours")}</option>
                        <option value="done">{t("common.done","Publié")}</option>
                        <option value="failed">{t("common.failed","Échoué")}</option>
                    </select>

                    {/* Date */}
                    <select
                        value={dateFilter}
                        onChange={(e) => {
                            setDateFilter(e.target.value);
                            setPage(1);
                        }}
                        className="px-3 py-2 rounded-lg bg-white/5 border border-slate-300 dark:border-white/10 text-sm text-white focus:outline-none focus:bg-white/10 focus:border-primary/50"
                    >
                        <option value="all">{t("common.allDates","Toutes les dates")}</option>
                        <option value="today">{t("common.today","Aujourd'hui")}</option>
                        <option value="week">{t("common.week","Cette semaine")}</option>
                        <option value="month">{t("common.month","Ce mois")}</option>
                    </select>

                    {/* Réinitialiser */}
                    {(platform !== "all" || status !== "all" || dateFilter !== "all" || searchInput) && (
                        <button
                            onClick={handleResetFilters}
                            className="px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-slate-300 dark:border-white/10 text-sm text-white transition-colors flex items-center gap-2"
                        >
                            <Filter size={14} />
                            {t("common.reset","Réinitialiser")}
                        </button>
                    )}
                </div>
            </div>

            {/* Contenu */}
            <div className="flex-1 overflow-y-auto custom-scrollbar px-6 py-6">
                {error && (
                    <div className="mb-4 p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                        {error}
                    </div>
                )}

                {loading ? (
                    <div className="flex items-center justify-center h-64">
                        <div className="flex flex-col items-center gap-3">
                            <Loader2 size={32} className="text-primary animate-spin" />
                            <p className="text-slate-500 dark:text-zinc-400">{t("social.loadPost","Chargement des publications...")}</p>
                        </div>
                    </div>
                ) : publications.length === 0 ? (
                    <div className="flex items-center justify-center h-64">
                        <div className="text-center">
                            <p className="text-slate-500 dark:text-zinc-400 mb-2">{t("social.noPostFound","Aucune publication trouvée")}</p>
                            <p className="text-xs text-slate-400 dark:text-zinc-500">{t("social.postsWillAppear","Les publications apparaîtront ici dès qu'elles seront créées.")}</p>
                        </div>
                    </div>
                ) : (
                    <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                        {publications.map((pub) => {
                            const badge = getStatusBadge(pub.status);
                            return (
                                <div
                                    key={pub.id}
                                    className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/[0.03] hover:bg-white/[0.06] transition-colors overflow-hidden"
                                >
                                    {/* En-tête avec plateforme */}
                                    <div className="p-4 border-b border-slate-200 dark:border-white/5 flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <span className="text-2xl">{getPlatformIcon(pub.platform)}</span>
                                            <div>
                                                <p className="text-xs uppercase font-semibold text-slate-500 dark:text-zinc-400 tracking-wider">
                                                    {pub.platform}
                                                </p>
                                            </div>
                                        </div>
                                        <div className={`px-2 py-1 rounded-full border text-xs font-medium ${badge.bg} ${badge.border} ${badge.text}`}>
                                            {badge.label}
                                        </div>
                                    </div>

                                    {/* Contenu */}
                                    <div className="p-4 space-y-3">
                                        {/* ID Externe */}
                                        {pub.external_id && (
                                            <div>
                                                <p className="text-[10px] text-slate-400 dark:text-zinc-500 uppercase tracking-wider mb-1">{t("common.externID","ID externe")}</p>
                                                <p className="font-mono text-xs text-slate-700 dark:text-zinc-300 truncate" title={pub.external_id}>
                                                    {pub.external_id}
                                                </p>
                                            </div>
                                        )}

                                        {/* Dates */}
                                        <div className="space-y-2">
                                            <div>
                                                <p className="text-[10px] text-slate-400 dark:text-zinc-500 uppercase tracking-wider mb-1 flex items-center gap-1">
                                                    <Calendar size={10} /> {t("common.created","Créée")}
                                                </p>
                                                <p className="text-xs text-slate-700 dark:text-zinc-300">
                                                    {formatDate(pub.created_at)}
                                                </p>
                                            </div>
                                            {pub.completed_at && (
                                                <div>
                                                    <p className="text-[10px] text-slate-400 dark:text-zinc-500 uppercase tracking-wider mb-1 flex items-center gap-1">
                                                        <Calendar size={10} /> {t("common.complete","Complétée")}
                                                    </p>
                                                    <p className="text-xs text-slate-700 dark:text-zinc-300">
                                                        {formatDate(pub.completed_at)}
                                                    </p>
                                                </div>
                                            )}
                                        </div>

                                        {/* Erreur */}
                                        {pub.error_message && (
                                            <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                                                <p className="text-[10px] text-red-400 font-medium mb-1">{t("common.error","Erreur")}</p>
                                                <p className="text-xs text-red-300 line-clamp-2">{pub.error_message}</p>
                                            </div>
                                        )}

                                        {/* Actions */}
                                        <div className="flex gap-2 pt-2">
                                            {pub.external_id && ["done", "processing"].includes(pub.status) && (
                                                <a
                                                    href={`https://${pub.platform === 'facebook' ? 'facebook.com' : pub.platform === 'instagram' ? 'instagram.com' : pub.platform === 'tiktok' ? 'tiktok.com' : 'youtube.com'}/${pub.external_id}`}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="flex-1 flex items-center justify-center gap-1 px-2 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary text-xs font-medium transition-colors"
                                                >
                                                    <ExternalLink size={12} />
                                                    {t("common.view","Voir")}
                                                </a>
                                            )}
                                            <button
                                                onClick={() => {
                                                    if (confirm("Êtes-vous sûr de vouloir supprimer cette publication ?")) {
                                                        // TODO: Implémenter la suppression
                                                    }
                                                }}
                                                className="flex-1 flex items-center justify-center gap-1 px-2 py-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs font-medium transition-colors"
                                            >
                                                <Trash2 size={12} />
                                                {t("reels.delete","Supprimer")}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="border-t border-slate-200 dark:border-white/5 bg-background/50 backdrop-blur-md px-6 py-4 shrink-0 flex items-center justify-between">
                    <p className="text-sm text-slate-500 dark:text-zinc-400">
                        Page <span className="font-semibold text-white">{page}</span> sur{" "}
                        <span className="font-semibold text-white">{totalPages}</span>
                    </p>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setPage(Math.max(1, page - 1))}
                            disabled={page === 1}
                            className="px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
                        >
                            {t("common.previous","Précédent")}
                        </button>
                        <button
                            onClick={() => setPage(Math.min(totalPages, page + 1))}
                            disabled={page === totalPages}
                            className="px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
                        >
                            {t("common.next","Suivant")}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}


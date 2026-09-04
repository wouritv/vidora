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

const getPlatformHost = (platform) => {
    const hosts = {
        facebook: "facebook.com",
        instagram: "instagram.com",
        tiktok: "tiktok.com",
        youtube: "youtube.com",
        linkedin: "linkedin.com",
    };
    return hosts[platform] || "youtube.com";
};

const getStatusBadge = (status) => {
    const badges = {
        pending: { bg: "bg-amber-100 dark:bg-yellow-500/10", border: "border-amber-300 dark:border-yellow-500/20", text: "text-amber-800 dark:text-yellow-400", label: "En attente" },
        processing: { bg: "bg-sky-100 dark:bg-blue-500/10", border: "border-sky-300 dark:border-blue-500/20", text: "text-sky-800 dark:text-blue-400", label: "En cours" },
        done: { bg: "bg-emerald-100 dark:bg-green-500/10", border: "border-emerald-300 dark:border-green-500/20", text: "text-emerald-800 dark:text-green-400", label: "Publié" },
        failed: { bg: "bg-rose-100 dark:bg-red-500/10", border: "border-rose-300 dark:border-red-500/20", text: "text-rose-800 dark:text-red-400", label: "Échoué" },
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

const SocialPublicationCard = ({ pub, badge, t, deletingId, onDeletePublication }) => {
    return (
        <div
            className="rounded-xl border border-slate-300 dark:border-white/10 bg-white dark:bg-white/[0.03] hover:bg-slate-50 dark:hover:bg-white/[0.06] transition-colors overflow-hidden"
        >
            <div className="p-4 border-b border-slate-200 dark:border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="text-2xl">{getPlatformIcon(pub.platform)}</span>
                    <div>
                        <p className="text-xs uppercase font-semibold text-slate-500 dark:text-zinc-400 tracking-wider">{pub.platform}</p>
                    </div>
                </div>
                <div className={`px-2 py-1 rounded-full border text-xs font-medium ${badge.bg} ${badge.border} ${badge.text}`}>
                    {badge.label}
                </div>
            </div>

            <div className="p-4 space-y-3">
                <SocialPublicationExternalId externalId={pub.external_id} t={t} />

                <div className="space-y-2">
                    <div>
                        <p className="text-[10px] text-slate-400 dark:text-zinc-500 uppercase tracking-wider mb-1 flex items-center gap-1">
                            <Calendar size={10} /> {t("common.created", "Créée")}
                        </p>
                        <p className="text-xs text-slate-700 dark:text-zinc-300">{formatDate(pub.created_at)}</p>
                    </div>
                    <SocialPublicationCompletedAt completedAt={pub.completed_at} t={t} />
                </div>

                {pub.error_message && (
                    <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                        <p className="text-[10px] text-red-400 font-medium mb-1">{t("common.error", "Erreur")}</p>
                        <p className="text-xs text-red-300 line-clamp-2">{pub.error_message}</p>
                    </div>
                )}

                <SocialPublicationActions
                    pub={pub}
                    deletingId={deletingId}
                    onDeletePublication={onDeletePublication}
                    t={t}
                />
            </div>
        </div>
    );
};

const SocialPublicationActions = ({ pub, deletingId, onDeletePublication, t }) => {
    const canViewPublication = pub.external_id && ["done", "processing"].includes(pub.status);

    return (
        <div className="flex gap-2 pt-2">
            {canViewPublication && (
                <a
                    href={`https://${getPlatformHost(pub.platform)}/${pub.external_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 flex items-center justify-center gap-1 px-2 py-2 rounded-lg border border-sky-300 dark:border-primary/30 bg-sky-100 dark:bg-primary/10 hover:bg-sky-200 dark:hover:bg-primary/20 text-sky-800 dark:text-primary text-xs font-medium transition-colors shadow-sm"
                >
                    <ExternalLink size={12} />
                    {t("common.see", "Voir")}
                </a>
            )}
            <button
                onClick={() => onDeletePublication(pub)}
                disabled={deletingId === pub.id}
                className="flex-1 flex items-center justify-center gap-1 px-2 py-2 rounded-lg border border-rose-300 dark:border-red-500/30 bg-rose-100 dark:bg-red-500/10 hover:bg-rose-200 dark:hover:bg-red-500/20 text-rose-800 dark:text-red-400 text-xs font-medium transition-colors shadow-sm disabled:opacity-50"
            >
                {deletingId === pub.id ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                {t("reels.delete", "Supprimer")}
            </button>
        </div>
    );
};

const SocialPublicationExternalId = ({ externalId, t }) => {
    if (!externalId) return null;

    return (
        <div>
            <p className="text-[10px] text-slate-400 dark:text-zinc-500 uppercase tracking-wider mb-1">{t("common.externID", "ID externe")}</p>
            <p className="font-mono text-xs text-slate-700 dark:text-zinc-300 truncate" title={externalId}>{externalId}</p>
        </div>
    );
};

const SocialPublicationCompletedAt = ({ completedAt, t }) => {
    if (!completedAt) return null;

    return (
        <div>
            <p className="text-[10px] text-slate-400 dark:text-zinc-500 uppercase tracking-wider mb-1 flex items-center gap-1">
                <Calendar size={10} /> {t("common.complete", "Complétée")}
            </p>
            <p className="text-xs text-slate-700 dark:text-zinc-300">{formatDate(completedAt)}</p>
        </div>
    );
};

const renderSocialPublicationsContent = ({ error, loading, publications, deletingId, t, onDeletePublication }) => {
    if (error) {
        return (
            <div className="mb-4 p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {error}
            </div>
        );
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="flex flex-col items-center gap-3">
                    <Loader2 size={32} className="text-primary animate-spin" />
                    <p className="text-slate-500 dark:text-zinc-400">{t("social.loadPost", "Chargement des publications...")}</p>
                </div>
            </div>
        );
    }

    if (publications.length === 0) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-center">
                    <p className="text-slate-500 dark:text-zinc-400 mb-2">{t("social.noPostFound", "Aucune publication trouvée")}</p>
                    <p className="text-xs text-slate-400 dark:text-zinc-500">{t("social.postsWillAppear", "Les publications apparaîtront ici dès qu'elles seront créées.")}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {publications.map((pub) => {
                const badge = getStatusBadge(pub.status);
                return (
                    <SocialPublicationCard
                        key={pub.id}
                        pub={pub}
                        badge={badge}
                        t={t}
                        deletingId={deletingId}
                        onDeletePublication={onDeletePublication}
                    />
                );
            })}
        </div>
    );
};

const deleteSocialPublication = async ({
    publication,
    userId,
    setDeletingId,
    setPublications,
    setTotal,
    setError,
    t,
}) => {
    if (!publication?.id) return;

    const confirmMessage = t("social.confirmDelete", "Delete this publication?");
    if (!window.confirm(confirmMessage)) return;

    try {
        setDeletingId(publication.id);
        const response = await fetch(getApiUrl(`/api/social/publish-jobs/${publication.id}`), {
            method: "DELETE",
            headers: {
                "X-User-Id": userId,
            },
        });

        if (!response.ok) {
            const detail = await response.text();
            throw new Error(detail || t("social.deleteFailed", "Deletion failed"));
        }

        setPublications((prev) => prev.filter((item) => item.id !== publication.id));
        setTotal((prev) => Math.max(0, prev - 1));
    } catch (err) {
        setError(err.message || t("social.deleteFailed", "Deletion failed"));
    } finally {
        setDeletingId("");
    }
};

const fetchSocialPublications = async ({
    userId,
    page,
    pageSize,
    platform,
    status,
    dateFilter,
    customDateStart,
    customDateEnd,
    searchInput,
}) => {
    const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
    });
    if (platform !== "all") params.set("platform", platform);
    if (status !== "all") params.set("status", status);
    if (dateFilter !== "all") params.set("date_filter", dateFilter);
    if (dateFilter === "custom") {
        if (customDateStart) params.set("date_from", customDateStart);
        if (customDateEnd) params.set("date_to", customDateEnd);
    }
    if (searchInput) params.set("search", searchInput);

    const response = await fetch(getApiUrl(`/api/social/publish-jobs?${params.toString()}`), {
        headers: {
            "X-User-Id": userId,
        },
    });

    if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Erreur lors du chargement des publications");
    }

    const data = await response.json();
    return {
        items: Array.isArray(data.items) ? data.items : [],
        total: data.total || 0,
    };
};

const renderPublicationCount = (total) => {
    if (total <= 0) return null;

    return (
        <div className="text-sm text-slate-500 dark:text-zinc-400">
            <span className="font-semibold text-slate-900 dark:text-white">{total}</span> publication{total !== 1 ? "s" : ""}
        </div>
    );
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
    const [customDateStart, setCustomDateStart] = useState("");
    const [customDateEnd, setCustomDateEnd] = useState("");
    const [searchInput, setSearchInput] = useState("");
    const [deletingId, setDeletingId] = useState("");

    useEffect(() => {
        if (!user?.id) return;

        let cancelled = false;
        async function loadPublications() {
            try {
                setLoading(true);
                setError("");

                const data = await fetchSocialPublications({
                    userId: user.id,
                    page,
                    pageSize,
                    platform,
                    status,
                    dateFilter,
                    customDateStart,
                    customDateEnd,
                    searchInput,
                });

                if (cancelled) return;
                setPublications(data.items);
                setTotal(data.total);
            } catch (err) {
                if (!cancelled) {
                    console.error("Error loading publications:", err);
                    setError(err.message || "Erreur réseau");
                    setPublications([]);
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        loadPublications();

        return () => {
            cancelled = true;
        };
    }, [user?.id, page, platform, status, dateFilter, customDateStart, customDateEnd, searchInput, pageSize]);

    const totalPages = Math.max(1, Math.ceil(total / pageSize));

    const handleResetFilters = () => {
        setPlatform("all");
        setStatus("all");
        setDateFilter("all");
        setCustomDateStart("");
        setCustomDateEnd("");
        setSearchInput("");
        setPage(1);
    };

    const content = renderSocialPublicationsContent({
        error,
        loading,
        publications,
        deletingId,
        t,
        onDeletePublication: (publication) =>
            deleteSocialPublication({
                publication,
                userId: user.id,
                setDeletingId,
                setPublications,
                setTotal,
                setError,
                t,
            }),
    });

    return (
        <div className="h-full flex flex-col bg-background overflow-hidden">
            {/* Header */}
            <div className="border-b border-slate-200 dark:border-white/5 bg-background/50 backdrop-blur-md px-6 py-4 shrink-0">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h1 className="text-3xl font-black tracking-tight">{t('social.socialPublications', 'Publications sociales')}</h1>
                        <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1">{t('social.realTimeTracking', 'Suivi en temps réel de vos publications')}</p>
                    </div>
                    {renderPublicationCount(total)}
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
                            className="w-full pl-9 pr-3 py-2 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-300 dark:border-white/10 text-sm text-slate-900 dark:text-white placeholder-slate-500 dark:placeholder-zinc-500 focus:outline-none focus:bg-white dark:focus:bg-white/10 focus:border-primary/50"
                        />
                    </div>

                    {/* Plateforme */}
                    <select
                        value={platform}
                        onChange={(e) => {
                            setPlatform(e.target.value);
                            setPage(1);
                        }}
                        className="px-3 py-2 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-300 dark:border-white/10 text-sm text-slate-900 dark:text-white focus:outline-none focus:bg-white dark:focus:bg-white/10 focus:border-primary/50"
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
                        className="px-3 py-2 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-300 dark:border-white/10 text-sm text-slate-900 dark:text-white focus:outline-none focus:bg-white dark:focus:bg-white/10 focus:border-primary/50"
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
                            if (e.target.value !== "custom") {
                                setCustomDateStart("");
                                setCustomDateEnd("");
                            }
                            setPage(1);
                        }}
                        className="px-3 py-2 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-300 dark:border-white/10 text-sm text-slate-900 dark:text-white focus:outline-none focus:bg-white dark:focus:bg-white/10 focus:border-primary/50"
                    >
                        <option value="all">{t("common.allDates","Toutes les dates")}</option>
                        <option value="today">{t("common.today","Aujourd'hui")}</option>
                        <option value="week">{t("common.week","Cette semaine")}</option>
                        <option value="month">{t("common.month","Ce mois")}</option>
                        <option value="custom">{t("common.customPeriod","Période personnalisée")}</option>
                    </select>

                    {dateFilter === "custom" ? (
                        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-300 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-2">
                            <input
                                type="date"
                                value={customDateStart}
                                onChange={(e) => {
                                    setCustomDateStart(e.target.value);
                                    setPage(1);
                                }}
                                className="px-3 py-2 rounded-lg bg-white dark:bg-black/20 border border-slate-300 dark:border-white/10 text-sm text-slate-900 dark:text-white focus:outline-none focus:border-primary/50 [color-scheme:light] dark:[color-scheme:dark]"
                                aria-label={t("common.startDate", "Date de début")}
                            />
                            <span className="text-xs font-medium text-slate-600 dark:text-zinc-400">→</span>
                            <input
                                type="date"
                                value={customDateEnd}
                                min={customDateStart || undefined}
                                onChange={(e) => {
                                    setCustomDateEnd(e.target.value);
                                    setPage(1);
                                }}
                                className="px-3 py-2 rounded-lg bg-white dark:bg-black/20 border border-slate-300 dark:border-white/10 text-sm text-slate-900 dark:text-white focus:outline-none focus:border-primary/50 [color-scheme:light] dark:[color-scheme:dark]"
                                aria-label={t("common.endDate", "Date de fin")}
                            />
                        </div>
                    ) : null}

                    {/* Réinitialiser */}
                    {(platform !== "all" || status !== "all" || dateFilter !== "all" || searchInput) && (
                        <button
                            onClick={handleResetFilters}
                            className="px-3 py-2 rounded-lg bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 border border-slate-300 dark:border-white/10 text-sm font-medium text-slate-800 dark:text-white transition-colors flex items-center gap-2 shadow-sm"
                        >
                            <Filter size={14} />
                            {t("common.reset","Réinitialiser")}
                        </button>
                    )}
                </div>
            </div>

            {/* Contenu */}
            <div className="flex-1 overflow-y-auto custom-scrollbar px-6 py-6">
                {content}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="border-t border-slate-200 dark:border-white/5 bg-background/50 backdrop-blur-md px-6 py-4 shrink-0 flex items-center justify-between">
                    <p className="text-sm text-slate-500 dark:text-zinc-400">
                        Page <span className="font-semibold text-slate-900 dark:text-white">{page}</span> sur{" "}
                        <span className="font-semibold text-slate-900 dark:text-white">{totalPages}</span>
                    </p>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setPage(Math.max(1, page - 1))}
                            disabled={page === 1}
                            className="px-3 py-2 rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium text-slate-800 dark:text-white transition-colors shadow-sm"
                        >
                            {t("common.previous","Précédent")}
                        </button>
                        <button
                            onClick={() => setPage(Math.min(totalPages, page + 1))}
                            disabled={page === totalPages}
                            className="px-3 py-2 rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium text-slate-800 dark:text-white transition-colors shadow-sm"
                        >
                            {t("common.next","Suivant")}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}


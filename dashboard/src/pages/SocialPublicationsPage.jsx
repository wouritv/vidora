import { useEffect, useState } from "react";
import { Loader2, Search, Trash2, ExternalLink, Calendar, Filter } from "lucide-react";
import { getApiUrl } from "../config";
import { getAuthHeaders } from "../lib/apiAuth";
import { useAuth } from "../state/AuthContext";
import { useTranslation } from "../state/LanguageContext";

const PLATFORMS = [
    { value: "facebook", label: "Facebook" },
    { value: "instagram", label: "Instagram" },
    { value: "tiktok", label: "TikTok" },
    { value: "youtube", label: "YouTube" },
    { value: "linkedin", label: "LinkedIn" },
];


const getPlatformIconColorClass = (platform) => {
    const colors = {
        facebook: "text-[#1877F2]",
        instagram: "text-[#E4405F]",
        tiktok: "text-slate-900 dark:text-white",
        youtube: "text-[#FF0000]",
        linkedin: "text-[#0A66C2]",
    };
    return colors[platform] || "text-slate-500 dark:text-zinc-400";
};

const PLATFORM_BRAND_PATHS = {
    facebook:
        "M24 12.073C24 5.405 18.627 0 12 0S0 5.405 0 12.073c0 6.016 4.388 10.993 10.125 11.854V15.49H7.078v-3.417h3.047V9.469c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.931-1.956 1.887v2.198h3.328l-.532 3.417h-2.796v8.437C19.612 23.066 24 18.089 24 12.073z",
    instagram:
        "M7.75 2C4.575 2 2 4.575 2 7.75v8.5C2 19.425 4.575 22 7.75 22h8.5C19.425 22 22 19.425 22 16.25v-8.5C22 4.575 19.425 2 16.25 2h-8.5zm0 1.8h8.5a3.95 3.95 0 0 1 3.95 3.95v8.5a3.95 3.95 0 0 1-3.95 3.95h-8.5a3.95 3.95 0 0 1-3.95-3.95v-8.5a3.95 3.95 0 0 1 3.95-3.95zm9.45 1.35a1.2 1.2 0 1 0 0 2.4 1.2 1.2 0 0 0 0-2.4zM12 6.65A5.35 5.35 0 1 0 12 17.35 5.35 5.35 0 0 0 12 6.65zm0 1.8A3.55 3.55 0 1 1 12 15.55 3.55 3.55 0 0 1 12 8.45z",
    tiktok:
        "M19.589 6.686a4.793 4.793 0 0 1-3.77-4.245V2h-3.445v13.672a2.896 2.896 0 0 1-5.201 1.743l-.002-.001.002.001a2.895 2.895 0 0 1 3.183-4.51v-3.5a6.329 6.329 0 0 0-5.394 10.692 6.33 6.33 0 0 0 10.857-4.424V8.687a8.182 8.182 0 0 0 4.773 1.526V6.79a4.831 4.831 0 0 1-1.003-.104z",
    youtube:
        "M23.498 6.186a2.997 2.997 0 0 0-2.11-2.12C19.53 3.545 12 3.545 12 3.545s-7.53 0-9.389.52a2.997 2.997 0 0 0-2.11 2.121C0 8.051 0 12 0 12s0 3.949.502 5.814a2.997 2.997 0 0 0 2.11 2.12c1.859.52 9.389.52 9.389.52s7.53 0 9.389-.52a2.997 2.997 0 0 0 2.11-2.12C24 15.949 24 12 24 12s0-3.949-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z",
    linkedin:
        "M20.447 20.452H16.89v-5.569c0-1.328-.024-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.345V9h3.414v1.561h.049c.476-.9 1.637-1.85 3.367-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 1 1 0-4.124 2.062 2.062 0 0 1 0 4.124zM7.119 20.452H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z",
    default:
        "M12 2a10 10 0 1 0 10 10A10.011 10.011 0 0 0 12 2zm0 2a8 8 0 0 1 8 8 7.907 7.907 0 0 1-1.54 4.7A11.117 11.117 0 0 0 12 14.6a11.117 11.117 0 0 0-6.46 2.1A7.907 7.907 0 0 1 4 12a8 8 0 0 1 8-8zm0 16a7.963 7.963 0 0 1-4.89-1.67 9.145 9.145 0 0 1 9.78 0A7.963 7.963 0 0 1 12 20z",
};

const PlatformBrandIcon = ({ platform }) => {
    const className = `h-5 w-5 ${getPlatformIconColorClass(platform)}`;
    const path = PLATFORM_BRAND_PATHS[platform] || PLATFORM_BRAND_PATHS.default;

    return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
            <path d={path} />
        </svg>
    );
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
                    <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-white dark:bg-zinc-900/70 border border-slate-200 dark:border-white/10">
                        <PlatformBrandIcon platform={pub.platform} />
                    </span>
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
                ...getAuthHeaders(userId),
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
            ...getAuthHeaders(userId),
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

const getPublicationCountLabel = (total, t) => {
    return total === 1
        ? t("social.publicationCount", "publication")
        : t("social.publicationsCount", "publications");
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
            {total > 0 && (
                <div className="border-t border-slate-300 dark:border-white/10 bg-background/50 backdrop-blur-md px-6 py-4 shrink-0 flex items-center justify-between text-sm">
                    <p className="text-sm text-slate-500 dark:text-zinc-400">
                        <span className="font-semibold text-slate-900 dark:text-white">{total}</span>{" "}
                        {getPublicationCountLabel(total, t)}
                    </p>
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={() => setPage(Math.max(1, page - 1))}
                            disabled={page === 1}
                            className="rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-3 py-1.5 font-medium text-slate-800 dark:text-zinc-300 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-40"
                        >
                            {t("common.previous", "Previous")}
                        </button>
                        <span className="text-slate-500 dark:text-zinc-400">{t("common.page", "Page")} {page} / {totalPages}</span>
                        <button
                            type="button"
                            onClick={() => setPage(Math.min(totalPages, page + 1))}
                            disabled={page === totalPages}
                            className="rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-3 py-1.5 font-medium text-slate-800 dark:text-zinc-300 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-40"
                        >
                            {t("common.next", "Next")}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}


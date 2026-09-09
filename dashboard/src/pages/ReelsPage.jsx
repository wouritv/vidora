import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Play, Plus, Download, Loader2, Search, Share2, Trash2, X } from "lucide-react";
import { fetchAppConfig, getApiUrl, getDefaultHideSocialPlatforms } from "../config";
import { useAuth } from "../state/AuthContext";
import { useUserCredits } from "../state/UserCreditsContext";
import { useNavigate } from "react-router-dom";
import ResultCard from "../components/ResultCard";
import SharePostModal from "../components/SharePostModal";
import MobileFilterDropdown from "../components/MobileFilterDropdown";
import { getConnectedPlatforms } from "../lib/platforms";
import { toResultCardClip } from "../lib/clips";
import { statusLabel, statusClass } from "../lib/status";
import { getAuthHeaders } from "../lib/apiAuth";
import { useTranslation } from "../state/LanguageContext";

export default function ReelsPage({ projectId = "" }) {
    const { user } = useAuth();
    const { credits, defaultCosts } = useUserCredits();
    const {t} = useTranslation();
    const connectedPlatforms = getConnectedPlatforms();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [page, setPage] = useState(1);
    const [pageSize] = useState(15);
    const [total, setTotal] = useState(0);
    const [queryInput, setQueryInput] = useState("");
    const [query, setQuery] = useState("");
    const [status, setStatus] = useState("");
    const [sharingId, setSharingId] = useState("");
    const [shareResult, setShareResult] = useState(null);
    const [shareModalItem, setShareModalItem] = useState(null);
    const [shareTitle, setShareTitle] = useState("");
    const [shareDescription, setShareDescription] = useState("");
    const [sharePlatforms, setSharePlatforms] = useState({
        tiktok: true,
        instagram: true,
        youtube: true,
        facebook: false,
        linkedin: false,
    });
    const [shareScheduling, setShareScheduling] = useState(false);
    const [shareScheduleDate, setShareScheduleDate] = useState("");
    const [deletingId, setDeletingId] = useState("");
    const [previewItem, setPreviewItem] = useState(null);
    const [previewUrl, setPreviewUrl] = useState("");
    const [hideSocialPlatforms, setHideSocialPlatforms] = useState(getDefaultHideSocialPlatforms());
    const [projectMeta, setProjectMeta] = useState(null);
    const navigate = useNavigate();

    const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);
    const publicationCostEstimate = Number(defaultCosts?.publication || 1);
    const hasAnyReelCredit = Number(credits || 0) > 0;
    const canShareReel = credits >= publicationCostEstimate;
    const statusOptions = [
        { value: "", label: t('reels.allStatuses', 'All statuses') },
        { value: "en_cours", label: t("reels.statusInProgress", "In progress") },
        { value: "termine", label: t("reels.statusDone", "Done") },
        { value: "echec", label: t("reels.statusFailed", "Failed") },
    ];


    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1);
            setQuery(queryInput.trim());
        }, 350);
        return () => clearTimeout(timer);
    }, [queryInput]);

    useEffect(() => {
        let active = true;
        fetchAppConfig()
            .then((cfg) => {
                if (!active || !cfg || typeof cfg.hideSocialPlatforms !== "boolean") return;
                setHideSocialPlatforms(cfg.hideSocialPlatforms);
            })
            .catch(() => {});
        return () => {
            active = false;
        };
    }, []);

    useEffect(() => {
        if (!user?.id) return;

        let cancelled = false;
        async function loadReels() {
            setLoading(true);
            setError("");

            try {
                let response;
                if (projectId) {
                    response = await fetch(getApiUrl(`/api/projects/${projectId}/reels`), {
                        headers: {
                            ...getAuthHeaders(user.id),
                        },
                    });
                } else {
                    const params = new URLSearchParams({
                        page: String(page),
                        page_size: String(pageSize),
                    });
                    if (query) params.set("q", query);
                    if (status) params.set("status", status);
                    response = await fetch(getApiUrl(`/api/reels?${params.toString()}`), {
                        headers: {
                            ...getAuthHeaders(user.id),
                        },
                    });
                }

                const data = await response.json();
                if (cancelled) return;

                if (!response.ok) {
                    const detail = data?.detail || "Unable to load reels";
                    setError(detail);
                    setItems([]);
                    return;
                }

                const rawItems = projectId ? data.reels : data.items;
                const nextItems = Array.isArray(rawItems) ? rawItems : [];
                const filteredItems = projectId
                    ? nextItems.filter((item) => {
                        const matchesQuery = !query || `${item.reel_title || ""} ${item.reel_description || ""}`.toLowerCase().includes(query.toLowerCase());
                        const matchesStatus = !status || item.reel_status === status;
                        return matchesQuery && matchesStatus;
                    })
                    : nextItems;

                setItems(filteredItems);
                setTotal(projectId ? filteredItems.length : Number(data.total || 0));
            } catch (err) {
                if (cancelled) return;
                setError(err.message || "Unable to load reels");
                setItems([]);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        async function loadProjectMeta() {
            if (!projectId) {
                setProjectMeta(null);
                return;
            }
            try {
                const response = await fetch(getApiUrl(`/api/projects/${projectId}`), {
                    headers: {
                        ...getAuthHeaders(user.id),
                    },
                });
                const data = await response.json();
                if (cancelled) return;
                if (response.ok) {
                    setProjectMeta(data || null);
                }
            } catch {
                // Best effort only for heading context.
            }
        }

        loadProjectMeta();
        loadReels();
        return () => {
            cancelled = true;
        };
    }, [user?.id, page, pageSize, query, status, projectId]);

    const refresh = async () => {
        if (!user?.id) return;
        setLoading(true);
        try {
            let response;
            if (projectId) {
                response = await fetch(getApiUrl(`/api/projects/${projectId}/reels`), {
                    headers: { ...getAuthHeaders(user.id) },
                });
            } else {
                const params = new URLSearchParams({
                    page: String(page),
                    page_size: String(pageSize),
                });
                if (query) params.set("q", query);
                if (status) params.set("status", status);
                response = await fetch(getApiUrl(`/api/reels?${params.toString()}`), {
                    headers: { ...getAuthHeaders(user.id) },
                });
            }
            const data = await response.json();
            if (!response.ok) {
                setError(data?.detail || "Refresh failed");
                setItems([]);
                return;
            }
            const rawItems = projectId ? data.reels : data.items;
            const nextItems = Array.isArray(rawItems) ? rawItems : [];
            const filteredItems = projectId
                ? nextItems.filter((item) => {
                    const matchesQuery = !query || `${item.reel_title || ""} ${item.reel_description || ""}`.toLowerCase().includes(query.toLowerCase());
                    const matchesStatus = !status || item.reel_status === status;
                    return matchesQuery && matchesStatus;
                })
                : nextItems;
            setItems(filteredItems);
            setTotal(projectId ? filteredItems.length : Number(data.total || 0));
        } catch (err) {
            setError(err.message || "Refresh failed");
        } finally {
            setLoading(false);
        }
    };

    const fetchFreshMediaUrl = async (reelId) => {
        const response = await fetch(getApiUrl(`/api/reels/${reelId}/media-url`), {
            headers: { ...getAuthHeaders(user.id) },
        });
        if (!response.ok) return null;
        const data = await response.json();
        return data.media_url || null;
    };

    const handleDelete = async (reelId) => {
        if (!user?.id) return;
        if (!globalThis.confirm(t("reels.confirmDelete", "Delete this reel?"))) return;

        setDeletingId(reelId);
        try {
            const response = await fetch(getApiUrl(`/api/reels/${reelId}`), {
                method: "DELETE",
                headers: {
                    ...getAuthHeaders(user.id),
                },
            });
            if (!response.ok) {
                const detail = await response.text();
                setError(detail || "Delete failed");
                return;
            }
            await refresh();
        } catch (err) {
            globalThis.alert(err.message || "Delete failed");
        } finally {
            setDeletingId("");
        }
    };

    const handleDownload = async (reelId) => {
        if (!user?.id) return;
        const currentItem = items.find((item) => item.id === reelId);
        const fallbackUrl = currentItem?.reel_download_url || currentItem?.reel_playback_url || currentItem?.reel_url || null;
        const mediaUrl = await fetchFreshMediaUrl(reelId);
        if (!mediaUrl) {
            if (fallbackUrl) {
                globalThis.open(fallbackUrl, "_blank", "noopener,noreferrer");
                return;
            }
            globalThis.alert(t("reels.noDownloadUrl", "No download URL available"));
            return;
        }

        globalThis.open(mediaUrl, "_blank", "noopener,noreferrer");
    };

    const handleShare = (item) => {
        if (!canShareReel) {
            setShareResult({ success: false, msg: t("reels.shareDisabledInsufficient", "Insufficient credits. Sharing is disabled.") });
            return;
        }
        const fallbackPlatforms = ['tiktok', 'instagram', 'youtube'];
        const nextDefaultPlatforms = connectedPlatforms.length > 0 ? connectedPlatforms : fallbackPlatforms;
        setSharePlatforms({
            tiktok: nextDefaultPlatforms.includes('tiktok'),
            instagram: nextDefaultPlatforms.includes('instagram'),
            youtube: nextDefaultPlatforms.includes('youtube'),
            facebook: nextDefaultPlatforms.includes('facebook'),
            linkedin: nextDefaultPlatforms.includes('linkedin'),
        });
        setShareTitle(item?.reel_title || t("reels.defaultShareTitle", "Viral Short"));
        setShareDescription(item?.reel_description || "");
        setShareScheduling(false);
        setShareScheduleDate("");
        setShareResult(null);
        setShareModalItem(item);
    };

    const submitShare = async () => {
        if (!user?.id) return;
        if (!shareModalItem?.id) return;
        if (!canShareReel) {
            setShareResult({ success: false, msg: t("reels.shareDisabledInsufficient", "Insufficient credits. Sharing is disabled.") });
            return;
        }

        const selectedPlatforms = Object.keys(sharePlatforms).filter((k) => Boolean(sharePlatforms[k]));
        if (selectedPlatforms.length === 0) {
            setShareResult({ success: false, msg: t("reels.selectAtLeastOnePlatform", "Select at least one platform.") });
            return;
        }
        if (shareScheduling && !shareScheduleDate) {
            setShareResult({ success: false, msg: t("reels.selectDateTime", "Please select a date and time.") });
            return;
        }

        setSharingId(shareModalItem.id);
        setShareResult(null);
        try {
            const payload = {
                platforms: selectedPlatforms,
                title: shareTitle || undefined,
                description: shareDescription || undefined,
            };
            if (shareScheduling && shareScheduleDate) {
                payload.scheduled_date = new Date(shareScheduleDate).toISOString();
                payload.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            }

            const response = await fetch(getApiUrl(`/api/reels/${shareModalItem.id}/share`), {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...getAuthHeaders(user.id),
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const errText = await response.text();
                let msg = t("reels.shareFailed", "Share failed");
                try {
                    const parsed = JSON.parse(errText);
                    msg = parsed?.detail || errText || msg;
                } catch {
                    msg = errText || msg;
                }
                setShareResult({ success: false, msg: `${t("reels.failedPrefix", "Failed")}: ${msg}` });
                return;
            }

            setShareResult({ success: true, msg: t("reels.shareSent", "Share request sent.") });
            setTimeout(() => {
                setShareResult(null);
                setShareModalItem(null);
            }, 1500);
        } catch (err) {
            setShareResult({ success: false, msg: `${t("reels.failedPrefix", "Failed")}: ${err.message || t("reels.shareFailed", "Share failed")}` });
        } finally {
            setSharingId("");
        }
    };



    const handlePreview = async (item) => {
        setPreviewItem(item);
        setPreviewUrl(item.media_url || item.reel_playback_url || item.reel_download_url || item.reel_url || "");
        const mediaUrl = await fetchFreshMediaUrl(item.id);
        if (mediaUrl) setPreviewUrl(mediaUrl);
    };

    const previewClip = previewItem ? toResultCardClip(previewItem, previewUrl) : null;
    const previewClipIndex = Number.isFinite(Number(previewItem?.reel_clip_index))
        ? Number(previewItem?.reel_clip_index)
        : 0;
    const previewJobId = typeof previewItem?.reel_job_id === "string" ? previewItem.reel_job_id : "";

    return (
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight">
                        {projectId ? (projectMeta?.name || t('projects.reelProjectTitle', 'Projet Reel')) : t('reels.title', 'Generated reels')}
                    </h1>
                    <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">
                        {projectId ? t('projects.reelProjectSubtitle', 'Contenus generes pour ce projet.') : t('reels.subtitle', 'Search, filter, delete, share and download.')}
                    </p>
                </div>

                {projectId ? (
                    <button
                        type="button"
                        onClick={() => navigate("/dashboard/reels")}
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                    >
                        <ArrowLeft size={14} />
                        {t('projects.backToProjects', 'Retour aux projets')}
                    </button>
                ) : (
                    <button
                        type="button"
                        onClick={() => {
                            navigate("/dashboard/reel-generator?new=1");
                        }}
                        className="flex items-center gap-2 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors group disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                        <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0">
                            <Plus size={16} />
                        </div>
                        <div className="hidden lg:block overflow-hidden">
                            <p className="text-sm font-bold text-white leading-none mb-0.5">{t('app.newOperation', 'New operation')}</p>
                        </div>
                    </button>
                )}
            </div>

            <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                {!hasAnyReelCredit ? (
                    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                        {t("common.insufficientCreditsStart", "Insufficient credits to start this operation.")}
                    </div>
                ) : null}
                {shareResult ? (
                    <div className={`rounded-lg border px-3 py-2 text-xs ${shareResult.success ? 'border-green-500/30 bg-green-500/10 text-green-300' : 'border-red-500/30 bg-red-500/10 text-red-300'}`}>
                        {shareResult.msg}
                    </div>
                ) : null}
                <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 md:grid-cols-[1fr_220px_auto_auto]">
                    <label className="relative">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-zinc-500" />
                        <input
                            value={queryInput}
                            onChange={(e) => setQueryInput(e.target.value)}
                            placeholder={t('reels.searchPlaceholder', 'Search by title or description...')}
                            className="w-full rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 py-2.5 pl-10 pr-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-primary/60"
                        />
                    </label>

                    <MobileFilterDropdown
                        value={status}
                        onChange={(nextValue) => {
                            setPage(1);
                            setStatus(nextValue);
                        }}
                        options={statusOptions}
                        ariaLabel={t('reels.allStatuses', 'All statuses')}
                    />

                    <select
                        value={status}
                        onChange={(e) => {
                            setPage(1);
                            setStatus(e.target.value);
                        }}
                        className="hidden rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white focus:outline-none focus:border-primary/60 md:block"
                    >
                        {statusOptions.map((option) => (
                            <option key={option.value || "all"} value={option.value}>{option.label}</option>
                        ))}
                    </select>

                    <button
                        type="button"
                        onClick={refresh}
                        className="rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                    >
                        {t('settings.refresh', 'Refresh')}
                    </button>

                </div>

                <div className="space-y-3 md:hidden">
                    {loading && (
                        <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-6 text-center text-slate-500 dark:text-zinc-400">
                            <span className="inline-flex items-center gap-2">
                                <Loader2 size={14} className="animate-spin" /> {t('reels.loading', 'Loading...')}
                            </span>
                        </div>
                    )}

                    {!loading && error && (
                        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-6 text-center text-red-300">{error}</div>
                    )}

                    {!loading && !error && items.length === 0 && (
                        <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-6 text-center text-slate-500 dark:text-zinc-400">
                            {t('common.noItemsFound', 'Aucun element trouve')}
                        </div>
                    )}

                    {!loading && !error && items.map((item) => (
                        <article key={item.id} className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 p-3 space-y-3">
                            <div className="space-y-1">
                                <p className="font-semibold text-slate-900 dark:text-white line-clamp-2">{item.reel_title || t("generatedMedia.untitled", "Untitled")}</p>
                                <p className="text-xs text-slate-500 dark:text-zinc-400 line-clamp-3">{item.reel_description || "-"}</p>
                            </div>

                            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
                                <span>{t("generatedMedia.tableDuration", "Duration")}: {item.reel_duration ? `${item.reel_duration}s` : "-"}</span>
                                <span>•</span>
                                <span>{item.reel_created_at ? new Date(item.reel_created_at).toLocaleString() : "-"}</span>
                            </div>

                            <div>
                                <span className={`inline-flex rounded-full border px-2 py-1 text-xs ${statusClass(item.reel_status)}`}>
                                    {statusLabel(item.reel_status)}
                                </span>
                            </div>

                            <div className="flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    onClick={() => handlePreview(item)}
                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-sky-300 dark:border-white/10 bg-sky-100 dark:bg-white/5 text-sky-800 dark:text-zinc-200 shadow-sm hover:bg-sky-200 dark:hover:bg-white/10"
                                    title={t('reels.preview', 'Preview')}
                                >
                                    <Play size={14} />
                                </button>

                                <button
                                    type="button"
                                    onClick={() => handleDownload(item.id)}
                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-indigo-300 dark:border-white/10 bg-indigo-100 dark:bg-white/5 text-indigo-800 dark:text-zinc-200 shadow-sm hover:bg-indigo-200 dark:hover:bg-white/10"
                                    title={t('reels.download', 'Download')}
                                >
                                    <Download size={14} />
                                </button>

                                {!hideSocialPlatforms ? (
                                    <button
                                        type="button"
                                        onClick={() => handleShare(item)}
                                        disabled={sharingId === item.id || !canShareReel}
                                        className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50"
                                        title={t('reels.share', 'Share')}
                                    >
                                        {sharingId === item.id ? <Loader2 size={14} className="animate-spin" /> : <Share2 size={14} />}
                                    </button>
                                ) : null}

                                <button
                                    type="button"
                                    onClick={() => handleDelete(item.id)}
                                    disabled={deletingId === item.id}
                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 disabled:opacity-50"
                                    title={t('reels.delete', 'Delete')}
                                >
                                    {deletingId === item.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                                </button>
                            </div>
                        </article>
                    ))}
                </div>

                <div className="hidden overflow-x-auto md:block">
                        <table className="min-w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-300 dark:border-white/10 text-left text-slate-500 dark:text-zinc-400 text-xs md:text-sm">
                                    <th className="px-2 md:px-3 py-3 font-medium">{t("reels.tableReel", "Reel")}</th>
                                    <th className="hidden md:table-cell px-2 md:px-3 py-3 font-medium">{t("generatedMedia.tableDescription", "Description")}</th>
                                    <th className="hidden sm:table-cell px-2 md:px-3 py-3 font-medium">{t("generatedMedia.tableDuration", "Duration")}</th>
                                    <th className="px-2 md:px-3 py-3 font-medium">{t("generatedMedia.tableStatus", "Status")}</th>
                                    <th className="hidden lg:table-cell px-2 md:px-3 py-3 font-medium">{t("generatedMedia.tableCreatedAt", "Created at")}</th>
                                    <th className="px-2 md:px-3 py-3 font-medium text-right">{t("generatedMedia.tableActions", "Actions")}</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading && (
                                    <tr>
                                        <td colSpan={6} className="px-3 py-10 text-center text-slate-500 dark:text-zinc-400">
                                            <span className="inline-flex items-center gap-2">
                                                <Loader2 size={14} className="animate-spin" /> {t('reels.loading', 'Loading...')}
                                            </span>
                                        </td>
                                    </tr>
                                )}

                                {!loading && error && (
                                    <tr>
                                        <td colSpan={6} className="px-3 py-10 text-center text-red-300">
                                            {error}
                                        </td>
                                    </tr>
                                )}

                                {!loading && !error && items.length === 0 && (
                                    <tr>
                                        <td colSpan={6} className="px-3 py-10 text-center text-slate-500 dark:text-zinc-400">
                                            {t('common.noItemsFound', 'Aucun element trouve')}
                                        </td>
                                    </tr>
                                )}

                                {!loading && !error &&
                                    items.map((item) => (
                                        <tr key={item.id} className="border-b border-slate-200 dark:border-white/5 align-top">
                                            <td className="px-2 md:px-3 py-2 md:py-3">
                                                <p className="font-semibold text-slate-900 dark:text-white line-clamp-2">{item.reel_title || t("generatedMedia.untitled", "Untitled")}</p>
                                            </td>
                                            <td className="hidden md:table-cell px-2 md:px-3 py-2 md:py-3 text-slate-700 dark:text-zinc-300 max-w-md">
                                                <p className="line-clamp-3">{item.reel_description || "-"}</p>
                                            </td>
                                            <td className="hidden sm:table-cell px-2 md:px-3 py-2 md:py-3 text-slate-700 dark:text-zinc-300">{item.reel_duration ? `${item.reel_duration}s` : "-"}</td>
                                            <td className="px-2 md:px-3 py-2 md:py-3">
                                                <span className={`inline-flex rounded-full border px-2 py-1 text-xs ${statusClass(item.reel_status)}`}>
                                                    {statusLabel(item.reel_status)}
                                                </span>
                                            </td>
                                            <td className="hidden lg:table-cell px-2 md:px-3 py-2 md:py-3 text-slate-500 dark:text-zinc-400">
                                                {item.reel_created_at ? new Date(item.reel_created_at).toLocaleString() : "-"}
                                            </td>
                                            <td className="px-2 md:px-3 py-2 md:py-3">
                                                <div className="flex items-center justify-end gap-1 md:gap-2">
                                                    <button
                                                        type="button"
                                                        onClick={() => handlePreview(item)}
                                                        className="inline-flex h-7 w-7 md:h-8 md:w-8 items-center justify-center rounded-lg border border-sky-300 dark:border-white/10 bg-sky-100 dark:bg-white/5 text-sky-800 dark:text-zinc-200 shadow-sm hover:bg-sky-200 dark:hover:bg-white/10"
                                                        title={t('reels.preview', 'Preview')}
                                                    >
                                                        <Play size={14} />
                                                    </button>

                                                    <button
                                                        type="button"
                                                        onClick={() => handleDownload(item.id)}
                                                        className="inline-flex h-7 w-7 md:h-8 md:w-8 items-center justify-center rounded-lg border border-indigo-300 dark:border-white/10 bg-indigo-100 dark:bg-white/5 text-indigo-800 dark:text-zinc-200 shadow-sm hover:bg-indigo-200 dark:hover:bg-white/10"
                                                        title={t('reels.download', 'Download')}
                                                    >
                                                        <Download size={14} />
                                                    </button>

                                                    {!hideSocialPlatforms ? (
                                                        <button
                                                            type="button"
                                                            onClick={() => handleShare(item)}
                                                            disabled={sharingId === item.id || !canShareReel}
                                                            className="inline-flex h-7 w-7 md:h-8 md:w-8 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50"
                                                            title={t('reels.share', 'Share')}
                                                        >
                                                            {sharingId === item.id ? <Loader2 size={14} className="animate-spin" /> : <Share2 size={14} />}
                                                        </button>
                                                    ) : null}

                                                    <button
                                                        type="button"
                                                        onClick={() => handleDelete(item.id)}
                                                        disabled={deletingId === item.id}
                                                        className="inline-flex h-7 w-7 md:h-8 md:w-8 items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 disabled:opacity-50"
                                                        title={t('reels.delete', 'Delete')}
                                                    >
                                                        {deletingId === item.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                            </tbody>
                        </table>
                </div>

                <div className="flex flex-col sm:flex-row items-center justify-between gap-2 sm:gap-0 border-t border-slate-300 dark:border-white/10 pt-4 text-sm">
                    <p className="text-slate-500 dark:text-zinc-400">{total} {t("reels.reelCount", "reel(s)")}</p>
                    <div className="flex w-full sm:w-auto items-center gap-2">
                        <button
                            type="button"
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page <= 1}
                            className="w-full sm:w-auto rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-2 md:px-3 py-1.5 text-xs md:text-sm font-medium text-slate-800 dark:text-zinc-300 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-40"
                        >
                            {t('reels.previous', 'Previous')}
                        </button>
                        <span className="text-slate-500 dark:text-zinc-400 text-xs md:text-sm">
                            {t('reels.page', 'Page')} {page} / {totalPages}
                        </span>
                        <button
                            type="button"
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page >= totalPages}
                            className="w-full sm:w-auto rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-2 md:px-3 py-1.5 text-xs md:text-sm font-medium text-slate-800 dark:text-zinc-300 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-40"
                        >
                            {t('reels.next', 'Next')}
                        </button>
                    </div>
                </div>
            </section>

            {!hideSocialPlatforms ? (
                <SharePostModal
                    isOpen={Boolean(shareModalItem)}
                    onClose={() => setShareModalItem(null)}
                    title={shareTitle}
                    onTitleChange={setShareTitle}
                    description={shareDescription}
                    onDescriptionChange={setShareDescription}
                    isScheduling={shareScheduling}
                    onSchedulingChange={setShareScheduling}
                    scheduleDate={shareScheduleDate}
                    onScheduleDateChange={setShareScheduleDate}
                    platforms={sharePlatforms}
                    onPlatformChange={(platform, checked) => setSharePlatforms((prev) => ({ ...prev, [platform]: checked }))}
                    connectedPlatforms={connectedPlatforms}
                    isSubmitting={Boolean(shareModalItem && sharingId === shareModalItem.id)}
                    result={shareResult}
                    onSubmit={submitShare}
                />
            ) : null}

            {previewItem && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md">
                    <div className="flex w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-slate-300 dark:border-white/10 bg-white dark:bg-zinc-950 shadow-2xl">
                        <div className="flex items-center justify-between border-b border-slate-300 dark:border-white/10 px-4 py-3">
                            <div>
                                <p className="text-sm font-semibold text-slate-900 dark:text-white">{previewItem.reel_title || t("reels.previewTitle", "Reel preview")}</p>
                                <p className="text-xs text-slate-500 dark:text-zinc-400">{t("reels.previewSubtitle", "Preview with the same actions as generated clips.")}</p>
                            </div>
                            <button
                                type="button"
                                onClick={() => {
                                    setPreviewItem(null);
                                    setPreviewUrl("");
                                }}
                                className="rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 p-2 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-white/10"
                                title={t('app.close', 'Close')}
                            >
                                <X size={16} />
                            </button>
                        </div>
                        <div className="max-h-[88vh] overflow-y-auto p-4 custom-scrollbar bg-slate-50 dark:bg-zinc-950">
                            {previewClip && (
                                <ResultCard
                                    clip={previewClip}
                                    index={previewClipIndex}
                                    jobId={previewJobId}
                                    compactActions={false}
                                    hideVideoPreview
                                />
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

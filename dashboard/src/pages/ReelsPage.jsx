import { useEffect, useMemo, useState } from "react";
import { Play, Plus, Download, Loader2, Search, Share2, Trash2, X, LayoutGrid, List } from "lucide-react";
import { getApiUrl } from "../config";
import { useAuth } from "../state/AuthContext";
import { useUserCredits } from "../state/UserCreditsContext";
import { useNavigate } from "react-router-dom";
import ResultCard from "../components/ResultCard";
import SharePostModal from "../components/SharePostModal";
import { getConnectedPlatforms } from "../lib/platforms";
import { toResultCardClip } from "../lib/clips";
import { statusLabel, statusClass } from "../lib/status";
import { useTranslation } from "../state/LanguageContext";

export default function ReelsPage() {
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
    const [viewMode, setViewMode] = useState("table");
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
    const [failedGridPreviewKeys, setFailedGridPreviewKeys] = useState(() => new Set());
    const navigate = useNavigate();

    const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);
    const reelCostEstimate = Number(defaultCosts?.reel || 1);
    const publicationCostEstimate = Number(defaultCosts?.publication || 1);
    const canCreateReel = credits >= reelCostEstimate;
    const canShareReel = credits >= publicationCostEstimate;

    const resolveReelPreview = (item) => item.reel_preview_url || item.reel_thumbnail_url || item.reel_playback_url || item.reel_url || "";
    const getGridPreviewKey = (item) => `${item.id || "unknown"}:${resolveReelPreview(item) || "none"}`;

    const handleGridPreviewError = (item) => {
        const key = getGridPreviewKey(item);
        setFailedGridPreviewKeys((prev) => {
            if (prev.has(key)) return prev;
            const next = new Set(prev);
            next.add(key);
            return next;
        });
    };

    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1);
            setQuery(queryInput.trim());
        }, 350);
        return () => clearTimeout(timer);
    }, [queryInput]);

    useEffect(() => {
        if (!user?.id) return;

        let cancelled = false;
        async function loadReels() {
            setLoading(true);
            setError("");

            const params = new URLSearchParams({
                page: String(page),
                page_size: String(pageSize),
            });
            if (query) params.set("q", query);
            if (status) params.set("status", status);

            try {
                const response = await fetch(getApiUrl(`/api/reels?${params.toString()}`), {
                    headers: {
                        "X-User-Id": user.id,
                    },
                });

                if (!response.ok) {
                    const detail = await response.text();
                    setError(detail || "Unable to load reels");
                    setItems([]);
                    return;
                }

                const data = await response.json();
                if (cancelled) return;

                setItems(Array.isArray(data.items) ? data.items : []);
                setTotal(Number(data.total || 0));
            } catch (err) {
                if (cancelled) return;
                setError(err.message || "Unable to load reels");
                setItems([]);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        loadReels();
        return () => {
            cancelled = true;
        };
    }, [user?.id, page, pageSize, query, status]);

    useEffect(() => {
        // Reset failed previews when list data changes so newly signed URLs can retry.
        setFailedGridPreviewKeys(new Set());
    }, [items]);

    const refresh = async () => {
        if (!user?.id) return;
        setLoading(true);
        try {
            const params = new URLSearchParams({
                page: String(page),
                page_size: String(pageSize),
            });
            if (query) params.set("q", query);
            if (status) params.set("status", status);

            const response = await fetch(getApiUrl(`/api/reels?${params.toString()}`), {
                headers: { "X-User-Id": user.id },
            });
            const data = await response.json();
            if (!response.ok) {
                setError(data?.detail || "Refresh failed");
                setItems([]);
                return;
            }
            setItems(Array.isArray(data.items) ? data.items : []);
            setTotal(Number(data.total || 0));
        } catch (err) {
            setError(err.message || "Refresh failed");
        } finally {
            setLoading(false);
        }
    };

    const fetchFreshMediaUrl = async (reelId) => {
        const response = await fetch(getApiUrl(`/api/reels/${reelId}/media-url`), {
            headers: { "X-User-Id": user.id },
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
                    "X-User-Id": user.id,
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
                    "X-User-Id": user.id,
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
                    <h1 className="text-3xl font-black tracking-tight">{t('reels.title', 'Generated reels')}</h1>
                    <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">{t('reels.subtitle', 'Search, filter, delete, share and download.')}</p>
                </div>

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
            </div>

            <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                {!canCreateReel ? (
                    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                        {t('reels.insufficientForNew', 'Insufficient balance for new generation ')}
                    </div>
                ) : null}
                {shareResult ? (
                    <div className={`rounded-lg border px-3 py-2 text-xs ${shareResult.success ? 'border-green-500/30 bg-green-500/10 text-green-300' : 'border-red-500/30 bg-red-500/10 text-red-300'}`}>
                        {shareResult.msg}
                    </div>
                ) : null}
                <div className="grid gap-3 md:grid-cols-[1fr_220px_auto_auto]">
                    <label className="relative">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-zinc-500" />
                        <input
                            value={queryInput}
                            onChange={(e) => setQueryInput(e.target.value)}
                            placeholder={t('reels.searchPlaceholder', 'Search by title or description...')}
                            className="w-full rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 py-2.5 pl-10 pr-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-primary/60"
                        />
                    </label>

                    <select
                        value={status}
                        onChange={(e) => {
                            setPage(1);
                            setStatus(e.target.value);
                        }}
                        className="rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white focus:outline-none focus:border-primary/60"
                    >
                        <option value="">{t('reels.allStatuses', 'All statuses')}</option>
                        <option value="en_cours">{t("reels.statusInProgress", "In progress")}</option>
                        <option value="termine">{t("reels.statusDone", "Done")}</option>
                        <option value="echec">{t("reels.statusFailed", "Failed")}</option>
                    </select>

                    <button
                        type="button"
                        onClick={refresh}
                        className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-4 py-2.5 text-sm text-zinc-200 hover:bg-white/10"
                    >
                        {t('settings.refresh', 'Refresh')}
                    </button>

                    <div className="inline-flex rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 p-1">
                        <button
                            type="button"
                            onClick={() => setViewMode("table")}
                            className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm ${viewMode === "table" ? "bg-white/10 text-white" : "text-slate-500 dark:text-zinc-400 hover:text-zinc-200"}`}
                            title={t("reels.tableView", "Table view")}
                        >
                            <List size={14} /> {t("reels.tableLabel", "Table")}
                        </button>
                        <button
                            type="button"
                            onClick={() => setViewMode("grid")}
                            className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm ${viewMode === "grid" ? "bg-white/10 text-white" : "text-slate-500 dark:text-zinc-400 hover:text-zinc-200"}`}
                            title={t("reels.gridView", "Grid view")}
                        >
                            <LayoutGrid size={14} /> {t("reels.gridLabel", "Grid")}
                        </button>
                    </div>
                </div>

                {viewMode === "table" ? (
                    <div className="overflow-x-auto">
                        <table className="min-w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-300 dark:border-white/10 text-left text-slate-500 dark:text-zinc-400">
                                    <th className="px-3 py-3 font-medium">{t("reels.tableReel", "Reel")}</th>
                                    <th className="px-3 py-3 font-medium">{t("generatedMedia.tableDescription", "Description")}</th>
                                    <th className="px-3 py-3 font-medium">{t("generatedMedia.tableDuration", "Duration")}</th>
                                    <th className="px-3 py-3 font-medium">{t("generatedMedia.tableStatus", "Status")}</th>
                                    <th className="px-3 py-3 font-medium">{t("generatedMedia.tableCreatedAt", "Created at")}</th>
                                    <th className="px-3 py-3 font-medium text-right">{t("generatedMedia.tableActions", "Actions")}</th>
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
                                            {t('reels.noneFound', 'No reels found.')}
                                        </td>
                                    </tr>
                                )}

                                {!loading && !error &&
                                    items.map((item) => (
                                        <tr key={item.id} className="border-b border-slate-200 dark:border-white/5 align-top">
                                            <td className="px-3 py-3">
                                                <p className="font-semibold text-white line-clamp-2">{item.reel_title || t("generatedMedia.untitled", "Untitled")}</p>
                                                <p className="mt-1 text-xs text-slate-400 dark:text-zinc-500">ID: {item.id}</p>
                                            </td>
                                            <td className="px-3 py-3 text-slate-700 dark:text-zinc-300 max-w-md">
                                                <p className="line-clamp-3">{item.reel_description || "-"}</p>
                                            </td>
                                            <td className="px-3 py-3 text-slate-700 dark:text-zinc-300">{item.reel_duration ? `${item.reel_duration}s` : "-"}</td>
                                            <td className="px-3 py-3">
                                                <span className={`inline-flex rounded-full border px-2 py-1 text-xs ${statusClass(item.reel_status)}`}>
                                                    {statusLabel(item.reel_status)}
                                                </span>
                                            </td>
                                            <td className="px-3 py-3 text-slate-500 dark:text-zinc-400">
                                                {item.reel_created_at ? new Date(item.reel_created_at).toLocaleString() : "-"}
                                            </td>
                                            <td className="px-3 py-3">
                                                <div className="flex items-center justify-end gap-2">
                                                    <button
                                                        type="button"
                                                        onClick={() => handlePreview(item)}
                                                        className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 text-zinc-200 hover:bg-white/10"
                                                        title={t('reels.preview', 'Preview')}
                                                    >
                                                        <Play size={14} />
                                                    </button>

                                                    <button
                                                        type="button"
                                                        onClick={() => handleDownload(item.id)}
                                                        className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 text-zinc-200 hover:bg-white/10"
                                                        title={t('reels.download', 'Download')}
                                                    >
                                                        <Download size={14} />
                                                    </button>

                                                    <button
                                                        type="button"
                                                        onClick={() => handleShare(item)}
                                                        disabled={sharingId === item.id || !canShareReel}
                                                        className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50"
                                                        title={t('reels.share', 'Share')}
                                                    >
                                                        {sharingId === item.id ? <Loader2 size={14} className="animate-spin" /> : <Share2 size={14} />}
                                                    </button>

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
                                            </td>
                                        </tr>
                                    ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div>
                        {loading ? (
                            <div className="px-3 py-10 text-center text-slate-500 dark:text-zinc-400">
                                <span className="inline-flex items-center gap-2">
                                    <Loader2 size={14} className="animate-spin" /> {t('reels.loading', 'Loading...')}
                                </span>
                            </div>
                        ) : null}

                        {!loading && error ? <div className="px-3 py-10 text-center text-red-300">{error}</div> : null}

                        {!loading && !error && items.length === 0 ? (
                            <div className="px-3 py-10 text-center text-slate-500 dark:text-zinc-400">{t('reels.noneFound', 'No reels found.')}</div>
                        ) : null}

                        {!loading && !error && items.length > 0 ? (
                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                                {items.map((item) => (
                                    <article key={item.id} className="group overflow-hidden rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5">
                                        <div className="relative aspect-video bg-black/40">
                                            {resolveReelPreview(item) && !failedGridPreviewKeys.has(getGridPreviewKey(item)) ? (
                                                <img
                                                    src={resolveReelPreview(item)}
                                                    alt={item.reel_title || "thumbnail"}
                                                    className="h-full w-full object-cover"
                                                    onError={() => handleGridPreviewError(item)}
                                                />
                                            ) : (
                                                <div className="flex h-full w-full items-center justify-center text-slate-400 dark:text-zinc-500">{t("reels.previewUnavailable", "Preview unavailable")}</div>
                                            )}

                                            <span className={`absolute right-2 top-2 inline-flex rounded-full border px-2 py-1 text-xs ${statusClass(item.reel_status)}`}>
                                                {statusLabel(item.reel_status)}
                                            </span>

                                            <div className="absolute inset-x-2 bottom-2 flex translate-y-2 items-center justify-center gap-2 opacity-0 transition group-hover:translate-y-0 group-hover:opacity-100">
                                                <button
                                                    type="button"
                                                    onClick={() => handlePreview(item)}
                                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-300 dark:border-white/10 bg-black/65 text-zinc-100 hover:bg-black/80"
                                                    title={t('reels.preview', 'Preview')}
                                                >
                                                    <Play size={14} />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleDownload(item.id)}
                                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-300 dark:border-white/10 bg-black/65 text-zinc-100 hover:bg-black/80"
                                                    title={t('reels.download', 'Download')}
                                                >
                                                    <Download size={14} />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleShare(item)}
                                                    disabled={sharingId === item.id || !canShareReel}
                                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-primary/40 bg-primary/20 text-primary hover:bg-primary/30 disabled:opacity-50"
                                                    title={t('reels.share', 'Share')}
                                                >
                                                    {sharingId === item.id ? <Loader2 size={14} className="animate-spin" /> : <Share2 size={14} />}
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleDelete(item.id)}
                                                    disabled={deletingId === item.id}
                                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-red-500/40 bg-red-500/20 text-red-300 hover:bg-red-500/30 disabled:opacity-50"
                                                    title={t('reels.delete', 'Delete')}
                                                >
                                                    {deletingId === item.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                                                </button>
                                            </div>
                                        </div>

                                        <div className="space-y-2 p-3">
                                            <p className="line-clamp-2 text-sm font-semibold text-white">{item.reel_title || t("generatedMedia.untitled", "Untitled")}</p>
                                            <p className="line-clamp-2 text-xs text-slate-500 dark:text-zinc-400">{item.reel_description || "-"}</p>
                                            <p className="text-xs text-slate-400 dark:text-zinc-500">
                                                {item.reel_duration ? `${item.reel_duration}s` : "-"} • {item.reel_created_at ? new Date(item.reel_created_at).toLocaleString() : "-"}
                                            </p>
                                        </div>
                                    </article>
                                ))}
                            </div>
                        ) : null}
                    </div>
                )}

                <div className="flex items-center justify-between border-t border-slate-300 dark:border-white/10 pt-4 text-sm">
                    <p className="text-slate-500 dark:text-zinc-400">{total} {t("reels.reelCount", "reel(s)")}</p>
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page <= 1}
                            className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-1.5 text-slate-700 dark:text-zinc-300 disabled:opacity-40"
                        >
                            {t('reels.previous', 'Previous')}
                        </button>
                        <span className="text-slate-500 dark:text-zinc-400">
                            {t('reels.page', 'Page')} {page} / {totalPages}
                        </span>
                        <button
                            type="button"
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page >= totalPages}
                            className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-1.5 text-slate-700 dark:text-zinc-300 disabled:opacity-40"
                        >
                            {t('reels.next', 'Next')}
                        </button>
                    </div>
                </div>
            </section>

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

            {previewItem && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md">
                    <div className="flex w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-slate-300 dark:border-white/10 bg-zinc-950 shadow-2xl">
                        <div className="flex items-center justify-between border-b border-slate-300 dark:border-white/10 px-4 py-3">
                            <div>
                                <p className="text-sm font-semibold text-white">{previewItem.reel_title || t("reels.previewTitle", "Reel preview")}</p>
                                <p className="text-xs text-slate-500 dark:text-zinc-400">{t("reels.previewSubtitle", "Preview with the same actions as generated clips.")}</p>
                            </div>
                            <button
                                type="button"
                                onClick={() => {
                                    setPreviewItem(null);
                                    setPreviewUrl("");
                                }}
                                className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 p-2 text-slate-700 dark:text-zinc-300 hover:bg-white/10"
                                title={t('app.close', 'Close')}
                            >
                                <X size={16} />
                            </button>
                        </div>
                        <div className="max-h-[88vh] overflow-y-auto p-4 custom-scrollbar">
                            {previewClip && (
                                <ResultCard
                                    clip={previewClip}
                                    index={previewClipIndex}
                                    jobId={previewJobId}
                                    compactActions={false}
                                />
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

import { useEffect, useMemo, useState } from "react";
import { Download, Loader2, Plus, Play, Search, Share2, Trash2, X } from "lucide-react";
import { getApiUrl } from "../config";
import { useAuth } from "../state/AuthContext";
import { getAuthHeaders } from "../lib/apiAuth";
import { useUserCredits } from "../state/UserCreditsContext";
import { useNavigate } from "react-router-dom";
import { statusLabel, statusClass } from "../lib/status";
import { getConnectedPlatforms } from "../lib/platforms";
import { useTranslation } from "../state/LanguageContext";

export default function GeneratedMediaPage({
    title,
    subtitle,
    createRoute,
    listEndpoint,
    mediaUrlEndpoint,
    deleteEndpoint,
    shareEndpoint,
    emptyLabel,
    sharePlatforms = ["tiktok", "instagram", "youtube"],
}) {
    const { user } = useAuth();
    const { credits, defaultCosts } = useUserCredits();
    const { t } = useTranslation();
    const navigate = useNavigate();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [page, setPage] = useState(1);
    const [pageSize] = useState(10);
    const [total, setTotal] = useState(0);
    const [queryInput, setQueryInput] = useState("");
    const [query, setQuery] = useState("");
    const [status, setStatus] = useState("");
    const [sharingId, setSharingId] = useState("");
    const [deletingId, setDeletingId] = useState("");
    const [previewItem, setPreviewItem] = useState(null);
    const [previewUrl, setPreviewUrl] = useState("");

    const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);
    const captionCostEstimate = Number(defaultCosts?.caption || 1);
    const publicationCostEstimate = Number(defaultCosts?.publication || 1);
    const canCreate = credits >= captionCostEstimate;
    const canShare = credits >= publicationCostEstimate;

    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1);
            setQuery(queryInput.trim());
        }, 350);
        return () => clearTimeout(timer);
    }, [queryInput]);

    const fetchFreshMediaUrl = async (itemId) => {
        const response = await fetch(getApiUrl(`${mediaUrlEndpoint}/${itemId}/media-url`), {
            headers: getAuthHeaders(user.id),
        });
        if (!response.ok) return null;
        const data = await response.json();
        return data.media_url || null;
    };

    useEffect(() => {
        if (!user?.id) return;

        let cancelled = false;
        async function loadItems() {
            setLoading(true);
            setError("");

            const params = new URLSearchParams({
                page: String(page),
                page_size: String(pageSize),
            });
            if (query) params.set("q", query);
            if (status) params.set("status", status);

            try {
                const response = await fetch(getApiUrl(`${listEndpoint}?${params.toString()}`), {
                    headers: getAuthHeaders(user.id),
                });

                if (!response.ok) {
                    const detail = await response.text();
                    setError(detail || `Unable to load ${title.toLowerCase()}`);
                    setItems([]);
                    return;
                }

                const data = await response.json();
                if (cancelled) return;
                setItems(Array.isArray(data.items) ? data.items : []);
                setTotal(Number(data.total || 0));
            } catch (err) {
                if (cancelled) return;
                setError(err.message || `Unable to load ${title.toLowerCase()}`);
                setItems([]);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        loadItems();
        return () => {
            cancelled = true;
        };
    }, [user?.id, page, pageSize, query, status, listEndpoint, title]);

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

            const response = await fetch(getApiUrl(`${listEndpoint}?${params.toString()}`), {
                headers: getAuthHeaders(user.id),
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

    const handleDelete = async (itemId) => {
        if (!user?.id) return;
        if (!globalThis.confirm(t("generatedMedia.confirmDelete", "Delete this media?"))) return;

        setDeletingId(itemId);
        try {
            const response = await fetch(getApiUrl(`${deleteEndpoint}/${itemId}`), {
                method: "DELETE",
                headers: getAuthHeaders(user.id),
            });
            if (!response.ok) {
                const detail = await response.text();
                setError(detail || t("generatedMedia.deleteFailed", "Delete failed"));
                return;
            }
            await refresh();
        } catch (err) {
            globalThis.alert(err.message || t("generatedMedia.deleteFailed", "Delete failed"));
        } finally {
            setDeletingId("");
        }
    };

    const handleDownload = async (itemId) => {
        if (!user?.id) return;
        const currentItem = items.find((item) => item.id === itemId);
        const fallbackUrl = currentItem?.media_url || null;
        const mediaUrl = await fetchFreshMediaUrl(itemId);
        if (!mediaUrl) {
            if (fallbackUrl) {
                globalThis.open(fallbackUrl, "_blank", "noopener,noreferrer");
                return;
            }
            globalThis.alert(t("generatedMedia.noDownloadUrl", "No download URL available"));
            return;
        }

        globalThis.open(mediaUrl, "_blank", "noopener,noreferrer");
    };

    const handleShare = async (itemId) => {
        if (!user?.id) return;
        if (!canShare) {
            setError(t('generatedMedia.insufficientForShare', 'Insufficient credits. ~{{required}} cr required, {{available}} cr available.', { required: publicationCostEstimate.toFixed(0), available: Number(credits || 0).toFixed(0) }));
            return;
        }

        const selectedPlatforms = getConnectedPlatforms(sharePlatforms);

        setSharingId(itemId);
        try {
            const payload = {
                platforms: selectedPlatforms,
            };

            const response = await fetch(getApiUrl(`${shareEndpoint}/${itemId}/share`), {
                method: "POST",
                headers: { "Content-Type": "application/json", ...getAuthHeaders(user.id) },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const detail = await response.text();
                setError(detail || t("generatedMedia.shareFailed", "Share failed"));
                return;
            }

            globalThis.alert(t("generatedMedia.shareSent", "Share request sent."));
        } catch (err) {
            globalThis.alert(err.message || t("generatedMedia.shareFailed", "Share failed"));
        } finally {
            setSharingId("");
        }
    };

    const handlePreview = async (item) => {
        setPreviewItem(item);
        setPreviewUrl(item.media_url || "");
        const mediaUrl = await fetchFreshMediaUrl(item.id);
        if (mediaUrl) setPreviewUrl(mediaUrl);
    };

    return (
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight">{title}</h1>
                    <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">{subtitle}</p>
                </div>

                <button
                    type="button"
                    onClick={() => navigate(createRoute)}
                    className="flex items-center gap-2 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors group disabled:opacity-40 disabled:cursor-not-allowed"
                >
                    <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0">
                        <Plus size={16} />
                    </div>
                    <div className="hidden lg:block overflow-hidden">
                        <p className="text-sm font-bold text-white leading-none mb-0.5">{t('generatedMedia.startAction', 'Start action')}</p>
                    </div>
                </button>
            </div>

            <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                {!canCreate ? (
                    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                        {t('reels.insufficientForNew', 'Pas assez de crédits, vous pouvez juste consulter sans faire de nouvelles opérations')}
                    </div>
                ) : null}
                <div className="grid gap-3 md:grid-cols-[1fr_220px_auto]">
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
                        <option value="">{t('generatedMedia.allStatuses', 'All statuses')}</option>
                        <option value="en_cours">{t("generatedMedia.statusInProgress", "In progress")}</option>
                        <option value="termine">{t("generatedMedia.statusDone", "Done")}</option>
                        <option value="echec">{t("generatedMedia.statusFailed", "Failed")}</option>
                    </select>

                    <button
                        type="button"
                        onClick={refresh}
                        className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-4 py-2.5 text-sm text-zinc-200 hover:bg-white/10"
                    >
                        {t('settings.refresh', 'Refresh')}
                    </button>
                </div>

                <div className="space-y-3 md:hidden">
                    {loading && (
                        <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-6 text-center text-slate-500 dark:text-zinc-400">
                            <span className="inline-flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> {t('reels.loading', 'Loading...')}</span>
                        </div>
                    )}

                    {!loading && error && (
                        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-6 text-center text-red-300">{error}</div>
                    )}

                    {!loading && !error && items.length === 0 && (
                        <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-6 text-center text-slate-500 dark:text-zinc-400">{emptyLabel}</div>
                    )}

                    {!loading && !error && items.map((item) => (
                        <article key={item.id} className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 p-3 space-y-3">
                            <div className="flex gap-3">
                                {item.media_thumbnail_url ? (
                                    <img
                                        src={item.media_thumbnail_url}
                                        alt={item.media_title || "thumbnail"}
                                        className="h-16 w-10 rounded-md object-cover border border-slate-300 dark:border-white/10"
                                    />
                                ) : null}
                                <div className="min-w-0 flex-1">
                                    <p className="font-semibold text-white line-clamp-2">{item.media_title || t("generatedMedia.untitled", "Untitled")}</p>
                                    <p className="mt-1 text-xs text-slate-500 dark:text-zinc-400 line-clamp-3">{item.media_description || "-"}</p>
                                </div>
                            </div>

                            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
                                <span>{t("generatedMedia.tableDuration", "Duration")}: {item.media_duration ? `${item.media_duration}s` : "-"}</span>
                                <span>•</span>
                                <span>{item.media_created_at ? new Date(item.media_created_at).toLocaleString() : "-"}</span>
                            </div>

                            <div>
                                <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusClass(item.media_status)}`}>
                                    {statusLabel(item.media_status)}
                                </span>
                            </div>

                            <div className="flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    onClick={() => handlePreview(item)}
                                    className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 p-2 text-slate-700 dark:text-zinc-300 hover:bg-white/10"
                                    title={t("reels.preview", "Preview")}
                                >
                                    <Play size={14} />
                                </button>
                                <button
                                    type="button"
                                    onClick={() => handleDownload(item.id)}
                                    className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 p-2 text-slate-700 dark:text-zinc-300 hover:bg-white/10"
                                    title={t("reels.download", "Download")}
                                >
                                    <Download size={14} />
                                </button>
                                <button
                                    type="button"
                                    onClick={() => handleShare(item.id)}
                                    disabled={sharingId === item.id || !canShare}
                                    className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 p-2 text-slate-700 dark:text-zinc-300 hover:bg-white/10 disabled:opacity-60"
                                    title={t("reels.share", "Share")}
                                >
                                    <Share2 size={14} />
                                </button>
                                <button
                                    type="button"
                                    onClick={() => handleDelete(item.id)}
                                    disabled={deletingId === item.id}
                                    className="rounded-lg border border-red-500/20 bg-red-500/10 p-2 text-red-300 hover:bg-red-500/20 disabled:opacity-60"
                                    title={t("reels.delete", "Delete")}
                                >
                                    <Trash2 size={14} />
                                </button>
                            </div>
                        </article>
                    ))}
                </div>

                <div className="hidden overflow-x-auto md:block">
                    <table className="min-w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-300 dark:border-white/10 text-left text-slate-500 dark:text-zinc-400">
                                <th className="px-3 py-3 font-medium">{t("generatedMedia.tableTitle", "Title")}</th>
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
                                        <span className="inline-flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> {t('reels.loading', 'Loading...')}</span>
                                    </td>
                                </tr>
                            )}

                            {!loading && error && (
                                <tr>
                                    <td colSpan={6} className="px-3 py-10 text-center text-red-300">{error}</td>
                                </tr>
                            )}

                            {!loading && !error && items.length === 0 && (
                                <tr>
                                    <td colSpan={6} className="px-3 py-10 text-center text-slate-500 dark:text-zinc-400">{emptyLabel}</td>
                                </tr>
                            )}

                            {!loading && !error &&
                                items.map((item) => (
                                    <tr key={item.id} className="border-b border-slate-200 dark:border-white/5 align-top">
                                        <td className="px-3 py-3">
                                            {item.media_thumbnail_url ? (
                                                <img
                                                    src={item.media_thumbnail_url}
                                                    alt={item.media_title || "thumbnail"}
                                                    className="mb-2 h-16 w-10 rounded-md object-cover border border-slate-300 dark:border-white/10"
                                                />
                                            ) : null}
                                            <p className="font-semibold text-white line-clamp-2">{item.media_title || t("generatedMedia.untitled", "Untitled")}</p>
                                        </td>
                                        <td className="px-3 py-3 text-slate-700 dark:text-zinc-300 max-w-md">
                                            <p className="line-clamp-3">{item.media_description || "-"}</p>
                                        </td>
                                        <td className="px-3 py-3 text-slate-700 dark:text-zinc-300">{item.media_duration ? `${item.media_duration}s` : "-"}</td>
                                        <td className="px-3 py-3">
                                            <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusClass(item.media_status)}`}>
                                                {statusLabel(item.media_status)}
                                            </span>
                                        </td>
                                        <td className="px-3 py-3 text-slate-500 dark:text-zinc-400">{item.media_created_at ? new Date(item.media_created_at).toLocaleString() : "-"}</td>
                                        <td className="px-3 py-3">
                                            <div className="flex justify-end gap-2">
                                                <button
                                                    type="button"
                                                    onClick={() => handlePreview(item)}
                                                    className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 p-2 text-slate-700 dark:text-zinc-300 hover:bg-white/10"
                                                    title={t("reels.preview", "Preview")}
                                                >
                                                    <Play size={14} />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleDownload(item.id)}
                                                    className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 p-2 text-slate-700 dark:text-zinc-300 hover:bg-white/10"
                                                    title={t("reels.download", "Download")}
                                                >
                                                    <Download size={14} />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleShare(item.id)}
                                                    disabled={sharingId === item.id || !canShare}
                                                    className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 p-2 text-slate-700 dark:text-zinc-300 hover:bg-white/10 disabled:opacity-60"
                                                    title={t("reels.share", "Share")}
                                                >
                                                    <Share2 size={14} />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleDelete(item.id)}
                                                    disabled={deletingId === item.id}
                                                    className="rounded-lg border border-red-500/20 bg-red-500/10 p-2 text-red-300 hover:bg-red-500/20 disabled:opacity-60"
                                                    title={t("reels.delete", "Delete")}
                                                >
                                                    <Trash2 size={14} />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                        </tbody>
                    </table>
                </div>

                <div className="flex flex-col gap-3 border-t border-slate-300 dark:border-white/10 pt-4 md:flex-row md:items-center md:justify-between">
                    <p className="text-xs text-slate-400 dark:text-zinc-500">
                        {t('reels.page', 'Page')} {page} / {totalPages} · {total}
                    </p>
                    <div className="flex flex-wrap gap-2">
                        <button
                            type="button"
                            disabled={page <= 1}
                            onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                            className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-2 text-sm text-zinc-200 disabled:opacity-40"
                        >
                            {t('reels.previous', 'Previous')}
                        </button>
                        <button
                            type="button"
                            disabled={page >= totalPages}
                            onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                            className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-2 text-sm text-zinc-200 disabled:opacity-40"
                        >
                            {t('reels.next', 'Next')}
                        </button>
                    </div>
                </div>
            </section>

            {previewItem && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md">
                    <div className="flex w-full max-w-[420px] flex-col overflow-hidden rounded-[2rem] border border-slate-300 dark:border-white/10 bg-zinc-950 shadow-2xl">
                        <div className="flex items-center justify-between border-b border-slate-300 dark:border-white/10 px-4 py-3">
                            <div>
                                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400 dark:text-zinc-500">{t("generatedMedia.previewLabel", "Preview")}</p>
                                <h3 className="title-contrast text-sm font-semibold">{previewItem.media_title || t("generatedMedia.untitled", "Untitled")}</h3>
                            </div>
                            <button
                                type="button"
                                onClick={() => {
                                    setPreviewItem(null);
                                    setPreviewUrl("");
                                }}
                                className="rounded-full border border-slate-300 dark:border-white/10 bg-white/5 p-2 text-slate-700 dark:text-zinc-300 hover:bg-white/10"
                            >
                                <X size={16} />
                            </button>
                        </div>

                        <div className="mx-auto aspect-[9/16] w-full max-h-[78vh] overflow-hidden bg-black">
                            <video
                                src={previewUrl || previewItem.media_url || ""}
                                controls
                                autoPlay
                                playsInline
                                className="h-full w-full object-contain"
                            />
                        </div>

                        <div className="space-y-3 border-t border-slate-300 dark:border-white/10 px-4 py-4 text-sm text-slate-700 dark:text-zinc-300">
                            <p className="line-clamp-4 text-slate-500 dark:text-zinc-400">{previewItem.media_description || t("generatedMedia.noDescription", "No description.")}</p>
                            <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-zinc-500">
                                <span className={`rounded-full border px-2 py-1 ${statusClass(previewItem.media_status)}`}>{statusLabel(previewItem.media_status)}</span>
                                <span>{previewItem.media_duration ? `${previewItem.media_duration}s` : t("generatedMedia.unknownDuration", "Unknown duration")}</span>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

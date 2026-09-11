import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Loader2, Plus, Quote, Search, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getApiUrl } from "../config";
import { useAuth } from "../state/AuthContext";
import { useTranslation } from "../state/LanguageContext";
import { getAuthHeaders } from "../lib/apiAuth";

const STATUS_BADGE_CLASSES = {
    completed: "bg-emerald-100 border-emerald-300 text-emerald-800 dark:bg-green-500/10 dark:border-green-500/30 dark:text-green-300",
    processing: "bg-sky-100 border-sky-300 text-sky-800 dark:bg-blue-500/10 dark:border-blue-500/30 dark:text-blue-300",
    queued: "bg-sky-100 border-sky-300 text-sky-800 dark:bg-blue-500/10 dark:border-blue-500/30 dark:text-blue-300",
    failed: "bg-rose-100 border-rose-300 text-rose-800 dark:bg-red-500/10 dark:border-red-500/30 dark:text-red-300",
    cancelled: "bg-white/5 border-slate-300 dark:border-white/10 text-slate-700 dark:text-zinc-300",
    draft: "bg-white/5 border-slate-300 dark:border-white/10 text-slate-700 dark:text-zinc-300",
};

export default function AnonymousStoriesListPage() {
    const { user } = useAuth();
    const { t } = useTranslation();
    const navigate = useNavigate();

    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [page, setPage] = useState(1);
    const [pageSize] = useState(15);
    const [total, setTotal] = useState(0);
    const [queryInput, setQueryInput] = useState("");
    const [query, setQuery] = useState("");
    const [deletingId, setDeletingId] = useState("");

    const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);

    const statusLabel = (status) => t(`anonymousStories.status${status ? status[0].toUpperCase() + status.slice(1) : "Draft"}`, status || "-");

    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1);
            setQuery(queryInput.trim());
        }, 350);
        return () => clearTimeout(timer);
    }, [queryInput]);

    const loadStories = async () => {
        if (!user?.id) return;
        setLoading(true);
        setError("");
        try {
            const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
            if (query) params.set("q", query);

            const response = await fetch(getApiUrl(`/api/anonymous-stories?${params.toString()}`), {
                headers: getAuthHeaders(user.id),
            });
            const data = await response.json();
            if (!response.ok) {
                setError(data?.detail || t("anonymousStories.genericError", "Une erreur est survenue."));
                setItems([]);
                return;
            }
            setItems(Array.isArray(data.items) ? data.items : []);
            setTotal(Number(data.total || 0));
        } catch (err) {
            setError(err.message || t("anonymousStories.genericError", "Une erreur est survenue."));
            setItems([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadStories();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user?.id, page, pageSize, query]);

    const handleOpen = (item) => {
        if (!item?.id) return;
        if (item.status === "processing" || item.status === "queued") {
            navigate(`/dashboard/anonymous-stories/new?job_id=${encodeURIComponent(item.job_id || "")}&story_id=${encodeURIComponent(item.id)}`);
            return;
        }
        navigate(`/dashboard/anonymous-stories/${item.id}`);
    };

    const handleDelete = async (item) => {
        if (!item?.id || !user?.id) return;
        if (!globalThis.confirm(t("anonymousStories.confirmDelete", "Supprimer ce temoignage ?"))) return;

        setDeletingId(item.id);
        try {
            const response = await fetch(getApiUrl(`/api/anonymous-stories/${item.id}`), {
                method: "DELETE",
                headers: getAuthHeaders(user.id),
            });
            if (!response.ok) {
                const detail = await response.text();
                setError(detail || t("anonymousStories.genericError", "Une erreur est survenue."));
                return;
            }
            await loadStories();
        } catch (err) {
            setError(err.message || t("anonymousStories.genericError", "Une erreur est survenue."));
        } finally {
            setDeletingId("");
        }
    };

    return (
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight">{t("anonymousStories.title", "Mes temoignages")}</h1>
                    <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">{t("anonymousStories.subtitle", "Importe une video ou un lien YouTube.")}</p>
                </div>
                <button
                    type="button"
                    onClick={() => navigate("/dashboard/anonymous-stories/new")}
                    className="w-full md:w-auto flex items-center justify-center gap-2 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors"
                >
                    <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0">
                        <Plus size={16} />
                    </div>
                    <span className="text-sm font-bold text-white">{t("anonymousStories.createCta", "Creer un temoignage")}</span>
                </button>
            </div>

            <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                {error ? (
                    <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                        <AlertCircle size={14} />
                        {error}
                    </div>
                ) : null}

                <label className="relative block">
                    <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-zinc-500" />
                    <input
                        value={queryInput}
                        onChange={(e) => setQueryInput(e.target.value)}
                        placeholder={t("projects.searchPlaceholder", "Rechercher...")}
                        className="w-full rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 py-2.5 pl-10 pr-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-primary/60"
                    />
                </label>

                <div className="hidden md:block">
                    <table className="w-full table-fixed text-sm">
                        <thead>
                            <tr className="border-b border-slate-300 dark:border-white/10 text-left text-slate-500 dark:text-zinc-400 text-xs md:text-sm">
                                <th className="w-[30%] px-2 md:px-3 py-3 font-medium">{t("anonymousStories.columnTitle", "Titre")}</th>
                                <th className="w-[15%] px-2 md:px-3 py-3 font-medium">{t("anonymousStories.columnSource", "Source")}</th>
                                <th className="w-[15%] px-2 md:px-3 py-3 font-medium">{t("anonymousStories.columnStatus", "Statut")}</th>
                                <th className="hidden lg:table-cell w-[20%] px-2 md:px-3 py-3 font-medium">{t("anonymousStories.columnCreatedAt", "Date de creation")}</th>
                                <th className="w-[20%] px-2 md:px-3 py-3 font-medium text-right">{t("anonymousStories.columnActions", "Actions")}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan={5} className="px-3 py-10 text-center text-slate-500 dark:text-zinc-400">
                                        <span className="inline-flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> {t("reels.loading", "Loading...")}</span>
                                    </td>
                                </tr>
                            ) : null}

                            {!loading && items.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="px-3 py-10 text-center text-slate-500 dark:text-zinc-400">{t("common.noItemsFound", "Aucun element trouve")}</td>
                                </tr>
                            ) : null}

                            {!loading && items.map((item) => (
                                <tr
                                    key={item.id}
                                    className="border-b border-slate-200 dark:border-white/5 align-top cursor-pointer hover:bg-white/5"
                                    onClick={() => handleOpen(item)}
                                >
                                    <td className="px-2 md:px-3 py-2 md:py-3">
                                        <p className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white line-clamp-2 break-words">
                                            <Quote size={14} className="shrink-0 text-primary" />
                                            {item.title || t("anonymousStories.untitled", "Temoignage sans titre")}
                                        </p>
                                    </td>
                                    <td className="px-2 md:px-3 py-2 md:py-3 text-slate-700 dark:text-zinc-300">
                                        {item.source_type === "youtube" ? t("anonymousStories.sourceYoutube", "YouTube") : t("anonymousStories.sourceUpload", "Video")}
                                    </td>
                                    <td className="px-2 md:px-3 py-2 md:py-3">
                                        <span className={`inline-flex rounded-full border px-2 py-1 text-xs ${STATUS_BADGE_CLASSES[item.status] || STATUS_BADGE_CLASSES.draft}`}>
                                            {statusLabel(item.status)}
                                        </span>
                                    </td>
                                    <td className="hidden lg:table-cell px-2 md:px-3 py-2 md:py-3 text-slate-500 dark:text-zinc-400">
                                        {item.created_at ? new Date(item.created_at).toLocaleString() : "-"}
                                    </td>
                                    <td className="px-2 md:px-3 py-2 md:py-3">
                                        <div className="flex items-center justify-end gap-2">
                                            <button
                                                type="button"
                                                disabled={deletingId === item.id}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDelete(item);
                                                }}
                                                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 disabled:opacity-50"
                                                title={t("projects.delete", "Supprimer")}
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
                    <p className="text-slate-500 dark:text-zinc-400">{total} {t("projects.count", "element(s)")}</p>
                    <div className="flex w-full sm:w-auto items-center gap-2">
                        <button
                            type="button"
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page <= 1}
                            className="w-full sm:w-auto rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-2 md:px-3 py-1.5 text-xs md:text-sm font-medium text-slate-800 dark:text-zinc-300 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-40"
                        >
                            {t("reels.previous", "Previous")}
                        </button>
                        <span className="text-slate-500 dark:text-zinc-400 text-xs md:text-sm">{t("reels.page", "Page")} {page} / {totalPages}</span>
                        <button
                            type="button"
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page >= totalPages}
                            className="w-full sm:w-auto rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-2 md:px-3 py-1.5 text-xs md:text-sm font-medium text-slate-800 dark:text-zinc-300 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-40"
                        >
                            {t("reels.next", "Next")}
                        </button>
                    </div>
                </div>
            </section>
        </div>
    );
}

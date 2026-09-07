import { useEffect, useMemo, useState } from "react";
import { Edit3, FolderOpen, Loader2, Plus, Search, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getApiUrl } from "../config";
import MobileFilterDropdown from "../components/MobileFilterDropdown";
import { useAuth } from "../state/AuthContext";
import { useTranslation } from "../state/LanguageContext";
import { statusClass, statusLabel } from "../lib/status";
import { getAuthHeaders } from "../lib/apiAuth";

function formatDurationHms(value) {
    const total = Number(value || 0);
    if (!Number.isFinite(total) || total <= 0) return "-";
    const sec = Math.max(0, Math.round(total));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function CaptionProjectsPage() {
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
    const [status, setStatus] = useState("");
    const [savingId, setSavingId] = useState("");
    const [deletingId, setDeletingId] = useState("");
    const statusOptions = [
        { value: "", label: t("reels.allStatuses", "All statuses") },
        { value: "processing", label: t("reels.statusInProgress", "In progress") },
        { value: "completed", label: t("reels.statusDone", "Done") },
        { value: "failed", label: t("reels.statusFailed", "Failed") },
        { value: "cancelled", label: t("projects.statusCancelled", "Cancelled") },
    ];

    const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);

    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1);
            setQuery(queryInput.trim());
        }, 350);
        return () => clearTimeout(timer);
    }, [queryInput]);

    const loadProjects = async () => {
        if (!user?.id) return;
        setLoading(true);
        setError("");
        try {
            const params = new URLSearchParams({
                page: String(page),
                page_size: String(pageSize),
                project_type: "caption",
            });
            if (query) params.set("q", query);
            if (status) params.set("status", status);

            const response = await fetch(getApiUrl(`/api/projects?${params.toString()}`), {
                headers: getAuthHeaders(user.id),
            });
            const data = await response.json();
            if (!response.ok) {
                setError(data?.detail || "Unable to load projects");
                setItems([]);
                return;
            }
            setItems(Array.isArray(data.items) ? data.items : []);
            setTotal(Number(data.total || 0));
        } catch (err) {
            setError(err.message || "Unable to load projects");
            setItems([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadProjects();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user?.id, page, pageSize, query, status]);

    const handleOpenProject = (project) => {
        const projectId = project?.id;
        if (!projectId) return;

        if (project?.status === "completed") {
            navigate(`/dashboard/captions/projects/${projectId}?autoplay=1`);
            return;
        }

        if (project?.status === "processing" || project?.status === "failed" || project?.status === "cancelled") {
            navigate(`/dashboard/captions/new?project_id=${encodeURIComponent(projectId)}`);
            return;
        }

        // Defensive fallback: always keep project context attached.
        navigate(`/dashboard/captions/new?project_id=${encodeURIComponent(projectId)}`);
    };

    const handleRename = async (project) => {
        if (!project?.id || !user?.id) return;
        const nextName = globalThis.prompt(t("projects.renamePrompt", "Nouveau nom du projet"), project.name || "");
        if (nextName == null) return;
        const trimmed = nextName.trim();
        if (!trimmed || trimmed === project.name) return;

        setSavingId(project.id);
        try {
            const response = await fetch(getApiUrl(`/api/projects/${project.id}`), {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    ...getAuthHeaders(user.id),
                },
                body: JSON.stringify({ name: trimmed }),
            });
            if (!response.ok) {
                const detail = await response.text();
                setError(detail || "Rename failed");
                return;
            }
            await loadProjects();
        } catch (err) {
            setError(err.message || "Rename failed");
        } finally {
            setSavingId("");
        }
    };

    const handleDelete = async (project) => {
        if (!project?.id || !user?.id) return;
        if (!globalThis.confirm(t("projects.confirmDelete", "Supprimer ce projet ?"))) return;

        setDeletingId(project.id);
        try {
            const response = await fetch(getApiUrl(`/api/projects/${project.id}`), {
                method: "DELETE",
                headers: getAuthHeaders(user.id),
            });
            if (!response.ok) {
                const detail = await response.text();
                setError(detail || "Delete failed");
                return;
            }
            await loadProjects();
        } catch (err) {
            setError(err.message || "Delete failed");
        } finally {
            setDeletingId("");
        }
    };

    return (
        <div className="captions-page-shell flex-1 overflow-y-auto p-8 space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight">{t("projects.captionsTitle", "Mes projets Sous-titres")}</h1>
                    <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">{t("projects.subtitle", "Organisez vos operations sans changer vos actions habituelles.")}</p>
                </div>
                <button
                    type="button"
                    onClick={() => navigate("/dashboard/captions/new")}
                    className="w-full md:w-auto flex items-center justify-center gap-2 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors"
                >
                    <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0">
                        <Plus size={16} />
                    </div>
                    <span className="text-sm font-bold text-white">{t("app.newOperation", "New operation")}</span>
                </button>
            </div>

            <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                {error ? <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</div> : null}

                <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 md:grid-cols-[1fr_220px_auto]">
                    <label className="relative">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-zinc-500" />
                        <input
                            value={queryInput}
                            onChange={(e) => setQueryInput(e.target.value)}
                            placeholder={t("projects.searchPlaceholder", "Rechercher par nom ou description...")}
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
                        ariaLabel={t("reels.allStatuses", "All statuses")}
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
                        onClick={loadProjects}
                        className="rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                    >
                        {t("settings.refresh", "Refresh")}
                    </button>
                </div>

                <div className="space-y-3 md:hidden">
                    {loading ? (
                        <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-6 text-center text-slate-500 dark:text-zinc-400">
                            <span className="inline-flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> {t("reels.loading", "Loading...")}</span>
                        </div>
                    ) : null}

                    {!loading && items.length === 0 ? (
                        <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-6 text-center text-slate-500 dark:text-zinc-400">{t("common.noItemsFound", "Aucun element trouve")}</div>
                    ) : null}

                    {!loading && items.map((item) => (
                        <article
                            key={item.id}
                            className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 p-3 space-y-3 cursor-pointer"
                            onClick={() => handleOpenProject(item)}
                        >
                            <div className="space-y-1">
                                <p className="font-semibold text-slate-900 dark:text-white line-clamp-2">{item.name || t("generatedMedia.untitled", "Untitled")}</p>
                                <p className="text-xs text-slate-500 dark:text-zinc-400 line-clamp-3">{item.description || "-"}</p>
                            </div>

                            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
                                <span>{t("generatedMedia.tableDuration", "Duration")}: {formatDurationHms(item.source_duration)}</span>
                            </div>

                            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
                                <span>{item.created_at ? new Date(item.created_at).toLocaleString() : "-"}</span>
                            </div>

                            <div>
                                <span className={`inline-flex rounded-full border px-2 py-1 text-xs ${statusClass(item.status)}`}>{statusLabel(item.status)}</span>
                            </div>

                            <div className="flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleOpenProject(item);
                                    }}
                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-sky-300 dark:border-white/10 bg-sky-100 dark:bg-white/5 text-sky-800 dark:text-zinc-200 shadow-sm hover:bg-sky-200 dark:hover:bg-white/10"
                                    title={t("projects.open", "Ouvrir")}
                                >
                                    <FolderOpen size={14} />
                                </button>
                                <button
                                    type="button"
                                    disabled={savingId === item.id}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleRename(item);
                                    }}
                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-amber-300 dark:border-white/10 bg-amber-100 dark:bg-white/5 text-amber-800 dark:text-zinc-200 shadow-sm hover:bg-amber-200 dark:hover:bg-white/10 disabled:opacity-50"
                                    title={t("projects.rename", "Renommer")}
                                >
                                    {savingId === item.id ? <Loader2 size={14} className="animate-spin" /> : <Edit3 size={14} />}
                                </button>
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
                        </article>
                    ))}
                </div>

                <div className="hidden overflow-x-auto md:block">
                    <table className="min-w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-300 dark:border-white/10 text-left text-slate-500 dark:text-zinc-400 text-xs md:text-sm">
                                <th className="px-2 md:px-3 py-3 font-medium">{t("projects.tableName", "Projet")}</th>
                                <th className="hidden md:table-cell px-2 md:px-3 py-3 font-medium">{t("generatedMedia.tableDescription", "Description")}</th>
                                <th className="hidden sm:table-cell px-2 md:px-3 py-3 font-medium">{t("generatedMedia.tableDuration", "Duration")}</th>
                                <th className="px-2 md:px-3 py-3 font-medium">{t("generatedMedia.tableStatus", "Status")}</th>
                                <th className="hidden lg:table-cell px-2 md:px-3 py-3 font-medium">{t("generatedMedia.tableCreatedAt", "Created at")}</th>
                                <th className="px-2 md:px-3 py-3 font-medium text-right">{t("generatedMedia.tableActions", "Actions")}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan={6} className="px-3 py-10 text-center text-slate-500 dark:text-zinc-400">
                                        <span className="inline-flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> {t("reels.loading", "Loading...")}</span>
                                    </td>
                                </tr>
                            ) : null}

                            {!loading && items.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="px-3 py-10 text-center text-slate-500 dark:text-zinc-400">{t("common.noItemsFound", "Aucun element trouve")}</td>
                                </tr>
                            ) : null}

                            {!loading && items.map((item) => (
                                <tr
                                    key={item.id}
                                    className="border-b border-slate-200 dark:border-white/5 align-top cursor-pointer hover:bg-white/5"
                                    onClick={() => handleOpenProject(item)}
                                >
                                    <td className="px-2 md:px-3 py-2 md:py-3">
                                        <p className="font-semibold text-slate-900 dark:text-white line-clamp-2">{item.name || t("generatedMedia.untitled", "Untitled")}</p>
                                    </td>
                                    <td className="hidden md:table-cell px-2 md:px-3 py-2 md:py-3 text-slate-700 dark:text-zinc-300 max-w-md"><p className="line-clamp-3">{item.description || "-"}</p></td>
                                    <td className="hidden sm:table-cell px-2 md:px-3 py-2 md:py-3 text-slate-700 dark:text-zinc-300">{formatDurationHms(item.source_duration)}</td>
                                    <td className="px-2 md:px-3 py-2 md:py-3">
                                        <span className={`inline-flex rounded-full border px-2 py-1 text-xs ${statusClass(item.status)}`}>{statusLabel(item.status)}</span>
                                    </td>
                                    <td className="hidden lg:table-cell px-2 md:px-3 py-2 md:py-3 text-slate-500 dark:text-zinc-400">{item.created_at ? new Date(item.created_at).toLocaleString() : "-"}</td>
                                    <td className="px-2 md:px-3 py-2 md:py-3">
                                        <div className="flex items-center justify-end gap-1 md:gap-2">
                                            <button
                                                type="button"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleOpenProject(item);
                                                }}
                                                className="inline-flex h-7 w-7 md:h-8 md:w-8 items-center justify-center rounded-lg border border-sky-300 dark:border-white/10 bg-sky-100 dark:bg-white/5 text-sky-800 dark:text-zinc-200 shadow-sm hover:bg-sky-200 dark:hover:bg-white/10"
                                                title={t("projects.open", "Ouvrir")}
                                            >
                                                <FolderOpen size={14} />
                                            </button>
                                            <button
                                                type="button"
                                                disabled={savingId === item.id}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleRename(item);
                                                }}
                                                className="inline-flex h-7 w-7 md:h-8 md:w-8 items-center justify-center rounded-lg border border-amber-300 dark:border-white/10 bg-amber-100 dark:bg-white/5 text-amber-800 dark:text-zinc-200 shadow-sm hover:bg-amber-200 dark:hover:bg-white/10 disabled:opacity-50"
                                                title={t("projects.rename", "Renommer")}
                                            >
                                                {savingId === item.id ? <Loader2 size={14} className="animate-spin" /> : <Edit3 size={14} />}
                                            </button>
                                            <button
                                                type="button"
                                                disabled={deletingId === item.id}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDelete(item);
                                                }}
                                                className="inline-flex h-7 w-7 md:h-8 md:w-8 items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 disabled:opacity-50"
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
                    <p className="text-slate-500 dark:text-zinc-400">{total} {t("projects.count", "projet(s)")}</p>
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


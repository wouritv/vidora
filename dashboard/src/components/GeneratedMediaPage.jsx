import { useEffect, useMemo, useState } from "react";
import { Download, Loader2, Plus, Play, Search, Share2, Trash2, X } from "lucide-react";
import { getApiUrl } from "../config";
import { useAuth } from "../state/AuthContext";
import { useNavigate } from "react-router-dom";

const SECRET_KEY = import.meta.env.VITE_ENCRYPTION_KEY || "OpenShorts-Static-Salt-Change-Me";
const ENCRYPTION_PREFIX = "ENC:";

function decrypt(text) {
    if (!text) return "";
    if (!text.startsWith(ENCRYPTION_PREFIX)) return text;

    try {
        const raw = text.slice(ENCRYPTION_PREFIX.length);
        const xor = atob(raw);
        return xor
            .split("")
            .map((c, i) => String.fromCodePoint(c.codePointAt(0) ^ SECRET_KEY.codePointAt(i % SECRET_KEY.length)))
            .join("");
    } catch {
        return "";
    }
}

function statusLabel(status) {
    if (status === "termine") return "Termine";
    if (status === "en_cours") return "En cours";
    if (status === "echec") return "Echec";
    return status || "-";
}

function statusClass(status) {
    if (status === "termine") return "bg-green-500/10 border-green-500/30 text-green-300";
    if (status === "en_cours") return "bg-blue-500/10 border-blue-500/30 text-blue-300";
    if (status === "echec") return "bg-red-500/10 border-red-500/30 text-red-300";
    return "bg-white/5 border-white/10 text-zinc-300";
}

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

    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1);
            setQuery(queryInput.trim());
        }, 350);
        return () => clearTimeout(timer);
    }, [queryInput]);

    const fetchFreshMediaUrl = async (itemId) => {
        const response = await fetch(getApiUrl(`${mediaUrlEndpoint}/${itemId}/media-url`), {
            headers: { "X-User-Id": user.id },
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
                    headers: { "X-User-Id": user.id },
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

    const handleDelete = async (itemId) => {
        if (!user?.id) return;
        if (!globalThis.confirm(`Supprimer ce media ?`)) return;

        setDeletingId(itemId);
        try {
            const response = await fetch(getApiUrl(`${deleteEndpoint}/${itemId}`), {
                method: "DELETE",
                headers: { "X-User-Id": user.id },
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
            globalThis.alert("No download url available");
            return;
        }

        globalThis.open(mediaUrl, "_blank", "noopener,noreferrer");
    };

    const handleShare = async (itemId) => {
        if (!user?.id) return;

        const encryptedUploadPostKey = localStorage.getItem("uploadPostKey_v3") || "";
        const apiKey = decrypt(encryptedUploadPostKey);
        const uploadPostUser = globalThis.localStorage.getItem("uploadUserId") || "";

        if (!apiKey || !uploadPostUser) {
            globalThis.alert("Configure Upload-Post API key and profile in Settings before sharing.");
            return;
        }

        setSharingId(itemId);
        try {
            const response = await fetch(getApiUrl(`${shareEndpoint}/${itemId}/share`), {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-User-Id": user.id },
                body: JSON.stringify({
                    api_key: apiKey,
                    user_id: uploadPostUser,
                    platforms: sharePlatforms,
                }),
            });

            if (!response.ok) {
                const detail = await response.text();
                setError(detail || "Share failed");
                return;
            }

            globalThis.alert("Share request sent.");
        } catch (err) {
            globalThis.alert(err.message || "Share failed");
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
                    <p className="mt-2 text-sm text-zinc-400">{subtitle}</p>
                </div>

                <button
                    type="button"
                    onClick={() => navigate(createRoute)}
                    className="flex items-center gap-2 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors group"
                >
                    <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0">
                        <Plus size={16} />
                    </div>
                    <div className="hidden lg:block overflow-hidden">
                        <p className="text-sm font-bold text-white leading-none mb-0.5">Démarrer une action</p>
                    </div>
                </button>
            </div>

            <section className="rounded-2xl border border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                <div className="grid gap-3 md:grid-cols-[1fr_220px_auto]">
                    <label className="relative">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                        <input
                            value={queryInput}
                            onChange={(e) => setQueryInput(e.target.value)}
                            placeholder="Rechercher par titre ou description..."
                            className="w-full rounded-xl border border-white/10 bg-black/30 py-2.5 pl-10 pr-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-primary/60"
                        />
                    </label>

                    <select
                        value={status}
                        onChange={(e) => {
                            setPage(1);
                            setStatus(e.target.value);
                        }}
                        className="rounded-xl border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white focus:outline-none focus:border-primary/60"
                    >
                        <option value="">Tous les statuts</option>
                        <option value="en_cours">En cours</option>
                        <option value="termine">Termine</option>
                        <option value="echec">Echec</option>
                    </select>

                    <button
                        type="button"
                        onClick={refresh}
                        className="rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-zinc-200 hover:bg-white/10"
                    >
                        Rafraichir
                    </button>
                </div>

                <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                        <thead>
                            <tr className="border-b border-white/10 text-left text-zinc-400">
                                <th className="px-3 py-3 font-medium">Titre</th>
                                <th className="px-3 py-3 font-medium">Description</th>
                                <th className="px-3 py-3 font-medium">Duree</th>
                                <th className="px-3 py-3 font-medium">Statut</th>
                                <th className="px-3 py-3 font-medium">Cree le</th>
                                <th className="px-3 py-3 font-medium text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading && (
                                <tr>
                                    <td colSpan={6} className="px-3 py-10 text-center text-zinc-400">
                                        <span className="inline-flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Chargement...</span>
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
                                    <td colSpan={6} className="px-3 py-10 text-center text-zinc-400">{emptyLabel}</td>
                                </tr>
                            )}

                            {!loading && !error &&
                                items.map((item) => (
                                    <tr key={item.id} className="border-b border-white/5 align-top">
                                        <td className="px-3 py-3">
                                            {item.media_thumbnail_url ? (
                                                <img
                                                    src={item.media_thumbnail_url}
                                                    alt={item.media_title || "thumbnail"}
                                                    className="mb-2 h-16 w-10 rounded-md object-cover border border-white/10"
                                                />
                                            ) : null}
                                            <p className="font-semibold text-white line-clamp-2">{item.media_title || "Sans titre"}</p>
                                            <p className="mt-1 text-xs text-zinc-500">ID: {item.id}</p>
                                        </td>
                                        <td className="px-3 py-3 text-zinc-300 max-w-md">
                                            <p className="line-clamp-3">{item.media_description || "-"}</p>
                                        </td>
                                        <td className="px-3 py-3 text-zinc-300">{item.media_duration ? `${item.media_duration}s` : "-"}</td>
                                        <td className="px-3 py-3">
                                            <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusClass(item.media_status)}`}>
                                                {statusLabel(item.media_status)}
                                            </span>
                                        </td>
                                        <td className="px-3 py-3 text-zinc-400">{item.media_created_at ? new Date(item.media_created_at).toLocaleString() : "-"}</td>
                                        <td className="px-3 py-3">
                                            <div className="flex justify-end gap-2">
                                                <button
                                                    type="button"
                                                    onClick={() => handlePreview(item)}
                                                    className="rounded-lg border border-white/10 bg-white/5 p-2 text-zinc-300 hover:bg-white/10"
                                                    title="Visualiser"
                                                >
                                                    <Play size={14} />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleDownload(item.id)}
                                                    className="rounded-lg border border-white/10 bg-white/5 p-2 text-zinc-300 hover:bg-white/10"
                                                    title="Télécharger"
                                                >
                                                    <Download size={14} />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleShare(item.id)}
                                                    disabled={sharingId === item.id}
                                                    className="rounded-lg border border-white/10 bg-white/5 p-2 text-zinc-300 hover:bg-white/10 disabled:opacity-60"
                                                    title="Partager"
                                                >
                                                    <Share2 size={14} />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleDelete(item.id)}
                                                    disabled={deletingId === item.id}
                                                    className="rounded-lg border border-red-500/20 bg-red-500/10 p-2 text-red-300 hover:bg-red-500/20 disabled:opacity-60"
                                                    title="Supprimer"
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

                <div className="flex flex-col gap-3 border-t border-white/10 pt-4 md:flex-row md:items-center md:justify-between">
                    <p className="text-xs text-zinc-500">
                        Page {page} sur {totalPages} · {total} résultat{total > 1 ? "s" : ""}
                    </p>
                    <div className="flex flex-wrap gap-2">
                        <button
                            type="button"
                            disabled={page <= 1}
                            onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                            className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-zinc-200 disabled:opacity-40"
                        >
                            Précédent
                        </button>
                        <button
                            type="button"
                            disabled={page >= totalPages}
                            onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                            className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-zinc-200 disabled:opacity-40"
                        >
                            Suivant
                        </button>
                    </div>
                </div>
            </section>

            {previewItem && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md">
                    <div className="flex w-full max-w-[420px] flex-col overflow-hidden rounded-[2rem] border border-white/10 bg-zinc-950 shadow-2xl">
                        <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                            <div>
                                <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Prévisualisation</p>
                                <h3 className="text-sm font-semibold text-white">{previewItem.media_title || "Sans titre"}</h3>
                            </div>
                            <button
                                type="button"
                                onClick={() => {
                                    setPreviewItem(null);
                                    setPreviewUrl("");
                                }}
                                className="rounded-full border border-white/10 bg-white/5 p-2 text-zinc-300 hover:bg-white/10"
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

                        <div className="space-y-3 border-t border-white/10 px-4 py-4 text-sm text-zinc-300">
                            <p className="line-clamp-4 text-zinc-400">{previewItem.media_description || "Aucune description."}</p>
                            <div className="flex items-center gap-2 text-xs text-zinc-500">
                                <span className={`rounded-full border px-2 py-1 ${statusClass(previewItem.media_status)}`}>{statusLabel(previewItem.media_status)}</span>
                                <span>{previewItem.media_duration ? `${previewItem.media_duration}s` : "Durée inconnue"}</span>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

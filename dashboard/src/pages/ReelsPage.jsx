import { useEffect, useMemo, useState } from "react";
import { Play, Plus, Download, Loader2, Search, Share2, Trash2, X } from "lucide-react";
import { getApiUrl } from "../config";
import { useAuth } from "../state/AuthContext";
import { useNavigate } from "react-router-dom";
import ResultCard from "../components/ResultCard";
import SharePostModal from "../components/SharePostModal";
import { decrypt } from "../lib/encryption";
import { getConnectedPlatforms } from "../lib/platforms";
import { toResultCardClip } from "../lib/clips";
import { statusLabel, statusClass } from "../lib/status";

export default function ReelsPage() {
    const { user } = useAuth();
    const connectedPlatforms = getConnectedPlatforms();
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
    const navigate = useNavigate();

    const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);

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
        if (!globalThis.confirm("Supprimer ce reel ?")) return;

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
            globalThis.alert("No download url available");
            return;
        }

        globalThis.open(mediaUrl, "_blank", "noopener,noreferrer");
    };

    const handleShare = (item) => {
        const fallbackPlatforms = ['tiktok', 'instagram', 'youtube'];
        const nextDefaultPlatforms = connectedPlatforms.length > 0 ? connectedPlatforms : fallbackPlatforms;
        setSharePlatforms({
            tiktok: nextDefaultPlatforms.includes('tiktok'),
            instagram: nextDefaultPlatforms.includes('instagram'),
            youtube: nextDefaultPlatforms.includes('youtube'),
            facebook: nextDefaultPlatforms.includes('facebook'),
            linkedin: nextDefaultPlatforms.includes('linkedin'),
        });
        setShareTitle(item?.reel_title || "Viral Short");
        setShareDescription(item?.reel_description || "");
        setShareScheduling(false);
        setShareScheduleDate("");
        setShareResult(null);
        setShareModalItem(item);
    };

    const submitShare = async () => {
        if (!user?.id) return;
        if (!shareModalItem?.id) return;

        const selectedPlatforms = Object.keys(sharePlatforms).filter((k) => Boolean(sharePlatforms[k]));
        if (selectedPlatforms.length === 0) {
            setShareResult({ success: false, msg: "Select at least one platform." });
            return;
        }
        if (shareScheduling && !shareScheduleDate) {
            setShareResult({ success: false, msg: "Please select a date and time." });
            return;
        }

        const encryptedUploadPostKey = localStorage.getItem("uploadPostKey_v3") || "";
        const apiKey = decrypt(encryptedUploadPostKey);
        const uploadPostUser = globalThis.localStorage.getItem("uploadUserId") || "";

        setSharingId(shareModalItem.id);
        setShareResult(null);
        try {
            const payload = {
                platforms: selectedPlatforms,
                title: shareTitle || undefined,
                description: shareDescription || undefined,
            };
            if (apiKey) payload.api_key = apiKey;
            if (uploadPostUser) payload.user_id = uploadPostUser;
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
                let msg = "Share failed";
                try {
                    const parsed = JSON.parse(errText);
                    msg = parsed?.detail || errText || msg;
                } catch {
                    msg = errText || msg;
                }
                setShareResult({ success: false, msg: `Failed: ${msg}` });
                return;
            }

            setShareResult({ success: true, msg: "Share request sent." });
            setTimeout(() => {
                setShareResult(null);
                setShareModalItem(null);
            }, 1500);
        } catch (err) {
            setShareResult({ success: false, msg: `Failed: ${err.message || "Share failed"}` });
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
                    <h1 className="text-3xl font-black tracking-tight">Reels generes</h1>
                    <p className="mt-2 text-sm text-zinc-400">Recherche, filtre, suppression, partage et telechargement.</p>
                </div>

                <button
                    type="button"
                    onClick={() => {
                        navigate("/dashboard/clip-generator?new=1");
                    }}
                    className="flex items-center gap-2 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors group"
                >
                    <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0">
                        <Plus size={16} />
                    </div>
                    <div className="hidden lg:block overflow-hidden">
                        <p className="text-sm font-bold text-white leading-none mb-0.5">Nouvelle opération</p>
                    </div>
                </button>
            </div>

            <section className="rounded-2xl border border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                {shareResult ? (
                    <div className={`rounded-lg border px-3 py-2 text-xs ${shareResult.success ? 'border-green-500/30 bg-green-500/10 text-green-300' : 'border-red-500/30 bg-red-500/10 text-red-300'}`}>
                        {shareResult.msg}
                    </div>
                ) : null}
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
                                <th className="px-3 py-3 font-medium">Reel</th>
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
                                        <span className="inline-flex items-center gap-2">
                                            <Loader2 size={14} className="animate-spin" /> Chargement...
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
                                    <td colSpan={6} className="px-3 py-10 text-center text-zinc-400">
                                        Aucun reel trouve.
                                    </td>
                                </tr>
                            )}

                            {!loading && !error &&
                                items.map((item) => (
                                    <tr key={item.id} className="border-b border-white/5 align-top">
                                        <td className="px-3 py-3">
                                            {item.reel_thumbnail_url ? (
                                                <img
                                                    src={item.reel_thumbnail_url}
                                                    alt={item.reel_title || "thumbnail"}
                                                    className="mb-2 h-16 w-10 rounded-md object-cover border border-white/10"
                                                />
                                            ) : null}
                                            <p className="font-semibold text-white line-clamp-2">{item.reel_title || "Sans titre"}</p>
                                            <p className="mt-1 text-xs text-zinc-500">ID: {item.id}</p>
                                        </td>
                                        <td className="px-3 py-3 text-zinc-300 max-w-md">
                                            <p className="line-clamp-3">{item.reel_description || "-"}</p>
                                        </td>
                                        <td className="px-3 py-3 text-zinc-300">{item.reel_duration ? `${item.reel_duration}s` : "-"}</td>
                                        <td className="px-3 py-3">
                                            <span className={`inline-flex rounded-full border px-2 py-1 text-xs ${statusClass(item.reel_status)}`}>
                                                {statusLabel(item.reel_status)}
                                            </span>
                                        </td>
                                        <td className="px-3 py-3 text-zinc-400">
                                            {item.reel_created_at ? new Date(item.reel_created_at).toLocaleString() : "-"}
                                        </td>
                                        <td className="px-3 py-3">
                                            <div className="flex items-center justify-end gap-2">
                                                <button
                                                    type="button"
                                                    onClick={() => handlePreview(item)}
                                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-zinc-200 hover:bg-white/10"
                                                    title="Visualiser"
                                                >
                                                    <Play size={14} />
                                                </button>

                                                <button
                                                    type="button"
                                                    onClick={() => handleDownload(item.id)}
                                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-zinc-200 hover:bg-white/10"
                                                    title="Telecharger"
                                                >
                                                    <Download size={14} />
                                                </button>

                                                <button
                                                    type="button"
                                                    onClick={() => handleShare(item)}
                                                    disabled={sharingId === item.id}
                                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50"
                                                    title="Partager"
                                                >
                                                    {sharingId === item.id ? <Loader2 size={14} className="animate-spin" /> : <Share2 size={14} />}
                                                </button>

                                                <button
                                                    type="button"
                                                    onClick={() => handleDelete(item.id)}
                                                    disabled={deletingId === item.id}
                                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 disabled:opacity-50"
                                                    title="Supprimer"
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

                <div className="flex items-center justify-between border-t border-white/10 pt-4 text-sm">
                    <p className="text-zinc-400">{total} reel(s)</p>
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page <= 1}
                            className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-zinc-300 disabled:opacity-40"
                        >
                            Precedent
                        </button>
                        <span className="text-zinc-400">
                            Page {page} / {totalPages}
                        </span>
                        <button
                            type="button"
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page >= totalPages}
                            className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-zinc-300 disabled:opacity-40"
                        >
                            Suivant
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
                hasLocalCredentials={Boolean(decrypt(globalThis.localStorage.getItem("uploadPostKey_v3") || "") && globalThis.localStorage.getItem("uploadUserId"))}
            />

            {previewItem && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md">
                    <div className="flex w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-white/10 bg-zinc-950 shadow-2xl">
                        <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                            <div>
                                <p className="text-sm font-semibold text-white">{previewItem.reel_title || "Visualisation du reel"}</p>
                                <p className="text-xs text-zinc-400">Apercu avec les memes actions que les clips generes.</p>
                            </div>
                            <button
                                type="button"
                                onClick={() => {
                                    setPreviewItem(null);
                                    setPreviewUrl("");
                                }}
                                className="rounded-lg border border-white/10 bg-white/5 p-2 text-zinc-300 hover:bg-white/10"
                                title="Fermer"
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

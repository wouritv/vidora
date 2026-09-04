import React, { useState, useEffect } from 'react';
import { Share2, Camera, Clapperboard, Video, AlertCircle, Loader2, Wand2, Type, SlidersHorizontal, X, RotateCcw, Play } from 'lucide-react';
import { fetchAppConfig, getApiUrl, getDefaultHideSocialPlatforms } from '../config';
import CaptionsModal from './CaptionsModal';
import HookModal from './HookModal';
import SharePostModal from './SharePostModal';
import { renderInBrowser } from '../lib/renderInBrowser';
import { getConnectedPlatforms } from '../lib/platforms';
import { inputFilenameFromVideoUrl } from '../lib/clips';
import { useAuth } from '../state/AuthContext';
import { useUserCredits } from '../state/UserCreditsContext';
import { useTranslation } from "../state/LanguageContext";
function readConnectedPlatformsFromSettings() {
    return getConnectedPlatforms();
}

const parseApiErrorText = (rawText) => {
    try {
        const parsed = JSON.parse(rawText || '{}');
        return parsed?.detail || rawText || 'Request failed';
    } catch {
        return rawText || 'Request failed';
    }
};

const isLikelyVideoAsset = (value) => {
    const text = String(value || '').trim().toLowerCase();
    if (!text) return false;
    const withoutQuery = text.split('?')[0];
    return ['.mp4', '.mov', '.webm', '.mkv', '.m4v'].some((ext) => withoutQuery.endsWith(ext));
};

export default function ResultCard({ clip, index, jobId, onPlay, onPause, compactActions = false, hideVideoPreview = false }) {
    const { t } = useTranslation();
    const { user } = useAuth();
    const { credits, defaultCosts } = useUserCredits();
    const safeClip = clip && typeof clip === 'object' ? clip : {};
    const clipIndexForApi = Number.isFinite(Number(safeClip.reel_clip_index))
        ? Number(safeClip.reel_clip_index)
        : index;
    const clipStart = Number.isFinite(Number(safeClip.start)) ? Number(safeClip.start) : 0;
    const clipEnd = Number.isFinite(Number(safeClip.end)) ? Number(safeClip.end) : clipStart + 30;
    const rawVideoUrl = typeof (safeClip.reel_playback_url || safeClip.caption_playback_url || safeClip.media_url || safeClip.video_url) === 'string'
        ? (safeClip.reel_playback_url || safeClip.caption_playback_url || safeClip.media_url || safeClip.video_url)
        : '';
    const connectedPlatforms = readConnectedPlatformsFromSettings();
    const defaultPlatforms = connectedPlatforms.length > 0 ? connectedPlatforms : ['tiktok', 'instagram', 'youtube'];
    const hasClipContext = Boolean(jobId) && Number.isFinite(Number(clipIndexForApi));
    const hasAnyEditingCredit = Number(credits || 0) > 0;
    const publicationCostEstimate = Number(defaultCosts?.publication || 1);
    const canShare = credits >= publicationCostEstimate;

    const [showModal, setShowModal] = useState(false);
    const [showCaptionsModal, setShowCaptionsModal] = useState(false);
    const videoRef = React.useRef(null);
    const originalVideoUrl = rawVideoUrl ? getApiUrl(rawVideoUrl) : '';
    const [currentVideoUrl, setCurrentVideoUrl] = useState(originalVideoUrl);

    const [platforms, setPlatforms] = useState({
        tiktok: defaultPlatforms.includes('tiktok'),
        instagram: defaultPlatforms.includes('instagram'),
        youtube: defaultPlatforms.includes('youtube'),
        facebook: defaultPlatforms.includes('facebook'),
        linkedin: defaultPlatforms.includes('linkedin'),
    });
    const [postTitle, setPostTitle] = useState("");
    const [postDescription, setPostDescription] = useState("");
    const [isScheduling, setIsScheduling] = useState(false);
    const [scheduleDate, setScheduleDate] = useState("");

    const [posting, setPosting] = useState(false);
    const [postResult, setPostResult] = useState(null);

    const [isEditing, setIsEditing] = useState(false);
    const [showAutoEditModal, setShowAutoEditModal] = useState(false);
    const [showVideoPreviewModal, setShowVideoPreviewModal] = useState(false);
    const [autoEditOptions, setAutoEditOptions] = useState({
        zoom: false,
        brightness: false,
        saturation: false,
        contrast: false,
        speed: false,
        removeSilence: false,
        cleanAudio: false,
        removeBadTakes: false,
    });
    const [isCaptioning, setIsCaptioning] = useState(false);
    const [isResettingStyles, setIsResettingStyles] = useState(false);
    const [captionsCreditBlocked, setCaptionsCreditBlocked] = useState(false);
    const [captionsCreditError, setCaptionsCreditError] = useState('');
    const [isHooking, setIsHooking] = useState(false);
    const [showHookModal, setShowHookModal] = useState(false);
    const [editError, setEditError] = useState(null);
    const [hideSocialPlatforms, setHideSocialPlatforms] = useState(getDefaultHideSocialPlatforms());

    const [clipDuration, setClipDuration] = useState(Math.max(1, clipEnd - clipStart));
    const autoEditLabel = isEditing ? t("common.editing", "Editing...") : t("common.autoEdit", "Auto Edit");
    const hookLabel = isHooking ? t("common.adding", "Adding...") : t("common.viralhook", "Viral Hook");
    const captionsLabel = isCaptioning ? t("common.adding", "Adding...") : t('common.subtitles', 'Subtitles');
    const resetLabel = isResettingStyles ? t("common.loading", "Loading...") : t('captionsModal.resetVideo', 'Reset');
    const insufficientCreditsMessage = () => (
        t("common.insufficientCreditsStart", "Crédits insuffisants pour initier cette opération.")
    );


    // Accumulate Remotion layers across operations
    const [activeLayers, setActiveLayers] = useState({ subtitles: null, captions: null, hook: null, effects: null });
    const latestEditableVideoUrl = currentVideoUrl || originalVideoUrl;
    const initialPreviewImageUrl = safeClip.preview_image_url || safeClip.thumbnail_url || safeClip.reel_preview_url || safeClip.reel_thumbnail_url || safeClip.caption_preview_url || safeClip.caption_thumbnail_url || '';
    const [previewImageUrl, setPreviewImageUrl] = useState(initialPreviewImageUrl);
    const [thumbnailEnsureAttempted, setThumbnailEnsureAttempted] = useState(false);
    const [isThumbnailRegenerating, setIsThumbnailRegenerating] = useState(false);

    const resolveTextLayer = (layers) => layers?.captions || layers?.subtitles || null;

    // Fetch clip duration from transcript endpoint
    useEffect(() => {
        if (!jobId || !Number.isFinite(Number(clipIndexForApi))) return;
        fetch(getApiUrl(`/api/clip/${jobId}/${clipIndexForApi}/transcript`))
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                if (data?.durationSec) setClipDuration(data.durationSec);
                if (data?.remotionLayers && typeof data.remotionLayers === 'object') {
                    setActiveLayers((prev) => ({
                        ...prev,
                        ...(data.remotionLayers || {}),
                    }));
                }
            })
            .catch(() => {});
    }, [jobId, clipIndexForApi]);

    // Keep player source in sync when preview URL updates (fixes stale/empty playback in modal previews).
    useEffect(() => {
        setCurrentVideoUrl(originalVideoUrl);
    }, [originalVideoUrl]);

    useEffect(() => {
        if (!videoRef.current) return;
        videoRef.current.pause();
        videoRef.current.load();
    }, [currentVideoUrl]);

    useEffect(() => {
        let active = true;
        fetchAppConfig()
            .then((cfg) => {
                if (!active || !cfg || typeof cfg.hideSocialPlatforms !== 'boolean') return;
                setHideSocialPlatforms(cfg.hideSocialPlatforms);
            })
            .catch(() => {});
        return () => {
            active = false;
        };
    }, []);

    useEffect(() => {
        if (showCaptionsModal) {
            setCaptionsCreditBlocked(false);
            setCaptionsCreditError('');
        }
    }, [showCaptionsModal]);

    useEffect(() => {
        setPreviewImageUrl(initialPreviewImageUrl);
    }, [initialPreviewImageUrl]);

    useEffect(() => {
        setThumbnailEnsureAttempted(false);
    }, [jobId, clipIndexForApi]);

    useEffect(() => {
        const needsImageFallback = !previewImageUrl || isLikelyVideoAsset(previewImageUrl);
        if (!hideVideoPreview || !hasClipContext || !needsImageFallback || thumbnailEnsureAttempted) return;

        const controller = new AbortController();
        let cancelled = false;
        setThumbnailEnsureAttempted(true);
        setIsThumbnailRegenerating(true);

        // Prevent stuck loading badge if backend hangs on legacy thumbnail generation.
        const timeoutId = window.setTimeout(() => controller.abort(), 20000);

        fetch(getApiUrl(`/api/clip/${jobId}/${clipIndexForApi}/preview-image/ensure`), {
            headers: {
                ...(user?.id ? { 'X-User-Id': user.id } : {}),
            },
            signal: controller.signal,
        })
            .then((res) => (res.ok ? res.json() : null))
            .then((data) => {
                if (cancelled) return;
                const nextImage = typeof data?.preview_image_url === 'string' ? data.preview_image_url : '';
                if (nextImage) setPreviewImageUrl(nextImage);
            })
            .catch(() => {})
            .finally(() => {
                window.clearTimeout(timeoutId);
                if (!cancelled) setIsThumbnailRegenerating(false);
            });

        return () => {
            cancelled = true;
            controller.abort();
            window.clearTimeout(timeoutId);
        };
    }, [thumbnailEnsureAttempted, hideVideoPreview, hasClipContext, previewImageUrl, jobId, clipIndexForApi, user?.id]);

    useEffect(() => {
        const hasValidPreviewImage = Boolean(previewImageUrl) && !isLikelyVideoAsset(previewImageUrl);
        if (hasValidPreviewImage) {
            setIsThumbnailRegenerating(false);
        }
    }, [previewImageUrl]);

    // Release generated object URLs to avoid leaking browser memory.
    useEffect(() => () => {
        if (currentVideoUrl?.startsWith('blob:')) {
            URL.revokeObjectURL(currentVideoUrl);
        }
    }, [currentVideoUrl]);

    useEffect(() => {
        const nextPlatforms = {
            tiktok: defaultPlatforms.includes('tiktok'),
            instagram: defaultPlatforms.includes('instagram'),
            youtube: defaultPlatforms.includes('youtube'),
            facebook: defaultPlatforms.includes('facebook'),
            linkedin: defaultPlatforms.includes('linkedin'),
        };
        setPlatforms((prev) => {
            const changed = Object.keys(nextPlatforms).some((k) => prev[k] !== nextPlatforms[k]);
            return changed ? nextPlatforms : prev;
        });
    }, [defaultPlatforms.join('|')]);

    // Initialize/Reset form when modal opens
    useEffect(() => {
        if (showModal) {
            setPostTitle(safeClip.video_title_for_youtube_short || "Viral Short");
            setPostDescription(safeClip.video_description_for_instagram || safeClip.video_description_for_tiktok || "");
            setIsScheduling(false);
            setScheduleDate("");
            setPostResult(null);
        }
    }, [showModal, clip]);

    const handleAutoEdit = async (selectedOptions = autoEditOptions) => {
        if (!hasAnyEditingCredit) {
            setEditError(insufficientCreditsMessage());
            setTimeout(() => setEditError(null), 5000);
            return;
        }
        if (!hasClipContext) {
            setEditError(t("reels.noActionAvailable", "Actions indisponibles: ce reel est detache de son job original."));
            setTimeout(() => setEditError(null), 5000);
            return;
        }
        setIsEditing(true);
        setEditError(null);
        try {
            const effectiveInputUrl = currentVideoUrl?.startsWith('blob:') ? originalVideoUrl : currentVideoUrl;
            const requiresBackendMediaPipeline = Boolean(
                selectedOptions?.removeSilence
                || selectedOptions?.cleanAudio
                || selectedOptions?.removeBadTakes
                || selectedOptions?.speed
            );
            // Gemini API Key is now configured server-side via .env
            // No need to send header from frontend

            // Try Remotion effects endpoint first
            if (!requiresBackendMediaPipeline) {
                const effectsRes = await fetch(getApiUrl('/api/effects/generate'), {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(user?.id ? { 'X-User-Id': user.id } : {}),
                    },
                    body: JSON.stringify({
                        job_id: jobId,
                        clip_index: clipIndexForApi,
                        input_filename: inputFilenameFromVideoUrl(currentVideoUrl),
                        input_url: effectiveInputUrl,
                        auto_edit_options: selectedOptions,
                    })
                });

                if (effectsRes.ok) {
                    const data = await effectsRes.json();
                    if (data?.effects?.segments) {
                        const newLayers = { ...activeLayers, effects: data.effects };
                        setActiveLayers(newLayers);
                        const blobUrl = await renderInBrowser({
                            videoUrl: originalVideoUrl,
                            durationInSeconds: clipDuration,
                            subtitles: resolveTextLayer(newLayers),
                            hook: newLayers.hook,
                            effects: newLayers.effects,
                        });
                        setCurrentVideoUrl(blobUrl);
                        if (videoRef.current) videoRef.current.load();
                        return;
                    }
                }
            }

            // Fallback: legacy FFmpeg edit endpoint
            const res = await fetch(getApiUrl('/api/edit'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(user?.id ? { 'X-User-Id': user.id } : {}),
                },
                body: JSON.stringify({
                    job_id: jobId,
                    clip_index: clipIndexForApi,
                    input_filename: inputFilenameFromVideoUrl(currentVideoUrl),
                    input_url: effectiveInputUrl,
                    auto_edit_options: selectedOptions,
                })
            });

            if (!res.ok) {
                const errText = await res.text();
                setEditError(parseApiErrorText(errText));
                setTimeout(() => setEditError(null), 5000);
                return;
            }

            const data = await res.json();
            if (data.new_video_url) {
                setCurrentVideoUrl(getApiUrl(data.new_video_url));
                if (videoRef.current) {
                    videoRef.current.load();
                }
            }

        } catch (e) {
            setEditError(e.message);
            setTimeout(() => setEditError(null), 5000);
        } finally {
            setIsEditing(false);
        }
    };

    const handleApplyAutoEdit = async () => {
        setShowAutoEditModal(false);
        await handleAutoEdit(autoEditOptions);
    };


    const handleCaptions = async (options) => {
        if (!hasAnyEditingCredit) {
            setEditError(insufficientCreditsMessage());
            setTimeout(() => setEditError(null), 5000);
            return;
        }
        if (!hasClipContext) {
            setEditError(t("reels.noActionAvailable", "Actions indisponibles: ce reel est detache de son job original."));
            setTimeout(() => setEditError(null), 5000);
            return;
        }

        setIsCaptioning(true);
        setEditError(null);
        setCaptionsCreditBlocked(false);
        setCaptionsCreditError('');
        try {
            const nextDurationSec = Number.isFinite(Number(options.previewDurationSec)) && Number(options.previewDurationSec) > 0
                ? Number(options.previewDurationSec)
                : clipDuration;
            const captionLayer = options.remotion || null;
            if (!captionLayer || !Array.isArray(captionLayer.captions) || captionLayer.captions.length === 0) {
                setEditError(t('captionsModal.noCaptions', 'No captions available for this clip.'));
                setTimeout(() => setEditError(null), 5000);
                return;
            }

            const newLayers = { ...activeLayers, captions: captionLayer, subtitles: null };
            setActiveLayers(newLayers);
            setClipDuration(nextDurationSec);
            const blobUrl = await renderInBrowser({
                videoUrl: originalVideoUrl,
                durationInSeconds: nextDurationSec,
                subtitles: resolveTextLayer(newLayers),
                hook: newLayers.hook,
                effects: newLayers.effects,
            });
            setCurrentVideoUrl(blobUrl);
            if (videoRef.current) videoRef.current.load();

            const renderedBlob = await fetch(blobUrl).then((res) => res.blob());
            const formData = new FormData();
            formData.append('file', renderedBlob, `captioned_${jobId}_${clipIndexForApi}.mp4`);
            formData.append('subtitle_config', JSON.stringify(captionLayer));
            formData.append('remotion_layers', JSON.stringify(newLayers));

            const persistRes = await fetch(getApiUrl(`/api/reels/${jobId}/${clipIndexForApi}/captions/persist`), {
                method: 'POST',
                headers: {
                    ...(user?.id ? { 'X-User-Id': user.id } : {}),
                },
                body: formData,
            });

            if (!persistRes.ok) {
                const status = persistRes.status;
                const raw = await persistRes.text();
                let detail = raw;
                try {
                    const parsed = JSON.parse(raw);
                    detail = parsed?.detail || raw;
                } catch {
                    // Keep raw fallback.
                }
                if (status === 402) {
                    const creditMsg = detail || t('captionsModal.insufficientCredits', 'Insufficient credits to generate captions for this reel.');
                    setCaptionsCreditBlocked(true);
                    setCaptionsCreditError(creditMsg);
                    setEditError(creditMsg);
                    setTimeout(() => setEditError(null), 5000);
                    return;
                }
                setEditError(detail || 'Caption persistence failed');
                setTimeout(() => setEditError(null), 5000);
                return;
            }

            const persistData = await persistRes.json();
            if (persistData?.preview_image_url) {
                setPreviewImageUrl(String(persistData.preview_image_url));
            }
            if (persistData.new_video_url) {
                if (blobUrl.startsWith('blob:')) {
                    URL.revokeObjectURL(blobUrl);
                }
                setCurrentVideoUrl(getApiUrl(persistData.new_video_url));
                if (videoRef.current) videoRef.current.load();
            }
            setShowCaptionsModal(false);
        } catch (e) {
            setEditError(e.message);
            setTimeout(() => setEditError(null), 5000);
        } finally {
            setIsCaptioning(false);
        }
    };

    const handleHook = async (hookData) => {
        if (!hasAnyEditingCredit) {
            setEditError(insufficientCreditsMessage());
            setTimeout(() => setEditError(null), 5000);
            return;
        }
        if (!hasClipContext) {
            setEditError(t("reels.noActionAvailable", "Actions indisponibles: ce reel est detache de son job original."));
            setTimeout(() => setEditError(null), 5000);
            return;
        }
        setIsHooking(true);
        setEditError(null);
        try {
            const effectiveInputUrl = currentVideoUrl?.startsWith('blob:') ? originalVideoUrl : currentVideoUrl;
            if (hookData.remotion) {
                // Accumulate layer and render all layers together
                const newLayers = { ...activeLayers, hook: hookData.remotion };
                setActiveLayers(newLayers);
                const blobUrl = await renderInBrowser({
                    videoUrl: originalVideoUrl,
                    durationInSeconds: clipDuration,
                        subtitles: resolveTextLayer(newLayers),
                    hook: newLayers.hook,
                    effects: newLayers.effects,
                });
                setCurrentVideoUrl(blobUrl);
                if (videoRef.current) videoRef.current.load();
                setShowHookModal(false);
                return;
            }

            // Fallback: legacy FFmpeg
            const payload = typeof hookData === 'string'
                ? { text: hookData, position: 'top', size: 'M' }
                : hookData;

            const res = await fetch(getApiUrl('/api/hook'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(user?.id ? { 'X-User-Id': user.id } : {}),
                },
                body: JSON.stringify({
                    job_id: jobId,
                    clip_index: clipIndexForApi,
                    text: payload.text,
                    position: payload.position,
                    size: payload.size,
                    input_filename: inputFilenameFromVideoUrl(currentVideoUrl),
                    input_url: effectiveInputUrl
                })
            });

            if (!res.ok) {
                const errText = await res.text();
                setEditError(parseApiErrorText(errText));
                setTimeout(() => setEditError(null), 5000);
                return;
            }
            const data = await res.json();
            if (data.new_video_url) {
                setCurrentVideoUrl(getApiUrl(data.new_video_url));
                if (videoRef.current) videoRef.current.load();
                setShowHookModal(false);
            }
        } catch (e) {
            setEditError(e.message);
            setTimeout(() => setEditError(null), 5000);
        } finally {
            setIsHooking(false);
        }
    };

    const handleResetStyles = async () => {
        if (!hasClipContext || !jobId) {
            setEditError(t("reels.noActionAvailable", "Actions indisponibles: ce reel est detache de son job original."));
            setTimeout(() => setEditError(null), 5000);
            return;
        }
        setIsResettingStyles(true);
        setEditError(null);
        try {
            const res = await fetch(getApiUrl(`/api/reels/${jobId}/${clipIndexForApi}/captions/reset`), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(user?.id ? { 'X-User-Id': user.id } : {}),
                },
            });
            if (!res.ok) {
                const errText = await res.text();
                setEditError(parseApiErrorText(errText));
                setTimeout(() => setEditError(null), 5000);
                return;
            }
            const data = await res.json();
            if (data.video_url) {
                setCurrentVideoUrl(getApiUrl(data.video_url));
                if (videoRef.current) videoRef.current.load();
            }
            setActiveLayers({ subtitles: null, captions: null, hook: null, effects: null });
        } catch (e) {
            setEditError(e.message);
            setTimeout(() => setEditError(null), 5000);
        } finally {
            setIsResettingStyles(false);
        }
    };

    const handlePost = async () => {
        if (!canShare) {
            setPostResult({ success: false, msg: insufficientCreditsMessage() });
            return;
        }
        if (!hasClipContext) {
            setPostResult({ success: false, msg: t("reels.noActionAvailable", "Publication indisponible: reel detache de son job original.") });
            return;
        }
        const selectedPlatforms = Object.keys(platforms).filter(k => platforms[k]);
        if (selectedPlatforms.length === 0) {
            setPostResult({ success: false, msg: t("reels.selectAtLeastOnePlatform", "Select at least one platform.") });
            return;
        }

        if (isScheduling && !scheduleDate) {
            setPostResult({ success: false, msg: t("reels.selectDateTime", "Please select a date and time.") });
            return;
        }

        setPosting(true);
        setPostResult(null);

        try {
            const payload = {
                job_id: jobId,
                    clip_index: clipIndexForApi,
                user_id: user?.id,
                platforms: selectedPlatforms,
                title: postTitle,
                description: postDescription
            };

            if (isScheduling && scheduleDate) {
                // Convert to ISO-8601
                payload.scheduled_date = new Date(scheduleDate).toISOString();
                // Optional: pass timezone if needed, backend defaults to UTC or we can send user's timezone
                payload.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            }

            const res = await fetch(getApiUrl('/api/social/post'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(user?.id ? { 'X-User-Id': user.id } : {}),
                },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const errText = await res.text();
                setPostResult({ success: false, msg: `Failed: ${parseApiErrorText(errText)}` });
                return;
            }

            setPostResult({ success: true, msg: isScheduling ? t("reels.scheduledSuccessfully", "Scheduled successfully!") : t("reels.postedSuccessfully", "Posted successfully!") });
            setTimeout(() => {
                setShowModal(false);
                setPostResult(null);
            }, 3000);

        } catch (e) {
            setPostResult({ success: false, msg: `Failed: ${e.message}` });
        } finally {
            setPosting(false);
        }
    };

    return (
        <div className="bg-surface border border-slate-200 dark:border-white/5 rounded-2xl overflow-hidden flex flex-col md:flex-row group hover:border-slate-300 dark:hover:border-white/10 transition-all animate-[fadeIn_0.5s_ease-out] min-h-[300px] h-auto" style={{ animationDelay: `${index * 0.1}s` }}>
            {/* Left: Video Preview (Responsive Width) */}
            <div className="w-full md:w-[180px] lg:w-[200px] bg-black relative shrink-0 aspect-[9/16] md:aspect-auto group/video">
                {hideVideoPreview ? (
                    previewImageUrl ? (
                        <img src={previewImageUrl} alt={`Clip ${index + 1}`} className="w-full h-full object-cover" loading="lazy" />
                    ) : (
                        <div className="relative h-full w-full overflow-hidden bg-zinc-900">
                            <div className="absolute inset-0 animate-pulse bg-gradient-to-br from-zinc-800 via-zinc-700 to-zinc-800" />
                            <div className="absolute inset-x-4 bottom-4 h-2 rounded bg-zinc-600/70" />
                            <div className="absolute inset-x-10 bottom-8 h-2 rounded bg-zinc-600/50" />
                        </div>
                    )
                ) : (
                    <video
                        key={currentVideoUrl || 'empty-video-src'}
                        ref={videoRef}
                        src={currentVideoUrl}
                        controls
                        className="w-full h-full object-cover"
                        playsInline
                        preload="metadata"
                        onPlay={() => {
                            const currentTime = videoRef.current ? videoRef.current.currentTime : 0;
                            onPlay?.(clipStart + currentTime);
                        }}
                        onPause={() => onPause?.()}
                        onEnded={() => {
                            if (videoRef.current) {
                                videoRef.current.currentTime = 0;
                                videoRef.current.play();
                            }
                        }}
                    />
                )}
                <div className="absolute top-3 left-3 flex gap-2">
                    <span className="bg-gradient-to-r from-indigo-600/95 to-blue-600/95 text-white text-[10px] font-bold px-2 py-1 rounded-md border border-indigo-300/40 shadow-md uppercase tracking-wide">
                        Clip {index + 1}
                    </span>
                </div>
                {hideVideoPreview && currentVideoUrl ? (
                    <button
                        type="button"
                        onClick={() => setShowVideoPreviewModal(true)}
                        className="absolute bottom-3 right-3 inline-flex items-center gap-1 rounded-md border border-cyan-200/50 bg-gradient-to-r from-cyan-600/95 to-sky-600/95 px-2 py-1 text-[10px] font-semibold text-white shadow-md hover:from-cyan-500 hover:to-sky-500"
                    >
                        <Play size={12} />
                        Preview
                    </button>
                ) : null}
                {hideVideoPreview && isThumbnailRegenerating ? (
                    <span className="absolute bottom-3 left-3 inline-flex items-center gap-1 rounded-md border border-amber-300/40 bg-amber-500/25 px-2 py-1 text-[10px] font-semibold text-amber-50 shadow-sm">
                        <Loader2 size={11} className="animate-spin" />
                        thumbnail regenerating...
                    </span>
                ) : null}

                {/* Auto Edit Overlay if Processing */}
                {isEditing && (
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex flex-col items-center justify-center z-10 p-4 text-center">
                        <Loader2 size={32} className="text-primary animate-spin mb-3" />
                        <span className="text-xs font-bold text-white uppercase tracking-wider">AI Magic in Progress...</span>
                        <span className="text-[10px] text-slate-500 dark:text-zinc-400 mt-1">Applying viral edits & zooms</span>
                    </div>
                )}
            </div>

            {/* Right: Content & Details */}
            <div className="flex-1 p-4 md:p-5 flex flex-col bg-white dark:bg-[#121214] overflow-hidden min-w-0">
                <div className="mb-4">
                    <h3 className="title-contrast text-base font-bold leading-tight line-clamp-2 mb-2 break-words" title={safeClip.video_title_for_youtube_short}>
                        {safeClip.video_title_for_youtube_short || "Viral Clip Generated"}
                    </h3>
                    <div className="flex flex-wrap gap-2 text-[10px] text-slate-400 dark:text-zinc-500 font-mono">
                        <span className="bg-white/5 px-1.5 py-0.5 rounded border border-slate-200 dark:border-white/5 shrink-0">{Math.floor(Math.max(1, clipEnd - clipStart))}s</span>
                        <span className="bg-white/5 px-1.5 py-0.5 rounded border border-slate-200 dark:border-white/5 shrink-0">#shorts</span>
                        <span className="bg-white/5 px-1.5 py-0.5 rounded border border-slate-200 dark:border-white/5 shrink-0">#viral</span>
                    </div>
                </div>

                {/* Scrollable Descriptions Area */}
                <div className="flex-1 overflow-y-auto custom-scrollbar space-y-3 pr-2 mb-4">
                    {/* YouTube */}
                    <div className="bg-slate-100 dark:bg-black/20 rounded-lg p-3 border border-slate-200 dark:border-white/5">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-red-400 mb-1.5 uppercase tracking-wider">
                            <Clapperboard size={12} className="shrink-0" /> <span className="truncate">{t("common.titleYoutube", "YouTube Title")}</span>
                        </div>
                        <p className="text-xs text-slate-700 dark:text-zinc-300 select-all break-words">
                            {safeClip.video_title_for_youtube_short || "Viral Short Video"}
                        </p>
                    </div>

                    {/* TikTok / IG */}
                    <div className="bg-slate-100 dark:bg-black/20 rounded-lg p-3 border border-slate-200 dark:border-white/5">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-slate-500 dark:text-zinc-400 mb-1.5 uppercase tracking-wider">
                            <Video size={12} className="text-cyan-400 shrink-0" />
                            <span className="text-slate-400 dark:text-zinc-500">/</span>
                            <Camera size={12} className="text-pink-400 shrink-0" />
                            <span className="truncate">{t("common.caption", "Caption")}</span>
                        </div>
                        <p className="text-xs text-slate-700 dark:text-zinc-300 line-clamp-3 hover:line-clamp-none transition-all cursor-pointer select-all break-words">
                            {safeClip.video_description_for_tiktok || safeClip.video_description_for_instagram}
                        </p>
                    </div>
                </div>

                {/* Error Message */}
                {editError && (
                    <div className="mb-3 p-2 bg-red-500/10 border border-red-500/20 text-red-400 text-[10px] rounded-lg flex items-center gap-2">
                        <AlertCircle size={12} className="shrink-0" />
                        {editError}
                    </div>
                )}

                {!hasAnyEditingCredit && (
                    <div className="mb-3 p-2 bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[10px] rounded-lg flex items-center gap-2">
                        <AlertCircle size={12} className="shrink-0" />
                        {insufficientCreditsMessage()}
                    </div>
                )}

                {/* Actions Footer */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-auto pt-4 border-t border-slate-200 dark:border-white/5">
                    <button
                        onClick={() => setShowAutoEditModal(true)}
                        disabled={isEditing || !hasClipContext || !hasAnyEditingCredit}
                        title="Auto Edit"
                        className={`col-span-1 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg text-xs font-bold shadow-lg shadow-purple-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 mb-1 truncate px-1 ${compactActions ? 'min-h-[40px]' : ''}`}
                    >
                        {isEditing ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}
                        {!compactActions ? autoEditLabel : null}
                    </button>

                    <button
                        onClick={() => setShowHookModal(true)}
                        disabled={isHooking || !hasClipContext || !hasAnyEditingCredit}
                        title="Viral Hook"
                        className={`col-span-1 py-2 bg-gradient-to-r from-amber-400 to-yellow-500 hover:from-amber-300 hover:to-yellow-400 text-black rounded-lg text-xs font-bold shadow-lg shadow-yellow-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 mb-1 truncate px-1 ${compactActions ? 'min-h-[40px]' : ''}`}
                    >
                        {isHooking ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}
                        {!compactActions ? hookLabel : null}
                    </button>

                    <button
                        onClick={() => setShowCaptionsModal(true)}
                        disabled={isCaptioning || !hasClipContext || !hasAnyEditingCredit}
                        title={t('common.subtitles', 'Subtitles')}
                        className={`col-span-1 py-2 bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 text-white rounded-lg text-xs font-bold shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 mb-1 truncate px-1 ${compactActions ? 'min-h-[40px]' : ''}`}
                    >
                        {isCaptioning ? <Loader2 size={14} className="animate-spin" /> : <Type size={14} />}
                        {!compactActions ? captionsLabel : null}
                    </button>

                    <button
                        onClick={handleResetStyles}
                        disabled={isResettingStyles || !hasClipContext}
                        title={t('captionsModal.resetVideo', 'Reset')}
                        className={`col-span-1 py-2 bg-rose-100 dark:bg-rose-500/10 hover:bg-rose-200 dark:hover:bg-rose-500/20 border border-rose-300/60 dark:border-rose-500/40 text-rose-700 dark:text-rose-200 rounded-lg text-xs font-bold transition-all active:scale-[0.98] flex items-center justify-center gap-2 mb-1 truncate px-1 ${compactActions ? 'min-h-[40px]' : ''}`}
                    >
                        {isResettingStyles ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
                        {!compactActions ? resetLabel : null}
                    </button>

                    {!hideSocialPlatforms ? (
                        <button
                            onClick={() => setShowModal(true)}
                            disabled={!hasClipContext || !canShare}
                            title={t("common.post", "Post")}
                            className={`col-span-1 py-2 bg-primary hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-xs font-bold shadow-lg shadow-primary/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 truncate px-2 ${compactActions ? 'min-h-[40px]' : ''}`}
                        >
                            <Share2 size={14} className="shrink-0" />
                            {!compactActions ? t("common.post", "Post") : null}
                        </button>
                    ) : null}
                </div>
            </div>

            {!hideSocialPlatforms ? (
                <SharePostModal
                    isOpen={showModal}
                    onClose={() => setShowModal(false)}
                    title={postTitle}
                    onTitleChange={setPostTitle}
                    description={postDescription}
                    onDescriptionChange={setPostDescription}
                    isScheduling={isScheduling}
                    onSchedulingChange={setIsScheduling}
                    scheduleDate={scheduleDate}
                    onScheduleDateChange={setScheduleDate}
                    platforms={platforms}
                    onPlatformChange={(platform, checked) => setPlatforms((prev) => ({ ...prev, [platform]: checked }))}
                    connectedPlatforms={connectedPlatforms}
                    isSubmitting={posting}
                    result={postResult}
                    onSubmit={handlePost}
                />
            ) : null}

            {showAutoEditModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
                    <div className="w-full max-w-lg rounded-2xl border border-slate-300 dark:border-white/10 bg-white dark:bg-zinc-950 p-5">
                        <div className="mb-4 flex items-center justify-between">
                            <h3 className="title-contrast text-lg font-bold inline-flex items-center gap-2">
                                <SlidersHorizontal size={16} className="text-primary" />
                                {t("common.autoEdit", "Auto Edit")}
                            </h3>
                            <button
                                type="button"
                                onClick={() => setShowAutoEditModal(false)}
                                className="rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 p-2 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-white/10"
                            >
                                <X size={14} />
                            </button>
                        </div>

                        <div className="space-y-2">
                            {[
                                ["zoom", t("zoom","Zoom")],
                                ["brightness", t("luminosity","Luminosite")],
                                ["saturation", t("saturation","Saturation")],
                                ["contrast", t("contrast","Contraste")],
                                ["speed", t("speed","Vitesse")],
                                ["removeSilence", t("removeSilence","Retirer les silences")],
                                ["cleanAudio", t("cleanAudio","Nettoyer l'audio")],
                                ["removeBadTakes", t("removeBadTakes","Retirer les mauvaises prises")],
                            ].map(([key, label]) => (
                                <label key={key} className="flex items-center justify-between rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-3 py-2 text-sm text-slate-800 dark:text-zinc-200">
                                    <span>{label}</span>
                                    <button
                                        type="button"
                                        onClick={() => setAutoEditOptions((prev) => ({ ...prev, [key]: !prev[key] }))}
                                        className={`rounded-full px-3 py-1 text-xs font-semibold ${autoEditOptions[key] ? "bg-emerald-500/20 text-emerald-300" : "bg-slate-200 dark:bg-black/40 text-slate-600 dark:text-slate-400"}`}
                                    >
                                        {autoEditOptions[key] ? "ON" : "OFF"}
                                    </button>
                                </label>
                            ))}
                        </div>

                        <button
                            type="button"
                            onClick={handleApplyAutoEdit}
                            disabled={isEditing}
                            className="mt-4 w-full rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
                        >
                            {isEditing ? t("common.editing", "Editing...") : t("captionsModal.apply", "Appliquer")}
                        </button>
                    </div>
                </div>
            )}


            <CaptionsModal
                isOpen={showCaptionsModal}
                onClose={() => setShowCaptionsModal(false)}
                onGenerate={handleCaptions}
                onResetStyles={handleResetStyles}
                isResettingStyles={isResettingStyles}
                isProcessing={isCaptioning}
                creditBlocked={captionsCreditBlocked}
                creditError={captionsCreditError}
                videoUrl={latestEditableVideoUrl}
                jobId={jobId}
                clipIndex={clipIndexForApi}
                existingHook={activeLayers.hook}
                existingEffects={activeLayers.effects}
            />

            <HookModal
                isOpen={showHookModal}
                onClose={() => setShowHookModal(false)}
                onGenerate={handleHook}
                isProcessing={isHooking}
                videoUrl={latestEditableVideoUrl}
                initialText={safeClip.viral_hook_text}
                durationInSeconds={Math.max(1, clipEnd - clipStart)}
                existingSubtitles={resolveTextLayer(activeLayers)}
            />

            {showVideoPreviewModal && currentVideoUrl ? (
                <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
                    <div className="w-full max-w-md overflow-hidden rounded-2xl border border-slate-300 dark:border-white/10 bg-white dark:bg-zinc-950">
                        <div className="flex items-center justify-between border-b border-slate-300 dark:border-white/10 px-4 py-3">
                            <p className="text-sm font-semibold text-slate-900 dark:text-white">{t('reels.preview', 'Preview')}</p>
                            <button
                                type="button"
                                onClick={() => setShowVideoPreviewModal(false)}
                                className="rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 p-2 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-white/10"
                            >
                                <X size={14} />
                            </button>
                        </div>
                        <div className="bg-black p-3">
                            <video src={currentVideoUrl} controls className="mx-auto max-h-[75vh] w-full rounded-lg" playsInline preload="metadata" />
                        </div>
                    </div>
                </div>
            ) : null}


        </div>
    );
}

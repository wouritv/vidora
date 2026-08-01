import React, { useState, useEffect } from 'react';
import { Share2, Instagram, Youtube, Video, CheckCircle, AlertCircle, X, Loader2, Wand2, Type, Calendar, Clock, Languages, Facebook, Linkedin } from 'lucide-react';
import { getApiUrl } from '../config';
import SubtitleModal from './SubtitleModal';
import HookModal from './HookModal';
import TranslateModal from './TranslateModal';
import { renderInBrowser } from '../lib/renderInBrowser';

const SECRET_KEY = import.meta.env.VITE_ENCRYPTION_KEY || 'OpenShorts-Static-Salt-Change-Me';
const ENCRYPTION_PREFIX = 'ENC:';
const SUPPORTED_SOCIAL_PLATFORMS = ['tiktok', 'instagram', 'youtube', 'facebook', 'linkedin'];

const PLATFORM_LABELS = {
    tiktok: 'TikTok',
    instagram: 'Instagram',
    youtube: 'YouTube Shorts',
    facebook: 'Facebook',
    linkedin: 'LinkedIn',
};

function decrypt(text) {
    if (!text) return '';
    if (!text.startsWith(ENCRYPTION_PREFIX)) return text;
    try {
        const raw = text.slice(ENCRYPTION_PREFIX.length);
        const xor = atob(raw);
        return xor
            .split('')
            .map((c, i) => String.fromCodePoint(c.codePointAt(0) ^ SECRET_KEY.codePointAt(i % SECRET_KEY.length)))
            .join('');
    } catch {
        return '';
    }
}

function readConnectedPlatformsFromSettings() {
    try {
        const raw = globalThis.localStorage.getItem('openshorts-connected-networks') || '{}';
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') return [];
        return SUPPORTED_SOCIAL_PLATFORMS.filter((platform) => Boolean(parsed[platform]));
    } catch {
        return [];
    }
}

function inputFilenameFromVideoUrl(videoUrl) {
    if (!videoUrl || videoUrl.startsWith('blob:')) return undefined;
    try {
        const clean = videoUrl.split('?')[0] || '';
        const filename = clean.split('/').pop();
        return filename || undefined;
    } catch {
        return undefined;
    }
}

export default function ResultCard({ clip, index, jobId, onPlay, onPause, compactActions = false }) {
    const safeClip = clip && typeof clip === 'object' ? clip : {};
    const clipStart = Number.isFinite(Number(safeClip.start)) ? Number(safeClip.start) : 0;
    const clipEnd = Number.isFinite(Number(safeClip.end)) ? Number(safeClip.end) : clipStart + 30;
    const rawVideoUrl = typeof safeClip.video_url === 'string' ? safeClip.video_url : '';
    const uploadPostKey = decrypt(globalThis.localStorage.getItem('uploadPostKey_v3') || '');
    const uploadUserId = globalThis.localStorage.getItem('uploadUserId') || '';
    const connectedPlatforms = readConnectedPlatformsFromSettings();
    const defaultPlatforms = connectedPlatforms.length > 0 ? connectedPlatforms : ['tiktok', 'instagram', 'youtube'];
    const hasClipContext = Boolean(jobId) && Number.isFinite(Number(index));

    const [showModal, setShowModal] = useState(false);
    const [showSubtitleModal, setShowSubtitleModal] = useState(false);
    const [showTranslateModal, setShowTranslateModal] = useState(false);
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
    const [isSubtitling, setIsSubtitling] = useState(false);
    const [isTranslating, setIsTranslating] = useState(false);
    const [isHooking, setIsHooking] = useState(false);
    const [showHookModal, setShowHookModal] = useState(false);
    const [editError, setEditError] = useState(null);

    const [clipDuration, setClipDuration] = useState(Math.max(1, clipEnd - clipStart));

    // Accumulate Remotion layers across operations
    const [activeLayers, setActiveLayers] = useState({ subtitles: null, hook: null, effects: null });

    // Fetch clip duration from transcript endpoint
    useEffect(() => {
        if (!jobId || index === undefined) return;
        fetch(getApiUrl(`/api/clip/${jobId}/${index}/transcript`))
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                if (data && data.durationSec) setClipDuration(data.durationSec);
            })
            .catch(() => {});
    }, [jobId, index]);

    // Keep player source in sync when preview URL updates (fixes stale/empty playback in modal previews).
    useEffect(() => {
        setCurrentVideoUrl(originalVideoUrl);
    }, [originalVideoUrl]);

    useEffect(() => {
        if (!videoRef.current) return;
        videoRef.current.pause();
        videoRef.current.load();
    }, [currentVideoUrl]);

    // Release generated object URLs to avoid leaking browser memory.
    useEffect(() => () => {
        if (currentVideoUrl && currentVideoUrl.startsWith('blob:')) {
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

    const handleAutoEdit = async () => {
        if (!hasClipContext) {
            setEditError('Actions indisponibles: ce reel est detache de son job original.');
            setTimeout(() => setEditError(null), 5000);
            return;
        }
        setIsEditing(true);
        setEditError(null);
        try {
            // Gemini API Key is now configured server-side via .env
            // No need to send header from frontend

            // Try Remotion effects endpoint first
            const effectsRes = await fetch(getApiUrl('/api/effects/generate'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    job_id: jobId,
                    clip_index: index,
                    input_filename: currentVideoUrl.split('/').pop()
                })
            });

            if (effectsRes.ok) {
                const data = await effectsRes.json();
                if (data.effects && data.effects.segments) {
                    const newLayers = { ...activeLayers, effects: data.effects };
                    setActiveLayers(newLayers);
                    const blobUrl = await renderInBrowser({
                        videoUrl: originalVideoUrl,
                        durationInSeconds: clipDuration,
                        subtitles: newLayers.subtitles,
                        hook: newLayers.hook,
                        effects: newLayers.effects,
                    });
                    setCurrentVideoUrl(blobUrl);
                    if (videoRef.current) videoRef.current.load();
                    return;
                }
            }

            // Fallback: legacy FFmpeg edit endpoint
            const res = await fetch(getApiUrl('/api/edit'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    job_id: jobId,
                    clip_index: index,
                    input_filename: currentVideoUrl.split('/').pop()
                })
            });

            if (!res.ok) {
                const errText = await res.text();
                try {
                    const jsonErr = JSON.parse(errText);
                    throw new Error(jsonErr.detail || errText);
                } catch (e) {
                    throw new Error(errText);
                }
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

    const handleSubtitle = async (options) => {
        if (!hasClipContext) {
            setEditError('Actions indisponibles: ce reel est detache de son job original.');
            setTimeout(() => setEditError(null), 5000);
            return;
        }
        setIsSubtitling(true);
        setEditError(null);
        try {
            if (options.remotion) {
                // Accumulate layer and render all layers together
                const newLayers = { ...activeLayers, subtitles: options.remotion };
                setActiveLayers(newLayers);
                const blobUrl = await renderInBrowser({
                    videoUrl: originalVideoUrl,
                    durationInSeconds: clipDuration,
                    subtitles: newLayers.subtitles,
                    hook: newLayers.hook,
                    effects: newLayers.effects,
                });
                setCurrentVideoUrl(blobUrl);
                if (videoRef.current) videoRef.current.load();
                setShowSubtitleModal(false);
                return;
            }

            // Fallback: legacy FFmpeg
            const res = await fetch(getApiUrl('/api/subtitle'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    job_id: jobId,
                    clip_index: index,
                    position: options.position,
                    font_size: options.fontSize,
                    font_name: options.fontName,
                    font_color: options.fontColor,
                    border_color: options.borderColor,
                    border_width: options.borderWidth,
                    bg_color: options.bgColor,
                    bg_opacity: options.bgOpacity,
                    input_filename: currentVideoUrl.split('/').pop()
                })
            });

            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            if (data.new_video_url) {
                setCurrentVideoUrl(getApiUrl(data.new_video_url));
                if (videoRef.current) videoRef.current.load();
                setShowSubtitleModal(false);
            }
        } catch (e) {
            setEditError(e.message);
            setTimeout(() => setEditError(null), 5000);
        } finally {
            setIsSubtitling(false);
        }
    };

    const handleHook = async (hookData) => {
        if (!hasClipContext) {
            setEditError('Actions indisponibles: ce reel est detache de son job original.');
            setTimeout(() => setEditError(null), 5000);
            return;
        }
        setIsHooking(true);
        setEditError(null);
        try {
            if (hookData.remotion) {
                // Accumulate layer and render all layers together
                const newLayers = { ...activeLayers, hook: hookData.remotion };
                setActiveLayers(newLayers);
                const blobUrl = await renderInBrowser({
                    videoUrl: originalVideoUrl,
                    durationInSeconds: clipDuration,
                    subtitles: newLayers.subtitles,
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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    job_id: jobId,
                    clip_index: index,
                    text: payload.text,
                    position: payload.position,
                    size: payload.size,
                    input_filename: currentVideoUrl.split('/').pop()
                })
            });

            if (!res.ok) throw new Error(await res.text());
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

    const handleTranslate = async ({ targetLanguage }) => {
        if (!hasClipContext) {
            setEditError('Actions indisponibles: ce reel est detache de son job original.');
            setTimeout(() => setEditError(null), 5000);
            return;
        }
        setIsTranslating(true);
        setEditError(null);
        try {
            const payload = {
                job_id: jobId,
                clip_index: index,
                target_language: targetLanguage,
            };
            const inferredFilename = inputFilenameFromVideoUrl(currentVideoUrl) || inputFilenameFromVideoUrl(originalVideoUrl);
            if (inferredFilename) payload.input_filename = inferredFilename;

            const res = await fetch(getApiUrl('/api/translate'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!res.ok) {
                const errText = await res.text();
                throw new Error(errText || 'Translate failed');
            }

            const data = await res.json();
            if (data.new_video_url) {
                setCurrentVideoUrl(getApiUrl(data.new_video_url));
                if (videoRef.current) videoRef.current.load();
            }
            setShowTranslateModal(false);
        } catch (e) {
            setEditError(e.message || 'Translate failed');
            setTimeout(() => setEditError(null), 5000);
        } finally {
            setIsTranslating(false);
        }
    };

    const handlePost = async () => {
        if (!hasClipContext) {
            setPostResult({ success: false, msg: 'Publication indisponible: reel detache de son job original.' });
            return;
        }
        const selectedPlatforms = Object.keys(platforms).filter(k => platforms[k]);
        if (selectedPlatforms.length === 0) {
            setPostResult({ success: false, msg: "Select at least one platform." });
            return;
        }

        if (isScheduling && !scheduleDate) {
            setPostResult({ success: false, msg: "Please select a date and time." });
            return;
        }

        setPosting(true);
        setPostResult(null);

        try {
            const payload = {
                job_id: jobId,
                clip_index: index,
                platforms: selectedPlatforms,
                title: postTitle,
                description: postDescription
            };

            // Optional overrides: backend can fallback to server-side env vars.
            if (uploadPostKey) payload.api_key = uploadPostKey;
            if (uploadUserId) payload.user_id = uploadUserId;

            if (isScheduling && scheduleDate) {
                // Convert to ISO-8601
                payload.scheduled_date = new Date(scheduleDate).toISOString();
                // Optional: pass timezone if needed, backend defaults to UTC or we can send user's timezone
                payload.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            }

            const res = await fetch(getApiUrl('/api/social/post'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const errText = await res.text();
                try {
                    const jsonErr = JSON.parse(errText);
                    throw new Error(jsonErr.detail || errText);
                } catch (e) {
                    throw new Error(errText);
                }
            }

            setPostResult({ success: true, msg: isScheduling ? "Scheduled successfully!" : "Posted successfully!" });
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
        <div className="bg-surface border border-white/5 rounded-2xl overflow-hidden flex flex-col md:flex-row group hover:border-white/10 transition-all animate-[fadeIn_0.5s_ease-out] min-h-[300px] h-auto" style={{ animationDelay: `${index * 0.1}s` }}>
            {/* Left: Video Preview (Responsive Width) */}
            <div className="w-full md:w-[180px] lg:w-[200px] bg-black relative shrink-0 aspect-[9/16] md:aspect-auto group/video">
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
                        onPlay && onPlay(clipStart + currentTime);
                    }}
                    onPause={() => onPause && onPause()}
                    onEnded={() => {
                        if (videoRef.current) {
                            videoRef.current.currentTime = 0;
                            videoRef.current.play();
                        }
                    }}
                />
                <div className="absolute top-3 left-3 flex gap-2">
                    <span className="bg-black/60 backdrop-blur-md text-white text-[10px] font-bold px-2 py-1 rounded-md border border-white/10 uppercase tracking-wide">
                        Clip {index + 1}
                    </span>
                </div>

                {/* Auto Edit Overlay if Processing */}
                {isEditing && (
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex flex-col items-center justify-center z-10 p-4 text-center">
                        <Loader2 size={32} className="text-primary animate-spin mb-3" />
                        <span className="text-xs font-bold text-white uppercase tracking-wider">AI Magic in Progress...</span>
                        <span className="text-[10px] text-zinc-400 mt-1">Applying viral edits & zooms</span>
                    </div>
                )}
            </div>

            {/* Right: Content & Details */}
            <div className="flex-1 p-4 md:p-5 flex flex-col bg-[#121214] overflow-hidden min-w-0">
                <div className="mb-4">
                    <h3 className="text-base font-bold text-white leading-tight line-clamp-2 mb-2 break-words" title={safeClip.video_title_for_youtube_short}>
                        {safeClip.video_title_for_youtube_short || "Viral Clip Generated"}
                    </h3>
                    <div className="flex flex-wrap gap-2 text-[10px] text-zinc-500 font-mono">
                        <span className="bg-white/5 px-1.5 py-0.5 rounded border border-white/5 shrink-0">{Math.floor(Math.max(1, clipEnd - clipStart))}s</span>
                        <span className="bg-white/5 px-1.5 py-0.5 rounded border border-white/5 shrink-0">#shorts</span>
                        <span className="bg-white/5 px-1.5 py-0.5 rounded border border-white/5 shrink-0">#viral</span>
                    </div>
                </div>

                {/* Scrollable Descriptions Area */}
                <div className="flex-1 overflow-y-auto custom-scrollbar space-y-3 pr-2 mb-4">
                    {/* YouTube */}
                    <div className="bg-black/20 rounded-lg p-3 border border-white/5">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-red-400 mb-1.5 uppercase tracking-wider">
                            <Youtube size={12} className="shrink-0" /> <span className="truncate">YouTube Title</span>
                        </div>
                        <p className="text-xs text-zinc-300 select-all break-words">
                            {safeClip.video_title_for_youtube_short || "Viral Short Video"}
                        </p>
                    </div>

                    {/* TikTok / IG */}
                    <div className="bg-black/20 rounded-lg p-3 border border-white/5">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-zinc-400 mb-1.5 uppercase tracking-wider">
                            <Video size={12} className="text-cyan-400 shrink-0" />
                            <span className="text-zinc-500">/</span>
                            <Instagram size={12} className="text-pink-400 shrink-0" />
                            <span className="truncate">Caption</span>
                        </div>
                        <p className="text-xs text-zinc-300 line-clamp-3 hover:line-clamp-none transition-all cursor-pointer select-all break-words">
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

                {/* Actions Footer */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-auto pt-4 border-t border-white/5">
                    <button
                        onClick={handleAutoEdit}
                        disabled={isEditing || !hasClipContext}
                        title="Auto Edit"
                        className={`col-span-1 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg text-xs font-bold shadow-lg shadow-purple-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 mb-1 truncate px-1 ${compactActions ? 'min-h-[40px]' : ''}`}
                    >
                        {isEditing ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}
                        {!compactActions ? (isEditing ? 'Editing...' : 'Auto Edit') : null}
                    </button>

                    <button
                        onClick={() => setShowSubtitleModal(true)}
                        disabled={isSubtitling || !hasClipContext}
                        title="Subtitles"
                        className={`col-span-1 py-2 bg-gradient-to-r from-yellow-600 to-orange-600 hover:from-yellow-500 hover:to-orange-500 text-white rounded-lg text-xs font-bold shadow-lg shadow-orange-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 mb-1 truncate px-1 ${compactActions ? 'min-h-[40px]' : ''}`}
                    >
                        {isSubtitling ? <Loader2 size={14} className="animate-spin" /> : <Type size={14} />}
                        {!compactActions ? (isSubtitling ? 'Adding...' : 'Subtitles') : null}
                    </button>

                    <button
                        onClick={() => setShowTranslateModal(true)}
                        disabled={isTranslating || !hasClipContext}
                        title="Translate"
                        className={`col-span-1 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white rounded-lg text-xs font-bold shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 mb-1 truncate px-1 ${compactActions ? 'min-h-[40px]' : ''}`}
                    >
                        {isTranslating ? <Loader2 size={14} className="animate-spin" /> : <Languages size={14} />}
                        {!compactActions ? (isTranslating ? 'Translating...' : 'Translate') : null}
                    </button>

                    <button
                        onClick={() => setShowHookModal(true)}
                        disabled={isHooking || !hasClipContext}
                        title="Viral Hook"
                        className={`col-span-1 py-2 bg-gradient-to-r from-amber-400 to-yellow-500 hover:from-amber-300 hover:to-yellow-400 text-black rounded-lg text-xs font-bold shadow-lg shadow-yellow-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 mb-1 truncate px-1 ${compactActions ? 'min-h-[40px]' : ''}`}
                    >
                        {isHooking ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}
                        {!compactActions ? (isHooking ? 'Adding...' : 'Viral Hook') : null}
                    </button>

                    <button
                        onClick={() => setShowModal(true)}
                        disabled={!hasClipContext}
                        title="Post"
                        className={`col-span-1 py-2 bg-primary hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-xs font-bold shadow-lg shadow-primary/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 truncate px-2 ${compactActions ? 'min-h-[40px]' : ''}`}
                    >
                        <Share2 size={14} className="shrink-0" />
                        {!compactActions ? 'Post' : null}
                    </button>
                </div>
            </div>

            {/* Post Modal */}
            {showModal && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
                    <div className="bg-[#121214] border border-white/10 p-6 rounded-2xl w-full max-w-md shadow-2xl relative max-h-[90vh] overflow-y-auto custom-scrollbar">
                        <button
                            onClick={() => setShowModal(false)}
                            className="absolute top-4 right-4 text-zinc-500 hover:text-white"
                        >
                            <X size={20} />
                        </button>

                        <h3 className="text-lg font-bold text-white mb-4">Post / Schedule</h3>

                        {!uploadPostKey || !uploadUserId ? (
                            <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/20 text-blue-200 text-xs rounded-lg">
                                API key/profile not found locally. The backend will use server-side social credentials if configured.
                            </div>
                        ) : null}

                        <div className="space-y-4 mb-6">
                            {/* Title & Description */}
                            <div>
                                <label className="block text-xs font-bold text-zinc-400 mb-1">Video Title</label>
                                <input
                                    type="text"
                                    value={postTitle}
                                    onChange={(e) => setPostTitle(e.target.value)}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg p-2 text-sm text-white focus:outline-none focus:border-primary/50 placeholder-zinc-600"
                                    placeholder="Enter a catchy title..."
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-zinc-400 mb-1">Caption / Description</label>
                                <textarea
                                    value={postDescription}
                                    onChange={(e) => setPostDescription(e.target.value)}
                                    rows={4}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg p-2 text-sm text-white focus:outline-none focus:border-primary/50 placeholder-zinc-600 resize-none"
                                    placeholder="Write a caption for your post..."
                                />
                            </div>

                            {/* Scheduling */}
                            <div className="p-3 bg-white/5 rounded-lg border border-white/5">
                                <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center gap-2 text-sm text-white font-medium">
                                        <Calendar size={16} className="text-purple-400" /> Schedule Post
                                    </div>
                                    <label className="relative inline-flex items-center cursor-pointer">
                                        <input type="checkbox" checked={isScheduling} onChange={(e) => setIsScheduling(e.target.checked)} className="sr-only peer" />
                                        <div className="w-9 h-5 bg-zinc-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
                                    </label>
                                </div>

                                {isScheduling && (
                                    <div className="mt-3 animate-[fadeIn_0.2s_ease-out]">
                                        <label className="block text-xs text-zinc-400 mb-1">Select Date & Time</label>
                                        <div className="relative">
                                            <input
                                                type="datetime-local"
                                                value={scheduleDate}
                                                onChange={(e) => setScheduleDate(e.target.value)}
                                                className="w-full bg-black/40 border border-white/10 rounded-lg p-2 pl-9 text-sm text-white focus:outline-none focus:border-purple-500/50 [color-scheme:dark]"
                                            />
                                            <Clock size={14} className="absolute left-3 top-2.5 text-zinc-500" />
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Platforms */}
                            <div>
                                <label className="block text-xs font-bold text-zinc-400 mb-2">Select Platforms</label>
                                <div className="grid grid-cols-1 gap-2">
                                    {SUPPORTED_SOCIAL_PLATFORMS.filter((platform) => connectedPlatforms.length === 0 || connectedPlatforms.includes(platform)).map((platform) => {
                                        const Icon = platform === 'instagram' ? Instagram
                                            : platform === 'youtube' ? Youtube
                                                : platform === 'facebook' ? Facebook
                                                    : platform === 'linkedin' ? Linkedin
                                                        : Video;
                                        return (
                                            <label key={platform} className="flex items-center gap-3 p-3 bg-white/5 rounded-lg cursor-pointer hover:bg-white/10 transition-colors border border-white/5">
                                                <input
                                                    type="checkbox"
                                                    checked={Boolean(platforms[platform])}
                                                    onChange={e => setPlatforms({ ...platforms, [platform]: e.target.checked })}
                                                    className="w-4 h-4 rounded border-zinc-600 bg-black/50 text-primary focus:ring-primary"
                                                />
                                                <div className="flex items-center gap-2 text-sm text-white">
                                                    <Icon size={16} className="text-zinc-300" /> {PLATFORM_LABELS[platform]}
                                                </div>
                                            </label>
                                        );
                                    })}
                                </div>
                                {connectedPlatforms.length === 0 ? (
                                    <p className="mt-2 text-xs text-zinc-500">No platform is marked as connected in Settings, so defaults are shown.</p>
                                ) : null}
                            </div>
                        </div>

                        {postResult && (
                            <div className={`mb-4 p-3 rounded-lg text-xs flex items-start gap-2 ${postResult.success ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                                {postResult.success ? <CheckCircle size={14} className="mt-0.5 shrink-0" /> : <AlertCircle size={14} className="mt-0.5 shrink-0" />}
                                <div>{postResult.msg}</div>
                            </div>
                        )}

                        <button
                            onClick={handlePost}
                            disabled={posting}
                            className="w-full py-3 bg-primary hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-white font-bold transition-all flex items-center justify-center gap-2"
                        >
                            {posting ? <><Loader2 size={16} className="animate-spin" /> {isScheduling ? 'Scheduling...' : 'Publishing...'}</> : <><Share2 size={16} /> {isScheduling ? 'Schedule Post' : 'Publish Now'}</>}
                        </button>
                    </div>
                </div>
            )}

            <SubtitleModal
                isOpen={showSubtitleModal}
                onClose={() => setShowSubtitleModal(false)}
                onGenerate={handleSubtitle}
                isProcessing={isSubtitling}
                videoUrl={originalVideoUrl}
                jobId={jobId}
                clipIndex={index}
                existingHook={activeLayers.hook}
            />

            <HookModal
                isOpen={showHookModal}
                onClose={() => setShowHookModal(false)}
                onGenerate={handleHook}
                isProcessing={isHooking}
                videoUrl={originalVideoUrl}
                initialText={safeClip.viral_hook_text}
                durationInSeconds={Math.max(1, clipEnd - clipStart)}
                existingSubtitles={activeLayers.subtitles}
            />

            <TranslateModal
                isOpen={showTranslateModal}
                onClose={() => setShowTranslateModal(false)}
                onTranslate={handleTranslate}
                isProcessing={isTranslating}
                videoUrl={currentVideoUrl || originalVideoUrl}
            />


        </div>
    );
}

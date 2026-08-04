import React, { useState, useEffect } from 'react';
import { Share2, Instagram, Youtube, Video, AlertCircle, Loader2, Wand2, Type } from 'lucide-react';
import { getApiUrl } from '../config';
import SubtitleModal from './SubtitleModal';
import HookModal from './HookModal';
import SharePostModal from './SharePostModal';
import { renderInBrowser } from '../lib/renderInBrowser';
import { decrypt } from '../lib/encryption';
import { getConnectedPlatforms } from '../lib/platforms';
import { inputFilenameFromVideoUrl } from '../lib/clips';
function readConnectedPlatformsFromSettings() {
    return getConnectedPlatforms();
}

export default function ResultCard({ clip, index, jobId, onPlay, onPause, compactActions = false }) {
    const safeClip = clip && typeof clip === 'object' ? clip : {};
    const clipIndexForApi = Number.isFinite(Number(safeClip.reel_clip_index))
        ? Number(safeClip.reel_clip_index)
        : index;
    const clipStart = Number.isFinite(Number(safeClip.start)) ? Number(safeClip.start) : 0;
    const clipEnd = Number.isFinite(Number(safeClip.end)) ? Number(safeClip.end) : clipStart + 30;
    const rawVideoUrl = typeof safeClip.video_url === 'string' ? safeClip.video_url : '';
    const uploadPostKey = decrypt(globalThis.localStorage.getItem('uploadPostKey_v3') || '');
    const uploadUserId = globalThis.localStorage.getItem('uploadUserId') || '';
    const connectedPlatforms = readConnectedPlatformsFromSettings();
    const defaultPlatforms = connectedPlatforms.length > 0 ? connectedPlatforms : ['tiktok', 'instagram', 'youtube'];
    const hasClipContext = Boolean(jobId) && Number.isFinite(Number(clipIndexForApi));

    const [showModal, setShowModal] = useState(false);
    const [showSubtitleModal, setShowSubtitleModal] = useState(false);
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
    const [isHooking, setIsHooking] = useState(false);
    const [showHookModal, setShowHookModal] = useState(false);
    const [editError, setEditError] = useState(null);

    const [clipDuration, setClipDuration] = useState(Math.max(1, clipEnd - clipStart));

    // Accumulate Remotion layers across operations
    const [activeLayers, setActiveLayers] = useState({ subtitles: null, hook: null, effects: null });

    // Fetch clip duration from transcript endpoint
    useEffect(() => {
        if (!jobId || !Number.isFinite(Number(clipIndexForApi))) return;
        fetch(getApiUrl(`/api/clip/${jobId}/${clipIndexForApi}/transcript`))
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                if (data && data.durationSec) setClipDuration(data.durationSec);
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
            const effectiveInputUrl = currentVideoUrl?.startsWith('blob:') ? originalVideoUrl : currentVideoUrl;
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
                    clip_index: clipIndexForApi,
                    input_filename: inputFilenameFromVideoUrl(currentVideoUrl),
                    input_url: effectiveInputUrl,
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
                    clip_index: clipIndexForApi,
                    input_filename: inputFilenameFromVideoUrl(currentVideoUrl),
                    input_url: effectiveInputUrl,
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
            const effectiveInputUrl = currentVideoUrl?.startsWith('blob:') ? originalVideoUrl : currentVideoUrl;
            if (options.remotion) {
                let nextCaptions = Array.isArray(options.translatedCaptions) && options.translatedCaptions.length > 0
                    ? options.translatedCaptions
                    : (Array.isArray(options.remotion.captions) ? options.remotion.captions : []);
                let nextDurationSec = Number.isFinite(Number(options.previewDurationSec)) && Number(options.previewDurationSec) > 0
                    ? Number(options.previewDurationSec)
                    : clipDuration;

                if (options.targetLanguage && nextCaptions.length === 0) {
                    const captionsRes = await fetch(getApiUrl('/api/translate/captions'), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            job_id: jobId,
                                clip_index: clipIndexForApi,
                            target_language: options.targetLanguage,
                            input_url: effectiveInputUrl,
                        }),
                    });

                    if (!captionsRes.ok) {
                        const errText = await captionsRes.text();
                        throw new Error(errText || 'Subtitle translation failed');
                    }

                    const translatedData = await captionsRes.json();
                    nextCaptions = Array.isArray(translatedData.captions) ? translatedData.captions : [];
                    if (translatedData.durationSec) {
                        nextDurationSec = translatedData.durationSec;
                    }
                }

                // Accumulate layer and render all layers together
                const subtitleLayer = {
                    ...options.remotion,
                    captions: nextCaptions,
                };
                const newLayers = { ...activeLayers, subtitles: subtitleLayer };
                setActiveLayers(newLayers);
                setClipDuration(nextDurationSec);
                const blobUrl = await renderInBrowser({
                    videoUrl: originalVideoUrl,
                    durationInSeconds: nextDurationSec,
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
                    clip_index: clipIndexForApi,
                    position: options.position,
                    font_size: options.fontSize,
                    font_name: options.fontName,
                    font_color: options.fontColor,
                    border_color: options.borderColor,
                    border_width: options.borderWidth,
                    bg_color: options.bgColor,
                    bg_opacity: options.bgOpacity,
                    input_filename: inputFilenameFromVideoUrl(currentVideoUrl),
                    input_url: effectiveInputUrl
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
            const effectiveInputUrl = currentVideoUrl?.startsWith('blob:') ? originalVideoUrl : currentVideoUrl;
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
                    clip_index: clipIndexForApi,
                    text: payload.text,
                    position: payload.position,
                    size: payload.size,
                    input_filename: inputFilenameFromVideoUrl(currentVideoUrl),
                    input_url: effectiveInputUrl
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
                    clip_index: clipIndexForApi,
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
                hasLocalCredentials={Boolean(uploadPostKey && uploadUserId)}
            />

            <SubtitleModal
                isOpen={showSubtitleModal}
                onClose={() => setShowSubtitleModal(false)}
                onGenerate={handleSubtitle}
                isProcessing={isSubtitling}
                videoUrl={originalVideoUrl}
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
                videoUrl={originalVideoUrl}
                initialText={safeClip.viral_hook_text}
                durationInSeconds={Math.max(1, clipEnd - clipStart)}
                existingSubtitles={activeLayers.subtitles}
            />


        </div>
    );
}

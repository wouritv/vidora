import React, { useState, useEffect, useRef } from 'react';
import { X, Type, Loader2, Languages, Globe } from 'lucide-react';
import { getApiUrl } from '../config';
import RemotionPreview from './RemotionPreview';
import { ANIMATION_OPTIONS, COLOR_PRESETS, DEFAULT_SUBTITLE_FORM_STYLE, FONT_OPTIONS, HIGHLIGHT_COLOR_PRESETS } from '../lib/subtitleOptions';

const LANGUAGES = {
    es: 'Spanish',
    fr: 'French',
    de: 'German',
    it: 'Italian',
    pt: 'Portuguese',
    pl: 'Polish',
    hi: 'Hindi',
    ja: 'Japanese',
    ko: 'Korean',
    zh: 'Chinese',
    ar: 'Arabic',
    ru: 'Russian',
    tr: 'Turkish',
    nl: 'Dutch',
    sv: 'Swedish',
    id: 'Indonesian',
    fil: 'Filipino',
    ms: 'Malay',
    vi: 'Vietnamese',
    th: 'Thai',
    uk: 'Ukrainian',
    el: 'Greek',
    cs: 'Czech',
    fi: 'Finnish',
    ro: 'Romanian',
    da: 'Danish',
    bg: 'Bulgarian',
    hr: 'Croatian',
    sk: 'Slovak',
    ta: 'Tamil',
    en: 'English',
};

export default function SubtitleModal({ isOpen, onClose, onGenerate, isProcessing, videoUrl, jobId, clipIndex, existingHook, existingEffects }) {
    const previewCacheRef = useRef({});
    const [positionX, setPositionX] = useState(DEFAULT_SUBTITLE_FORM_STYLE.positionX);
    const [positionY, setPositionY] = useState(DEFAULT_SUBTITLE_FORM_STYLE.positionY);
    const [fontSize, setFontSize] = useState(DEFAULT_SUBTITLE_FORM_STYLE.fontSize);
    const [fontName, setFontName] = useState(DEFAULT_SUBTITLE_FORM_STYLE.fontName);
    const [fontColor, setFontColor] = useState(DEFAULT_SUBTITLE_FORM_STYLE.fontColor);
    const [highlightColor, setHighlightColor] = useState(DEFAULT_SUBTITLE_FORM_STYLE.highlightColor);
    const [borderColor, setBorderColor] = useState(DEFAULT_SUBTITLE_FORM_STYLE.borderColor);
    const [borderWidth, setBorderWidth] = useState(DEFAULT_SUBTITLE_FORM_STYLE.borderWidth);
    const [textShadowColor, setTextShadowColor] = useState(DEFAULT_SUBTITLE_FORM_STYLE.textShadowColor);
    const [shadowBlur, setShadowBlur] = useState(DEFAULT_SUBTITLE_FORM_STYLE.shadowBlur);
    const [shadowOffsetX, setShadowOffsetX] = useState(DEFAULT_SUBTITLE_FORM_STYLE.shadowOffsetX);
    const [shadowOffsetY, setShadowOffsetY] = useState(DEFAULT_SUBTITLE_FORM_STYLE.shadowOffsetY);
    const [bgColor, setBgColor] = useState(DEFAULT_SUBTITLE_FORM_STYLE.bgColor);
    const [bgOpacity, setBgOpacity] = useState(DEFAULT_SUBTITLE_FORM_STYLE.bgOpacity);
    const [textCase, setTextCase] = useState(DEFAULT_SUBTITLE_FORM_STYLE.textCase);
    const [bold, setBold] = useState(DEFAULT_SUBTITLE_FORM_STYLE.bold);
    const [italic, setItalic] = useState(DEFAULT_SUBTITLE_FORM_STYLE.italic);
    const [wordsPerLine, setWordsPerLine] = useState(DEFAULT_SUBTITLE_FORM_STYLE.wordsPerLine);
    const [animation, setAnimation] = useState(DEFAULT_SUBTITLE_FORM_STYLE.animation);
    const [showTextEditor, setShowTextEditor] = useState(false);

    // Remotion preview state
    const [captions, setCaptions] = useState([]);
    const [originalCaptions, setOriginalCaptions] = useState([]);
    const [editableText, setEditableText] = useState('');
    const [durationSec, setDurationSec] = useState(30);
    const [captionsLoading, setCaptionsLoading] = useState(false);
    const [useRemotionPreview, setUseRemotionPreview] = useState(false);
    const [translationEnabled, setTranslationEnabled] = useState(false);
    const [targetLanguage, setTargetLanguage] = useState('es');
    const [languages, setLanguages] = useState(LANGUAGES);
    const [translatedPreviewCaptions, setTranslatedPreviewCaptions] = useState([]);
    const [previewProviders, setPreviewProviders] = useState([]);
    const [previewError, setPreviewError] = useState('');
    const [isPreviewTranslating, setIsPreviewTranslating] = useState(false);

    useEffect(() => {
        if (!isOpen) return;
        let cancelled = false;

        const loadLanguages = async () => {
            try {
                const res = await fetch(getApiUrl('/api/translate/languages'));
                if (!res.ok) return;
                const data = await res.json();
                if (!Array.isArray(data?.languages)) return;

                const next = {};
                data.languages.forEach((item) => {
                    if (item?.code && item?.name) next[item.code] = item.name;
                });
                if (!cancelled && Object.keys(next).length > 0) {
                    setLanguages(next);
                    if (!next[targetLanguage]) {
                        setTargetLanguage(Object.keys(next)[0]);
                    }
                }
            } catch {
                // Keep static fallback list.
            }
        };

        loadLanguages();
        return () => {
            cancelled = true;
        };
    }, [isOpen, targetLanguage]);

    // Fetch word-level captions when modal opens
    useEffect(() => {
        if (!isOpen || !jobId || clipIndex === undefined || clipIndex === null || clipIndex < 0) return;

        setCaptionsLoading(true);
        fetch(getApiUrl(`/api/clip/${jobId}/${clipIndex}/transcript`))
            .then((res) => res.ok ? res.json() : null)
            .then((data) => {
                if (data && data.captions && data.captions.length > 0) {
                    setCaptions(data.captions);
                    setOriginalCaptions(data.captions);
                    setEditableText(data.captions.map(c => c.text).join(' '));
                    setDurationSec(data.durationSec || 30);
                    setUseRemotionPreview(true);
                } else {
                    setUseRemotionPreview(false);
                }
            })
            .catch(() => setUseRemotionPreview(false))
            .finally(() => setCaptionsLoading(false));
    }, [isOpen, jobId, clipIndex]);

    useEffect(() => {
        if (!isOpen || !translationEnabled || !jobId || clipIndex === undefined || clipIndex === null || clipIndex < 0 || !targetLanguage) {
            return;
        }

        const previewInputUrl = videoUrl && !videoUrl.startsWith('blob:')
            ? (videoUrl.startsWith('http') ? videoUrl : `${window.location.origin}${videoUrl}`)
            : undefined;
        const previewCacheKey = `${jobId}:${clipIndex}:${targetLanguage}`;
        const cachedPreview = previewCacheRef.current[previewCacheKey];
        if (cachedPreview) {
            setPreviewError('');
            setTranslatedPreviewCaptions(cachedPreview.captions || []);
            setPreviewProviders(Array.isArray(cachedPreview.providers) ? cachedPreview.providers : []);
            if (cachedPreview.durationSec) {
                setDurationSec(cachedPreview.durationSec);
            }
            setIsPreviewTranslating(false);
            return;
        }

        setTranslatedPreviewCaptions([]);
        setPreviewProviders([]);

        const controller = new AbortController();
        const timeout = setTimeout(async () => {
            setIsPreviewTranslating(true);
            setPreviewError('');

            try {
                const res = await fetch(getApiUrl('/api/translate/captions'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        job_id: jobId,
                        clip_index: clipIndex,
                        target_language: targetLanguage,
                        input_url: previewInputUrl,
                    }),
                    signal: controller.signal,
                });

                if (!res.ok) {
                    const errText = await res.text();
                    throw new Error(errText || 'Preview translation failed');
                }

                const data = await res.json();
                previewCacheRef.current[previewCacheKey] = {
                    captions: Array.isArray(data.captions) ? data.captions : [],
                    providers: Array.isArray(data.providers) ? data.providers : [],
                    durationSec: data.durationSec || 0,
                };
                const nextCaptions = Array.isArray(data.captions) ? data.captions : [];
                setTranslatedPreviewCaptions(nextCaptions);
                setPreviewProviders(Array.isArray(data.providers) ? data.providers : []);
                if (nextCaptions.length > 0) {
                    setUseRemotionPreview(true);
                }
                if (data.durationSec) {
                    setDurationSec(data.durationSec);
                }
            } catch (error) {
                if (error.name === 'AbortError') return;
                setTranslatedPreviewCaptions([]);
                setPreviewProviders([]);
                setPreviewError(error.message || 'Preview translation failed');
            } finally {
                setIsPreviewTranslating(false);
            }
        }, 250);

        return () => {
            controller.abort();
            clearTimeout(timeout);
        };
    }, [clipIndex, isOpen, jobId, targetLanguage, translationEnabled, videoUrl]);

    // When user edits text, redistribute words across original timestamps
    const handleTextEdit = (newText) => {
        setEditableText(newText);
        const newWords = newText.split(/\s+/).filter(w => w.length > 0);
        if (newWords.length === 0 || originalCaptions.length === 0) {
            setCaptions([]);
            return;
        }

        // Distribute new words across the time span of original captions
        const totalDurationMs = originalCaptions[originalCaptions.length - 1].endMs - originalCaptions[0].startMs;
        const startMs = originalCaptions[0].startMs;
        const wordDurationMs = totalDurationMs / newWords.length;

        const newCaptions = newWords.map((word, i) => ({
            text: word,
            startMs: Math.round(startMs + i * wordDurationMs),
            endMs: Math.round(startMs + (i + 1) * wordDurationMs),
        }));
        setCaptions(newCaptions);
    };

    if (!isOpen) return null;

    const effectiveCaptions = translationEnabled ? translatedPreviewCaptions : captions;

    // Build subtitle config for Remotion
    const subtitleConfig = {
        captions: effectiveCaptions,
        style: {
            positionX,
            positionY,
            fontFamily: fontName,
            fontSize: fontSize * 2.2, // Scale up for 1080p (modal fontSize is for small preview)
            fontColor,
            highlightColor,
            borderColor,
            borderWidth: borderWidth * 1.5,
            textShadowColor,
            shadowBlur,
            shadowOffsetX,
            shadowOffsetY,
            bgColor,
            bgOpacity,
            textCase,
            bold,
            italic,
            wordsPerLine,
            animation,
        },
    };

    // Fallback: static CSS preview (same as original)
    const bw = Math.max(borderWidth, 0);
    const bc = borderColor;
    const outlineShadow = bw > 0 ? [
        `-${bw}px -${bw}px 0 ${bc}`, `${bw}px -${bw}px 0 ${bc}`,
        `-${bw}px ${bw}px 0 ${bc}`, `${bw}px ${bw}px 0 ${bc}`,
        `0 -${bw}px 0 ${bc}`, `0 ${bw}px 0 ${bc}`,
        `-${bw}px 0 0 ${bc}`, `${bw}px 0 0 ${bc}`,
    ].join(', ') : 'none';

    const fallbackPreviewStyle = {
        fontFamily: fontName,
        color: fontColor,
        fontSize: `${fontSize}px`,
        fontWeight: bold ? 700 : 500,
        fontStyle: italic ? 'italic' : 'normal',
        textTransform: textCase === 'uppercase' ? 'uppercase' : textCase === 'lowercase' ? 'lowercase' : 'none',
        maxWidth: '85%',
        padding: '6px 12px',
        borderRadius: '4px',
        textAlign: 'center',
        lineHeight: '1.3',
        boxShadow: `0 0 ${shadowBlur}px ${textShadowColor}`,
        ...(bgOpacity > 0
            ? {
                backgroundColor: `${bgColor}${Math.round(bgOpacity * 255).toString(16).padStart(2, '0')}`,
                textShadow: 'none',
            }
            : { textShadow: outlineShadow }
        ),
    };

    const previewWords = effectiveCaptions.length > 0
        ? effectiveCaptions.map((caption) => caption.text)
        : ['This', 'is', 'how', 'your', 'subtitles', 'will', 'appear', 'on', 'the', 'video'];
    const previewWordsPerLine = Math.min(8, Math.max(2, Number(wordsPerLine) || 4));
    const fallbackPreviewLines = [];
    for (let i = 0; i < previewWords.length; i += previewWordsPerLine) {
        fallbackPreviewLines.push(previewWords.slice(i, i + previewWordsPerLine).join(' '));
    }

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
            <div className="bg-[#121214] border border-slate-300 dark:border-white/10 p-6 rounded-2xl w-full max-w-5xl shadow-2xl relative flex flex-col md:flex-row gap-6 max-h-[90vh]">
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 text-slate-400 dark:text-zinc-500 hover:text-white z-10"
                >
                    <X size={20} />
                </button>

                {/* Left: Preview */}
                <div className="flex-1 flex flex-col items-center justify-center bg-black rounded-lg border border-slate-200 dark:border-white/5 overflow-hidden relative aspect-[9/16] max-h-[600px]">
                    {captionsLoading ? (
                        <div className="flex items-center gap-2 text-slate-500 dark:text-zinc-400">
                            <Loader2 size={16} className="animate-spin" />
                            <span className="text-sm">Loading preview...</span>
                        </div>
                    ) : useRemotionPreview ? (
                        <RemotionPreview
                            videoUrl={videoUrl}
                            durationInSeconds={durationSec}
                            subtitles={subtitleConfig}
                            hook={existingHook || null}
                            effects={existingEffects || null}
                        />
                    ) : (
                        <>
                            <video src={videoUrl} className="w-full h-full object-contain opacity-50" muted playsInline />
                            <div className="absolute w-full px-8 text-center transition-all duration-300 pointer-events-none flex flex-col items-center justify-center" style={{ left: `${positionX}%`, top: `${positionY}%`, transform: 'translate(-50%, -50%)' }}>
                                <div className="flex flex-col items-center gap-1.5" style={{ maxWidth: '85%' }}>
                                    {fallbackPreviewLines.map((line, index) => (
                                        <span key={`${line}-${index}`} style={fallbackPreviewStyle}>
                                            {line}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                {/* Right: Controls */}
                <div className="w-full md:w-80 flex flex-col">
                    <h3 className="title-contrast text-xl font-bold mb-4 flex items-center gap-2 shrink-0">
                        <Type className="text-primary" /> Auto Subtitles
                    </h3>

                    <div className="space-y-5 flex-1 overflow-y-auto custom-scrollbar pr-1">
                        {/* Position Selector */}
                        <div className="p-3 rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03]">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <p className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                                        <Languages size={14} className="text-emerald-400" />
                                        Activer la traduction
                                    </p>
                                    <p className="text-[11px] text-slate-400 dark:text-zinc-500 mt-1">Conserve les memes styles/animations avec preview en direct.</p>
                                </div>
                                <label className="relative inline-flex items-center cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={translationEnabled}
                                        onChange={(e) => {
                                            const enabled = e.target.checked;
                                            setTranslationEnabled(enabled);
                                            setPreviewError('');
                                            if (!enabled) {
                                                setTranslatedPreviewCaptions([]);
                                                setPreviewProviders([]);
                                                setIsPreviewTranslating(false);
                                            }
                                        }}
                                        className="sr-only peer"
                                    />
                                    <div className="w-9 h-5 bg-zinc-700 rounded-full peer peer-checked:bg-emerald-600 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:after:translate-x-full" />
                                </label>
                            </div>

                            {translationEnabled ? (
                                <div className="mt-3 space-y-3 animate-[fadeIn_0.2s_ease-out]">
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2">
                                            <Globe size={12} className="inline mr-1" />
                                            Language
                                        </label>
                                        <select
                                            value={targetLanguage}
                                            onChange={(e) => setTargetLanguage(e.target.value)}
                                            className="w-full bg-black/40 border border-slate-300 dark:border-white/10 rounded-lg p-2.5 text-sm text-white focus:outline-none focus:border-emerald-500/50"
                                            disabled={isProcessing}
                                        >
                                            {Object.entries(languages)
                                                .sort((a, b) => a[1].localeCompare(b[1]))
                                                .map(([code, name]) => (
                                                    <option key={code} value={code}>{name}</option>
                                                ))}
                                        </select>
                                    </div>

                                    {isPreviewTranslating ? (
                                        <div className="text-xs text-emerald-300 flex items-center gap-2">
                                            <Loader2 size={12} className="animate-spin" />
                                            Updating translated preview...
                                        </div>
                                    ) : null}
                                    {previewError ? (
                                        <div className="text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded-lg p-2">
                                            {previewError}
                                        </div>
                                    ) : null}
                                    {!previewError && previewProviders.length > 0 ? (
                                        <p className="text-[11px] text-slate-400 dark:text-zinc-500">
                                            Provider: {previewProviders.join(', ')}
                                        </p>
                                    ) : null}
                                </div>
                            ) : null}
                        </div>

                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 block">Position libre (X/Y)</label>
                            <div className="space-y-3 rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] p-3">
                                <div>
                                    <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-zinc-400 mb-1">
                                        <span>X</span>
                                        <span>{positionX}%</span>
                                    </div>
                                    <input
                                        type="range"
                                        min="5"
                                        max="95"
                                        value={positionX}
                                        onChange={(e) => setPositionX(Number(e.target.value))}
                                        className="w-full accent-primary"
                                    />
                                </div>
                                <div>
                                    <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-zinc-400 mb-1">
                                        <span>Y</span>
                                        <span>{positionY}%</span>
                                    </div>
                                    <input
                                        type="range"
                                        min="5"
                                        max="95"
                                        value={positionY}
                                        onChange={(e) => setPositionY(Number(e.target.value))}
                                        className="w-full accent-primary"
                                    />
                                </div>
                            </div>
                        </div>

                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 block">Style du texte</label>
                            <div className="grid grid-cols-2 gap-2">
                                <button
                                    type="button"
                                    onClick={() => setBold((v) => !v)}
                                    className={`rounded-lg border px-3 py-2 text-xs font-semibold ${bold ? 'border-primary bg-primary/20 text-white' : 'border-slate-300 dark:border-white/10 bg-white/5 text-slate-500 dark:text-zinc-400'}`}
                                >
                                    Gras
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setItalic((v) => !v)}
                                    className={`rounded-lg border px-3 py-2 text-xs font-semibold ${italic ? 'border-primary bg-primary/20 text-white' : 'border-slate-300 dark:border-white/10 bg-white/5 text-slate-500 dark:text-zinc-400'}`}
                                >
                                    Italique
                                </button>
                            </div>
                            <div className="grid grid-cols-3 gap-2 mt-2">
                                {[
                                    { value: 'none', label: 'Normal' },
                                    { value: 'uppercase', label: 'MAJ' },
                                    { value: 'lowercase', label: 'min' },
                                ].map((opt) => (
                                    <button
                                        key={opt.value}
                                        type="button"
                                        onClick={() => setTextCase(opt.value)}
                                        className={`rounded-lg border px-2 py-2 text-xs ${textCase === opt.value ? 'border-primary bg-primary/20 text-white' : 'border-slate-300 dark:border-white/10 bg-white/5 text-slate-500 dark:text-zinc-400'}`}
                                    >
                                        {opt.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Animation Style (new) */}
                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 block">Animation</label>
                            <div className="grid grid-cols-2 gap-2">
                                {ANIMATION_OPTIONS.map((opt) => (
                                    <button
                                        key={opt.value}
                                        onClick={() => setAnimation(opt.value)}
                                        title={opt.desc}
                                        className={`p-2 rounded-lg border text-center transition-all ${animation === opt.value ? 'bg-primary/20 border-primary text-white' : 'bg-white/5 border-slate-200 dark:border-white/5 text-slate-500 dark:text-zinc-400 hover:bg-white/10'}`}
                                    >
                                        <div className="text-xs font-medium">{opt.label}</div>
                                        <div className="text-[10px] text-slate-400 dark:text-zinc-500 leading-tight mt-0.5 line-clamp-2">{opt.desc}</div>
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Editable Transcript (collapsible) */}
                        {useRemotionPreview && !translationEnabled && (
                            <div>
                                <button
                                    type="button"
                                    onClick={() => setShowTextEditor(!showTextEditor)}
                                    className="w-full flex items-center justify-between text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2"
                                >
                                    <span>Edit Text ({captions.length} words)</span>
                                    <span className={`transition-transform ${showTextEditor ? 'rotate-180' : ''}`}>▾</span>
                                </button>
                                {showTextEditor && (
                                    <textarea
                                        value={editableText}
                                        onChange={(e) => handleTextEdit(e.target.value)}
                                        rows={5}
                                        className="w-full bg-black/40 border border-slate-300 dark:border-white/10 rounded-lg p-2.5 text-sm text-white focus:outline-none focus:border-primary/50 resize-none leading-relaxed animate-[fadeIn_0.15s_ease-out]"
                                        placeholder="Edit subtitle text..."
                                    />
                                )}
                            </div>
                        )}

                        {/* Font Family */}
                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 block">
                                Police — <span className="text-slate-400 dark:text-zinc-500 normal-case font-normal" style={{ fontFamily: fontName }}>{fontName}</span>
                            </label>
                            <div className="max-h-52 overflow-y-auto custom-scrollbar pr-1 space-y-2">
                                {[...new Set(FONT_OPTIONS.map(f => f.category))].map(cat => (
                                    <div key={cat}>
                                        <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1 px-0.5">{cat}</div>
                                        <div className="grid grid-cols-2 gap-1">
                                            {FONT_OPTIONS.filter(f => f.category === cat).map((f) => (
                                                <button
                                                    key={f.value}
                                                    onClick={() => setFontName(f.value)}
                                                    className={`px-2 py-1.5 rounded-lg border text-sm text-center truncate transition-all ${fontName === f.value ? 'bg-primary/20 border-primary text-white' : 'bg-white/5 border-slate-200 dark:border-white/5 text-slate-700 dark:text-zinc-300 hover:bg-white/10 hover:border-slate-400 dark:border-white/20'}`}
                                                    style={{ fontFamily: f.value }}
                                                    title={f.label}
                                                >
                                                    {f.label}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Font Size */}
                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 block">
                                Taille du texte <span className="text-slate-400 dark:text-zinc-500 normal-case font-normal">({fontSize}px)</span>
                            </label>
                            <input
                                type="range"
                                min="14"
                                max="40"
                                value={fontSize}
                                onChange={(e) => setFontSize(Number(e.target.value))}
                                className="w-full accent-primary"
                            />
                            <div className="flex justify-between text-[10px] text-slate-400 dark:text-zinc-500 mt-1">
                                <span>Petit</span>
                                <span>Grand</span>
                            </div>
                        </div>

                        {/* Text Color */}
                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 block">Text Color</label>
                            <div className="flex flex-wrap gap-2">
                                {COLOR_PRESETS.map((c) => (
                                    <button
                                        key={c.color}
                                        onClick={() => setFontColor(c.color)}
                                        className={`w-7 h-7 rounded-full border-2 transition-all ${fontColor === c.color ? 'border-white scale-110' : 'border-slate-400 dark:border-white/20 hover:border-slate-200 dark:border-white/50'}`}
                                        style={{ backgroundColor: c.color }}
                                        title={c.label}
                                    />
                                ))}
                                <label className="w-7 h-7 rounded-full border-2 border-dashed border-slate-400 dark:border-white/20 cursor-pointer flex items-center justify-center hover:border-slate-200 dark:border-white/50 transition-all overflow-hidden relative" title="Custom color">
                                    <span className="text-[10px] text-slate-500 dark:text-zinc-400">+</span>
                                    <input type="color" value={fontColor} onChange={(e) => setFontColor(e.target.value)} className="absolute inset-0 opacity-0 cursor-pointer" />
                                </label>
                            </div>
                        </div>

                        {/* Highlight Color (new) */}
                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 block">Highlight Color</label>
                            <div className="flex flex-wrap gap-2">
                                {HIGHLIGHT_COLOR_PRESETS.map((c) => (
                                    <button
                                        key={c.color}
                                        onClick={() => setHighlightColor(c.color)}
                                        className={`w-7 h-7 rounded-full border-2 transition-all ${highlightColor === c.color ? 'border-white scale-110' : 'border-slate-400 dark:border-white/20 hover:border-slate-200 dark:border-white/50'}`}
                                        style={{ backgroundColor: c.color }}
                                        title={c.label}
                                    />
                                ))}
                            </div>
                        </div>

                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 block">Couleur de l'ombre</label>
                            <div className="flex items-center gap-3 rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] p-3">
                                <label className="relative w-8 h-8 rounded-lg border border-slate-300 dark:border-white/10 cursor-pointer overflow-hidden shrink-0" title="Shadow color">
                                    <div className="w-full h-full" style={{ backgroundColor: textShadowColor }} />
                                    <input type="color" value={textShadowColor} onChange={(e) => setTextShadowColor(e.target.value)} className="absolute inset-0 opacity-0 cursor-pointer" />
                                </label>
                                <div className="flex-1 grid grid-cols-3 gap-2 text-[10px] text-slate-400 dark:text-zinc-500">
                                    <div>
                                        <div className="mb-1 text-slate-500 dark:text-zinc-400">Blur {shadowBlur}px</div>
                                        <input type="range" min="0" max="24" value={shadowBlur} onChange={(e) => setShadowBlur(Number(e.target.value))} className="w-full accent-primary" />
                                    </div>
                                    <div>
                                        <div className="mb-1 text-slate-500 dark:text-zinc-400">Offset X {shadowOffsetX}px</div>
                                        <input type="range" min="-20" max="20" value={shadowOffsetX} onChange={(e) => setShadowOffsetX(Number(e.target.value))} className="w-full accent-primary" />
                                    </div>
                                    <div>
                                        <div className="mb-1 text-slate-500 dark:text-zinc-400">Offset Y {shadowOffsetY}px</div>
                                        <input type="range" min="-20" max="20" value={shadowOffsetY} onChange={(e) => setShadowOffsetY(Number(e.target.value))} className="w-full accent-primary" />
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Border / Outline */}
                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 block">Border</label>
                            <div className="flex items-center gap-3">
                                <label className="relative w-8 h-8 rounded-lg border border-slate-300 dark:border-white/10 cursor-pointer overflow-hidden shrink-0" title="Border color">
                                    <div className="w-full h-full" style={{ backgroundColor: borderColor }} />
                                    <input type="color" value={borderColor} onChange={(e) => setBorderColor(e.target.value)} className="absolute inset-0 opacity-0 cursor-pointer" />
                                </label>
                                <div className="flex-1">
                                    <input
                                        type="range"
                                        min="0"
                                        max="5"
                                        value={borderWidth}
                                        onChange={(e) => setBorderWidth(parseInt(e.target.value))}
                                        className="w-full accent-primary"
                                    />
                                    <div className="flex justify-between text-[10px] text-slate-400 dark:text-zinc-500">
                                        <span>None</span>
                                        <span>Thick</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 block">
                                Mots par ligne <span className="text-slate-400 dark:text-zinc-500 normal-case font-normal">({wordsPerLine})</span>
                            </label>
                            <input
                                type="range"
                                min="2"
                                max="8"
                                value={wordsPerLine}
                                onChange={(e) => setWordsPerLine(Number(e.target.value))}
                                className="w-full accent-primary"
                            />
                            <div className="flex justify-between text-[10px] text-slate-400 dark:text-zinc-500 mt-1">
                                <span>2</span>
                                <span>8</span>
                            </div>
                        </div>

                        {/* Background Box */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider">Background Box</label>
                                <label className="relative inline-flex items-center cursor-pointer">
                                    <input type="checkbox" checked={bgOpacity > 0} onChange={(e) => setBgOpacity(e.target.checked ? 0.5 : 0)} className="sr-only peer" />
                                    <div className="w-8 h-4 bg-zinc-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[0px] after:left-[0px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                                </label>
                            </div>
                            {bgOpacity > 0 && (
                                <div className="space-y-3 animate-[fadeIn_0.2s_ease-out]">
                                    <div className="flex items-center gap-3">
                                        <label className="relative w-8 h-8 rounded-lg border border-slate-300 dark:border-white/10 cursor-pointer overflow-hidden shrink-0" title="Background color">
                                            <div className="w-full h-full" style={{ backgroundColor: bgColor }} />
                                            <input type="color" value={bgColor} onChange={(e) => setBgColor(e.target.value)} className="absolute inset-0 opacity-0 cursor-pointer" />
                                        </label>
                                        <div className="flex-1">
                                            <input
                                                type="range"
                                                min="10"
                                                max="100"
                                                value={Math.round(bgOpacity * 100)}
                                                onChange={(e) => setBgOpacity(parseInt(e.target.value) / 100)}
                                                className="w-full accent-primary"
                                            />
                                            <div className="flex justify-between text-[10px] text-slate-400 dark:text-zinc-500">
                                                <span>Transparent</span>
                                                <span>{Math.round(bgOpacity * 100)}%</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    <button
                        onClick={() => onGenerate({
                            positionX, positionY, fontSize, fontName, fontColor, borderColor, borderWidth,
                            textShadowColor, shadowBlur, shadowOffsetX, shadowOffsetY,
                            bgColor, bgOpacity, textCase, bold, italic, wordsPerLine, animation,
                            highlightColor,
                            targetLanguage: translationEnabled ? targetLanguage : null,
                            translatedCaptions: translationEnabled ? translatedPreviewCaptions : [],
                            previewDurationSec: translationEnabled ? durationSec : null,
                            // Remotion data
                            remotion: useRemotionPreview ? subtitleConfig : null,
                        })}
                        disabled={isProcessing}
                        className="w-full py-3 mt-4 bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-400 hover:to-orange-400 text-black font-bold rounded-xl shadow-lg shadow-orange-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 shrink-0"
                    >
                        {isProcessing ? <Loader2 size={20} className="animate-spin" /> : <Type size={20} />}
                        {isProcessing ? 'Generating...' : 'Generate Subtitles'}
                    </button>
                </div>
            </div>
        </div>
    );
}

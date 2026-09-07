import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, Loader2, MessageSquareText, Plus, RotateCcw, X } from 'lucide-react';
import { getApiUrl } from '../config';
import RemotionPreview from './RemotionPreview';
import { ANIMATION_OPTIONS, COLOR_PRESETS, HIGHLIGHT_COLOR_PRESETS, FONT_OPTIONS } from '../lib/subtitleOptions';
import { useTranslation } from '../state/LanguageContext';
import { useAuth } from '../state/AuthContext';

const DEFAULT_STYLE = {
  positionX: 50,
  positionY: 82,
  fontFamily: 'Arial',
  fontSize: 52,
  fontColor: '#FFFFFF',
  highlightColor: '#FFDD00',
  borderColor: '#000000',
  borderWidth: 3,
  textShadowColor: '#000000',
  shadowBlur: 8,
  shadowOffsetX: 0,
  shadowOffsetY: 2,
  bgColor: '#000000',
  bgOpacity: 0,
  textCase: 'none',
  bold: true,
  italic: false,
  wordsPerLine: 4,
  animation: 'word-highlight',
};

const FALLBACK_LANGUAGES = {
  fr: 'French',
  en: 'English',
  es: 'Spanish',
  de: 'German',
  it: 'Italian',
  pt: 'Portuguese',
};

const EMOJI_GROUPS = {
  popular: ['🔥', '😂', '😍', '🤯', '😎', '✨', '🎯', '💥', '✅', '🚀', '💡', '👏', '🙌', '💯', '🥳', '🤩', '🤔', '😮', '😭', '❤️'],
  faces: ['😀', '😁', '😄', '😅', '🤣', '😊', '😉', '😌', '😘', '😜', '🤪', '😴', '😤', '😡', '😱', '🥶', '🥵', '🤗', '🫶', '🫠'],
  symbols: ['✅', '❌', '⚠️', '⭐', '🌟', '🔔', '📌', '📍', '➡️', '⬆️', '⬇️', '💬', '📈', '📉', '🧠', '🛠️', '🔍', '💣', '🧲', '🧩'],
  business: ['💼', '📊', '📉', '📈', '🧾', '🏆', '💰', '💵', '💸', '🪙', '⌛', '🧭', '🧮', '🏁', '🎖️', '🚨', '🧠', '📣', '📦', '🗂️'],
  social: ['📱', '🎥', '🎬', '🎤', '🎧', '📸', '📰', '🌍', '💻', '🖥️', '🕒', '📢', '🛰️', '🕹️', '🎮', '📺', '🧵', '🔁', '🔗', '🧷'],
  objects: ['🔋', '💡', '🧯', '🪄', '🎁', '📦', '🧱', '🧪', '🧬', '🔬', '🛰️', '⚙️', '🪛', '🔧', '🪜', '🪵', '🧲', '🧰', '🪙', '🧿'],
  nature: ['🌞', '🌤️', '🌈', '⛈️', '🌙', '⭐', '🌊', '🍀', '🌴', '🌻', '🌸', '🌼', '🍎', '🍋', '🍉', '🥑', '🍓', '🍇', '🌶️', '🥥'],
  flags: ['🇫🇷', '🇺🇸', '🇪🇸', '🇩🇪', '🇮🇹', '🇵🇹', '🇬🇧', '🇨🇦', '🇧🇪', '🇨🇭', '🇲🇦', '🇩🇿', '🇹🇳', '🇸🇳', '🇨🇮', '🇨🇲', '🇯🇵', '🇰🇷', '🇮🇳', '🇧🇷'],
};

const ALL_EMOJIS = Object.values(EMOJI_GROUPS).flat();

const makeLineId = (index) => `line-${index}-${Math.random().toString(36).slice(2, 8)}`;

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const parseApiDetail = (rawText, fallback) => {
  try {
    const parsed = JSON.parse(rawText || '{}');
    return String(parsed?.detail || rawText || fallback);
  } catch {
    return String(rawText || fallback);
  }
};

const getResponsiveWordsPerLine = () => {
  if (typeof window === 'undefined') return 4;
  const width = window.innerWidth || 0;
  if (width < 480) return 4;
  if (width < 768) return 5;
  if (width < 1200) return 6;
  return 7;
};

const normalizeWord = (word = {}, lineId = '', index = 0) => ({
  id: `${lineId}-word-${index}-${Math.random().toString(36).slice(2, 6)}`,
  text: String(word.text || '').trim(),
  startMs: Number(word.startMs) || 0,
  endMs: Number(word.endMs) || 0,
  color: '#FFFFFF',
  lineId,
});

const buildLinesFromCaptions = (captions = [], chunkSize = 4) => {
  if (!Array.isArray(captions) || !captions.length) return [];
  const size = clamp(Number(chunkSize) || 4, 2, 8);
  const wordsPerBlock = size * 2;
  const lines = [];
  for (let i = 0; i < captions.length; i += wordsPerBlock) {
    const id = makeLineId(i / wordsPerBlock);
    const words = captions.slice(i, i + wordsPerBlock).map((word, idx) => normalizeWord(word, id, idx));
    lines.push({
      id,
      emoji: '',
      words,
      style: { ...DEFAULT_STYLE, wordsPerLine: size },
      startMs: words[0]?.startMs ?? 0,
      endMs: words[words.length - 1]?.endMs ?? 0,
    });
  }
  return lines;
};

const flattenLines = (lines = []) => (
  lines.flatMap((line) => {
    const style = { ...DEFAULT_STYLE, ...(line.style || {}) };
    return (line.words || []).map((word) => ({
      text: String(word.text || '').trim(),
      startMs: Number(word.startMs) || 0,
      endMs: Number(word.endMs) || 0,
      color: word.color || '#FFFFFF',
      lineId: line.id,
      lineEmoji: line.emoji || '',
      linePositionX: style.positionX,
      linePositionY: style.positionY,
      lineFontSize: style.fontSize,
      lineFontFamily: style.fontFamily,
      lineFontColor: style.fontColor,
      lineHighlightColor: style.highlightColor,
      lineAnimation: style.animation,
      lineBold: style.bold,
      lineItalic: style.italic,
      lineBorderColor: style.borderColor,
      lineBorderWidth: style.borderWidth,
      lineBgColor: style.bgColor,
      lineBgOpacity: style.bgOpacity,
      lineTextShadowColor: style.textShadowColor,
      lineShadowBlur: style.shadowBlur,
      lineShadowOffsetX: style.shadowOffsetX,
      lineShadowOffsetY: style.shadowOffsetY,
      lineTextCase: style.textCase,
    }));
  }).filter((word) => word.text.length > 0)
);

const styleFromSavedWord = (word = {}, fallbackWordsPerLine = 4) => ({
  ...DEFAULT_STYLE,
  positionX: Number.isFinite(Number(word.linePositionX)) ? Number(word.linePositionX) : DEFAULT_STYLE.positionX,
  positionY: Number.isFinite(Number(word.linePositionY)) ? Number(word.linePositionY) : DEFAULT_STYLE.positionY,
  fontSize: Number.isFinite(Number(word.lineFontSize)) ? Number(word.lineFontSize) : DEFAULT_STYLE.fontSize,
  fontFamily: String(word.lineFontFamily || DEFAULT_STYLE.fontFamily),
  fontColor: String(word.lineFontColor || DEFAULT_STYLE.fontColor),
  highlightColor: String(word.lineHighlightColor || DEFAULT_STYLE.highlightColor),
  borderColor: String(word.lineBorderColor || DEFAULT_STYLE.borderColor),
  borderWidth: Number.isFinite(Number(word.lineBorderWidth)) ? Number(word.lineBorderWidth) : DEFAULT_STYLE.borderWidth,
  bgColor: String(word.lineBgColor || DEFAULT_STYLE.bgColor),
  bgOpacity: Number.isFinite(Number(word.lineBgOpacity)) ? Number(word.lineBgOpacity) : DEFAULT_STYLE.bgOpacity,
  textShadowColor: String(word.lineTextShadowColor || DEFAULT_STYLE.textShadowColor),
  shadowBlur: Number.isFinite(Number(word.lineShadowBlur)) ? Number(word.lineShadowBlur) : DEFAULT_STYLE.shadowBlur,
  shadowOffsetX: Number.isFinite(Number(word.lineShadowOffsetX)) ? Number(word.lineShadowOffsetX) : DEFAULT_STYLE.shadowOffsetX,
  shadowOffsetY: Number.isFinite(Number(word.lineShadowOffsetY)) ? Number(word.lineShadowOffsetY) : DEFAULT_STYLE.shadowOffsetY,
  textCase: String(word.lineTextCase || DEFAULT_STYLE.textCase),
  animation: String(word.lineAnimation || DEFAULT_STYLE.animation),
  bold: Boolean(word.lineBold ?? DEFAULT_STYLE.bold),
  italic: Boolean(word.lineItalic ?? DEFAULT_STYLE.italic),
  wordsPerLine: clamp(Number(fallbackWordsPerLine) || DEFAULT_STYLE.wordsPerLine, 2, 8),
});

const buildLinesFromSavedSubtitleConfig = (subtitleConfig = {}) => {
  if (!subtitleConfig || typeof subtitleConfig !== 'object') return [];
  const captions = Array.isArray(subtitleConfig.captions) ? subtitleConfig.captions : [];
  if (!captions.length) return [];

  const fallbackWordsPerLine = clamp(Number(subtitleConfig?.style?.wordsPerLine) || getResponsiveWordsPerLine(), 2, 8);
  const grouped = new Map();
  captions.forEach((word, idx) => {
    const lineId = String(word?.lineId || `line-${Math.floor(idx / (fallbackWordsPerLine * 2))}`);
    if (!grouped.has(lineId)) grouped.set(lineId, []);
    grouped.get(lineId).push(word || {});
  });

  return Array.from(grouped.entries()).map(([lineId, words]) => {
    const lineWords = words.map((word, idx) => ({
      id: `${lineId}-word-${idx}-${Math.random().toString(36).slice(2, 6)}`,
      text: String(word?.text || '').trim(),
      startMs: Number(word?.startMs) || 0,
      endMs: Number(word?.endMs) || 0,
      color: String(word?.color || '#FFFFFF'),
      lineId,
    })).filter((word) => word.text.length > 0);
    const seedWord = words[0] || {};
    const lineStart = lineWords[0]?.startMs ?? 0;
    const lineEnd = lineWords[lineWords.length - 1]?.endMs ?? lineStart;
    return {
      id: lineId,
      emoji: String(seedWord?.lineEmoji || ''),
      words: lineWords,
      style: styleFromSavedWord(seedWord, fallbackWordsPerLine),
      startMs: lineStart,
      endMs: lineEnd,
    };
  }).filter((line) => line.words.length > 0);
};

const rebalanceLineWords = (line, words) => {
  const base = words.filter((word) => String(word.text || '').trim().length > 0);
  if (!base.length) return line.words;
  const lineStart = Number(line.startMs || base[0].startMs || 0);
  const lineEnd = Math.max(lineStart + 300, Number(line.endMs || base[base.length - 1].endMs || lineStart + 1200));
  const segment = Math.max(120, Math.floor((lineEnd - lineStart) / base.length));
  return base.map((word, idx) => {
    const startMs = lineStart + idx * segment;
    return {
      ...word,
      startMs,
      endMs: idx === base.length - 1 ? lineEnd : startMs + segment,
      id: word.id || `${line.id}-word-${idx}`,
    };
  });
};

export default function CaptionsModal({
  isOpen,
  onClose,
  onGenerate,
  isProcessing,
  creditBlocked = false,
  creditError = '',
  videoUrl,
  jobId,
  clipIndex,
  existingHook,
  existingEffects,
  onResetStyles,
  isResettingStyles = false,
}) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const previewRef = useRef(null);

  const [lines, setLines] = useState([]);
  const [durationSec, setDurationSec] = useState(30);
  const [captionsLoading, setCaptionsLoading] = useState(false);
  const [fetchError, setFetchError] = useState('');
  const [selectedLineId, setSelectedLineId] = useState(null);
  const [showStyleEditor, setShowStyleEditor] = useState(false);

  const [translationEnabled, setTranslationEnabled] = useState(false);
  const [translateText, setTranslateText] = useState(true);
  const [targetLanguage, setTargetLanguage] = useState('fr');
  const [languages, setLanguages] = useState(FALLBACK_LANGUAGES);
  const [isTranslating, setIsTranslating] = useState(false);
  const [translationError, setTranslationError] = useState('');
  const [wordsPerLineTouched, setWordsPerLineTouched] = useState(false);
  const [emojiLineId, setEmojiLineId] = useState(null);
  const [emojiGroup, setEmojiGroup] = useState('popular');
  const [emojiSearch, setEmojiSearch] = useState('');

  const selectedLine = useMemo(() => lines.find((line) => line.id === selectedLineId) || null, [lines, selectedLineId]);
  const selectedLineStyle = useMemo(() => ({ ...DEFAULT_STYLE, ...(selectedLine?.style || {}) }), [selectedLine]);
  const flattenedCaptions = useMemo(() => flattenLines(lines), [lines]);

  const subtitleConfig = useMemo(() => ({
    captions: flattenedCaptions,
    style: { ...DEFAULT_STYLE, ...(lines[0]?.style || {}) },
  }), [flattenedCaptions, lines]);

  const visibleEmojis = useMemo(() => {
    const term = String(emojiSearch || '').trim();
    if (term) return ALL_EMOJIS.filter((emoji) => emoji.includes(term));
    return EMOJI_GROUPS[emojiGroup] || EMOJI_GROUPS.popular;
  }, [emojiGroup, emojiSearch]);

  const updateLine = (lineId, updater) => {
    setLines((prev) => prev.map((line) => (line.id === lineId ? updater(line) : line)));
  };

  const updateLineStyle = (lineId, patch) => {
    updateLine(lineId, (line) => ({ ...line, style: { ...DEFAULT_STYLE, ...(line.style || {}), ...patch } }));
  };

  const resetSelectedLineStyle = () => {
    if (!selectedLine) return;
    updateLineStyle(selectedLine.id, { ...DEFAULT_STYLE });
  };

  const applyWordsPerLine = (nextWordsPerLine) => {
    const size = clamp(Number(nextWordsPerLine) || 4, 2, 8);
    const allWords = flattenLines(lines).map((word) => ({
      text: word.text,
      startMs: word.startMs,
      endMs: word.endMs,
      color: word.color || '#FFFFFF',
    }));
    const nextLines = buildLinesFromCaptions(allWords, size).map((line) => ({
      ...line,
      style: {
        ...DEFAULT_STYLE,
        ...(selectedLine ? selectedLine.style : {}),
        wordsPerLine: size,
      },
    }));
    setLines(nextLines);
    setSelectedLineId(nextLines[0]?.id || null);
  };

  const focusPreviewLine = (lineId) => {
    const line = lines.find((item) => item.id === lineId);
    if (!line) return;
    previewRef.current?.seekToMs?.(line.startMs || 0);
  };

  const applySelectedStyleToAll = () => {
    if (!selectedLine) return;
    const sourceStyle = { ...DEFAULT_STYLE, ...(selectedLine.style || {}) };
    setLines((prev) => prev.map((line) => ({ ...line, style: { ...sourceStyle } })));
  };

  const applyLineStyleToAll = (lineId) => {
    const sourceLine = lines.find((line) => line.id === lineId);
    if (!sourceLine) return;
    const sourceStyle = { ...DEFAULT_STYLE, ...(sourceLine.style || {}) };
    setLines((prev) => prev.map((line) => ({ ...line, style: { ...sourceStyle } })));
  };

  const updateWordText = (lineId, wordId, text) => {
    updateLine(lineId, (line) => {
      const words = line.words.map((word) => (word.id === wordId ? { ...word, text } : word));
      return { ...line, words: rebalanceLineWords(line, words) };
    });
  };

  const deleteWord = (lineId, wordId) => {
    updateLine(lineId, (line) => {
      const remaining = line.words.filter((word) => word.id !== wordId);
      if (!remaining.length) return line;
      return { ...line, words: rebalanceLineWords(line, remaining) };
    });
  };

  const addWord = (lineId) => {
    updateLine(lineId, (line) => {
      const words = [...line.words, {
        id: `${line.id}-word-${Date.now().toString(36)}`,
        text: t('captionsModal.newWord', 'new'),
        color: '#FFFFFF',
        lineId,
      }];
      return { ...line, words: rebalanceLineWords(line, words) };
    });
  };

  const appendEmojiToLineEnd = (lineId, emoji) => {
    if (!emoji) return;
    updateLine(lineId, (line) => {
      if (!line.words?.length) return line;
      const lastWordIndex = line.words.length - 1;
      return {
        ...line,
        emoji: '',
        words: line.words.map((word, idx) => (
          idx === lastWordIndex
            ? { ...word, text: `${String(word.text || '').trim()} ${emoji}`.trim() }
            : word
        )),
      };
    });
    setEmojiLineId(null);
    setEmojiSearch('');
    focusPreviewLine(lineId);
  };

  useEffect(() => {
    if (!isOpen || !jobId || clipIndex == null || clipIndex < 0) return;
    let cancelled = false;

    const headers = user?.id ? { 'X-User-Id': user.id } : {};

    setCaptionsLoading(true);
    setFetchError('');
    setTranslationError('');
    setEmojiLineId(null);
    setEmojiSearch('');
    fetch(getApiUrl(`/api/clip/${jobId}/${clipIndex}/transcript`), { headers })
      .then(async (res) => {
        if (!res.ok) {
          const raw = await res.text();
          throw new Error(parseApiDetail(raw, t('captionsModal.loadFailed', 'Unable to load subtitles for this clip.')));
        }
        return res.json();
      })
      .then((data) => {
        if (cancelled) return;
        const responsiveWords = getResponsiveWordsPerLine();
        const restoredLines = buildLinesFromSavedSubtitleConfig(data?.subtitleConfig || {});
        const nextLines = restoredLines.length > 0
          ? restoredLines
          : buildLinesFromCaptions(data?.captions || [], responsiveWords);
        if (!nextLines.length) {
          setFetchError(t('captionsModal.noCaptions', 'No captions available for this clip.'));
        }
        setLines(nextLines);
        setSelectedLineId(nextLines[0]?.id || null);
        setDurationSec(Number(data?.durationSec) > 0 ? Number(data.durationSec) : 30);
        setWordsPerLineTouched(false);
      })
      .catch((err) => {
        if (!cancelled) {
          setLines([]);
          setFetchError(err?.message || t('captionsModal.loadFailed', 'Unable to load subtitles for this clip.'));
        }
      })
      .finally(() => {
        if (!cancelled) setCaptionsLoading(false);
      });

    fetch(getApiUrl('/api/translate/languages'), { headers })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !Array.isArray(data?.languages)) return;
        const mapped = {};
        data.languages.forEach((item) => {
          if (item?.code && item?.name) mapped[item.code] = item.name;
        });
        if (Object.keys(mapped).length > 0) {
          setLanguages(mapped);
          setTargetLanguage((prev) => (mapped[prev] ? prev : Object.keys(mapped)[0]));
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [clipIndex, isOpen, jobId, t, user?.id]);

  useEffect(() => {
    if (!isOpen || wordsPerLineTouched) return;
    const onResize = () => {
      if (!Array.isArray(lines) || lines.length === 0) return;
      applyWordsPerLine(getResponsiveWordsPerLine());
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [isOpen, lines, wordsPerLineTouched]);

  const handleApplyTranslation = async () => {
    if (!translationEnabled || !translateText || !targetLanguage || !jobId) return;
    setIsTranslating(true);
    setTranslationError('');
    try {
      const payload = {
        job_id: jobId,
        clip_index: clipIndex,
        target_language: targetLanguage,
      };
      const stableInput = videoUrl && !videoUrl.startsWith('blob:') ? videoUrl : undefined;
      if (stableInput) payload.input_url = stableInput;
      const res = await fetch(getApiUrl('/api/translate/captions'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(user?.id ? { 'X-User-Id': user.id } : {}),
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const errorText = await res.text();
        setTranslationError(errorText || t('captionsModal.translationFailed', 'Subtitle translation failed.'));
        return;
      }
      const data = await res.json();
      const translated = Array.isArray(data?.captions) ? data.captions : [];
      const nextLines = buildLinesFromCaptions(translated, getResponsiveWordsPerLine());
      setLines(nextLines);
      setSelectedLineId(nextLines[0]?.id || null);
      if (Number(data?.durationSec) > 0) setDurationSec(Number(data.durationSec));
    } catch (error) {
      setTranslationError(error.message || t('captionsModal.translationFailed', 'Subtitle translation failed.'));
    } finally {
      setIsTranslating(false);
    }
  };

  useEffect(() => {
    if (showStyleEditor && !selectedLine) {
      setShowStyleEditor(false);
    }
  }, [showStyleEditor, selectedLine]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
      <div className="bg-white dark:bg-[#121214] border border-slate-300 dark:border-white/10 p-5 md:p-6 rounded-2xl w-full max-w-7xl shadow-2xl relative flex flex-col md:flex-row gap-5 md:gap-6 max-h-[92vh] overflow-x-hidden">
        <button onClick={onClose} className="absolute top-4 right-4 text-slate-400 dark:text-zinc-500 hover:text-slate-700 dark:hover:text-white z-10">
          <X size={20} />
        </button>

        <div className="w-full md:w-[50%] rounded-xl border border-slate-300 dark:border-white/10 bg-slate-50 dark:bg-black/30 p-4 md:p-5 overflow-y-auto overflow-x-hidden custom-scrollbar">
          {showStyleEditor && selectedLine ? (
            <>
              <div className="mb-4 flex items-center justify-between gap-2">
                <button onClick={() => setShowStyleEditor(false)} className="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                  <ArrowLeft size={14} /> {t('captionsModal.back', 'Retour')}
                </button>
                <h4 className="text-sm font-bold text-slate-900 dark:text-white">{t('captionsModal.styleEditor', 'Edition de style')}</h4>
              </div>

              <div className="space-y-4">
                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.freePosition', 'Free position (X/Y)')}</label>
                  <div className="mt-2 space-y-2">
                    <label className="block text-[11px] text-slate-600 dark:text-slate-300">X ({selectedLineStyle.positionX}%)
                      <input type="range" min="5" max="95" value={selectedLineStyle.positionX} onChange={(e) => { updateLineStyle(selectedLine.id, { positionX: Number(e.target.value) || 50 }); focusPreviewLine(selectedLine.id); }} className="mt-1 w-full accent-emerald-500" />
                    </label>
                    <label className="block text-[11px] text-slate-600 dark:text-slate-300">Y ({selectedLineStyle.positionY}%)
                      <input type="range" min="5" max="95" value={selectedLineStyle.positionY} onChange={(e) => { updateLineStyle(selectedLine.id, { positionY: Number(e.target.value) || 82 }); focusPreviewLine(selectedLine.id); }} className="mt-1 w-full accent-emerald-500" />
                    </label>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.textStyle', 'Text style')}</label>
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    {[
                      { key: 'normal', label: t('captionsModal.normal', 'Normal'), patch: { bold: false, italic: false } },
                      { key: 'bold', label: t('captionsModal.bold', 'Bold'), patch: { bold: true, italic: false } },
                      { key: 'italic', label: t('captionsModal.italic', 'Italic'), patch: { bold: false, italic: true } },
                    ].map((opt) => {
                      const isActive = (opt.key === 'normal' && !selectedLineStyle.bold && !selectedLineStyle.italic)
                        || (opt.key === 'bold' && selectedLineStyle.bold && !selectedLineStyle.italic)
                        || (opt.key === 'italic' && selectedLineStyle.italic && !selectedLineStyle.bold);
                      return (
                        <button
                          key={`${selectedLine.id}-emph-${opt.key}`}
                          type="button"
                          onClick={() => { updateLineStyle(selectedLine.id, opt.patch); focusPreviewLine(selectedLine.id); }}
                          className={`rounded-md border px-2 py-1.5 text-xs ${isActive ? 'border-emerald-400 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200' : 'border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 text-slate-700 dark:text-slate-300'}`}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    {[
                      { value: 'none', label: t('captionsModal.caseNormal', 'Normal') },
                      { value: 'uppercase', label: t('captionsModal.caseUpper', 'UPPER') },
                      { value: 'lowercase', label: t('captionsModal.caseLower', 'lower') },
                    ].map((opt) => (
                      <button
                        key={`${selectedLine.id}-case-${opt.value}`}
                        type="button"
                        onClick={() => { updateLineStyle(selectedLine.id, { textCase: opt.value }); focusPreviewLine(selectedLine.id); }}
                        className={`rounded-md border px-2 py-1.5 text-xs ${selectedLineStyle.textCase === opt.value ? 'border-emerald-400 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200' : 'border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 text-slate-700 dark:text-slate-300'}`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.animation', 'Animation')}</label>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    {ANIMATION_OPTIONS.map((opt) => (
                      <button key={`${selectedLine.id}-anim-${opt.value}`} type="button" onClick={() => { updateLineStyle(selectedLine.id, { animation: opt.value }); focusPreviewLine(selectedLine.id); }} className={`rounded-md border px-2 py-1.5 text-left ${selectedLineStyle.animation === opt.value ? 'border-emerald-400 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200' : 'border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 text-slate-700 dark:text-slate-300'}`}>
                        <div className="text-xs font-medium">{opt.label}</div>
                        <div className="mt-0.5 text-[10px] leading-tight opacity-80">{opt.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.fontFamily', 'Font family')}</label>
                  <select value={selectedLineStyle.fontFamily} onChange={(e) => { updateLineStyle(selectedLine.id, { fontFamily: e.target.value }); focusPreviewLine(selectedLine.id); }} className="mt-2 w-full bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1.5 text-xs text-slate-900 dark:text-zinc-100">
                    {[...new Set(FONT_OPTIONS.map((opt) => opt.category))].map((cat) => (
                      <optgroup key={cat} label={cat}>{FONT_OPTIONS.filter((opt) => opt.category === cat).map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}</optgroup>
                    ))}
                  </select>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.lineSize', 'Line size')} ({selectedLineStyle.fontSize}px)</label>
                  <input type="range" min="28" max="96" value={selectedLineStyle.fontSize} onChange={(e) => { updateLineStyle(selectedLine.id, { fontSize: Number(e.target.value) || 52 }); focusPreviewLine(selectedLine.id); }} className="mt-2 w-full accent-emerald-500" />
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.textColor', 'Text color')}</label>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {COLOR_PRESETS.map((preset) => (
                      <button key={`${selectedLine.id}-${preset.color}`} type="button" onClick={() => { updateLineStyle(selectedLine.id, { fontColor: preset.color }); focusPreviewLine(selectedLine.id); }} className={`h-6 w-6 rounded-full border-2 ${selectedLineStyle.fontColor === preset.color ? 'border-white scale-110' : 'border-slate-400 dark:border-white/20'}`} style={{ backgroundColor: preset.color }} />
                    ))}
                    <label className="relative h-6 w-6 rounded-full border border-dashed border-slate-400/80 overflow-hidden" title={t('captionsModal.customColor', 'Custom color')}>
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] text-slate-300">+</span>
                      <input type="color" value={selectedLineStyle.fontColor} onChange={(e) => { updateLineStyle(selectedLine.id, { fontColor: e.target.value }); focusPreviewLine(selectedLine.id); }} className="absolute inset-0 opacity-0 cursor-pointer" />
                    </label>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.highlightColor', 'Highlight color')}</label>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {HIGHLIGHT_COLOR_PRESETS.map((preset) => (
                      <button key={`${selectedLine.id}-hl-${preset.color}`} type="button" onClick={() => { updateLineStyle(selectedLine.id, { highlightColor: preset.color }); focusPreviewLine(selectedLine.id); }} className={`h-6 w-6 rounded-full border-2 ${selectedLineStyle.highlightColor === preset.color ? 'border-white scale-110' : 'border-slate-400 dark:border-white/20'}`} style={{ backgroundColor: preset.color }} />
                    ))}
                    <label className="relative h-6 w-6 rounded-full border border-dashed border-slate-400/80 overflow-hidden" title={t('captionsModal.customColor', 'Custom color')}>
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] text-slate-300">+</span>
                      <input type="color" value={selectedLineStyle.highlightColor} onChange={(e) => { updateLineStyle(selectedLine.id, { highlightColor: e.target.value }); focusPreviewLine(selectedLine.id); }} className="absolute inset-0 opacity-0 cursor-pointer" />
                    </label>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.shadowColor', 'Shadow color')}</label>
                  <div className="mt-2 flex items-center gap-3 rounded-md border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 p-2">
                    <label className="relative h-7 w-7 rounded border border-slate-300 dark:border-white/10 overflow-hidden" title={t('captionsModal.shadowColor', 'Shadow color')}>
                      <div className="h-full w-full" style={{ backgroundColor: selectedLineStyle.textShadowColor }} />
                      <input type="color" value={selectedLineStyle.textShadowColor} onChange={(e) => { updateLineStyle(selectedLine.id, { textShadowColor: e.target.value }); focusPreviewLine(selectedLine.id); }} className="absolute inset-0 opacity-0 cursor-pointer" />
                    </label>
                    <div className="grid flex-1 grid-cols-3 gap-2 text-[10px] text-slate-400">
                      <label>{t('captionsModal.blur', 'Blur')} {selectedLineStyle.shadowBlur}px
                        <input type="range" min="0" max="24" value={selectedLineStyle.shadowBlur} onChange={(e) => { updateLineStyle(selectedLine.id, { shadowBlur: Number(e.target.value) || 0 }); focusPreviewLine(selectedLine.id); }} className="mt-1 w-full accent-emerald-500" />
                      </label>
                      <label>{t('captionsModal.offsetX', 'Offset X')} {selectedLineStyle.shadowOffsetX}px
                        <input type="range" min="-20" max="20" value={selectedLineStyle.shadowOffsetX} onChange={(e) => { updateLineStyle(selectedLine.id, { shadowOffsetX: Number(e.target.value) || 0 }); focusPreviewLine(selectedLine.id); }} className="mt-1 w-full accent-emerald-500" />
                      </label>
                      <label>{t('captionsModal.offsetY', 'Offset Y')} {selectedLineStyle.shadowOffsetY}px
                        <input type="range" min="-20" max="20" value={selectedLineStyle.shadowOffsetY} onChange={(e) => { updateLineStyle(selectedLine.id, { shadowOffsetY: Number(e.target.value) || 0 }); focusPreviewLine(selectedLine.id); }} className="mt-1 w-full accent-emerald-500" />
                      </label>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.border', 'Border')}</label>
                  <div className="mt-2 flex items-center gap-3 rounded-md border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 p-2">
                    <label className="relative h-7 w-7 rounded border border-slate-300 dark:border-white/10 overflow-hidden" title={t('captionsModal.borderColor', 'Border color')}>
                      <div className="h-full w-full" style={{ backgroundColor: selectedLineStyle.borderColor }} />
                      <input type="color" value={selectedLineStyle.borderColor} onChange={(e) => { updateLineStyle(selectedLine.id, { borderColor: e.target.value }); focusPreviewLine(selectedLine.id); }} className="absolute inset-0 opacity-0 cursor-pointer" />
                    </label>
                    <label className="flex-1 text-[10px] text-slate-400">{t('captionsModal.thickness', 'Thickness')} ({selectedLineStyle.borderWidth})
                      <input type="range" min="0" max="6" value={selectedLineStyle.borderWidth} onChange={(e) => { updateLineStyle(selectedLine.id, { borderWidth: Number(e.target.value) || 0 }); focusPreviewLine(selectedLine.id); }} className="mt-1 w-full accent-emerald-500" />
                    </label>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.wordsPerLine', 'Words per line')} ({selectedLineStyle.wordsPerLine || 4})</label>
                  <input
                    type="range"
                    min="2"
                    max="8"
                    value={selectedLineStyle.wordsPerLine || 4}
                    onChange={(e) => {
                      const value = clamp(Number(e.target.value) || 4, 2, 8);
                      setWordsPerLineTouched(true);
                      updateLineStyle(selectedLine.id, { wordsPerLine: value });
                      applyWordsPerLine(value);
                      focusPreviewLine(selectedLine.id);
                    }}
                    className="mt-2 w-full accent-emerald-500"
                  />
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <div className="flex items-center justify-between text-xs text-slate-700 dark:text-slate-300">
                    <span>{t('captionsModal.backgroundBox', 'Background box')}</span>
                    <input
                      type="checkbox"
                      checked={selectedLineStyle.bgOpacity > 0}
                      onChange={(e) => {
                        updateLineStyle(selectedLine.id, { bgOpacity: e.target.checked ? 0.5 : 0 });
                        focusPreviewLine(selectedLine.id);
                      }}
                    />
                  </div>
                  {selectedLineStyle.bgOpacity > 0 ? (
                    <div className="mt-3 flex items-center gap-3">
                      <label className="relative h-7 w-7 rounded border border-slate-300 dark:border-white/10 overflow-hidden" title={t('captionsModal.backgroundColor', 'Background color')}>
                        <div className="h-full w-full" style={{ backgroundColor: selectedLineStyle.bgColor }} />
                        <input type="color" value={selectedLineStyle.bgColor} onChange={(e) => { updateLineStyle(selectedLine.id, { bgColor: e.target.value }); focusPreviewLine(selectedLine.id); }} className="absolute inset-0 opacity-0 cursor-pointer" />
                      </label>
                      <label className="flex-1 text-[10px] text-slate-400">{t('captionsModal.opacity', 'Opacity')} ({Math.round((selectedLineStyle.bgOpacity || 0) * 100)}%)
                        <input type="range" min="10" max="100" value={Math.round((selectedLineStyle.bgOpacity || 0) * 100)} onChange={(e) => { updateLineStyle(selectedLine.id, { bgOpacity: (Number(e.target.value) || 0) / 100 }); focusPreviewLine(selectedLine.id); }} className="mt-1 w-full accent-emerald-500" />
                      </label>
                    </div>
                  ) : null}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button type="button" onClick={resetSelectedLineStyle} className="rounded-md border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 px-3 py-1.5 text-xs text-slate-700 dark:text-slate-300">
                    {t('captionsModal.resetStyles', 'Reset styles')}
                  </button>
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 className="title-contrast text-lg font-bold flex items-center gap-2">
                  <MessageSquareText className="text-emerald-400" size={18} />
                  {t('captionsModal.subtitleTitle', 'Sous-titres')}
                </h3>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setShowStyleEditor(true)}
                    disabled={!selectedLine}
                    className="rounded-lg border border-slate-300 dark:border-white/10 bg-white dark:bg-white/5 hover:bg-slate-100 dark:hover:bg-white/10 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 disabled:opacity-40"
                  >
                    {t('captionsModal.styleEditor', 'Edition de style')}
                  </button>
                  <button
                    type="button"
                    onClick={() => onResetStyles?.()}
                    disabled={isResettingStyles}
                    className="rounded-lg border border-rose-300/60 dark:border-rose-500/40 bg-rose-50 dark:bg-rose-500/10 hover:bg-rose-100 dark:hover:bg-rose-500/20 px-3 py-1.5 text-xs font-semibold text-rose-700 dark:text-rose-200 disabled:opacity-40 inline-flex items-center gap-1"
                  >
                    {isResettingStyles ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
                    {t('captionsModal.resetVideo', 'Reset')}
                  </button>
                </div>
              </div>

              <p className="mb-3 text-xs text-slate-400 dark:text-zinc-500">{t('captionsModal.clickLineHint', 'Click a line to edit.')}</p>

              <div className="mb-4 rounded-xl border border-slate-300 dark:border-white/10 bg-white/[0.04] p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">{t('captionsModal.translation', 'Traduction')}</span>
                  <input type="checkbox" checked={translationEnabled} onChange={(e) => setTranslationEnabled(e.target.checked)} />
                </div>
                {translationEnabled ? (
                  <>
                    <div className="flex items-center justify-between text-xs text-slate-700 dark:text-slate-300">
                      <span>{t('captionsModal.translationText', 'Texte')}</span>
                      <input type="checkbox" checked={translateText} onChange={(e) => setTranslateText(e.target.checked)} />
                    </div>
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>{t('captionsModal.translationVoice', 'Voix')}</span>
                      <input type="checkbox" checked={false} disabled />
                    </div>
                    <select value={targetLanguage} onChange={(e) => setTargetLanguage(e.target.value)} className="w-full bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1 text-xs text-slate-900 dark:text-zinc-100">
                      {Object.entries(languages).map(([code, name]) => (
                        <option key={code} value={code}>{name}</option>
                      ))}
                    </select>
                    <button type="button" onClick={handleApplyTranslation} disabled={isTranslating || !translateText} className="w-full rounded-md bg-emerald-500/20 border border-emerald-500/40 px-3 py-1.5 text-xs text-emerald-200 disabled:opacity-50">
                      {isTranslating ? t('captionsModal.applying', 'Applying...') : t('captionsModal.apply', 'Appliquer')}
                    </button>
                    {translationError ? <p className="text-[11px] text-red-300">{translationError}</p> : null}
                  </>
                ) : null}
              </div>

              {captionsLoading ? <p className="text-sm text-slate-400">{t('captionsModal.loading', 'Loading subtitles...')}</p> : null}
              {fetchError ? <p className="text-xs text-red-300">{fetchError}</p> : null}
              {creditBlocked ? <p className="text-xs text-amber-300 mb-3">{creditError || t('captionsModal.insufficientCredits', 'Insufficient credits')}</p> : null}

              <div className="space-y-3">
                {lines.map((line, lineIndex) => (
                  <div key={line.id} onClick={() => { setSelectedLineId(line.id); previewRef.current?.seekToMs?.(line.startMs || 0); }} className={`relative rounded-xl border p-3 space-y-3 ${selectedLineId === line.id ? 'border-emerald-400 bg-emerald-500/10' : 'border-slate-300 dark:border-white/10 bg-white/[0.05]'}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] uppercase tracking-wider text-slate-400">{t('captionsModal.line', 'Line')} {lineIndex + 1}</span>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEmojiLineId((prev) => (prev === line.id ? null : line.id));
                            setEmojiSearch('');
                            setEmojiGroup('popular');
                          }}
                          className="rounded-md border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 px-2 py-1 text-[11px] text-slate-700 dark:text-slate-200"
                        >
                          {t('captionsModal.addEmoji', 'Add emoji')}
                        </button>
                        <button type="button" onClick={(e) => { e.stopPropagation(); applyLineStyleToAll(line.id); }} className="rounded-md border border-emerald-300 bg-emerald-100 px-2 py-1 text-[11px] font-semibold text-emerald-800 hover:bg-emerald-200 dark:border-emerald-500/40 dark:bg-emerald-500/15 dark:text-emerald-200 dark:hover:bg-emerald-500/25">
                          {t('captionsModal.applyToAll', 'Appliquer a tous')}
                        </button>
                        <button type="button" onClick={(e) => { e.stopPropagation(); setLines((prev) => prev.filter((item) => item.id !== line.id)); }} className="rounded-md border border-rose-300 bg-rose-100 px-2 py-1 text-[11px] font-semibold text-rose-800 hover:bg-rose-200 dark:border-rose-500/40 dark:bg-rose-500/15 dark:text-rose-200 dark:hover:bg-rose-500/25">
                          {t('captionsModal.deleteLine', 'Delete line')}
                        </button>
                      </div>
                    </div>

                    {emojiLineId === line.id ? (
                      <div onClick={(e) => e.stopPropagation()} className="rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-black/50 p-2.5 space-y-2">
                        <input
                          type="text"
                          value={emojiSearch}
                          onChange={(e) => setEmojiSearch(e.target.value)}
                          placeholder={t('captionsModal.searchEmoji', 'Search emoji...')}
                          className="w-full bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1 text-xs text-slate-900 dark:text-zinc-100"
                        />
                        <div className="flex flex-wrap gap-1.5">
                          {Object.keys(EMOJI_GROUPS).map((groupKey) => (
                            <button
                              key={`${line.id}-${groupKey}`}
                              type="button"
                              onClick={() => setEmojiGroup(groupKey)}
                              className={`rounded-md border px-2 py-1 text-[10px] uppercase tracking-wide ${emojiGroup === groupKey ? 'border-emerald-400 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200' : 'border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 text-slate-700 dark:text-slate-300'}`}
                            >
                              {t(`captionsModal.emojiCategory.${groupKey}`, groupKey)}
                            </button>
                          ))}
                        </div>
                        <div className="grid grid-cols-10 gap-1 max-h-32 overflow-y-auto custom-scrollbar pr-1">
                          {visibleEmojis.map((emoji) => (
                            <button
                              key={`${line.id}-${emoji}`}
                              type="button"
                              onClick={() => appendEmojiToLineEnd(line.id, emoji)}
                              className="h-7 rounded-md border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 hover:bg-slate-200 dark:hover:bg-black/60 text-sm"
                              title={emoji}
                            >
                              {emoji}
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    <div className="flex flex-wrap gap-2">
                      {line.words.map((word) => (
                        <div key={word.id} className="inline-flex items-center rounded-md border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 overflow-hidden">
                          <input
                            value={word.text}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => updateWordText(line.id, word.id, e.target.value)}
                            className="bg-transparent px-2 py-1 text-xs text-slate-900 dark:text-zinc-100 min-w-[72px] outline-none"
                          />
                          <input
                            type="color"
                            value={word.color || '#FFFFFF'}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => updateLine(line.id, (curr) => ({ ...curr, words: curr.words.map((w) => (w.id === word.id ? { ...w, color: e.target.value } : w)) }))}
                            className="h-6 w-6 border-l border-slate-300 dark:border-white/10 bg-transparent"
                          />
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (line.words.length > 1) deleteWord(line.id, word.id);
                            }}
                            className="px-1 text-red-300 text-xs"
                            disabled={line.words.length <= 1}
                          >
                            ×
                          </button>
                        </div>
                      ))}
                      <button type="button" onClick={(e) => { e.stopPropagation(); addWord(line.id); }} className="inline-flex items-center gap-1 rounded-md border border-emerald-300 bg-emerald-100 px-2 py-1 text-[11px] font-semibold text-emerald-800 hover:bg-emerald-200 dark:border-emerald-500/40 dark:bg-emerald-500/15 dark:text-emerald-200 dark:hover:bg-emerald-500/25">
                        <Plus size={11} /> {t('captionsModal.addWord', 'Add word')}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="w-full md:w-[50%] rounded-xl border border-slate-300 dark:border-white/10 bg-slate-50 dark:bg-black/30 p-4 md:p-5 flex flex-col gap-3 overflow-x-hidden">
          <h3 className="title-contrast text-lg font-bold">{t('captionsModal.preview', 'Preview')}</h3>
          <div className="flex-1 rounded-lg border border-slate-300 dark:border-white/10 overflow-hidden bg-black min-h-[360px]">
            <RemotionPreview
              ref={previewRef}
              videoUrl={videoUrl}
              durationInSeconds={durationSec}
              subtitles={flattenedCaptions.length > 0 ? subtitleConfig : null}
              hook={existingHook || null}
              effects={existingEffects || null}
            />
          </div>

          <button
            type="button"
            onClick={() => onGenerate({ remotion: subtitleConfig, previewDurationSec: durationSec })}
            disabled={isProcessing || flattenedCaptions.length === 0 || creditBlocked}
            className="w-full py-3 bg-gradient-to-r from-emerald-500 to-green-500 hover:from-emerald-400 hover:to-green-400 text-black font-bold rounded-xl shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98] inline-flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {isProcessing ? <Loader2 size={16} className="animate-spin" /> : <MessageSquareText size={16} />}
            {isProcessing ? t('captionsModal.generating', 'Generating...') : t('captionsModal.generateSubtitles', 'Generate subtitles')}
          </button>
        </div>
      </div>
    </div>
  );
}


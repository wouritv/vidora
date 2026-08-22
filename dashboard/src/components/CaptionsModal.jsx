import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, MessageSquareText, Trash2, X } from 'lucide-react';
import { getApiUrl } from '../config';
import RemotionPreview from './RemotionPreview';
import { ANIMATION_OPTIONS, COLOR_PRESETS, FONT_OPTIONS } from '../lib/subtitleOptions';
import { useTranslation } from '../state/LanguageContext';

const DEFAULT_WORDS_PER_LINE = 4;
const DEFAULT_LINE_FONT_SIZE = 52;
const DEFAULT_LINE_STYLE = {
  emoji: '',
  positionX: 50,
  positionY: 82,
  fontSize: DEFAULT_LINE_FONT_SIZE,
  fontFamily: 'Arial',
};
const EMOJI_SUGGESTIONS = ['🔥', '😂', '😮', '💡', '✅', '🚀', '🎯', '💥'];
const EMOJI_CATEGORIES = {
  popular: ['🔥', '😂', '😮', '💡', '✅', '🚀', '🎯', '💥', '✨', '❤️', '👏', '😎'],
  faces: ['😀', '😁', '🤣', '😊', '😍', '🤩', '😢', '😡', '🤯', '🥶', '😴', '🤔'],
  symbols: ['✅', '❌', '⚠️', '💯', '⭐', '🎉', '💥', '🔔', '📌', '📈', '🧠', '🛠️'],
  media: ['🎬', '🎥', '🎤', '🎧', '📱', '💻', '📸', '📰', '🎮', '📢', '🌍', '🕒'],
};

const makeLineId = (index) => `line-${index}-${Math.random().toString(36).slice(2, 8)}`;

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

function normalizeWord(word = {}, index = 0, lineId = '') {
  return {
    id: `${lineId}-word-${index}`,
    text: String(word.text || '').trim(),
    startMs: Number(word.startMs) || 0,
    endMs: Number(word.endMs) || 0,
    color: '#FFFFFF',
    lineId,
  };
}

function buildLinesFromCaptions(captions = [], wordsPerLine = DEFAULT_WORDS_PER_LINE) {
  if (!Array.isArray(captions) || captions.length === 0) {
    return [];
  }

  const safePerLine = clamp(Number(wordsPerLine) || DEFAULT_WORDS_PER_LINE, 1, 12);
  const lines = [];

  for (let i = 0; i < captions.length; i += safePerLine) {
    const chunk = captions.slice(i, i + safePerLine);
    const lineId = makeLineId(i / safePerLine);
    const words = chunk.map((word, idx) => normalizeWord(word, idx, lineId));
    lines.push({
      id: lineId,
      words,
      ...DEFAULT_LINE_STYLE,
      startMs: words[0]?.startMs ?? 0,
      endMs: words[words.length - 1]?.endMs ?? 0,
    });
  }

  return lines;
}

function flattenLines(lines = []) {
  return lines
    .flatMap((line) => {
      const words = Array.isArray(line.words) ? line.words : [];
      return words.map((word) => ({
        text: String(word.text || '').trim(),
        startMs: Number(word.startMs) || 0,
        endMs: Number(word.endMs) || 0,
        color: word.color || '#FFFFFF',
        lineId: line.id,
        lineEmoji: line.emoji || '',
        linePositionX: clamp(Number(line.positionX) || 50, 0, 100),
        linePositionY: clamp(Number(line.positionY) || 82, 0, 100),
        lineFontSize: clamp(Number(line.fontSize) || DEFAULT_LINE_FONT_SIZE, 20, 120),
        lineFontFamily: String(line.fontFamily || 'Arial'),
      }));
    })
    .filter((word) => word.text.length > 0);
}

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
}) {
  const { t } = useTranslation();
  const [lines, setLines] = useState([]);
  const [captionsLoading, setCaptionsLoading] = useState(false);
  const [fetchError, setFetchError] = useState('');
  const [durationSec, setDurationSec] = useState(30);
  const [selectedWordRef, setSelectedWordRef] = useState(null);
  const [selectedLineId, setSelectedLineId] = useState(null);
  const [openEmojiLineId, setOpenEmojiLineId] = useState(null);
  const [emojiSearch, setEmojiSearch] = useState('');
  const [emojiCategory, setEmojiCategory] = useState('popular');
  const [fontFamily, setFontFamily] = useState('Arial');
  const [highlightColor, setHighlightColor] = useState('#FFDD00');
  const [animation, setAnimation] = useState('word-highlight');
  const [bold, setBold] = useState(true);
  const [italic, setItalic] = useState(false);
  const previewRef = useRef(null);

  useEffect(() => {
    if (!isOpen || !jobId || clipIndex === undefined || clipIndex === null || clipIndex < 0) {
      return;
    }

    let cancelled = false;
    setCaptionsLoading(true);
    setFetchError('');
    setSelectedWordRef(null);
    setSelectedLineId(null);
    setOpenEmojiLineId(null);
    setEmojiSearch('');
    setEmojiCategory('popular');

    fetch(getApiUrl(`/api/clip/${jobId}/${clipIndex}/transcript`))
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled) return;
        const nextLines = buildLinesFromCaptions(data?.captions || []);
        setLines(nextLines);
        setDurationSec(Number(data?.durationSec) > 0 ? Number(data.durationSec) : 30);
      })
      .catch(() => {
        if (!cancelled) {
          setLines([]);
          setFetchError(t('captionsModal.loadFailed', 'Unable to load clip captions.'));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCaptionsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, jobId, clipIndex, t]);

  const flattenedCaptions = useMemo(() => flattenLines(lines), [lines]);

  const selectedWord = useMemo(() => {
    if (!selectedWordRef) return null;
    const line = lines.find((item) => item.id === selectedWordRef.lineId);
    if (!line) return null;
    const word = line.words.find((item) => item.id === selectedWordRef.wordId);
    return word || null;
  }, [lines, selectedWordRef]);

  const filteredEmojis = useMemo(() => {
    const source = EMOJI_CATEGORIES[emojiCategory] || [];
    const term = String(emojiSearch || '').trim();
    if (!term) return source;
    return source.filter((emoji) => emoji.includes(term));
  }, [emojiCategory, emojiSearch]);

  const subtitleConfig = useMemo(() => ({
    captions: flattenedCaptions,
    style: {
      positionX: 50,
      positionY: 82,
      fontFamily,
      fontSize: 52,
      fontColor: '#FFFFFF',
      highlightColor,
      borderColor: '#000000',
      borderWidth: 3,
      textShadowColor: '#000000',
      shadowBlur: 8,
      shadowOffsetX: 0,
      shadowOffsetY: 2,
      bgColor: '#000000',
      bgOpacity: 0,
      textCase: 'none',
      bold,
      italic,
      wordsPerLine: 8,
      animation,
    },
  }), [animation, bold, flattenedCaptions, fontFamily, highlightColor, italic]);

  const updateLine = (lineId, updater) => {
    setLines((prev) => prev.map((line) => (line.id === lineId ? updater(line) : line)));
  };

  const resetStyles = () => {
    setLines((prev) => prev.map((line) => ({
      ...line,
      ...DEFAULT_LINE_STYLE,
      words: line.words.map((word) => ({ ...word, color: '#FFFFFF' })),
    })));
    setHighlightColor('#FFDD00');
    setFontFamily('Arial');
    setAnimation('word-highlight');
    setBold(true);
    setItalic(false);
  };

  const applyLineStyleToAll = (sourceLineId) => {
    const source = lines.find((line) => line.id === sourceLineId);
    if (!source) return;
    const sourceWordColors = source.words.map((word) => word.color || '#FFFFFF');
    setLines((prev) => prev.map((line) => ({
      ...line,
      emoji: source.emoji,
      positionX: source.positionX,
      positionY: source.positionY,
      fontSize: source.fontSize,
      fontFamily: source.fontFamily,
      words: line.words.map((word, idx) => ({
        ...word,
        color: sourceWordColors[idx] || word.color || '#FFFFFF',
      })),
    })));
  };

  const updateWord = (lineId, wordId, updater) => {
    updateLine(lineId, (line) => ({
      ...line,
      words: line.words.map((word) => (word.id === wordId ? updater(word) : word)),
    }));
  };

  const deleteLine = (lineId) => {
    setLines((prev) => prev.filter((line) => line.id !== lineId));
    setSelectedWordRef((prev) => (prev?.lineId === lineId ? null : prev));
    setSelectedLineId((prev) => (prev === lineId ? null : prev));
  };

  const appendEmojiToLine = (lineId, emoji) => {
    if (!emoji) return;
    updateLine(lineId, (line) => {
      if (!line.words.length) return line;
      const lastWordIndex = line.words.length - 1;
      return {
        ...line,
        emoji,
        words: line.words.map((word, idx) => (
          idx === lastWordIndex
            ? { ...word, text: `${String(word.text || '').replace(/[\s\u{1F300}-\u{1FAFF}]+$/gu, '')}${emoji}` }
            : word
        )),
      };
    });
  };

  const handleLineFocus = (line) => {
    setSelectedLineId(line.id);
    const firstWord = Array.isArray(line.words) ? line.words[0] : null;
    if (firstWord?.id) {
      setSelectedWordRef({ lineId: line.id, wordId: firstWord.id });
    }
    previewRef.current?.seekToMs?.(line.startMs || 0);
  };

  const applyColorToLineWord = (lineId, color) => {
    const targetRef = selectedWordRef?.lineId === lineId
      ? selectedWordRef
      : (() => {
        const targetLine = lines.find((item) => item.id === lineId);
        const fallbackWord = targetLine?.words?.[0];
        return fallbackWord ? { lineId, wordId: fallbackWord.id } : null;
      })();

    if (!targetRef) return;
    if (!selectedWordRef || selectedWordRef.lineId !== targetRef.lineId || selectedWordRef.wordId !== targetRef.wordId) {
      setSelectedWordRef(targetRef);
    }
    updateWord(targetRef.lineId, targetRef.wordId, (prev) => ({ ...prev, color }));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
      <div className="bg-[#121214] border border-slate-300 dark:border-white/10 p-5 md:p-6 rounded-2xl w-full max-w-7xl shadow-2xl relative flex flex-col md:flex-row gap-5 md:gap-6 max-h-[92vh]">
        <button onClick={onClose} className="absolute top-4 right-4 text-slate-400 dark:text-zinc-500 hover:text-white z-10">
          <X size={20} />
        </button>

        <div className="w-full md:w-[50%] rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 p-4 md:p-5 overflow-y-auto custom-scrollbar">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h3 className="title-contrast text-lg font-bold flex items-center gap-2">
            <MessageSquareText className="text-emerald-400" size={18} />
            {t('captionsModal.title', 'Captions')}
            </h3>
            <button
              type="button"
              onClick={resetStyles}
              className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 hover:bg-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200"
            >
              {t('captionsModal.resetStyles', 'Reset styles')}
            </button>
          </div>

          <p className="mb-3 text-xs text-slate-400 dark:text-zinc-500">
            {t('captionsModal.clickLineHint', 'Click a line to edit.')}
          </p>

          {captionsLoading ? (
            <div className="flex items-center gap-2 text-sm text-slate-400 dark:text-zinc-500 py-4">
              <Loader2 size={14} className="animate-spin" />
              {t('captionsModal.loading', 'Loading captions...')}
            </div>
          ) : null}

          {fetchError ? (
            <div className="mb-3 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-300">{fetchError}</div>
          ) : null}

          {creditBlocked ? (
            <div className="mb-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
              {creditError || t('captionsModal.insufficientCredits', 'Insufficient credits to generate captions for this reel.')}
            </div>
          ) : null}

          {!captionsLoading && lines.length === 0 ? (
            <p className="text-xs text-slate-400 dark:text-zinc-500">{t('captionsModal.noCaptions', 'No captions available for this clip.')}</p>
          ) : null}

          <div className="space-y-3">
            {lines.map((line, lineIndex) => (
              <div
                key={line.id}
                onClick={() => handleLineFocus(line)}
                className={`rounded-xl border p-3 md:p-3.5 space-y-3 cursor-pointer transition ${selectedLineId === line.id ? 'border-emerald-400 bg-emerald-500/10' : 'border-slate-300 dark:border-white/10 bg-white/[0.06] hover:bg-white/[0.1]'}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] uppercase tracking-wider text-slate-400 dark:text-zinc-500">
                    {t('captionsModal.line', 'Line')} {lineIndex + 1}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        applyLineStyleToAll(line.id);
                      }}
                      className="inline-flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[11px] text-emerald-300 hover:bg-emerald-500/20"
                    >
                      {t('captionsModal.applyToAll', 'Apply style to all')}
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteLine(line.id);
                      }}
                      className="inline-flex items-center gap-1 text-[11px] text-red-300 hover:text-red-200"
                      title={t('captionsModal.deleteLine', 'Delete line')}
                    >
                      <Trash2 size={12} />
                      {t('captionsModal.delete', 'Delete')}
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-5 gap-2">
                  <label className="text-[11px] text-slate-400 dark:text-zinc-500">
                    {t('captionsModal.emoji', 'Emoji')}
                    <div className="mt-1 flex items-center gap-2">
                      <input
                        type="text"
                        value={line.emoji}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => appendEmojiToLine(line.id, e.target.value.slice(0, 3))}
                        className="w-full bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1 text-sm text-zinc-100"
                        placeholder="🔥"
                      />
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenEmojiLineId((prev) => (prev === line.id ? null : line.id));
                          setEmojiSearch('');
                        }}
                        className="shrink-0 rounded-md border border-slate-300 dark:border-white/10 bg-black/40 px-2 py-1 text-[11px] text-slate-200 hover:bg-black/60"
                      >
                        {t('captionsModal.pickEmoji', 'Pick')}
                      </button>
                    </div>
                  </label>
                  <label className="text-[11px] text-slate-400 dark:text-zinc-500">
                    {t('captionsModal.lineSize', 'Line size')} ({line.fontSize}px)
                    <input
                      type="range"
                      min="28"
                      max="96"
                      value={line.fontSize}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => updateLine(line.id, (prev) => ({ ...prev, fontSize: Number(e.target.value) || DEFAULT_LINE_FONT_SIZE }))}
                      className="mt-2 w-full accent-emerald-500"
                    />
                  </label>
                  <label className="text-[11px] text-slate-400 dark:text-zinc-500">
                    {t('captionsModal.lineFont', 'Line font')}
                    <select
                      value={line.fontFamily || 'Arial'}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => updateLine(line.id, (prev) => ({ ...prev, fontFamily: e.target.value }))}
                      className="mt-1 w-full bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1 text-xs text-zinc-100"
                    >
                      {[...new Set(FONT_OPTIONS.map((option) => option.category))].map((category) => (
                        <optgroup key={`${line.id}-${category}`} label={category}>
                          {FONT_OPTIONS.filter((option) => option.category === category).map((option) => (
                            <option key={`${line.id}-${option.value}`} value={option.value}>{option.label}</option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </label>
                  <label className="text-[11px] text-slate-400 dark:text-zinc-500">
                    {t('captionsModal.positionY', 'Vertical position')} ({line.positionY}%)
                    <input
                      type="range"
                      min="10"
                      max="95"
                      value={line.positionY}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => updateLine(line.id, (prev) => ({ ...prev, positionY: Number(e.target.value) || 82 }))}
                      className="mt-2 w-full accent-emerald-500"
                    />
                  </label>
                  <label className="text-[11px] text-slate-400 dark:text-zinc-500">
                    {t('captionsModal.positionX', 'Horizontal position')} ({line.positionX}%)
                    <input
                      type="range"
                      min="5"
                      max="95"
                      value={line.positionX}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => updateLine(line.id, (prev) => ({ ...prev, positionX: Number(e.target.value) || 50 }))}
                      className="mt-2 w-full accent-emerald-500"
                    />
                  </label>
                </div>

                {openEmojiLineId === line.id ? (
                  <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-black/50 p-2.5 space-y-2" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="text"
                      value={emojiSearch}
                      onChange={(e) => setEmojiSearch(e.target.value)}
                      placeholder={t('captionsModal.searchEmoji', 'Search emoji...')}
                      className="w-full bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1 text-xs text-zinc-100"
                    />
                    <div className="flex flex-wrap gap-1.5">
                      {Object.keys(EMOJI_CATEGORIES).map((categoryKey) => (
                        <button
                          key={`${line.id}-${categoryKey}`}
                          type="button"
                          onClick={() => setEmojiCategory(categoryKey)}
                          className={`rounded-md border px-2 py-1 text-[10px] uppercase tracking-wide ${emojiCategory === categoryKey ? 'border-emerald-400 bg-emerald-500/15 text-emerald-200' : 'border-slate-300 dark:border-white/10 bg-black/30 text-slate-300'}`}
                        >
                          {t(`captionsModal.emojiCategory.${categoryKey}`, categoryKey)}
                        </button>
                      ))}
                    </div>
                    <div className="grid grid-cols-8 gap-1.5 max-h-32 overflow-y-auto custom-scrollbar pr-1">
                      {(filteredEmojis.length > 0 ? filteredEmojis : EMOJI_SUGGESTIONS).map((emoji) => (
                        <button
                          key={`${line.id}-picker-${emoji}`}
                          type="button"
                          onClick={() => {
                            appendEmojiToLine(line.id, emoji);
                            setOpenEmojiLineId(null);
                          }}
                          className="h-7 rounded-md border border-slate-300 dark:border-white/10 bg-black/30 hover:bg-black/60 text-sm"
                          title={emoji}
                        >
                          {emoji}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}


                <div className="flex flex-wrap items-center gap-1.5">
                  {EMOJI_SUGGESTIONS.map((emoji) => (
                    <button
                      key={`${line.id}-${emoji}`}
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        appendEmojiToLine(line.id, emoji);
                      }}
                      className="h-7 w-7 rounded-md border border-slate-300 dark:border-white/10 bg-black/30 hover:bg-black/60 text-sm"
                      title={`${t('captionsModal.addEmoji', 'Add emoji')} ${emoji}`}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>

                <div className="flex flex-wrap gap-2">
                  {line.words.map((word) => {
                    const isSelected = selectedWordRef?.wordId === word.id && selectedWordRef?.lineId === line.id;
                    return (
                      <button
                        key={word.id}
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedWordRef({ lineId: line.id, wordId: word.id });
                          setSelectedLineId(line.id);
                          previewRef.current?.seekToMs?.(word.startMs || line.startMs || 0);
                        }}
                        className={`rounded-md border px-2 py-1 text-xs transition ${isSelected ? 'border-emerald-400 bg-emerald-500/20 text-white' : 'border-slate-300 dark:border-white/10 bg-black/30 text-slate-200 hover:bg-black/50'}`}
                        style={{ color: word.color || '#FFFFFF' }}
                      >
                        {word.text}
                      </button>
                    );
                  })}
                </div>

                <div className="space-y-1.5">
                  <p className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-zinc-500">
                    {t('captionsModal.inlineWordColor', 'Word color in line')}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {COLOR_PRESETS.map((preset) => (
                      <button
                        key={`${line.id}-inline-color-${preset.color}`}
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          applyColorToLineWord(line.id, preset.color);
                        }}
                        className="w-6 h-6 rounded-full border-2 border-slate-400 dark:border-white/20 hover:scale-105"
                        style={{ backgroundColor: preset.color }}
                        title={preset.label}
                      />
                    ))}
                    <label
                      className="w-6 h-6 rounded-full border-2 border-dashed border-slate-400 dark:border-white/20 cursor-pointer relative overflow-hidden"
                      onClick={(e) => e.stopPropagation()}
                      title={t('captionsModal.wordColor', 'Word color')}
                    >
                      <input
                        type="color"
                        value={selectedWordRef?.lineId === line.id ? (selectedWord?.color || '#FFFFFF') : '#FFFFFF'}
                        onChange={(e) => applyColorToLineWord(line.id, e.target.value)}
                        className="absolute inset-0 opacity-0 cursor-pointer"
                      />
                    </label>
                  </div>
                  <p className="text-[10px] text-slate-500 dark:text-zinc-500">
                    {selectedWordRef?.lineId === line.id
                      ? t('captionsModal.inlineWordColorHintActive', 'Color applies to the selected word in this line.')
                      : t('captionsModal.inlineWordColorHint', 'Select a word in this line, or the first word will be used.')}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {selectedWord ? (
            <div className="mt-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 space-y-2">
              <p className="text-[11px] uppercase tracking-wider text-emerald-300">{t('captionsModal.selectedWord', 'Selected word')}</p>
              <input
                type="text"
                value={selectedWord.text}
                onChange={(e) => updateWord(selectedWordRef.lineId, selectedWordRef.wordId, (prev) => ({ ...prev, text: e.target.value }))}
                className="w-full bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1 text-sm text-zinc-100"
              />
              <label className="text-[11px] text-slate-300 inline-flex items-center gap-2">
                {t('captionsModal.wordColor', 'Word color')}
                <input
                  type="color"
                  value={selectedWord.color || '#FFFFFF'}
                  onChange={(e) => updateWord(selectedWordRef.lineId, selectedWordRef.wordId, (prev) => ({ ...prev, color: e.target.value }))}
                  className="h-7 w-10 rounded border border-slate-300 dark:border-white/10 bg-transparent"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                {COLOR_PRESETS.map((preset) => (
                  <button
                    key={`word-color-${preset.color}`}
                    type="button"
                    onClick={() => updateWord(selectedWordRef.lineId, selectedWordRef.wordId, (prev) => ({ ...prev, color: preset.color }))}
                    className={`h-6 w-6 rounded-full border-2 ${selectedWord?.color === preset.color ? 'border-white scale-110' : 'border-slate-400 dark:border-white/20'}`}
                    style={{ backgroundColor: preset.color }}
                    title={preset.label}
                  />
                ))}
              </div>
            </div>
          ) : null}

          <div className="mt-4 space-y-2">
            <label className="text-xs font-semibold text-slate-400 dark:text-zinc-500 block">{t('captionsModal.fontFamily', 'Font family')}</label>
            <select
              value={fontFamily}
              onChange={(e) => setFontFamily(e.target.value)}
              className="w-full bg-black/40 border border-slate-300 dark:border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-100"
            >
              {[...new Set(FONT_OPTIONS.map((option) => option.category))].map((category) => (
                <optgroup key={category} label={category}>
                  {FONT_OPTIONS.filter((option) => option.category === category).map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </optgroup>
              ))}
            </select>

            <label className="text-xs font-semibold text-slate-400 dark:text-zinc-500 block">{t('captionsModal.animation', 'Animation')}</label>
            <div className="grid grid-cols-2 gap-2">
              {ANIMATION_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setAnimation(option.value)}
                  className={`rounded-md border px-2 py-1.5 text-[11px] text-left ${animation === option.value ? 'border-emerald-400 bg-emerald-500/15 text-emerald-200' : 'border-slate-300 dark:border-white/10 bg-black/30 text-slate-300'}`}
                >
                  {option.label}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setBold((v) => !v)}
                className={`rounded-md border px-2 py-1.5 text-xs font-semibold ${bold ? 'border-emerald-400 bg-emerald-500/15 text-emerald-200' : 'border-slate-300 dark:border-white/10 bg-black/30 text-slate-300'}`}
              >
                {t('captionsModal.bold', 'Bold')}
              </button>
              <button
                type="button"
                onClick={() => setItalic((v) => !v)}
                className={`rounded-md border px-2 py-1.5 text-xs font-semibold ${italic ? 'border-emerald-400 bg-emerald-500/15 text-emerald-200' : 'border-slate-300 dark:border-white/10 bg-black/30 text-slate-300'}`}
              >
                {t('captionsModal.italic', 'Italic')}
              </button>
            </div>

            <label className="text-xs font-semibold text-slate-400 dark:text-zinc-500 block">{t('captionsModal.highlightColor', 'Active color')}</label>
            <div className="flex flex-wrap gap-2">
              {COLOR_PRESETS.map((preset) => (
                <button
                  key={preset.color}
                  type="button"
                  onClick={() => setHighlightColor(preset.color)}
                  className={`w-6 h-6 rounded-full border-2 ${highlightColor === preset.color ? 'border-white scale-110' : 'border-slate-400 dark:border-white/20'}`}
                  style={{ backgroundColor: preset.color }}
                  title={preset.label}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="w-full md:w-[50%] rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 p-4 md:p-5 flex flex-col gap-3">
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
            {isProcessing
              ? t('captionsModal.generating', 'Generating...')
              : t('captionsModal.generate', 'Generate captions')}
          </button>
        </div>
      </div>
    </div>
  );
}


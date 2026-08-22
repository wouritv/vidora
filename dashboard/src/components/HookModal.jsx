import React, { useState } from 'react';
import { X, Sparkles, Loader2, Maximize, MoveVertical, Zap } from 'lucide-react';
import RemotionPreview from './RemotionPreview';
import { useTranslation } from '../state/LanguageContext';

const ENTRANCE_OPTIONS = [
    { value: 'spring', label: 'Bounce' },
    { value: 'fade', label: 'Fade' },
    { value: 'slide-up', label: 'Slide Up' },
    { value: 'none', label: 'None' },
];

export default function HookModal({ isOpen, onClose, onGenerate, isProcessing, videoUrl, initialText, durationInSeconds, existingSubtitles }) {
    const { t } = useTranslation();
    const [text, setText] = useState(initialText || t('hookModal.defaultText', 'POV: You are using the viral hook feature'));
    const [position, setPosition] = useState('top');
    const [size, setSize] = useState('M');
    const [entranceAnimation, setEntranceAnimation] = useState('spring');
    const [displayDuration, setDisplayDuration] = useState(5);

    if (!isOpen) return null;

    // Build hook config for Remotion preview
    const hookConfig = {
        text: text || t('hookModal.textPlaceholder', 'Enter text that will stop the scroll...'),
        position,
        size,
        entranceAnimation,
        displayDurationSec: displayDuration,
    };

    const useRemotionPreview = !!videoUrl;

    // Fallback preview logic (same as original)
    const getPositionClass = () => {
        switch (position) {
            case 'center': return 'items-center justify-center';
            case 'bottom': return 'items-center justify-end pb-[20%]';
            case 'top': default: return 'items-center justify-start pt-[20%]';
        }
    };

    const getSizeStyle = () => {
        switch (size) {
            case 'S': return { fontSize: '14px', maxWidth: '80%' };
            case 'L': return { fontSize: '24px', maxWidth: '95%' };
            case 'M': default: return { fontSize: '18px', maxWidth: '90%' };
        }
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
            <div className="bg-[#121214] border border-slate-300 dark:border-white/10 p-6 rounded-2xl w-full max-w-4xl shadow-2xl relative flex flex-col md:flex-row gap-6 max-h-[90vh]">
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 text-slate-400 dark:text-zinc-500 hover:text-white z-10"
                >
                    <X size={20} />
                </button>

                {/* Left: Preview */}
                <div className="flex-1 flex flex-col items-center justify-center bg-black rounded-lg border border-slate-200 dark:border-white/5 overflow-hidden relative aspect-[9/16] max-h-[600px]">
                    {useRemotionPreview ? (
                        <RemotionPreview
                            videoUrl={videoUrl}
                            durationInSeconds={durationInSeconds || 30}
                            hook={hookConfig}
                            subtitles={existingSubtitles || null}
                        />
                    ) : (
                        <>
                            <video src={videoUrl} className="w-full h-full object-contain opacity-50" muted playsInline />
                            <div className={`absolute w-full px-8 text-center transition-all duration-300 pointer-events-none flex flex-col h-full ${getPositionClass()}`}>
                                <div
                                    className="text-black font-bold px-3 py-2 rounded-xl shadow-2xl text-center whitespace-pre-wrap transition-all duration-200"
                                    style={{
                                        ...getSizeStyle(),
                                        backgroundColor: 'rgba(255, 255, 255, 0.82)',
                                        fontFamily: 'Noto Serif, serif',
                                        boxShadow: '0 4px 15px rgba(0,0,0,0.5)',
                                        paddingTop: '10px',
                                        paddingBottom: '10px',
                                        paddingLeft: '12px',
                                        paddingRight: '12px'
                                    }}
                                >
                                    {text || t('hookModal.textPlaceholder', 'Enter text that will stop the scroll...')}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                {/* Right: Controls */}
                <div className="w-full md:w-80 flex flex-col">
                    <h3 className="title-contrast text-xl font-bold mb-6 flex items-center gap-2">
                        <Sparkles className="text-yellow-400" /> {t('hookModal.title', 'Viral Hook')}
                    </h3>

                    <div className="space-y-6 flex-1 overflow-y-auto custom-scrollbar pr-2">
                        {/* Text Input */}
                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-3 block">{t('hookModal.text', 'Text')}</label>
                            <textarea
                                value={text}
                                onChange={(e) => setText(e.target.value)}
                                rows={4}
                                className="w-full bg-black/40 border border-slate-300 dark:border-white/10 rounded-xl p-3 text-white placeholder-zinc-600 focus:outline-none focus:border-yellow-500/50 resize-none font-serif"
                                placeholder={t('hookModal.textPlaceholder', 'Enter text that will stop the scroll...')}
                            />
                        </div>

                        {/* Position Control */}
                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                <MoveVertical size={12} /> Position
                            </label>
                            <div className="grid grid-cols-3 gap-2">
                                {['top', 'center', 'bottom'].map((pos) => (
                                    <button
                                        key={pos}
                                        onClick={() => setPosition(pos)}
                                        className={`py-2 px-1 rounded-lg text-xs font-bold capitalize transition-all border ${position === pos
                                            ? 'bg-white text-black border-white'
                                            : 'bg-white/5 text-slate-500 dark:text-zinc-400 border-slate-200 dark:border-white/5 hover:bg-white/10'
                                            }`}
                                    >
                                        {t(`hookModal.position.${pos}`, pos)}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Size Control */}
                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                <Maximize size={12} /> Size
                            </label>
                            <div className="grid grid-cols-3 gap-2">
                                {['S', 'M', 'L'].map((sz) => (
                                    <button
                                        key={sz}
                                        onClick={() => setSize(sz)}
                                        className={`py-2 px-1 rounded-lg text-xs font-bold transition-all border ${size === sz
                                            ? 'bg-white text-black border-white'
                                            : 'bg-white/5 text-slate-500 dark:text-zinc-400 border-slate-200 dark:border-white/5 hover:bg-white/10'
                                            }`}
                                    >
                                        {sz === 'S' ? t('hookModal.size.small', 'Small') : sz === 'M' ? t('hookModal.size.medium', 'Medium') : t('hookModal.size.large', 'Large')}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Entrance Animation (new) */}
                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                <Zap size={12} /> Entrance
                            </label>
                            <div className="grid grid-cols-2 gap-2">
                                {ENTRANCE_OPTIONS.map((opt) => (
                                    <button
                                        key={opt.value}
                                        onClick={() => setEntranceAnimation(opt.value)}
                                        className={`py-2 px-1 rounded-lg text-xs font-bold transition-all border ${entranceAnimation === opt.value
                                            ? 'bg-white text-black border-white'
                                            : 'bg-white/5 text-slate-500 dark:text-zinc-400 border-slate-200 dark:border-white/5 hover:bg-white/10'
                                            }`}
                                    >
                                        {opt.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Display Duration (new) */}
                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 block">{t('hookModal.duration', 'Duration')}: {displayDuration}s</label>
                            <input
                                type="range"
                                min="2"
                                max="15"
                                value={displayDuration}
                                onChange={(e) => setDisplayDuration(parseInt(e.target.value))}
                                className="w-full accent-yellow-500"
                            />
                            <div className="flex justify-between text-[10px] text-slate-400 dark:text-zinc-500">
                                <span>2s</span>
                                <span>15s</span>
                            </div>
                        </div>

                        <div className="p-3 bg-white/5 rounded-lg border border-slate-200 dark:border-white/5 text-[11px] text-slate-500 dark:text-zinc-400">
                            <strong>{t('hookModal.tip', 'Tip')}:</strong> {t('hookModal.tipText', 'Keep it short and punchy. Using "POV:" or specific questions works best for retention.')}
                        </div>
                    </div>

                    <button
                        onClick={() => onGenerate({
                            text, position, size,
                            // Remotion data
                            remotion: hookConfig,
                        })}
                        disabled={isProcessing || !text.trim()}
                        className="w-full py-4 mt-4 bg-gradient-to-r from-yellow-500 to-amber-600 hover:from-yellow-400 hover:to-amber-500 text-black font-bold rounded-xl shadow-lg shadow-amber-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
                    >
                        {isProcessing ? <Loader2 size={20} className="animate-spin" /> : <Sparkles size={20} />}
                        {isProcessing ? t('hookModal.generating', 'Generating...') : t('hookModal.addHook', 'Add Hook')}
                    </button>
                </div>
            </div>
        </div>
    );
}

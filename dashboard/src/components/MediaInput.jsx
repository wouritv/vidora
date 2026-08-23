import React, { useState, useEffect } from 'react';
import { Youtube, Upload, FileVideo, X } from 'lucide-react';
import { getApiUrl } from '../config';
import { useTranslation } from '../state/LanguageContext';

export default function MediaInput({
    onProcess,
    isProcessing,
    isCreditBlocked = false,
    disableActions = false,
    creditWarning = "",
    localOnly = false,
    submitLabel = "",
    processingLabel = "",
}) {
    const { t } = useTranslation();
    const [youtubeUrlEnabled, setYoutubeUrlEnabled] = useState(true);
    const [mode, setMode] = useState(localOnly ? 'file' : 'url'); // 'url' | 'file'
    const [url, setUrl] = useState('');
    const [file, setFile] = useState(null);
    const [acknowledged, setAcknowledged] = useState(false);

    useEffect(() => {
        fetch(getApiUrl('/api/config'))
            .then((r) => r.ok ? r.json() : null)
            .then((cfg) => {
                if (cfg && cfg.youtubeUrlEnabled === false) {
                    setYoutubeUrlEnabled(false);
                    setMode('file');
                }
            })
            .catch(() => {});
    }, []);

    useEffect(() => {
        if (localOnly) {
            setMode('file');
        }
    }, [localOnly]);

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!acknowledged) return;
        if (mode === 'url' && url) {
            onProcess({ type: 'url', payload: url, acknowledged: true });
        } else if (mode === 'file' && file) {
            onProcess({ type: 'file', payload: file, acknowledged: true });
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            setFile(e.dataTransfer.files[0]);
            setMode('file');
        }
    };

    return (
        <div className="bg-surface border border-slate-200 dark:border-white/5 rounded-2xl p-6 animate-[fadeIn_0.6s_ease-out]">
            <div className="flex gap-4 mb-6 border-b border-slate-200 dark:border-white/5 pb-4">
                {youtubeUrlEnabled && !localOnly && (
                    <button
                        type="button"
                        onClick={() => setMode('url')}
                        disabled={disableActions}
                        className={`flex items-center gap-2 pb-2 px-2 transition-all ${mode === 'url'
                            ? 'text-primary border-b-2 border-primary -mb-[17px]'
                            : 'text-slate-500 dark:text-zinc-400 hover:text-white'
                            } disabled:opacity-40 disabled:cursor-not-allowed`}
                    >
                        <Youtube size={18} />
                        {t('mediaInput.youtubeUrl', 'YouTube URL')}
                    </button>
                )}
                <button
                    type="button"
                    onClick={() => setMode('file')}
                    disabled={disableActions}
                    className={`flex items-center gap-2 pb-2 px-2 transition-all ${(mode === 'file' || localOnly)
                        ? 'text-primary border-b-2 border-primary -mb-[17px]'
                        : 'text-slate-500 dark:text-zinc-400 hover:text-white'
                        } disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                    <Upload size={18} />
                    {t('mediaInput.uploadFile', 'Upload File')}
                </button>
            </div>

            <form onSubmit={handleSubmit}>
                {mode === 'url' && !localOnly ? (
                    <div className="space-y-4">
                        <input
                            type="url"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            placeholder="https://www.youtube.com/watch?v=..."
                            className="input-field"
                            required
                        />
                    </div>
                ) : (
                    <div
                        className={`border-2 border-dashed rounded-xl p-8 text-center transition-all ${file ? 'border-primary/50 bg-primary/5' : 'border-zinc-700 hover:border-zinc-500 bg-white/5'
                            } ${disableActions ? 'opacity-60 pointer-events-none' : ''}`}
                        onDragOver={(e) => {
                            if (disableActions) return;
                            e.preventDefault();
                        }}
                        onDrop={(e) => {
                            if (disableActions) return;
                            handleDrop(e);
                        }}
                    >
                        {file ? (
                            <div className="flex items-center justify-center gap-3 text-white">
                                <FileVideo className="text-primary" />
                                <span className="font-medium">{file.name}</span>
                                <button
                                    type="button"
                                    onClick={() => setFile(null)}
                                    disabled={disableActions}
                                    className="p-1 hover:bg-white/10 rounded-full"
                                >
                                    <X size={16} />
                                </button>
                            </div>
                        ) : (
                            <label className="cursor-pointer block">
                                <input
                                    type="file"
                                    accept="video/*"
                                    disabled={disableActions}
                                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                                    className="hidden"
                                />
                                <Upload className="mx-auto mb-3 text-slate-400 dark:text-zinc-500" size={24} />
                                <p className="text-slate-500 dark:text-zinc-400">{t('mediaInput.uploadHint', 'Click to upload or drag and drop')}</p>
                                <p className="text-xs text-zinc-600 mt-1">{t('mediaInput.uploadDetail', 'MP4, MOV, AVI')}</p>
                            </label>
                        )}
                    </div>
                )}

                {creditWarning ? (
                    <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                        {creditWarning}
                    </div>
                ) : null}

                <label className="flex items-start gap-2 mt-5 text-xs text-slate-500 dark:text-zinc-400 cursor-pointer select-none">
                    <input
                        type="checkbox"
                        checked={acknowledged}
                        disabled={disableActions}
                        onChange={(e) => setAcknowledged(e.target.checked)}
                        className="mt-0.5 accent-primary cursor-pointer"
                    />
                    <span>
                        {t('mediaInput.ack', 'I confirm I own this content or have the rights to process it. I am responsible for any content I submit. See our')} <a href="http://wouri-academy.com/wp-content/uploads/2026/08/politique_confidentialite.pdf" target="_blank" rel="noopener noreferrer" className="text-primary underline" onClick={(e) => e.stopPropagation()}>{t('mediaInput.terms', 'Terms & Privacy')}</a>.
                    </span>
                </label>

                <button
                    type="submit"
                    disabled={disableActions || isProcessing || isCreditBlocked || !acknowledged || ((mode === 'url' && !localOnly) && !url) || (mode === 'file' && !file)}
                    className="w-full btn-primary mt-4 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {isProcessing ? (
                        <>
                            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            {processingLabel || t('mediaInput.processing', 'Processing Video...')}
                        </>
                    ) : isCreditBlocked ? (
                        <>{t('mediaInput.insufficientCredits', 'Insufficient credits')}</>
                    ) : (
                        <>{submitLabel || t('mediaInput.generateClips', 'Generate Clips')}</>
                    )}
                </button>
            </form>
        </div>
    );
}

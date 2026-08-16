import React from 'react';
import { X, Loader2, Share2, Calendar, Clock, Instagram, Youtube, Video, Facebook, Linkedin, CheckCircle, AlertCircle } from 'lucide-react';
import { SUPPORTED_SOCIAL_PLATFORMS, PLATFORM_LABELS } from '../lib/platforms';

export default function SharePostModal({
    isOpen,
    onClose,
    title,
    onTitleChange,
    description,
    onDescriptionChange,
    isScheduling,
    onSchedulingChange,
    scheduleDate,
    onScheduleDateChange,
    platforms,
    onPlatformChange,
    connectedPlatforms,
    isSubmitting,
    result,
    onSubmit,
}) {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
            <div className="bg-[#121214] border border-slate-300 dark:border-white/10 p-6 rounded-2xl w-full max-w-md shadow-2xl relative max-h-[90vh] overflow-y-auto custom-scrollbar">
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 text-slate-400 dark:text-zinc-500 hover:text-white"
                >
                    <X size={20} />
                </button>

                <h3 className="title-contrast text-lg font-bold mb-4">Post / Schedule</h3>


                <div className="space-y-4 mb-6">
                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-1">Video Title</label>
                        <input
                            type="text"
                            value={title}
                            onChange={(e) => onTitleChange(e.target.value)}
                            className="w-full bg-black/40 border border-slate-300 dark:border-white/10 rounded-lg p-2 text-sm text-white focus:outline-none focus:border-primary/50 placeholder-zinc-600"
                            placeholder="Enter a catchy title..."
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-1">Caption / Description</label>
                        <textarea
                            value={description}
                            onChange={(e) => onDescriptionChange(e.target.value)}
                            rows={4}
                            className="w-full bg-black/40 border border-slate-300 dark:border-white/10 rounded-lg p-2 text-sm text-white focus:outline-none focus:border-primary/50 placeholder-zinc-600 resize-none"
                            placeholder="Write a caption for your post..."
                        />
                    </div>

                    <div className="p-3 bg-white/5 rounded-lg border border-slate-200 dark:border-white/5">
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2 text-sm text-white font-medium">
                                <Calendar size={16} className="text-purple-400" /> Schedule Post
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" checked={isScheduling} onChange={(e) => onSchedulingChange(e.target.checked)} className="sr-only peer" />
                                <div className="w-9 h-5 bg-zinc-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
                            </label>
                        </div>

                        {isScheduling ? (
                            <div className="mt-3 animate-[fadeIn_0.2s_ease-out]">
                                <label className="block text-xs text-slate-500 dark:text-zinc-400 mb-1">Select Date & Time</label>
                                <div className="relative">
                                    <input
                                        type="datetime-local"
                                        value={scheduleDate}
                                        onChange={(e) => onScheduleDateChange(e.target.value)}
                                        className="w-full bg-black/40 border border-slate-300 dark:border-white/10 rounded-lg p-2 pl-9 text-sm text-white focus:outline-none focus:border-purple-500/50 [color-scheme:dark]"
                                    />
                                    <Clock size={14} className="absolute left-3 top-2.5 text-slate-400 dark:text-zinc-500" />
                                </div>
                            </div>
                        ) : null}
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-2">Select Platforms</label>
                        <div className="grid grid-cols-1 gap-2">
                            {SUPPORTED_SOCIAL_PLATFORMS
                                .filter((platform) => connectedPlatforms.length === 0 || connectedPlatforms.includes(platform))
                                .map((platform) => {
                                    const Icon = platform === 'instagram' ? Instagram
                                        : platform === 'youtube' ? Youtube
                                            : platform === 'facebook' ? Facebook
                                                : platform === 'linkedin' ? Linkedin
                                                    : Video;
                                    return (
                                        <label key={platform} className="flex items-center gap-3 p-3 bg-white/5 rounded-lg cursor-pointer hover:bg-white/10 transition-colors border border-slate-200 dark:border-white/5">
                                            <input
                                                type="checkbox"
                                                checked={Boolean(platforms[platform])}
                                                onChange={(e) => onPlatformChange(platform, e.target.checked)}
                                                className="w-4 h-4 rounded border-zinc-600 bg-black/50 text-primary focus:ring-primary"
                                            />
                                            <div className="flex items-center gap-2 text-sm text-white">
                                                <Icon size={16} className="text-slate-700 dark:text-zinc-300" /> {PLATFORM_LABELS[platform]}
                                            </div>
                                        </label>
                                    );
                                })}
                        </div>
                        {connectedPlatforms.length === 0 ? (
                            <p className="mt-2 text-xs text-slate-400 dark:text-zinc-500">No platform is marked as connected in Settings, so defaults are shown.</p>
                        ) : null}
                    </div>
                </div>

                {result ? (
                    <div className={`mb-4 p-3 rounded-lg text-xs flex items-start gap-2 ${result.success ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                        {result.success ? <CheckCircle size={14} className="mt-0.5 shrink-0" /> : <AlertCircle size={14} className="mt-0.5 shrink-0" />}
                        <div>{result.msg}</div>
                    </div>
                ) : null}

                <button
                    onClick={onSubmit}
                    disabled={isSubmitting}
                    className="w-full py-3 bg-primary hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-white font-bold transition-all flex items-center justify-center gap-2"
                >
                    {isSubmitting ? (
                        <>
                            <Loader2 size={16} className="animate-spin" />
                            {isScheduling ? 'Scheduling...' : 'Publishing...'}
                        </>
                    ) : (
                        <>
                            <Share2 size={16} />
                            {isScheduling ? 'Schedule Post' : 'Publish Now'}
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}


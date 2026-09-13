import React from 'react';
import { X, Loader2, Share2, Calendar, Clock, Facebook, Linkedin, CheckCircle, AlertCircle, Check } from 'lucide-react';
import { useTranslation } from "../state/LanguageContext";

// Anonymous stories only publish to Facebook/LinkedIn (per the feature
// request), unlike SharePostModal's full tiktok/instagram/youtube/facebook/
// linkedin list for reels and captions.
const PUBLISH_PLATFORMS = ['facebook', 'linkedin'];
const PLATFORM_ICONS = { facebook: Facebook, linkedin: Linkedin };
const PLATFORM_LABELS = { facebook: 'Facebook', linkedin: 'LinkedIn' };

export default function AnonymousStoryPublishModal({
    isOpen,
    onClose,
    backgrounds,
    backgroundId,
    onBackgroundChange,
    isScheduling,
    onSchedulingChange,
    scheduleDate,
    onScheduleDateChange,
    platforms,
    onPlatformChange,
    isSubmitting,
    result,
    onSubmit,
}) {
    const { t } = useTranslation();

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
            <div className="bg-white dark:bg-[#121214] border border-slate-300 dark:border-white/10 p-6 rounded-2xl w-full max-w-md shadow-2xl relative max-h-[90vh] overflow-y-auto custom-scrollbar">
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 text-slate-400 dark:text-zinc-500 hover:text-slate-700 dark:hover:text-white"
                >
                    <X size={20} />
                </button>

                <h3 className="title-contrast text-lg font-bold mb-4">{t("anonymousStories.publishModalTitle", "Publier l'histoire")}</h3>

                <div className="space-y-4 mb-6">
                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-2">
                            {t("anonymousStories.publishSelectPlatformLabel", "Choisir les plateformes")}
                        </label>
                        <div className="grid grid-cols-1 gap-2">
                            {PUBLISH_PLATFORMS.map((platform) => {
                                const Icon = PLATFORM_ICONS[platform];
                                return (
                                    <label
                                        key={platform}
                                        className="flex items-center gap-3 p-3 bg-slate-100 dark:bg-white/5 rounded-lg cursor-pointer hover:bg-slate-200 dark:hover:bg-white/10 transition-colors border border-slate-200 dark:border-white/5"
                                    >
                                        <input
                                            type="checkbox"
                                            checked={Boolean(platforms[platform])}
                                            onChange={(e) => onPlatformChange(platform, e.target.checked)}
                                            className="w-4 h-4 rounded border-zinc-600 bg-black/50 text-primary focus:ring-primary"
                                        />
                                        <div className="flex items-center gap-2 text-sm text-slate-800 dark:text-white">
                                            <Icon size={16} className="text-slate-700 dark:text-zinc-300" /> {t(`social.${platform}`, PLATFORM_LABELS[platform])}
                                        </div>
                                    </label>
                                );
                            })}
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-2">
                            {t("anonymousStories.publishBackgroundLabel", "Arriere-plan de la publication")}
                        </label>
                        <div className="grid grid-cols-3 gap-2">
                            {(backgrounds || []).map((preset) => {
                                const isSelected = backgroundId === preset.id;
                                const colors = preset.colors && preset.colors.length ? preset.colors : ['#0f2027'];
                                const gradientColors = colors.length > 1 ? colors : [colors[0], colors[0]];
                                return (
                                    <button
                                        key={preset.id}
                                        type="button"
                                        onClick={() => onBackgroundChange(preset.id)}
                                        title={preset.name}
                                        className={`relative h-14 rounded-lg border-2 transition ${isSelected ? 'border-primary' : 'border-transparent'}`}
                                        style={{ background: `linear-gradient(135deg, ${gradientColors.join(', ')})` }}
                                    >
                                        {isSelected ? (
                                            <span className="absolute inset-0 flex items-center justify-center">
                                                <Check size={18} className="text-white drop-shadow" />
                                            </span>
                                        ) : null}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    <div className="p-3 bg-slate-100 dark:bg-white/5 rounded-lg border border-slate-200 dark:border-white/5">
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2 text-sm text-slate-800 dark:text-white font-medium">
                                <Calendar size={16} className="text-purple-400" /> {t("social.postSchedule", "Schedule Post")}
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" checked={isScheduling} onChange={(e) => onSchedulingChange(e.target.checked)} className="sr-only peer" />
                                <div className="w-9 h-5 bg-zinc-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
                            </label>
                        </div>

                        {isScheduling ? (
                            <div className="mt-3 animate-[fadeIn_0.2s_ease-out]">
                                <label className="block text-xs text-slate-500 dark:text-zinc-400 mb-1">{t("social.postSchedulePlaceholder", "Select Date & Time")}</label>
                                <div className="relative">
                                    <input
                                        type="datetime-local"
                                        value={scheduleDate}
                                        onChange={(e) => onScheduleDateChange(e.target.value)}
                                        className="w-full bg-slate-50 dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-lg p-2 pl-9 text-sm text-slate-900 dark:text-white focus:outline-none focus:border-purple-500/50 [color-scheme:light] dark:[color-scheme:dark]"
                                    />
                                    <Clock size={14} className="absolute left-3 top-2.5 text-slate-400 dark:text-zinc-500" />
                                </div>
                            </div>
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
                    className="w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold shadow-lg shadow-blue-500/20 transition-all hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                    {isSubmitting ? (
                        <>
                            <Loader2 size={16} className="animate-spin" />
                            {isScheduling ? t("social.postScheduling", "Scheduling...") : t("social.postPublishing", "Publishing...")}
                        </>
                    ) : (
                        <>
                            <Share2 size={16} />
                            {isScheduling ? t("social.postScheduleButton", "Schedule Post") : t("social.postPublishButton", "Publish Now")}
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}

import React from 'react';
import { X, Loader2, Share2, Calendar, Clock, Facebook, Linkedin, CheckCircle, AlertCircle, Check, Ban } from 'lucide-react';
import { useTranslation } from "../state/LanguageContext";

const NO_BACKGROUND_ID = 'none';

// Anonymous stories only publish to Facebook/LinkedIn (per the feature
// request), unlike SharePostModal's full tiktok/instagram/youtube/facebook/
// linkedin list for reels and captions.
const PUBLISH_PLATFORMS = ['facebook', 'linkedin'];
const PLATFORM_ICONS = { facebook: Facebook, linkedin: Linkedin };
const PLATFORM_LABELS = { facebook: 'Facebook', linkedin: 'LinkedIn' };

// Facebook's own text-background posts show only the first ~130 characters
// inline behind a "See more" expander (confirmed against a live Publer
// test -- see app.py's publish_to_facebook_text_with_background); mirroring
// that here keeps the preview honest about what a long story will actually
// look like once published, instead of implying the full text is visible.
const PREVIEW_TEXT_LIMIT = 130;

function buildPreviewSnippet(text, seeMoreLabel) {
    const trimmed = (text || '').trim();
    if (trimmed.length <= PREVIEW_TEXT_LIMIT) return trimmed;
    return `${trimmed.slice(0, PREVIEW_TEXT_LIMIT).trimEnd()}… ${seeMoreLabel}`;
}

function backgroundGradient(preset) {
    const colors = preset?.colors && preset.colors.length ? preset.colors : ['#0f2027'];
    const gradientColors = colors.length > 1 ? colors : [colors[0], colors[0]];
    return `linear-gradient(135deg, ${gradientColors.join(', ')})`;
}

export default function AnonymousStoryPublishModal({
    isOpen,
    onClose,
    backgrounds,
    backgroundId,
    onBackgroundChange,
    previewText,
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

    const selectedPreset = (backgrounds || []).find((preset) => preset.id === backgroundId);
    const hasBackground = Boolean(selectedPreset) && selectedPreset.id !== NO_BACKGROUND_ID;
    const previewSnippet = buildPreviewSnippet(previewText, t("anonymousStories.publishPreviewSeeMore", "Voir plus"));

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
                        <p className="mb-2 text-[11px] text-slate-500 dark:text-zinc-400">
                            {t(
                                "anonymousStories.publishBackgroundFacebookOnly",
                                "Facebook uniquement : LinkedIn ne prend pas en charge ces arriere-plans et publie toujours en texte seul."
                            )}
                        </p>
                        {/* Small, fixed-size (60x60) swatches so the full 77-preset
                            catalog fits many per row -- a bounded, internally
                            scrolling grid keeps the whole modal from growing
                            instead of scrolling here. */}
                        <div className="flex flex-wrap gap-2 max-h-[220px] overflow-y-auto pr-1 custom-scrollbar">
                            {(backgrounds || []).map((preset) => {
                                const isSelected = backgroundId === preset.id;
                                const isNoBackground = preset.id === NO_BACKGROUND_ID;

                                if (isNoBackground) {
                                    return (
                                        <button
                                            key={preset.id}
                                            type="button"
                                            onClick={() => onBackgroundChange(preset.id)}
                                            title={t("anonymousStories.publishBackgroundNone", "No background (text only)")}
                                            className={`relative w-[60px] h-[60px] shrink-0 rounded-lg border-2 border-dashed flex flex-col items-center justify-center gap-0.5 text-[9px] font-medium transition ${isSelected ? 'border-primary text-primary' : 'border-slate-300 dark:border-white/20 text-slate-500 dark:text-zinc-400'}`}
                                        >
                                            <Ban size={14} />
                                            {t("anonymousStories.publishBackgroundNoneShort", "None")}
                                        </button>
                                    );
                                }

                                return (
                                    <button
                                        key={preset.id}
                                        type="button"
                                        onClick={() => onBackgroundChange(preset.id)}
                                        title={preset.name}
                                        className={`relative w-[60px] h-[60px] shrink-0 rounded-lg border-2 transition ${isSelected ? 'border-primary' : 'border-transparent'}`}
                                        style={{ background: backgroundGradient(preset) }}
                                    >
                                        {isSelected ? (
                                            <span className="absolute inset-0 flex items-center justify-center">
                                                <Check size={16} className="text-white drop-shadow" />
                                            </span>
                                        ) : null}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-2">
                            {t("anonymousStories.publishPreviewLabel", "Apercu de la publication")}
                        </label>
                        <div
                            className={`min-h-[140px] rounded-xl p-4 flex items-center justify-center text-center border border-slate-200 dark:border-white/5 ${hasBackground ? '' : 'bg-slate-100 dark:bg-white/5'}`}
                            style={
                                hasBackground
                                    ? { background: backgroundGradient(selectedPreset), color: selectedPreset.text_color || '#FFFFFF' }
                                    : undefined
                            }
                        >
                            <p
                                className={`text-sm font-semibold whitespace-pre-wrap break-words ${hasBackground ? '' : 'text-slate-800 dark:text-white'}`}
                            >
                                {previewSnippet || t("anonymousStories.publishPreviewEmpty", "Le texte de l'histoire apparaitra ici.")}
                            </p>
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

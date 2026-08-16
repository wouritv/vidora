import React, { useMemo, useState } from 'react';
import {
  Check,
  Film,
  Loader2,
  Sparkles,
  Upload,
  Wand2,
} from 'lucide-react';
import { getApiUrl } from '../config';
import { useUserCredits } from '../state/UserCreditsContext';
import { useTranslation } from '../state/LanguageContext';

const SUPPORTED_PLATFORMS = ['tiktok', 'youtube', 'linkedin', 'facebook', 'instagram'];

function StepIndicator({ step, labels }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {labels.map((label, idx) => (
        <React.Fragment key={label}>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border ${idx <= step
            ? 'bg-primary/15 text-primary border-primary/30'
            : 'bg-white/5 text-slate-400 dark:text-zinc-500 border-slate-300 dark:border-white/10'
            }`}>
            <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${idx < step ? 'bg-primary text-black' : 'bg-white/10 text-slate-700 dark:text-zinc-300'
              }`}>
              {idx < step ? <Check size={10} /> : idx + 1}
            </span>
            <span>{label}</span>
          </div>
          {idx < labels.length - 1 && <div className="w-6 h-px bg-white/10" />}
        </React.Fragment>
      ))}
    </div>
  );
}

export default function ThumbnailStudio({ geminiApiKey, appUserId }) {
  const { t } = useTranslation();
  const { credits, defaultCosts } = useUserCredits();
  const [step, setStep] = useState(0);
  const [videoFile, setVideoFile] = useState(null);
  const [sessionId, setSessionId] = useState('');
  const [platform, setPlatform] = useState('tiktok');
  const [removeSilences, setRemoveSilences] = useState(false);
  const [captions, setCaptions] = useState([]);
  const [language, setLanguage] = useState('auto');
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [mediaUrl, setMediaUrl] = useState('');
  const [error, setError] = useState('');
  const captionCostEstimate = Number(defaultCosts?.caption || 1);
  const canRunCaptionOps = credits >= captionCostEstimate;
  const steps = useMemo(
    () => [
      t('thumbnailStudio.stepUpload', 'Upload'),
      t('thumbnailStudio.stepAnalyze', 'Analyze'),
      t('thumbnailStudio.stepCustomize', 'Customize'),
      t('thumbnailStudio.stepRender', 'Render'),
    ],
    [t]
  );

  const [style, setStyle] = useState({
    font_name: 'Verdana',
    font_size: 16,
    font_color: '#FFFFFF',
    border_color: '#000000',
    border_width: 2,
    bg_color: '#000000',
    bg_opacity: 0,
    position: 'bottom',
  });

  const openaiKey = useMemo(() => {
    try {
      return localStorage.getItem('openai_key') || '';
    } catch {
      return '';
    }
  }, []);

  const updateCaptionText = (index, text) => {
    setCaptions((prev) => prev.map((item, idx) => (idx === index ? { ...item, text } : item)));
  };

  const handleUpload = async () => {
    if (!videoFile) return;
    setError('');
    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', videoFile);

      const response = await fetch(getApiUrl('/api/captions/upload'), {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const text = await response.text();
        try {
          const parsed = JSON.parse(text);
          throw new Error(parsed?.detail || text);
        } catch {
          throw new Error(text);
        }
      }
      const data = await response.json();
      setSessionId(data.session_id);
      setStep(1);
    } catch (err) {
      setError(err.message || t('thumbnailStudio.uploadFailed', 'Upload failed'));
    } finally {
      setIsUploading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!sessionId) return;
    if (!canRunCaptionOps) {
      setError(t('thumbnailStudio.insufficientForAnalyze', "Insufficient credits. Analysis is not available."));
      return;
    }
    setError('');
    setIsAnalyzing(true);

    try {
      const response = await fetch(getApiUrl('/api/captions/analyze'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(appUserId ? { 'X-User-Id': appUserId } : {}),
          ...(geminiApiKey ? { 'X-Gemini-Key': geminiApiKey } : {}),
          ...(openaiKey ? { 'X-OpenAI-Key': openaiKey } : {}),
        },
        body: JSON.stringify({
          session_id: sessionId,
          platform,
          remove_silences: removeSilences,
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        try {
          const parsed = JSON.parse(text);
          throw new Error(parsed?.detail || text);
        } catch {
          throw new Error(text);
        }
      }
      const data = await response.json();
      setCaptions(data.captions || []);
      setLanguage(data.language || 'auto');
      setStep(2);
    } catch (err) {
      setError(err.message || t('thumbnailStudio.analyzeFailed', 'Analysis failed'));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleRender = async () => {
    if (!sessionId || captions.length === 0) return;
    if (!canRunCaptionOps) {
      setError(t('thumbnailStudio.insufficientForRender', "Insufficient credits. Render is not available."));
      return;
    }
    setError('');
    setIsRendering(true);

    try {
      const response = await fetch(getApiUrl('/api/captions/render'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(appUserId ? { 'X-User-Id': appUserId } : {}),
        },
        body: JSON.stringify({
          session_id: sessionId,
          platform,
          captions,
          style,
          title: t('thumbnailStudio.renderTitle', 'Captions {{platform}}', { platform }),
          description: t('thumbnailStudio.renderDescription', 'Captions adapted for {{platform}}', { platform }),
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        try {
          const parsed = JSON.parse(text);
          throw new Error(parsed?.detail || text);
        } catch {
          throw new Error(text);
        }
      }
      const data = await response.json();
      setMediaUrl(data.media_url || '');
      setStep(3);
    } catch (err) {
      setError(err.message || t('thumbnailStudio.renderFailed', 'Render failed'));
    } finally {
      setIsRendering(false);
    }
  };


  return (
    <div className="h-full overflow-y-auto p-6 md:p-8 animate-[fadeIn_0.3s_ease-out]">
      <div className="max-w-6xl mx-auto">

        <p className="text-sm text-slate-400 dark:text-zinc-500 mb-6">
          {t('thumbnailStudio.subtitle', 'Upload video -> choose social platform -> generate AI captions -> customize style and text -> render final video.')}
        </p>

        <StepIndicator step={step} labels={steps} />

        {error && (
          <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {!canRunCaptionOps && (
          <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
            {t('reels.insufficientForNew', 'Pas assez de crédits, vous pouvez juste consulter sans faire de nouvelles opérations')}
          </div>
        )}

        {step === 0 && (
          <section className="glass-panel p-6 space-y-5">
            <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 p-5">
              <label className="cursor-pointer block">
                <input
                    type="file"
                    accept="video/*"
                    onChange={(e) => setVideoFile(e.target.files?.[0] || null)}
                    className="hidden"
                />
                <Upload className="mx-auto mb-3 text-slate-400 dark:text-zinc-500" size={24} />
                <p className="text-slate-500 dark:text-zinc-400">{t('thumbnailStudio.uploadHint', 'Click to upload a video or drag and drop')}</p>
                <p className="text-xs text-zinc-600 mt-1">{t('thumbnailStudio.uploadDetail', 'MP4, MOV, AVI (Max duration: 30min, Max size: 5GB)')}</p>
              </label>
              {videoFile && (
                <p className="mt-2 text-xs text-slate-400 dark:text-zinc-500 inline-flex items-center gap-2">
                  <Film size={12} /> {videoFile.name}
                </p>
              )}
            </div>

            <button
              onClick={handleUpload}
              disabled={!videoFile || isUploading}
              className="btn-primary py-3 px-5 rounded-xl text-sm font-semibold disabled:opacity-50 inline-flex items-center gap-2"
            >
              {isUploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
              {isUploading ? t('thumbnailStudio.uploading', 'Uploading...') : t('thumbnailStudio.uploadVideo', 'Upload video')}
            </button>
          </section>
        )}

        {step === 1 && (
          <section className="grid md:grid-cols-2 gap-6">
            <div className="glass-panel p-6 space-y-4">
              <h2 className="title-contrast text-sm font-semibold">{t('thumbnailStudio.targetPlatform', 'Target platform')}</h2>
              <div className="grid grid-cols-2 gap-2">
                {SUPPORTED_PLATFORMS.map((item) => (
                  <button
                    key={item}
                    onClick={() => setPlatform(item)}
                    className={`rounded-lg px-3 py-2 text-sm border transition ${platform === item
                      ? 'border-primary/50 bg-primary/10 text-primary'
                      : 'border-slate-300 dark:border-white/10 bg-white/5 text-slate-700 dark:text-zinc-300 hover:bg-white/10'
                      }`}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>

            <div className="glass-panel p-6 space-y-4">
              <h2 className="title-contrast text-sm font-semibold">{t('thumbnailStudio.options', 'Options')}</h2>
              <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-zinc-300">
                <input
                  type="checkbox"
                  checked={removeSilences}
                  onChange={(e) => setRemoveSilences(e.target.checked)}
                />
                {t('thumbnailStudio.removeSilence', 'Remove silence periods')}
              </label>
              <p className="text-xs text-slate-400 dark:text-zinc-500">{t('thumbnailStudio.removeSilenceHint', 'This option trims audio pauses before captions generation.')}</p>
            </div>

            <div className="md:col-span-2">
              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing || !canRunCaptionOps}
                className="btn-primary py-3 px-5 rounded-xl text-sm font-semibold disabled:opacity-50 inline-flex items-center gap-2"
              >
                {isAnalyzing ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                {isAnalyzing ? t('thumbnailStudio.analyzing', 'Analyzing...') : t('thumbnailStudio.analyze', 'Analyze and generate captions')}
              </button>
            </div>
          </section>
        )}

        {step === 2 && (
          <section className="space-y-6">
            <div className="glass-panel p-5">
              <p className="text-xs text-slate-400 dark:text-zinc-500">{t('thumbnailStudio.detectedLanguage', 'Detected language')}: <span className="text-slate-700 dark:text-zinc-300">{language}</span></p>
              <p className="text-xs text-slate-400 dark:text-zinc-500 mt-1">{t('thumbnailStudio.target', 'Target platform')}: <span className="text-slate-700 dark:text-zinc-300">{platform}</span></p>
            </div>

            <div className="grid lg:grid-cols-[1fr_340px] gap-6">
              <div className="glass-panel p-5 space-y-3 max-h-[560px] overflow-y-auto custom-scrollbar">
                <h2 className="title-contrast text-sm font-semibold">{t('thumbnailStudio.customCaptions', 'Customizable captions')}</h2>
                {captions.map((line, idx) => (
                  <div key={`${line.start}-${idx}`} className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 p-3 space-y-1">
                    <p className="text-[11px] text-slate-400 dark:text-zinc-500">{line.start.toFixed(2)}s → {line.end.toFixed(2)}s</p>
                    <textarea
                      value={line.text}
                      onChange={(e) => updateCaptionText(idx, e.target.value)}
                      className="w-full h-16 bg-black/30 border border-slate-300 dark:border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-100"
                    />
                  </div>
                ))}
              </div>

              <div className="glass-panel p-5 space-y-3">
                <h2 className="title-contrast text-sm font-semibold">{t('thumbnailStudio.captionStyle', 'Caption style')}</h2>
                <label className="text-xs text-slate-500 dark:text-zinc-400 block">{t('thumbnailStudio.fontSize', 'Font size')}</label>
                <input
                  type="number"
                  min={10}
                  max={72}
                  value={style.font_size}
                  onChange={(e) => setStyle((prev) => ({ ...prev, font_size: Number(e.target.value) || 16 }))}
                  className="input-field text-sm"
                />

                <label className="text-xs text-slate-500 dark:text-zinc-400 block">{t('thumbnailStudio.position', 'Position')}</label>
                <select
                  value={style.position}
                  onChange={(e) => setStyle((prev) => ({ ...prev, position: e.target.value }))}
                  className="input-field text-sm"
                >
                  <option value="top">{t('thumbnailStudio.positionTop', 'Top')}</option>
                  <option value="middle">{t('thumbnailStudio.positionMiddle', 'Middle')}</option>
                  <option value="bottom">{t('thumbnailStudio.positionBottom', 'Bottom')}</option>
                </select>

                <label className="text-xs text-slate-500 dark:text-zinc-400 block">{t('thumbnailStudio.textColor', 'Text color')}</label>
                <input
                  type="color"
                  value={style.font_color}
                  onChange={(e) => setStyle((prev) => ({ ...prev, font_color: e.target.value }))}
                  className="w-full h-10 rounded-lg border border-slate-300 dark:border-white/10 bg-black/30"
                />

                <label className="text-xs text-slate-500 dark:text-zinc-400 block">{t('thumbnailStudio.borderColor', 'Border color')}</label>
                <input
                  type="color"
                  value={style.border_color}
                  onChange={(e) => setStyle((prev) => ({ ...prev, border_color: e.target.value }))}
                  className="w-full h-10 rounded-lg border border-slate-300 dark:border-white/10 bg-black/30"
                />

                <button
                  onClick={handleRender}
                  disabled={isRendering || captions.length === 0 || !canRunCaptionOps}
                  className="w-full btn-primary py-3 rounded-xl text-sm font-semibold disabled:opacity-50 inline-flex items-center justify-center gap-2"
                >
                  {isRendering ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />}
                  {isRendering ? t('thumbnailStudio.rendering', 'Rendering...') : t('thumbnailStudio.render', 'Render final video')}
                </button>
              </div>
            </div>
          </section>
        )}

        {step === 3 && (
          <section className="glass-panel p-6 space-y-4">
            <h2 className="title-contrast text-sm font-semibold">{t('thumbnailStudio.result', 'Result')}</h2>
            {mediaUrl ? (
              <div className="space-y-4">
                <video src={getApiUrl(mediaUrl)} controls className="w-full max-h-[70vh] rounded-xl bg-black" />
                <a
                  href={getApiUrl(mediaUrl)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 px-4 py-2 text-sm text-zinc-200 hover:bg-white/10"
                >
                  <Check size={14} /> {t('thumbnailStudio.openDownload', 'Open / download')}
                </a>
              </div>
            ) : (
              <p className="text-sm text-slate-500 dark:text-zinc-400">{t('thumbnailStudio.noVideo', 'No rendered video.')}</p>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

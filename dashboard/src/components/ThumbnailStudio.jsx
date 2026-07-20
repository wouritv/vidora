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

const STEPS = ['Upload', 'Analyze', 'Customize', 'Render'];
const SUPPORTED_PLATFORMS = ['tiktok', 'youtube', 'linkedin', 'facebook'];

function StepIndicator({ step }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {STEPS.map((label, idx) => (
        <React.Fragment key={label}>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border ${idx <= step
            ? 'bg-primary/15 text-primary border-primary/30'
            : 'bg-white/5 text-zinc-500 border-white/10'
            }`}>
            <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${idx < step ? 'bg-primary text-black' : 'bg-white/10 text-zinc-300'
              }`}>
              {idx < step ? <Check size={10} /> : idx + 1}
            </span>
            <span>{label}</span>
          </div>
          {idx < STEPS.length - 1 && <div className="w-6 h-px bg-white/10" />}
        </React.Fragment>
      ))}
    </div>
  );
}

export default function ThumbnailStudio({ geminiApiKey, appUserId }) {
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

      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setSessionId(data.session_id);
      setStep(1);
    } catch (err) {
      setError(err.message || 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!sessionId) return;
    setError('');
    setIsAnalyzing(true);

    try {
      const response = await fetch(getApiUrl('/api/captions/analyze'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(geminiApiKey ? { 'X-Gemini-Key': geminiApiKey } : {}),
          ...(openaiKey ? { 'X-OpenAI-Key': openaiKey } : {}),
        },
        body: JSON.stringify({
          session_id: sessionId,
          platform,
          remove_silences: removeSilences,
        }),
      });

      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setCaptions(data.captions || []);
      setLanguage(data.language || 'auto');
      setStep(2);
    } catch (err) {
      setError(err.message || 'Analyze failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleRender = async () => {
    if (!sessionId || captions.length === 0) return;
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
          title: `IA Captions ${platform}`,
          description: `Captions adaptes pour ${platform}`,
        }),
      });

      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setMediaUrl(data.media_url || '');
      setStep(3);
    } catch (err) {
      setError(err.message || 'Render failed');
    } finally {
      setIsRendering(false);
    }
  };

  const resetAll = () => {
    setStep(0);
    setVideoFile(null);
    setSessionId('');
    setCaptions([]);
    setMediaUrl('');
    setError('');
    setLanguage('auto');
    setRemoveSilences(false);
  };

  return (
    <div className="h-full overflow-y-auto p-6 md:p-8 animate-[fadeIn_0.3s_ease-out]">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <span className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <Wand2 size={20} className="text-white" />
            </span>
            IA Captions
          </h1>
        </div>
        <p className="text-sm text-zinc-500 mb-6">
          Upload video → choose social platform → generate AI captions → customize style and text → render final video.
        </p>

        <StepIndicator step={step} />

        {error && (
          <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {step === 0 && (
          <section className="glass-panel p-6 space-y-5">
            <div className="rounded-xl border border-white/10 bg-white/5 p-5">
              <label className="cursor-pointer block">
                <input
                    type="file"
                    accept="video/*"
                    onChange={(e) => setVideoFile(e.target.files?.[0] || null)}
                    className="hidden"
                />
                <Upload className="mx-auto mb-3 text-zinc-500" size={24} />
                <p className="text-zinc-400">Click to upload or drag and drop</p>
                <p className="text-xs text-zinc-600 mt-1">MP4, MOV up to 500MB</p>
              </label>
              {videoFile && (
                <p className="mt-2 text-xs text-zinc-500 inline-flex items-center gap-2">
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
              {isUploading ? 'Upload en cours...' : 'Uploader la video'}
            </button>
          </section>
        )}

        {step === 1 && (
          <section className="grid md:grid-cols-2 gap-6">
            <div className="glass-panel p-6 space-y-4">
              <h2 className="text-sm font-semibold text-white">Target platform</h2>
              <div className="grid grid-cols-2 gap-2">
                {SUPPORTED_PLATFORMS.map((item) => (
                  <button
                    key={item}
                    onClick={() => setPlatform(item)}
                    className={`rounded-lg px-3 py-2 text-sm border transition ${platform === item
                      ? 'border-primary/50 bg-primary/10 text-primary'
                      : 'border-white/10 bg-white/5 text-zinc-300 hover:bg-white/10'
                      }`}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>

            <div className="glass-panel p-6 space-y-4">
              <h2 className="text-sm font-semibold text-white">Options</h2>
              <label className="flex items-center gap-2 text-sm text-zinc-300">
                <input
                  type="checkbox"
                  checked={removeSilences}
                  onChange={(e) => setRemoveSilences(e.target.checked)}
                />
                Supprimer les periodes de silence
              </label>
              <p className="text-xs text-zinc-500">Cette option coupe les pauses audio avant la generation des captions.</p>
            </div>

            <div className="md:col-span-2">
              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing}
                className="btn-primary py-3 px-5 rounded-xl text-sm font-semibold disabled:opacity-50 inline-flex items-center gap-2"
              >
                {isAnalyzing ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                {isAnalyzing ? 'Analyse en cours...' : 'Analyser et generer les captions'}
              </button>
            </div>
          </section>
        )}

        {step === 2 && (
          <section className="space-y-6">
            <div className="glass-panel p-5">
              <p className="text-xs text-zinc-500">Langue detectee: <span className="text-zinc-300">{language}</span></p>
              <p className="text-xs text-zinc-500 mt-1">Plateforme cible: <span className="text-zinc-300">{platform}</span></p>
            </div>

            <div className="grid lg:grid-cols-[1fr_340px] gap-6">
              <div className="glass-panel p-5 space-y-3 max-h-[560px] overflow-y-auto custom-scrollbar">
                <h2 className="text-sm font-semibold text-white">Captions personnalisables</h2>
                {captions.map((line, idx) => (
                  <div key={`${line.start}-${idx}`} className="rounded-xl border border-white/10 bg-white/5 p-3 space-y-1">
                    <p className="text-[11px] text-zinc-500">{line.start.toFixed(2)}s → {line.end.toFixed(2)}s</p>
                    <textarea
                      value={line.text}
                      onChange={(e) => updateCaptionText(idx, e.target.value)}
                      className="w-full h-16 bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-zinc-100"
                    />
                  </div>
                ))}
              </div>

              <div className="glass-panel p-5 space-y-3">
                <h2 className="text-sm font-semibold text-white">Style captions</h2>
                <label className="text-xs text-zinc-400 block">Font size</label>
                <input
                  type="number"
                  min={10}
                  max={72}
                  value={style.font_size}
                  onChange={(e) => setStyle((prev) => ({ ...prev, font_size: Number(e.target.value) || 16 }))}
                  className="input-field text-sm"
                />

                <label className="text-xs text-zinc-400 block">Position</label>
                <select
                  value={style.position}
                  onChange={(e) => setStyle((prev) => ({ ...prev, position: e.target.value }))}
                  className="input-field text-sm"
                >
                  <option value="top">Top</option>
                  <option value="middle">Middle</option>
                  <option value="bottom">Bottom</option>
                </select>

                <label className="text-xs text-zinc-400 block">Text color</label>
                <input
                  type="color"
                  value={style.font_color}
                  onChange={(e) => setStyle((prev) => ({ ...prev, font_color: e.target.value }))}
                  className="w-full h-10 rounded-lg border border-white/10 bg-black/30"
                />

                <label className="text-xs text-zinc-400 block">Border color</label>
                <input
                  type="color"
                  value={style.border_color}
                  onChange={(e) => setStyle((prev) => ({ ...prev, border_color: e.target.value }))}
                  className="w-full h-10 rounded-lg border border-white/10 bg-black/30"
                />

                <button
                  onClick={handleRender}
                  disabled={isRendering || captions.length === 0}
                  className="w-full btn-primary py-3 rounded-xl text-sm font-semibold disabled:opacity-50 inline-flex items-center justify-center gap-2"
                >
                  {isRendering ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />}
                  {isRendering ? 'Rendu en cours...' : 'Rendre la video finale'}
                </button>
              </div>
            </div>
          </section>
        )}

        {step === 3 && (
          <section className="glass-panel p-6 space-y-4">
            <h2 className="text-sm font-semibold text-white">Resultat</h2>
            {mediaUrl ? (
              <div className="space-y-4">
                <video src={getApiUrl(mediaUrl)} controls className="w-full max-h-[70vh] rounded-xl bg-black" />
                <a
                  href={getApiUrl(mediaUrl)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-zinc-200 hover:bg-white/10"
                >
                  <Check size={14} /> Ouvrir / telecharger
                </a>
              </div>
            ) : (
              <p className="text-sm text-zinc-400">Aucune video rendue.</p>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

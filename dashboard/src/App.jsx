import React, { useState, useEffect } from 'react';
import {
  Sparkles, Activity, Globe, Calendar, Instagram, Youtube, ArrowLeft,
  CheckCircle2, Clock3, Download, Film, Loader2, AlertCircle, X
} from 'lucide-react';
import MediaInput from './components/MediaInput';
import ResultCard from './components/ResultCard';
import ProcessingAnimation from './components/ProcessingAnimation';
import ThumbnailStudio from './components/ThumbnailStudio';
import ScheduleWeekModal from './components/ScheduleWeekModal';
import { getApiUrl } from './config';
import { useLocation, useNavigate } from "react-router-dom";
import { DASHBOARD_SIDEBAR_ITEMS } from "./lib/dashboard-nav";
import { useAuth } from "./state/AuthContext";
import SettingsPage from "./pages/Settings.jsx";

const TikTokIcon = ({ size = 16, className = "" }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M19.589 6.686a4.793 4.793 0 0 1-3.77-4.245V2h-3.445v13.672a2.896 2.896 0 0 1-5.201 1.743l-.002-.001.002.001a2.895 2.895 0 0 1 3.183-4.51v-3.5a6.329 6.329 0 0 0-5.394 10.692 6.33 6.33 0 0 0 10.857-4.424V8.687a8.182 8.182 0 0 0 4.773 1.526V6.79a4.831 4.831 0 0 1-1.003-.104z" />
    </svg>
);

const getStatusBadgeClass = (status) => {
  if (status === 'completed') status = 'complete';
  if (status === 'failed') status = 'error';
  if (status === 'processing') return 'bg-primary/10 border-primary/20 text-primary';
  if (status === 'complete') return 'bg-green-500/10 border-green-500/20 text-green-400';
  return 'bg-red-500/10 border-red-500/20 text-red-400';
};

const getProcessLabel = (status) => {
  if (status === 'completed') status = 'complete';
  if (status === 'failed') status = 'error';
  if (status === 'processing') return 'En cours';
  if (status === 'complete') return 'Termine';
  if (status === 'error') return 'Erreur';
  return 'En attente';
};

const normalizeStatus = (status) => {
  if (status === 'queued') return 'processing';
  if (status === 'completed') return 'complete';
  if (status === 'failed') return 'error';
  return status;
};

const getVisibleClips = (status, results, partialClips) => {
  status = normalizeStatus(status);
  if (status === 'complete') return results?.clips || [];
  if (results?.clips?.length) return results.clips;
  return partialClips;
};

const getHighestClipMention = (logs) => logs.reduce((max, line) => {
  const matches = [...line.matchAll(/clip\s+(\d+)/ig)];
  if (!matches.length) return max;
  return Math.max(max, ...matches.map((match) => Number(match[1]) || 0));
}, 0);

const buildProcessingSteps = ({ status, logs, visibleClips, processingMedia }) => {
  status = normalizeStatus(status);
  const hasLog = (regex) => logs.some((line) => regex.test(line));
  const highestClipMention = getHighestClipMention(logs);
  const generatedCount = visibleClips.length;
  const detectedCount = Math.max(highestClipMention, generatedCount);
  const processStarted = status !== 'idle';
  const sourceReady = processingMedia?.type === 'file'
    ? processStarted
    : hasLog(/download/i) || detectedCount > 0 || status === 'complete' || status === 'error';
  const transcriptReady = hasLog(/transcrib|transcript/i) || detectedCount > 0 || status === 'complete' || status === 'error';
  const reelsDetected = detectedCount > 0 || status === 'complete' || status === 'error';

  return [
    {
      key: 'started',
      label: 'Processus demarre',
      description: processStarted ? 'Le workflow a bien ete lance.' : 'En attente de lancement.',
      state: processStarted ? 'done' : 'pending',
    },
    {
      key: 'source',
      label: processingMedia?.type === 'file' ? 'Reception de la video' : 'Telechargement de la video',
      description: sourceReady
        ? 'La source est prete pour le traitement.'
        : 'Preparation de la source en cours.',
      state: sourceReady ? 'done' : processStarted ? 'active' : 'pending',
    },
    {
      key: 'transcript',
      label: 'Generation de la transcription',
      description: transcriptReady
        ? 'La transcription est disponible pour l’analyse.'
        : 'Transcription audio en cours.',
      state: transcriptReady ? 'done' : sourceReady && status === 'processing' ? 'active' : 'pending',
    },
    {
      key: 'detect',
      label: 'Detection du nombre de reels a creer',
      description: reelsDetected
        ? `${detectedCount || generatedCount} reel(s) identifies pour la generation.`
        : 'L’IA determine encore les meilleurs moments.',
      state: reelsDetected ? 'done' : transcriptReady && status === 'processing' ? 'active' : 'pending',
    },
    {
      key: 'create',
      label: 'Creation des reels',
      description: status === 'complete'
        ? `${generatedCount} reel(s) finalises et prets au telechargement.`
        : generatedCount > 0
          ? `${generatedCount} reel(s) deja generes.`
          : 'Generation des reels en cours.',
      state: status === 'complete'
        ? 'done'
        : status === 'error'
          ? 'error'
          : reelsDetected && status === 'processing'
            ? 'active'
            : 'pending',
    },
  ];
};

const StepStatusIcon = ({ state }) => {
  if (state === 'done') return <CheckCircle2 size={16} className="text-green-400" />;
  if (state === 'active') return <Loader2 size={16} className="text-primary animate-spin" />;
  if (state === 'error') return <AlertCircle size={16} className="text-red-400" />;
  return <Clock3 size={16} className="text-zinc-500" />;
};

const ProcessingChecklist = ({ status, logs, visibleClips, processingMedia }) => {
  const steps = buildProcessingSteps({ status, logs, visibleClips, processingMedia });
  const doneCount = steps.filter((step) => step.state === 'done').length;
  const totalCount = steps.length;
  const progressPercent = Math.round((doneCount / totalCount) * 100);

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">Suivi du process</p>
          <h3 className="mt-1 text-lg font-bold text-white">Generation des reels</h3>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1.5 text-xs text-zinc-300">
          <Activity size={14} className={status === 'processing' ? 'text-primary animate-pulse' : 'text-zinc-400'} />
          <span>{getProcessLabel(status)}</span>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-3">
        <div className="mb-2 flex items-center justify-between text-xs">
          <span className="text-zinc-400">Progression</span>
          <span className="font-medium text-zinc-200">{doneCount}/{totalCount} etapes ({progressPercent}%)</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {steps.map((step) => (
          <div key={step.key} className="flex items-start gap-3 rounded-xl border border-white/5 bg-black/20 px-4 py-3">
            <div className="mt-0.5 shrink-0">
              <StepStatusIcon state={step.state} />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white">{step.label}</p>
              <p className="mt-1 text-xs leading-5 text-zinc-400">{step.description}</p>
            </div>
          </div>
        ))}
      </div>

    </section>
  );
};

const GeneratedClipsList = ({ clips, status }) => {
  if (!clips.length) {
    return <EmptyResultsState status={status} />;
  }

  return (
    <div className="space-y-3">
      {clips.map((clip, index) => {
        const duration = Number.isFinite(clip?.end - clip?.start)
          ? Math.max(1, Math.round(clip.end - clip.start))
          : null;

        return (
          <div key={`${clip?.reel_id || clip?.video_url || 'clip'}-${index}`} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-full bg-primary/10 px-2 text-[11px] font-semibold text-primary">
                    {index + 1}
                  </span>
                  <p className="truncate text-sm font-semibold text-white">
                    {clip?.video_title_for_youtube_short || clip?.title || `Reel ${index + 1}`}
                  </p>
                </div>
                <p className="mt-2 text-xs leading-5 text-zinc-400">
                  {duration ? `${duration}s • ` : ''}
                  {status === 'complete' ? 'Pret pour telechargement et edition.' : 'Reel genere pendant le traitement.'}
                </p>
              </div>

              {clip?.video_url && (
                <a
                  href={getApiUrl(clip.video_url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-zinc-200 transition hover:bg-white/10"
                >
                  <Download size={14} />
                  Telecharger
                </a>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const EmptyResultsState = ({ status }) => {
  if (status === 'processing') {
    return (
        <div className="h-full flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-black/20 px-6 py-10 text-zinc-500 space-y-4">
          <div className="w-12 h-12 rounded-full border-2 border-zinc-800 border-t-primary animate-spin" />
          <p className="text-sm text-center">Les reels apparaitront ici au fur et a mesure de la generation.</p>
        </div>
    );
  }
  if (status === 'error') {
    return (
        <div className="h-full flex flex-col items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/5 px-6 py-10 text-red-400 space-y-2">
          <p>La generation a rencontre une erreur.</p>
        </div>
    );
  }
  return (
    <div className="h-full flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-black/20 px-6 py-10 text-zinc-500 space-y-2">
      <Film size={22} className="text-zinc-600" />
      <p className="text-sm">Aucun reel genere pour le moment.</p>
    </div>
  );
};

const Sidebar = ({ currentTab, onNavigate }) => (
    <div className="w-20 lg:w-64 bg-surface border-r border-white/5 flex flex-col h-full shrink-0 transition-all duration-300">
      <div className="p-6 flex items-center gap-3">
        <div className="w-8 h-8 bg-white/5 rounded-lg flex items-center justify-center shrink-0 overflow-hidden border border-white/5">
          <img src="/logo-openshorts.png" alt="Logo" className="w-full h-full object-cover" />
        </div>
        <span className="font-bold text-lg text-white hidden lg:block tracking-tight">OpenShorts</span>
      </div>

      <nav className="flex-1 px-4 py-4 space-y-2">
        {DASHBOARD_SIDEBAR_ITEMS.map((item) => {
          const ItemIcon = item.icon;
          return (
              <button
                  key={item.key}
                  onClick={() => onNavigate(item.path)}
                  className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-colors ${currentTab === item.key ? item.activeClassName : item.inactiveClassName}`}
              >
                <ItemIcon size={20} />
                <span className="font-medium hidden lg:block">{item.sidebarLabel}</span>
              </button>
          );
        })}
      </nav>

      <div className="p-4 border-t border-white/5 space-y-2">
        <button
            type="button"
            onClick={() => {
              localStorage.removeItem('openshorts_skip_landing');
              globalThis.location.hash = '';
              globalThis.location.reload();
            }}
            className="w-full flex items-center gap-2 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors group text-left"
        >
          <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0">
            <Globe size={16} />
          </div>
          <div className="hidden lg:block overflow-hidden">
            <p className="text-sm font-bold text-white leading-none mb-0.5">Landing Page</p>
            <p className="text-[10px] text-zinc-400 group-hover:text-zinc-300 transition-colors truncate">View website</p>
          </div>
        </button>
        <a
            href="https://github.com/mutonby/openshorts"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors group"
        >
          <div className="w-8 h-8 rounded-full bg-white text-black flex items-center justify-center shrink-0">
            <svg height="20" viewBox="0 0 16 16" version="1.1" width="20" aria-hidden="true">
              <path fillRule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
          </div>
          <div className="hidden lg:block overflow-hidden">
            <p className="text-sm font-bold text-white leading-none mb-0.5">Open Source</p>
            <p className="text-[10px] text-zinc-400 group-hover:text-zinc-300 transition-colors truncate">Free & Community Driven</p>
          </div>
        </a>
      </div>
    </div>
);

const SESSION_KEY = 'openshorts_session';
const SESSION_MAX_AGE = 3600000;

const pollJob = async (jobId) => {
  try {
    const res = await fetch(getApiUrl(`/api/status/${jobId}`));
    if (!res.ok) {
      throw new Error(`Status check failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
  } catch (e) {
    throw e;
  }
};

function App({ activeTab = "clip-generator", embedded = false } = {}) {

  const { user } = useAuth();

  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState('idle');
  const [results, setResults] = useState(null);
  const [partialClips, setPartialClips] = useState([]);  // Partial results during processing
  const [logs, setLogs] = useState([]);
  const [processingMedia, setProcessingMedia] = useState(null);
  const [showScheduleWeek, setShowScheduleWeek] = useState(false);
  const [showCompletionPanel, setShowCompletionPanel] = useState(false);

  const [syncedTime, setSyncedTime] = useState(0);
  const [isSyncedPlaying, setIsSyncedPlaying] = useState(false);
  const [syncTrigger, setSyncTrigger] = useState(0);
  const [hasNotifiedCompletion, setHasNotifiedCompletion] = useState(false);
  const uiStatus = normalizeStatus(status);
  const visibleClips = getVisibleClips(status, results, partialClips);
  const actionReadyClips = visibleClips.filter((clip) => typeof clip?.video_url === 'string' && clip.video_url.length > 0);
  const pendingClips = visibleClips.filter((clip) => !clip?.video_url);

  const handleClipPlay = (startTime) => {
    setSyncedTime(startTime);
    setIsSyncedPlaying(true);
    setSyncTrigger(prev => prev + 1);
  };

  const navigate = useNavigate();
  const location = useLocation();
  const currentTab = activeTab;
  const forceNewOperation = new URLSearchParams(location.search).get('new') === '1';

  const handleClipPause = () => setIsSyncedPlaying(false);

  // Session Recovery: Restore on mount unless user explicitly requests a fresh start.
  useEffect(() => {
    if (currentTab !== 'clip-generator') return;
    if (forceNewOperation) {
      localStorage.removeItem(SESSION_KEY);
      setStatus('idle');
      setJobId(null);
      setResults(null);
      setPartialClips([]);
      setLogs([]);
      setProcessingMedia(null);
      setShowCompletionPanel(false);
      return;
    }

    const saved = localStorage.getItem(SESSION_KEY);
    if (!saved) return;
    try {
      const session = JSON.parse(saved);
      if (Date.now() - session.timestamp > SESSION_MAX_AGE) {
        localStorage.removeItem(SESSION_KEY);
        return;
      }
      if (session.jobId && session.status && session.status !== 'idle') {
        setJobId(session.jobId);
        setResults(session.results || null);
        if (session.processingMedia) setProcessingMedia(session.processingMedia);
        setStatus(normalizeStatus(session.status));
      }
    } catch {
      localStorage.removeItem(SESSION_KEY);
    }
  }, [currentTab, forceNewOperation]);

  // Session Recovery: Save state changes
  useEffect(() => {
    if (status === 'idle') {
      localStorage.removeItem(SESSION_KEY);
      return;
    }
    try {
      // Keep session payload small to avoid quota issues and auth side effects.
      localStorage.setItem(SESSION_KEY, JSON.stringify({
        jobId,
        status: uiStatus,
        results: uiStatus === 'complete' ? results : null,
        processingMedia: processingMedia?.type === 'url' ? processingMedia : null,
        activeTab,
        timestamp: Date.now()
      }));
    } catch {
      // Ignore storage failures: never remove auth/session provider keys.
    }
   }, [jobId, uiStatus, activeTab, processingMedia, results]);


  useEffect(() => {
    let interval = null;
    
    // Poll while processing; transition to complete only when final payload is available.
    if (uiStatus === 'processing' && jobId) {
      // Create interval immediately
      interval = setInterval(async () => {
        try {
          const data = await pollJob(jobId);
          const backendStatus = normalizeStatus(data.status);

          // Update partial clips during processing
          if (data.partialClips && data.partialClips.length > 0) {
            setPartialClips(data.partialClips);
          }

          // Update final results when complete
          if (data.result) {
            setResults(data.result);
            if (data.status === 'completed') {
              setPartialClips([]);
            }
          }

          if (backendStatus === 'complete') {
            // Backend can mark completed slightly before final result is hydrated.
            if (data.result) {
              setStatus('complete');
              if (interval) clearInterval(interval);
            }
          } else if (backendStatus === 'error') {
            setStatus('error');
            const errorMsg = data.error || (data.logs?.length > 0 ? data.logs[data.logs.length - 1] : "Process failed");
            setLogs(prev => [...prev, "Error: " + errorMsg]);
            if (interval) clearInterval(interval);
          } else if (data.logs) {
            setLogs(data.logs);
          }
        } catch (e) {
          console.error("Polling error:", e.message);
          // Continue polling on transient errors
        }
      }, 2000);
    }
    
    // Cleanup function: always clear interval when effect unmounts or deps change
    return () => {
      if (interval !== null) {
        clearInterval(interval);
        interval = null;
      }
    };
  }, [uiStatus, jobId]);

  useEffect(() => {
    if ((uiStatus === 'complete' || uiStatus === 'error') && !hasNotifiedCompletion) {
      setShowCompletionPanel(true);
      setHasNotifiedCompletion(true);
    }
  }, [uiStatus, results, hasNotifiedCompletion]);

  const handleProcess = async (data) => {
    if (!user?.id) {
      setStatus('error');
      setLogs(["Authentication required. Please reconnect your session."]);
      return;
    }

    setHasNotifiedCompletion(false);
    setShowCompletionPanel(false);
    setStatus('processing');
    setLogs(["Starting process..."]);
    setResults(null);
    setPartialClips([]);
    setProcessingMedia(data);

    try {
      let body;
      const headers = { 'X-User-Id': user.id };
      if (data.type === 'url') {
        headers['Content-Type'] = 'application/json';
        body = JSON.stringify({ url: data.payload, acknowledged: !!data.acknowledged });
      } else {
        const formData = new FormData();
        formData.append('file', data.payload);
        formData.append('acknowledged', data.acknowledged ? 'true' : 'false');
        body = formData;
      }
      const res = await fetch(getApiUrl('/api/process'), {
        method: 'POST',
        headers: data.type === 'url' ? headers : { 'X-User-Id': user.id },
        body
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText);
      }
      const resData = await res.json();
      setJobId(resData.job_id);
    } catch (e) {
      setStatus('error');
      setLogs(l => [...l, `Error starting job: ${e.message}`]);
    }
  };

  // ─── Modals (rendus dans les deux modes) ───────────────────────────────────

  const modals = (
    <ScheduleWeekModal
        isOpen={showScheduleWeek}
        onClose={() => setShowScheduleWeek(false)}
        clips={results?.clips || []}
        jobId={jobId}
    />
  );

  // ─── Contenu principal (partagé entre les deux modes) ─────────────────────
  const mainContent = (
      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Background Gradients */}
        <div className="absolute inset-0 overflow-hidden -z-10 pointer-events-none">
          <div className="absolute -top-[10%] -right-[10%] w-[50%] h-[50%] bg-primary/5 rounded-full blur-[120px]" />
        </div>

        {/* Top Header */}
        <header>

          {currentTab === 'clip-generator' && (
             <div className="h-16 border-b border-white/5 bg-background/50 backdrop-blur-md flex items-center justify-between px-6 shrink-0 z-10">
              <div className="flex items-center gap-4">
                <div>
                  <h1 className="text-3xl font-black tracking-tight">Génération de réels</h1>
                </div>
              </div>

               <button
                   type="button"
                   onClick={() => {
                     navigate("/dashboard/reels");
                   }}
                   className="flex items-center gap-2 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors group"
               >
                 <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0">
                   <ArrowLeft size={16} />
                 </div>
                 <div className="hidden lg:block overflow-hidden">
                   <p className="text-sm font-bold text-white leading-none mb-0.5">Retour à la liste</p>
                 </div>
               </button>

             </div>
          )}

          {currentTab === 'youtube-studio' && (
              <div className="h-16 border-b border-white/5 bg-background/50 backdrop-blur-md flex items-center justify-between px-6 shrink-0 z-10">
                <div className="flex items-center gap-4">
                  <div>
                    <h1 className="text-3xl font-black tracking-tight">IA Captions</h1>
                  </div>
                </div>

                <button
                    type="button"
                    onClick={() => {
                      navigate("/dashboard/youtube-resumes");
                    }}
                    className="flex items-center gap-2 p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors group"
                >
                  <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0">
                    <ArrowLeft size={16} />
                  </div>
                  <div className="hidden lg:block overflow-hidden">
                    <p className="text-sm font-bold text-white leading-none mb-0.5">Retour à la liste</p>
                  </div>
                </button>

              </div>
          )}


        </header>

        {/* Main Workspace */}
        <div className="flex-1 overflow-hidden relative">

          {/* View: Settings */}
          {currentTab === 'settings' && (
              <SettingsPage />
          )}


           {/* View: Thumbnails */}
           {currentTab === 'youtube-studio' && (
               <ThumbnailStudio appUserId={user?.id} />
           )}

          {/* View: Dashboard (Idle) */}
          {currentTab === 'clip-generator' && uiStatus === 'idle' && (
              <div className="h-full flex flex-col items-center justify-center p-6 animate-[fadeIn_0.3s_ease-out]">
                <div className="max-w-xl w-full text-center space-y-8">
                  <div className="space-y-4">
                    <h1 className="text-4xl md:text-5xl font-black bg-gradient-to-b from-white to-white/60 bg-clip-text text-transparent">
                      Create Viral Shorts
                    </h1>
                    <p className="text-zinc-400 text-lg">
                      Drop your long-form video below to instantly generate viral clips with AI.
                    </p>
                  </div>
                  <MediaInput onProcess={handleProcess} isProcessing={uiStatus === 'processing'} />
                  <div className="flex items-center justify-center gap-8 text-zinc-500 text-sm">
                    <span className="flex items-center gap-2"><Youtube size={16} /> YouTube</span>
                    <span className="flex items-center gap-2"><Instagram size={16} /> Instagram</span>
                    <span className="flex items-center gap-2"><TikTokIcon size={16} /> TikTok</span>
                  </div>
                </div>
              </div>
          )}

          {/* View: Processing / Results (Split View) */}
          {currentTab === 'clip-generator' && (
            uiStatus === 'processing' || uiStatus === 'complete' || uiStatus === 'error'
          ) && (
              <div className="h-full flex flex-col animate-[fadeIn_0.3s_ease-out]">
                <div className="flex-1 flex flex-col md:flex-row min-h-0">

                  {/* Left Panel */}
                  <div className={`${uiStatus === 'complete' ? 'w-full md:w-[32%] lg:w-[28%]' : 'w-full md:w-[48%] lg:w-[44%]'} h-full flex flex-col border-r border-white/5 bg-black/20 p-6 overflow-y-auto custom-scrollbar transition-all duration-700 ease-in-out`}>
                    <div className="mb-6 flex items-center justify-between">
                      <h2 className="text-lg font-semibold flex items-center gap-2">
                        <Activity className={`text-primary ${uiStatus === 'processing' ? 'animate-pulse' : ''}`} size={20} />
                        Scan de la video
                      </h2>
                      <span className={`text-xs px-2 py-1 rounded-full border ${getStatusBadgeClass(uiStatus)}`}>
                        {uiStatus.toUpperCase()}
                      </span>
                    </div>

                    {processingMedia ? (
                      <ProcessingAnimation
                        media={processingMedia}
                        isComplete={uiStatus === 'complete'}
                        syncedTime={syncedTime}
                        isSyncedPlaying={isSyncedPlaying}
                        syncTrigger={syncTrigger}
                      />
                    ) : (
                      <div className="flex-1 flex items-center justify-center rounded-2xl border border-dashed border-white/10 bg-black/20 px-6 py-10 text-center text-zinc-400">
                        {uiStatus === 'processing'
                          ? 'Generation en cours. La vue source n’est plus disponible, mais le suivi du workflow continue a droite.'
                          : 'Le rendu est termine. Consulte les reels generes dans le panneau de droite.'}
                      </div>
                    )}
                  </div>

                  {/* Right Panel */}
                  <div className={`${uiStatus === 'complete' ? 'w-full md:w-[68%] lg:w-[72%]' : 'w-full md:w-[52%] lg:w-[56%]'} h-full flex flex-col bg-background p-6 transition-all duration-700 ease-in-out overflow-y-auto custom-scrollbar`}>
                    <ProcessingChecklist
                      status={uiStatus}
                      logs={logs}
                      visibleClips={visibleClips}
                      processingMedia={processingMedia}
                    />

                    <div className="mt-6 flex-1 min-h-0">
                      <h2 className="text-lg font-semibold mb-6 flex items-center gap-2 shrink-0">
                        <Sparkles className="text-yellow-400" size={20} />
                        Reels generes
                        {visibleClips.length > 0 && (
                          <span className="text-xs bg-white/10 text-white px-2 py-0.5 rounded-full ml-auto">
                            {visibleClips.length} Clips
                          </span>
                        )}
                        {uiStatus === 'complete' && results?.cost_analysis && (
                          <span className="text-xs bg-green-500/10 border border-green-500/20 text-green-400 px-2 py-0.5 rounded-full ml-2" title={`Input: ${results.cost_analysis.input_tokens} | Output: ${results.cost_analysis.output_tokens}`}>
                            ${results.cost_analysis.total_cost.toFixed(5)}
                          </span>
                        )}
                        {results?.clips?.length > 1 && uiStatus === 'complete' && (
                          <button
                            onClick={() => setShowScheduleWeek(true)}
                            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-purple-500/20 to-indigo-500/20 hover:from-purple-500/30 hover:to-indigo-500/30 border border-purple-500/30 text-purple-300 hover:text-purple-200 rounded-full text-xs font-bold transition-all"
                          >
                            <Calendar size={14} />
                            Programar Semana
                          </button>
                        )}
                      </h2>

                      <div className="flex-1 overflow-y-auto custom-scrollbar p-1">
                        {actionReadyClips.length > 0 ? (
                          <div className="grid gap-4 pb-10 grid-cols-1 xl:grid-cols-2">
                            {actionReadyClips.map((clip, i) => (
                              <ResultCard
                                // eslint-disable-next-line react/no-array-index-key
                                key={i}
                                clip={clip}
                                index={i}
                                jobId={jobId}
                                onPlay={(time) => handleClipPlay(time)}
                                onPause={handleClipPause}
                                compactActions={true}
                              />
                            ))}
                          </div>
                        ) : pendingClips.length > 0 ? (
                          <GeneratedClipsList clips={pendingClips} status={uiStatus} />
                        ) : (
                          <GeneratedClipsList clips={visibleClips} status={uiStatus} />
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {showCompletionPanel && (uiStatus === 'complete' || uiStatus === 'error') && (
                  <div className="border-t border-white/10 bg-background/95 px-6 py-4 backdrop-blur-md">
                    <div className="mx-auto flex max-w-6xl flex-col gap-4 rounded-2xl border border-white/10 bg-white/[0.03] p-4 md:flex-row md:items-center md:justify-between">
                      <div className="flex items-start gap-3">
                        <div className={`mt-0.5 inline-flex h-10 w-10 items-center justify-center rounded-xl ${uiStatus === 'complete' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                          {uiStatus === 'complete' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-white">
                            {uiStatus === 'complete' ? 'Generation terminee' : 'Generation interrompue'}
                          </p>
                          <p className="mt-1 text-xs leading-5 text-zinc-400">
                            {uiStatus === 'complete'
                              ? `${results?.clips?.length || visibleClips.length} reel(s) sont prets. Tu peux les telecharger, les modifier ou lancer une nouvelle operation.`
                              : 'Une erreur a ete detectee pendant le workflow. Tu peux fermer ce panneau puis relancer une generation.'}
                          </p>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-3">
                        <button
                          type="button"
                          onClick={() => setShowCompletionPanel(false)}
                          className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-zinc-200 transition hover:bg-white/10"
                        >
                          <X size={14} />
                          Fermer
                        </button>
                        <button
                          type="button"
                          onClick={() => navigate('/dashboard/clip-generator?new=1')}
                          className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500"
                        >
                          Nouvelle operation
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
          )}

          {currentTab === 'clip-generator' && uiStatus !== 'idle' && uiStatus !== 'processing' && uiStatus !== 'complete' && uiStatus !== 'error' && (
            <div className="h-full flex items-center justify-center p-6">
              <div className="max-w-lg w-full rounded-2xl border border-white/10 bg-white/[0.03] p-6 text-center">
                <p className="text-sm text-zinc-300">Etat de generation non reconnu: <span className="font-mono text-white">{String(status)}</span></p>
                <button
                  type="button"
                  onClick={() => navigate('/dashboard/clip-generator?new=1')}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500"
                >
                  Reinitialiser la vue
                </button>
              </div>
            </div>
          )}

        </div>
      </main>
  );

  // ─── Mode embedded : pas de shell, juste le contenu + modals ──────────────
  if (embedded) {
    return (
        <>
          {mainContent}
          {modals}
        </>
    );
  }

  // ─── Mode normal : shell complet avec sidebar ──────────────────────────────
  return (
      <div className="flex h-screen bg-background overflow-hidden selection:bg-primary/30">
        <Sidebar currentTab={currentTab} onNavigate={navigate} />
        {mainContent}
        {modals}
      </div>
  );
}

export default App;
import React, { useState, useEffect } from 'react';
import {
  Sparkles, Activity, ArrowLeft,
  CheckCircle2, Clock3, Download, Film, Loader2, AlertCircle, X,
} from 'lucide-react';
import MediaInput from './components/MediaInput';
import ResultCard from './components/ResultCard';
import ProcessingAnimation from './components/ProcessingAnimation';
import ScheduleWeekModal from './components/ScheduleWeekModal';
import { getApiUrl } from './config';
import { useLocation, useNavigate } from "react-router-dom";
import { DASHBOARD_SIDEBAR_ITEMS } from "./lib/dashboard-nav";
import { useAuth } from "./state/AuthContext";
import { useTranslation } from "./state/LanguageContext";
import { SESSION_KEY, SESSION_MAX_AGE } from "./lib/session";
import SettingsPage from "./pages/Settings.jsx";
import { useUserCredits } from "./state/UserCreditsContext";

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
  if (status === 'retry_wait') return 'processing';
  if (status === 'retry_enqueued') return 'processing';
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

const normalizeLogLine = (line) => {
  if (typeof line === 'string') return line;
  if (line == null) return '';
  try {
    return JSON.stringify(line);
  } catch {
    return String(line);
  }
};

const getHighestClipMention = (logs) => logs.reduce((max, line) => {
  const textLine = normalizeLogLine(line);
  const matches = Array.from(textLine.matchAll(/clip\s+(\d+)/ig));
  if (!matches.length) return max;
  return Math.max(max, ...matches.map((match) => Number(match[1]) || 0));
}, 0);

const buildProcessingSteps = ({ status, logs, visibleClips, processingMedia, t }) => {
  status = normalizeStatus(status);
  const hasLog = (regex) => logs.some((line) => regex.test(normalizeLogLine(line)));
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
      label: t('common.processStarted','Processus demarré'),
      description: processStarted ? t('common.workflowStarted','Le workflow a bien ete lance.') : t('common.processWait','En attente de lancement.'),
      state: processStarted ? 'done' : 'pending',
    },
    {
      key: 'source',
      label: processingMedia?.type === 'file' ? t('common.fileReceived','Reception de la video') : t('common.fileDownloaded','Telechargement de la video'),
      description: sourceReady
        ? t('common.processReady','La source est prete pour le traitement.')
        : t('common.processGo','Preparation de la source en cours.'),
      state: sourceReady ? 'done' : processStarted ? 'active' : 'pending',
    },
    {
      key: 'transcript',
      label: t('common.processTranscript','Generation de la transcription'),
      description: transcriptReady
        ? t('common.processTranscriptOk','La transcription est disponible pour l’analyse.')
        : t('common.processTranscriptPending','Transcription audio en cours.'),
      state: transcriptReady ? 'done' : sourceReady && status === 'processing' ? 'active' : 'pending',
    },
    {
      key: 'detect',
      label: t('common.processReel','Detection du nombre de reels a creer'),
      description: reelsDetected
        ? `${detectedCount || generatedCount} ${t('common.processReelCreate','reel(s) identifies pour la generation.')}`
        : t('common.processReelText','L’IA determine encore les meilleurs moments.'),
      state: reelsDetected ? 'done' : transcriptReady && status === 'processing' ? 'active' : 'pending',
    },
    {
      key: 'create',
      label: t('common.processReelTextOk','Creation des reels'),
      description: status === 'complete'
        ? `${generatedCount} ${t('common.processReelTextFinished','reel(s) finalises et prets au telechargement.')}`
        : generatedCount > 0
          ? `${generatedCount} ${t('common.processReelCurrent','reel(s) deja generes.')}`
          : t('common.processReelPending','Generation des reels en cours.'),
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
  return <Clock3 size={16} className="text-slate-400 dark:text-zinc-500" />;
};

const ProcessingChecklist = ({ status, logs, visibleClips, processingMedia }) => {
  const { t } = useTranslation();
  const steps = buildProcessingSteps({ status, logs, visibleClips, processingMedia, t });
  const doneCount = steps.filter((step) => step.state === 'done').length;
  const totalCount = steps.length;
  const progressPercent = Math.round((doneCount / totalCount) * 100);

  return (
    <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/[0.03] p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">{t("reels.processFollowup","Suivi du processus")}</p>
          <h3 className="title-contrast mt-1 text-lg font-bold">{t("reels.reelGeneration","Generation des reels")}</h3>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-slate-300 dark:border-white/10 bg-black/20 px-3 py-1.5 text-xs text-slate-700 dark:text-zinc-300">
          <Activity size={14} className={status === 'processing' ? 'text-primary animate-pulse' : 'text-slate-500 dark:text-zinc-400'} />
          <span>{getProcessLabel(status)}</span>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-slate-300 dark:border-white/10 bg-black/20 p-3">
        <div className="mb-2 flex items-center justify-between text-xs">
          <span className="text-slate-500 dark:text-zinc-400">Progression</span>
          <span className="font-medium text-zinc-200">{doneCount}/{totalCount} {t("reel.step","étapes")} ({progressPercent}%)</span>
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
          <div key={step.key} className="flex items-start gap-3 rounded-xl border border-slate-200 dark:border-white/5 bg-black/20 px-4 py-3">
            <div className="mt-0.5 shrink-0">
              <StepStatusIcon state={step.state} />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white">{step.label}</p>
              <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-zinc-400">{step.description}</p>
            </div>
          </div>
        ))}
      </div>

    </section>
  );
};

const GeneratedClipsList = ({ clips, status }) => {
  const { t } = useTranslation();
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
          <div key={`${clip?.reel_id || clip?.video_url || 'clip'}-${index}`} className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/[0.03] p-4">
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
                <p className="mt-2 text-xs leading-5 text-slate-500 dark:text-zinc-400">
                  {duration ? `${duration}s • ` : ''}
                  {status === 'complete' ? t('reels.readyToDownload','Pret pour telechargement et edition') : t('reels.generateReel','Reel genere pendant le traitement.')}
                </p>
              </div>

              {clip?.video_url && (
                <a
                  href={getApiUrl(clip.video_url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-zinc-200 transition hover:bg-white/10"
                >
                  <Download size={14} />
                  {t('reels.download','Télécharger')}
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
  const { t } = useTranslation();
  if (status === 'processing') {
    return (
        <div className="h-full flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 dark:border-white/10 bg-black/20 px-6 py-10 text-slate-400 dark:text-zinc-500 space-y-4">
          <div className="w-12 h-12 rounded-full border-2 border-zinc-800 border-t-primary animate-spin" />
          <p className="text-sm text-center">{t("reels.reelShowed","Les reels apparaitront ici au fur et a mesure de la generation.")}</p>
        </div>
    );
  }
  if (status === 'error') {
    return (
        <div className="h-full flex flex-col items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/5 px-6 py-10 text-red-400 space-y-2">
          <p>{t("reels.processError","La generation a rencontre une erreur.")}</p>
        </div>
    );
  }
  return (
    <div className="h-full flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 dark:border-white/10 bg-black/20 px-6 py-10 text-slate-400 dark:text-zinc-500 space-y-2">
      <Film size={22} className="text-zinc-600" />
      <p className="text-sm">{t("reels.noReelsGenerated","Aucun reel genere pour le moment.")}</p>
    </div>
  );
};

const Sidebar = ({ currentTab, onNavigate }) => (
    <div className="w-20 lg:w-64 bg-surface border-r border-slate-200 dark:border-white/5 flex flex-col h-full shrink-0 transition-all duration-300">
      <div className="p-6 flex items-center gap-3">
        <div className="w-8 h-8 bg-white/5 rounded-lg flex items-center justify-center shrink-0 overflow-hidden border border-slate-200 dark:border-white/5">
          <img src="/logo.png" alt="Logo" className="w-full h-full object-cover" />
        </div>
        <span className="font-bold text-lg text-white hidden lg:block tracking-tight">Vireel</span>
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

    </div>
);


const pollJob = async (jobId, userId = "") => {
  try {
    const headers = userId ? { "X-User-Id": userId } : undefined;
    const res = await fetch(getApiUrl(`/api/status/${jobId}`), headers ? { headers } : undefined);
    if (!res.ok) {
      throw new Error(`Status check failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
  } catch (e) {
    throw e;
  }
};

function App({ activeTab = "reel-generator", embedded = false } = {}) {

  const { user } = useAuth();
  const { credits } = useUserCredits();
  const { t } = useTranslation();

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

  const hasAnyReelCredit = Number(credits || 0) > 0;

  const handleClipPlay = (startTime) => {
    setSyncedTime(startTime);
    setIsSyncedPlaying(true);
    setSyncTrigger(prev => prev + 1);
  };

  const navigate = useNavigate();
  const location = useLocation();
  const currentTab = activeTab;
  const searchParams = new URLSearchParams(location.search);
  const forceNewOperation = searchParams.get('new') === '1';
  const projectId = searchParams.get('project_id') || '';

  const handleClipPause = () => setIsSyncedPlaying(false);

  // Session Recovery: Restore on mount unless user explicitly requests a fresh start.
  useEffect(() => {
    if (currentTab !== 'reel-generator') return;
    if (forceNewOperation) {
      localStorage.removeItem(SESSION_KEY);
      setStatus('idle');
      setJobId(null);
      setResults(null);
      setPartialClips([]);
      setLogs([]);
      setProcessingMedia(null);
      setShowCompletionPanel(false);
      setHasNotifiedCompletion(false);
      return;
    }

    if (projectId && user?.id) {
      let cancelled = false;
      const restoreProjectJob = async () => {
        try {
          const response = await fetch(getApiUrl(`/api/projects/${projectId}/job`), {
            headers: { 'X-User-Id': user.id },
          });
          const payload = await response.json().catch(() => ({}));
          if (cancelled) return;
          if (!response.ok) {
            // Fallback for older backend versions where /projects/{id}/job may not exist yet.
            const projectResp = await fetch(getApiUrl(`/api/projects/${projectId}`), {
              headers: { 'X-User-Id': user.id },
            });
            const projectPayload = await projectResp.json().catch(() => ({}));
            if (cancelled) return;
            if (!projectResp.ok) {
              setStatus('error');
              setJobId(null);
              setResults(null);
              setPartialClips([]);
              setLogs([projectPayload?.detail || payload?.detail || 'Project not found']);
              setProcessingMedia({ type: 'url', payload: '' });
              return;
            }

            const projectStatus = normalizeStatus(projectPayload?.status || 'processing');
            if (projectStatus === 'complete') {
              navigate(`/dashboard/reels/projects/${projectId}`);
              return;
            }
            setJobId(null);
            setResults(null);
            setPartialClips([]);
            setStatus(projectStatus === 'error' ? 'error' : 'processing');
            setLogs(
              projectStatus === 'error'
                ? ['Le projet a echoue. Consultez les details de traitement.']
                : ['Traitement du projet en cours...']
            );
            setProcessingMedia({ type: 'url', payload: '' });
            return;
          }

          const linkedJob = payload?.job || null;
          if (linkedJob?.id) {
            setJobId(String(linkedJob.id));
            setStatus(normalizeStatus(linkedJob.status || payload?.project_status || 'processing'));
            setLogs(Array.isArray(linkedJob.logs) ? linkedJob.logs : []);
            setResults(linkedJob.result || null);
            setPartialClips(Array.isArray(linkedJob.partialClips) ? linkedJob.partialClips : []);
          } else {
            const projectStatus = normalizeStatus(payload?.project_status || 'processing');
            if (projectStatus === 'complete') {
              navigate(`/dashboard/reels/projects/${projectId}`);
              return;
            }
            setJobId(null);
            setStatus(projectStatus === 'error' ? 'error' : 'processing');
            setResults(null);
            setPartialClips([]);
            setLogs(
              projectStatus === 'error'
                ? ['Le projet a echoue. Consultez les details de traitement.']
                : ['Traitement du projet en cours...']
            );
          }
          setProcessingMedia({ type: 'url', payload: '' });
        } catch {
          if (cancelled) return;
          setStatus('error');
          setJobId(null);
          setResults(null);
          setPartialClips([]);
          setLogs(['Unable to recover this project job state.']);
          setProcessingMedia({ type: 'url', payload: '' });
        }
      };

      restoreProjectJob();
      return () => {
        cancelled = true;
      };
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
  }, [currentTab, forceNewOperation, projectId, user?.id, navigate]);

  // Session Recovery: Save state changes
  useEffect(() => {
    if (projectId) {
      return;
    }
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
   }, [jobId, uiStatus, activeTab, processingMedia, results, projectId, status]);


  useEffect(() => {
    let interval = null;
    
    // Poll while processing; transition to complete only when final payload is available.
    if (uiStatus === 'processing' && jobId) {
      // Create interval immediately
      interval = setInterval(async () => {
        try {
          const data = await pollJob(jobId, user?.id || "");
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
  }, [uiStatus, jobId, user?.id]);

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
    if (!hasAnyReelCredit) {
      setStatus('idle');
      const message = t("common.insufficientCreditsStart", "Crédits insuffisants pour initier cette opération.");
      setLogs([message]);
      globalThis.alert(message);
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
        let errDetail = errText;
        try {
          const parsed = JSON.parse(errText);
          errDetail = parsed?.detail || errText;
        } catch {
          // Keep raw text when response is not JSON.
        }
        if (res.status === 402) {
          const creditMessage = errDetail || t('reels.shareDisabledInsufficient', 'Insufficient credits. Sharing is disabled.');
          setStatus('idle');
          setLogs([creditMessage]);
          globalThis.alert(creditMessage);
          return;
        }
        throw new Error(errDetail);
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
        userId={user?.id || ""}
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

          {currentTab === 'reel-generator' && (
              <div className="flex-1 overflow-y-auto p-8 space-y-6">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <h1 className="text-3xl font-black tracking-tight">{t('app.reelGenerator', 'Reel generation')}</h1>
                  <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">{t('app.dropVideo', 'Drop your long-form video below to instantly generate viral clips with AI.')}</p>
                </div>

                  <button
                      type="button"
                      onClick={() => navigate("/dashboard/reels")}
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                  >
                    <ArrowLeft size={14} />
                    {t("app.backToList", "Back to list")}
                  </button>

              </div>

             </div>
          )}

        </header>

        {/* Main Workspace */}
        <div className="flex-1 overflow-hidden relative">

          {/* View: Settings */}
          {currentTab === 'settings' && (
              <SettingsPage />
          )}


          {/* View: Dashboard (Idle) */}
          {currentTab === 'reel-generator' && uiStatus === 'idle' && !projectId && (
              <div className="flex-1 overflow-y-auto px-8 pb-8 pt-2 space-y-2 animate-[fadeIn_0.3s_ease-out]">
                <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                  <MediaInput
                    onProcess={handleProcess}
                    isProcessing={uiStatus === 'processing'}
                    isCreditBlocked={!hasAnyReelCredit}
                    disableActions={!hasAnyReelCredit}
                    creditWarning={!hasAnyReelCredit ? t("common.insufficientCreditsStart", "Crédits insuffisants pour initier cette opération.") : ""}
                  />
                </section>
              </div>
          )}

          {currentTab === 'reel-generator' && uiStatus === 'idle' && !!projectId && (
              <div className="flex-1 overflow-y-auto p-8 animate-[fadeIn_0.3s_ease-out]">
                <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5">
                  <span className="inline-flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
                    <Loader2 size={14} className="animate-spin" />
                    Chargement du projet...
                  </span>
                </section>
              </div>
          )}

          {/* View: Processing / Results (Split View) */}
          {currentTab === 'reel-generator' && (
            uiStatus === 'processing' || uiStatus === 'complete' || uiStatus === 'error'
          ) && (
              <div className="h-full flex flex-col animate-[fadeIn_0.3s_ease-out]">
                <div className="flex-1 flex flex-col md:flex-row min-h-0">

                  {/* Left Panel */}
                  <div className={`${uiStatus === 'complete' ? 'w-full md:w-[32%] lg:w-[28%]' : 'w-full md:w-[48%] lg:w-[44%]'} h-full flex flex-col border-r border-slate-200 dark:border-white/5 bg-black/20 p-6 overflow-y-auto custom-scrollbar transition-all duration-700 ease-in-out`}>
                    <div className="mb-6 flex items-center justify-between">
                      <h2 className="text-lg font-semibold flex items-center gap-2">
                        <Activity className={`text-primary ${uiStatus === 'processing' ? 'animate-pulse' : ''}`} size={20} />
                        {t('reel.videoScan', 'Scan de la vidéo')}
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
                      <div className="flex-1 flex items-center justify-center rounded-2xl border border-dashed border-slate-300 dark:border-white/10 bg-black/20 px-6 py-10 text-center text-slate-500 dark:text-zinc-400">
                        {uiStatus === 'processing'
                          ? t("reels.reelGenerationProgress","Generation en cours. La vue source n’est plus disponible, mais le suivi du workflow continue a droite.")
                          : t("reels.reelGenerationComplete","Le rendu est termine. Consulte les reels generes dans le panneau de droite.")}
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
                        {t('app.generatedReels', 'Generated reels')}
                        {visibleClips.length > 0 && (
                          <span className="text-xs bg-white/10 text-white px-2 py-0.5 rounded-full ml-auto">
                            {visibleClips.length} Clips
                          </span>
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
                                index={Number.isFinite(Number(clip?.reel_clip_index)) ? Number(clip.reel_clip_index) : i}
                                jobId={jobId}
                                onPlay={(time) => handleClipPlay(time)}
                                onPause={handleClipPause}
                                compactActions={true}
                                hideVideoPreview
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
                  <div className="border-t border-slate-300 dark:border-white/10 bg-background/95 px-6 py-4 backdrop-blur-md">
                    <div className="mx-auto flex max-w-6xl flex-col gap-4 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/[0.03] p-4 md:flex-row md:items-center md:justify-between">
                      <div className="flex items-start gap-3">
                        <div className={`mt-0.5 inline-flex h-10 w-10 items-center justify-center rounded-xl ${uiStatus === 'complete' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                          {uiStatus === 'complete' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-white">
                            {uiStatus === 'complete' ? 'Generation terminee' : 'Generation interrompue'}
                          </p>
                          <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-zinc-400">
                            {uiStatus === 'complete'
                              ? `${results?.clips?.length || visibleClips.length} ${t('reels.readyReels', 'reel(s) sont prets. Tu peux les telecharger, les modifier ou lancer une nouvelle operation.')}`
                              : t('reels.reelGenerationFailed', 'Une erreur a ete detectee pendant le workflow. Tu peux fermer ce panneau puis relancer une generation.')}
                          </p>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-3">
                        <button
                          type="button"
                          onClick={() => setShowCompletionPanel(false)}
                          className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-4 py-2 text-sm text-zinc-200 transition hover:bg-white/10"
                        >
                          <X size={14} />
                          {t('app.close', 'Close')}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            localStorage.removeItem(SESSION_KEY);
                            setStatus('idle');
                            setJobId(null);
                            setResults(null);
                            setPartialClips([]);
                            setLogs([]);
                            setProcessingMedia(null);
                            setShowCompletionPanel(false);
                            setHasNotifiedCompletion(false);
                            navigate('/dashboard/reel-generator');
                          }}
                          className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500"
                        >
                          {t('app.newOperationAction', 'New operation')}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
          )}

          {currentTab === 'reel-generator' && uiStatus !== 'idle' && uiStatus !== 'processing' && uiStatus !== 'complete' && uiStatus !== 'error' && (
            <div className="h-full flex items-center justify-center p-6">
              <div className="max-w-lg w-full rounded-2xl border border-slate-300 dark:border-white/10 bg-white/[0.03] p-6 text-center">
                <p className="text-sm text-slate-700 dark:text-zinc-300">{t('app.statusUnknown', 'Unknown generation status:')} <span className="font-mono text-white">{String(status)}</span></p>
                <button
                  type="button"
                  onClick={() => {
                    localStorage.removeItem(SESSION_KEY);
                    setStatus('idle');
                    setJobId(null);
                    setResults(null);
                    setPartialClips([]);
                    setLogs([]);
                    setProcessingMedia(null);
                    setShowCompletionPanel(false);
                    setHasNotifiedCompletion(false);
                    navigate('/dashboard/reel-generator');
                  }}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500"
                >
                  {t('app.resetView', 'Reset view')}
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
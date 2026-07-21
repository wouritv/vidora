import React, { useState, useEffect } from 'react';
import {
  Sparkles, ChevronDown, Activity,
  Terminal, Globe, Calendar, Instagram, Youtube, ArrowLeft
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
  if (status === 'processing') return 'bg-primary/10 border-primary/20 text-primary';
  if (status === 'complete') return 'bg-green-500/10 border-green-500/20 text-green-400';
  return 'bg-red-500/10 border-red-500/20 text-red-400';
};


const EmptyResultsState = ({ status }) => {
  if (status === 'processing') {
    return (
        <div className="h-full flex flex-col items-center justify-center text-zinc-500 space-y-4 opacity-50">
          <div className="w-12 h-12 rounded-full border-2 border-zinc-800 border-t-primary animate-spin" />
          <p className="text-sm">Waiting for clips...</p>
        </div>
    );
  }
  if (status === 'error') {
    return (
        <div className="h-full flex flex-col items-center justify-center text-red-400 space-y-2">
          <p>Generation failed.</p>
        </div>
    );
  }
  return null;
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
      console.error(`Status check failed: ${res.status} ${res.statusText}`);
      throw new Error(`Status check failed: ${res.status} ${res.statusText}`);
    }
    const data = await res.json();
    console.debug(`[Poll] Job ${jobId}: status=${data.status}, logsCount=${data.logs?.length || 0}`);
    return data;
  } catch (e) {
    console.error('Poll request error:', e.message);
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
  const [logsVisible, setLogsVisible] = useState(true);
  const [processingMedia, setProcessingMedia] = useState(null);
  const [showScheduleWeek, setShowScheduleWeek] = useState(false);

  const [syncedTime, setSyncedTime] = useState(0);
  const [isSyncedPlaying, setIsSyncedPlaying] = useState(false);
  const [syncTrigger, setSyncTrigger] = useState(0);
  const [hasNotifiedCompletion, setHasNotifiedCompletion] = useState(false);

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
        setStatus(session.status === 'processing' ? 'processing' : session.status);
        setSessionRecovered(true);
        setTimeout(() => setSessionRecovered(false), 5000);
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
      localStorage.setItem(SESSION_KEY, JSON.stringify({
        jobId,
        status,
        results,
        processingMedia: processingMedia?.type === 'url' ? processingMedia : null,
        activeTab,
        timestamp: Date.now()
      }));
    } catch (e) {
      // localStorage full or serialization error
      // Try to clear space by removing other sessions
      console.warn("localStorage write failed:", e.message);
      if (e.name === 'QuotaExceededError') {
        try {
          const keys = Object.keys(localStorage);
          keys.forEach(key => {
            if (key !== SESSION_KEY && (key.startsWith('openshorts_') || key.startsWith('supabase'))) {
              localStorage.removeItem(key);
            }
          });
          // Try again after cleanup
          localStorage.setItem(SESSION_KEY, JSON.stringify({
            jobId,
            status,
            results,
            processingMedia: processingMedia?.type === 'url' ? processingMedia : null,
            activeTab,
            timestamp: Date.now()
          }));
        } catch (e2) {
          console.error("Failed to recover from localStorage quota:", e2);
        }
      }
    }
   }, [jobId, status, results, activeTab]);


  useEffect(() => {
    let interval = null;
    
    // Only poll if we're actively processing or have just completed
    if ((status === 'processing' || status === 'complete') && jobId) {
      console.log(`[Polling] Starting poll for job ${jobId}, status=${status}`);
      // Create interval immediately
      interval = setInterval(async () => {
        try {
          const data = await pollJob(jobId);

          // Update partial clips during processing
          if (data.partialClips && data.partialClips.length > 0) {
            console.debug(`[Polling] Got ${data.partialClips.length} partial clips`);
            setPartialClips(data.partialClips);
          }

          // Update final results when complete
          if (data.result) {
            console.debug(`[Polling] Got result with ${data.result.clips?.length || 0} clips`);
            setResults(data.result);
            setPartialClips([]);  // Clear partial clips once we have final result
          }

          if (data.status === 'completed') {
            console.log(`[Polling] Job completed, stopping poll`);
            setStatus('complete');
            if (interval) clearInterval(interval);
          } else if (data.status === 'failed') {
            console.error(`[Polling] Job failed`);
            setStatus('error');
            const errorMsg = data.error || (data.logs?.length > 0 ? data.logs[data.logs.length - 1] : "Process failed");
            setLogs(prev => [...prev, "Error: " + errorMsg]);
            if (interval) clearInterval(interval);
          } else if (data.logs) {
            console.debug(`[Polling] Updating logs, count=${data.logs.length}`);
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
        console.log(`[Polling] Clearing interval`);
        clearInterval(interval);
        interval = null;
      }
    };
  }, [status, jobId]);

  useEffect(() => {
    if (status !== 'complete' || hasNotifiedCompletion) return;
    if (!results?.clips?.length) return;

    const notify = () => {
      new Notification('Reels generated', {
        body: `${results.clips.length} reel(s) are ready in your gallery.`,
      });
      setHasNotifiedCompletion(true);
    };

    if (typeof window === 'undefined' || !('Notification' in window)) {
      setHasNotifiedCompletion(true);
      return;
    }

    if (Notification.permission === 'granted') {
      notify();
      return;
    }

    if (Notification.permission === 'default') {
      Notification.requestPermission().then((permission) => {
        if (permission === 'granted') notify();
        else setHasNotifiedCompletion(true);
      });
      return;
    }

    setHasNotifiedCompletion(true);
  }, [status, results, hasNotifiedCompletion]);

  const handleProcess = async (data) => {
    if (!user?.id) {
      setStatus('error');
      setLogs(["Authentication required. Please reconnect your session."]);
      return;
    }

    setHasNotifiedCompletion(false);
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
          {currentTab === 'clip-generator' && status === 'idle' && (
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
                  <MediaInput onProcess={handleProcess} isProcessing={status === 'processing'} />
                  <div className="flex items-center justify-center gap-8 text-zinc-500 text-sm">
                    <span className="flex items-center gap-2"><Youtube size={16} /> YouTube</span>
                    <span className="flex items-center gap-2"><Instagram size={16} /> Instagram</span>
                    <span className="flex items-center gap-2"><TikTokIcon size={16} /> TikTok</span>
                  </div>
                </div>
              </div>
          )}

          {/* View: Processing / Results (Split View) */}
          {currentTab === 'clip-generator' && (status === 'processing' || status === 'complete' || status === 'error') && (
              <div className="h-full flex flex-col md:flex-row animate-[fadeIn_0.3s_ease-out]">

                {/* Left Panel */}
                <div className={`${status === 'complete' ? 'w-full md:w-[30%] lg:w-[25%]' : 'w-full md:w-[55%] lg:w-[60%]'} h-full flex flex-col border-r border-white/5 bg-black/20 p-6 overflow-y-auto custom-scrollbar transition-all duration-700 ease-in-out`}>
                  <div className="mb-6 flex items-center justify-between">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                      <Activity className={`text-primary ${status === 'processing' ? 'animate-pulse' : ''}`} size={20} />
                      Live Analysis
                    </h2>
                    <span className={`text-xs px-2 py-1 rounded-full border ${getStatusBadgeClass(status)}`}>
                  {status.toUpperCase()}
                </span>
                  </div>

                  {processingMedia && (
                      <ProcessingAnimation
                          media={processingMedia}
                          isComplete={status === 'complete'}
                          syncedTime={syncedTime}
                          isSyncedPlaying={isSyncedPlaying}
                          syncTrigger={syncTrigger}
                      />
                  )}

                  <div className={`bg-[#0c0c0e] rounded-xl border border-white/10 overflow-hidden flex flex-col transition-all duration-500 ${status === 'complete' ? 'h-32 min-h-0 opacity-50 hover:opacity-100' : 'flex-1 min-h-[200px]'}`}>
                    <div className="px-4 py-2 border-b border-white/5 flex items-center justify-between bg-white/5 shrink-0">
                  <span className="text-xs font-mono text-zinc-400 flex items-center gap-2">
                    <Terminal size={12} /> System Logs
                  </span>
                      <button onClick={() => setLogsVisible(!logsVisible)} className="text-zinc-500 hover:text-white transition-colors">
                        <ChevronDown size={14} className={logsVisible ? '' : 'rotate-180'} />
                      </button>
                    </div>
                    {logsVisible && (
                        <div className="flex-1 p-4 overflow-y-auto font-mono text-xs space-y-1.5 custom-scrollbar text-zinc-400">
                          {logs.map((log, i) => (
                              <div
                                  // eslint-disable-next-line react/no-array-index-key
                                  key={i}
                                  className={`flex gap-2 ${log.toLowerCase().includes('error') ? 'text-red-400' : 'text-zinc-400'}`}
                              >
                                <span className="text-zinc-700 shrink-0">{new Date().toLocaleTimeString()}</span>
                                <span>{log}</span>
                              </div>
                          ))}
                          {status === 'processing' && <div className="animate-pulse text-primary/70">_</div>}
                        </div>
                    )}
                  </div>
                </div>

                {/* Right Panel */}
                <div className={`${status === 'complete' ? 'w-full md:w-[70%] lg:w-[75%]' : 'w-full md:w-[45%] lg:w-[40%]'} h-full flex flex-col bg-background p-6 transition-all duration-700 ease-in-out`}>
                   <h2 className="text-lg font-semibold mb-6 flex items-center gap-2 shrink-0">
                     <Sparkles className="text-yellow-400" size={20} />
                     Generated Shorts
                     {(results?.clips?.length > 0 || partialClips.length > 0) && (
                         <span className="text-xs bg-white/10 text-white px-2 py-0.5 rounded-full ml-auto">
                     {(results?.clips?.length || partialClips.length)} Clips
                   </span>
                     )}
                    {results?.cost_analysis && (
                        <span className="text-xs bg-green-500/10 border border-green-500/20 text-green-400 px-2 py-0.5 rounded-full ml-2" title={`Input: ${results.cost_analysis.input_tokens} | Output: ${results.cost_analysis.output_tokens}`}>
                    ${results.cost_analysis.total_cost.toFixed(5)}
                  </span>
                    )}
                    {results?.clips?.length > 1 && status === 'complete' && (
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
                     {(results?.clips?.length > 0 || partialClips.length > 0) ? (
                         <div className={`grid gap-4 pb-10 ${status === 'complete' ? 'grid-cols-1 xl:grid-cols-2' : 'grid-cols-1'}`}>
                           {(results?.clips || partialClips).map((clip, i) => (
                                <ResultCard
                                    // eslint-disable-next-line react/no-array-index-key
                                    key={i}
                                    clip={clip}
                                    index={i}
                                    jobId={jobId}
                                    onPlay={(time) => handleClipPlay(time)}
                                    onPause={handleClipPause}
                                />
                           ))}
                         </div>
                     ) : (
                         <EmptyResultsState status={status} />
                     )}
                   </div>
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
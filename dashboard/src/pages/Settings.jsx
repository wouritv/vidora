import React, { useEffect, useMemo, useState } from 'react';
import {
  User, Mail, Copy, Check, Moon, Sun, Monitor, Linkedin, Twitch, Youtube, Facebook, Instagram,
  CreditCardIcon, History, Plus, Minus, Loader2, AlertTriangle, Coins, PauseCircle, PlayCircle, RefreshCw
} from 'lucide-react';
import { useAuth } from '../state/AuthContext';
import { useTheme } from '../state/ThemeContext';
import { useUserCredits } from '../state/UserCreditsContext';
import ServiceUsage from "../components/ServiceUsage.jsx";
import { getApiUrl } from '../config';
import { getAuthHeaders } from '../lib/apiAuth';
import { useTranslation } from '../state/LanguageContext';

const SOCIAL_NETWORKS = [
  {
    id: 'linkedin',
    name: 'LinkedIn',
    icon: Linkedin,
    color: 'from-blue-600 to-blue-400',
    description: 'Share your professional network',
  },
  {
    id: 'tiktok',
    name: 'TikTok',
    icon: Twitch,
    color: 'from-gray-900 to-black',
    description: 'Reach millions of viewers',
  },
  {
    id: 'youtube',
    name: 'YouTube',
    icon: Youtube,
    color: 'from-red-600 to-red-400',
    description: 'Upload to your channel',
  },
  {
    id: 'facebook',
    name: 'Facebook',
    icon: Facebook,
    color: 'from-blue-600 to-blue-400',
    description: 'Share with your community',
  },
  {
    id: 'instagram',
    name: 'Instagram',
    icon: Instagram,
    color: 'from-pink-600 to-orange-400',
    description: 'Post to your feed',
  },
];

export default function SettingsPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();
  const { credits, creditMax, refresh: refreshCredits } = useUserCredits();

  const [displayName, setDisplayName] = useState(user?.user_metadata?.display_name || user?.email?.split('@')[0] || '');
  const [email] = useState(user?.email || '');
  const [userId] = useState(user?.id || '');
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
  const [connectedNetworks, setConnectedNetworks] = useState({});
  const [socialAccounts, setSocialAccounts] = useState([]);
  const [oauthLoading, setOauthLoading] = useState({});
  const [socialError, setSocialError] = useState('');

  // Credit history state
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const HISTORY_PAGE_SIZE = 10;

  // Buy credits state
  const [buyAmount, setBuyAmount] = useState(5);
  const [buyLoading, setBuyLoading] = useState(false);
  const [buyError, setBuyError] = useState('');
  const CREDIT_RATE = 100; // 1 EUR = 100 credits

  // Subscription management state
  const [subscription, setSubscription] = useState(null);
  const [subscriptionHistory, setSubscriptionHistory] = useState([]);
  const [subPlans, setSubPlans] = useState([]);
  const [selectedPlan, setSelectedPlan] = useState('');
  const [subLoading, setSubLoading] = useState(false);
  const [subActionLoading, setSubActionLoading] = useState('');
  const [subError, setSubError] = useState('');
  const [subMessage, setSubMessage] = useState('');

  const creditsToAdd = Math.round(buyAmount * CREDIT_RATE);
  const canBuyCredits = Boolean(subscription);

  const accountByPlatform = useMemo(() => {
    const next = {};
    for (const account of socialAccounts) {
      if (account?.platform && !next[account.platform]) {
        next[account.platform] = account;
      }
    }
    return next;
  }, [socialAccounts]);

  const planNameById = useMemo(() => {
    const next = {};
    for (const plan of subPlans) {
      if (plan?.id) {
        next[String(plan.id)] = plan.name || String(plan.id);
      }
    }
    return next;
  }, [subPlans]);

  const currentPlanLabel = useMemo(() => {
    if (!subscription) return t('settings.inactive', 'Inactive');
    if (subscription.abonnement_name) return subscription.abonnement_name;
    const rawId = String(subscription.abonnement || '').trim();
    return planNameById[rawId] || rawId || t('settings.active', 'Active');
  }, [subscription, planNameById, t]);

  const syncConnectedNetworksCache = (accounts) => {
    const next = {};
    for (const network of SOCIAL_NETWORKS) {
      next[network.id] = accounts.some((account) => account.platform === network.id);
    }
    setConnectedNetworks(next);
    localStorage.setItem('Vireel-connected-networks', JSON.stringify(next));
  };

  const refreshConnectedAccounts = async () => {
    if (!user?.id) return;
    try {
      setSocialError('');
      const response = await fetch(getApiUrl(`/api/social/accounts?user_id=${encodeURIComponent(user.id)}`), {
        headers: getAuthHeaders(user.id),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || t("settings.socialError","Impossible de charger les comptes sociaux."));
      }
      const data = await response.json();
      const accounts = Array.isArray(data?.accounts) ? data.accounts : [];
      setSocialAccounts(accounts);
      syncConnectedNetworksCache(accounts);
    } catch (error) {
      setSocialError(error.message || t("settings.socialError","Impossible de charger les comptes sociaux."));
      setSocialAccounts([]);
      syncConnectedNetworksCache([]);
    }
  };

  useEffect(() => {
    refreshConnectedAccounts();
  }, [user?.id]);

  // Detect credit_purchase success/cancel query param
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('credit_purchase') === 'success') {
      refreshCredits();
      loadHistory(1);
    }
  }, []);

  const loadHistory = async (page = 1) => {
    if (!user?.id) return;
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const res = await fetch(
        getApiUrl(`/api/user/history?page=${page}&page_size=${HISTORY_PAGE_SIZE}`),
        { headers: getAuthHeaders(user.id) }
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setHistory(Array.isArray(data.items) ? data.items : []);
      setHistoryTotal(data.total || 0);
      setHistoryPage(page);
    } catch (err) {
      setHistoryError(err.message || t("settings.historyError","Impossible de charger l'historique."));
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (user?.id) loadHistory(1);
  }, [user?.id]);

  const handleBuyCredits = async () => {
    if (!user?.id) return;
    setBuyLoading(true);
    setBuyError('');
    try {
      const res = await fetch(getApiUrl('/api/stripe/buy-credits'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(user.id),
          ...(user?.email ? { 'X-User-Email': user.email } : {}),
        },
        body: JSON.stringify({ amount_usd: buyAmount }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || t("abonnement.paiementError","Erreur lors du paiement"));
      if (data?.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch (err) {
      setBuyError(err.message || t("abonnement.aboError","Impossible de démarrer le paiement"));
    } finally {
      setBuyLoading(false);
    }
  };

  const historyTotalPages = Math.max(1, Math.ceil(historyTotal / HISTORY_PAGE_SIZE));

  const loadSubscriptionState = async () => {
    if (!user?.id) return;
    setSubLoading(true);
    setSubError('');
    try {
      const [currentRes, historyRes, plansRes] = await Promise.all([
        fetch(getApiUrl('/api/souscription'), { headers: getAuthHeaders(user.id) }),
        fetch(getApiUrl('/api/souscription/history'), { headers: getAuthHeaders(user.id) }),
        fetch(getApiUrl('/api/abonnements')),
      ]);

      if (currentRes.ok) {
        const data = await currentRes.json();
        setSubscription(data || null);
      } else {
        setSubscription(null);
      }

      if (historyRes.ok) {
        const data = await historyRes.json();
        const items = Array.isArray(data?.items) ? data.items : [];
        setSubscriptionHistory(items);
      } else {
        setSubscriptionHistory([]);
      }

      if (plansRes.ok) {
        const data = await plansRes.json();
        const plans = Array.isArray(data?.plans) ? data.plans : [];
        setSubPlans(plans);
      } else {
        setSubPlans([]);
      }
    } catch (err) {
      setSubError(err.message || t("settings.erreurInfo","Impossible de charger les informations abonnement"));
    } finally {
      setSubLoading(false);
    }
  };

  useEffect(() => {
    loadSubscriptionState();
  }, [user?.id]);

  const runSubAction = async (action, body = null) => {
    if (!user?.id) return;
    setSubActionLoading(action);
    setSubError('');
    setSubMessage('');
    try {
      const res = await fetch(getApiUrl(`/api/souscription/${action}`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(user.id),
          ...(user?.email ? { 'X-User-Email': user.email } : {}),
        },
        body: body ? JSON.stringify(body) : JSON.stringify({}),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || t("settings.erreurInfo","Action abonnement impossible"));
      setSubMessage(t('settings.actionSuccess', 'Action terminée avec succès.'));
      await loadSubscriptionState();
      await refreshCredits();
    } catch (err) {
      setSubError(err.message || t("settings.aboError","Erreur abonnement"));
    } finally {
      setSubActionLoading('');
    }
  };

  const handleSaveProfile = async () => {
    setIsSaving(true);
    try {
      // Save to localStorage as a fallback since we might not have direct profile updates
      localStorage.setItem('Vireel-display-name', displayName);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to save profile:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCopyUserId = () => {
    navigator.clipboard.writeText(userId);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const finalizeFacebookPageSelection = async (oauthPayload) => {
    const selectionToken = oauthPayload?.selection_token;
    const pages = Array.isArray(oauthPayload?.pages)
      ? oauthPayload.pages.filter((page) => page?.page_id)
      : [];

    if (!selectionToken || pages.length === 0) {
      throw new Error(t('settings.facebookPagesMissing', 'No Facebook page available for selection.'));
    }

    let selectedPage = pages[0];
    if (pages.length > 1) {
      const menu = pages
        .map((page, index) => `${index + 1}. ${page.page_name || page.page_id}`)
        .join('\n');
      const rawChoice = window.prompt(
        `${t('settings.selectFacebookPage', 'Select a Facebook page to connect:')}\n\n${menu}`,
        '1',
      );

      if (rawChoice === null) {
        throw new Error(t('settings.facebookSelectionCanceled', 'Facebook page selection canceled.'));
      }

      const selectedIndex = Number(rawChoice) - 1;
      if (!Number.isInteger(selectedIndex) || selectedIndex < 0 || selectedIndex >= pages.length) {
        throw new Error(t('settings.invalidFacebookPageSelection', 'Invalid Facebook page selection.'));
      }
      selectedPage = pages[selectedIndex];
    }

    const response = await fetch(getApiUrl('/api/auth/facebook/select-page'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(user.id),
      },
      body: JSON.stringify({
        selection_token: selectionToken,
        page_id: selectedPage.page_id,
      }),
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload?.detail || t('settings.facebookConnectFailed', 'Unable to connect selected Facebook page.'));
    }
  };

  const connectPlatform = async (platform) => {
    if (!user?.id) return;
    setOauthLoading((prev) => ({ ...prev, [platform]: true }));
    setSocialError('');
    try {
      const res = await fetch(getApiUrl(`/api/auth/${platform}/connect?user_id=${encodeURIComponent(user.id)}`));
      if (!res.ok) {
        throw new Error(await res.text());
      }
      const { auth_url: authUrl } = await res.json();
      if (!authUrl) throw new Error('OAuth URL missing');

      const popup = window.open(authUrl, 'oauth', 'width=600,height=700');
      if (!popup) throw new Error('Popup blocked by browser');

      await new Promise((resolve, reject) => {
        const timeoutId = window.setTimeout(() => {
          window.removeEventListener('message', handleMessage);
          reject(new Error('OAuth timeout'));
        }, 180000);

        const closePoll = window.setInterval(() => {
          if (popup.closed) {
            window.clearInterval(closePoll);
            window.clearTimeout(timeoutId);
            window.removeEventListener('message', handleMessage);
            resolve();
          }
        }, 500);

        function handleMessage(event) {
          const data = event.data || {};
          if (data.platform !== platform) return;

          if (data.type === 'oauth_page_selection') {
            window.clearInterval(closePoll);
            window.clearTimeout(timeoutId);
            window.removeEventListener('message', handleMessage);

            finalizeFacebookPageSelection(data)
              .then(() => resolve())
              .catch((error) => reject(error));
            return;
          }

          if (data.type === 'oauth_success') {
            window.clearInterval(closePoll);
            window.clearTimeout(timeoutId);
            window.removeEventListener('message', handleMessage);
            resolve();
          }
          if (data.type === 'oauth_error') {
            window.clearInterval(closePoll);
            window.clearTimeout(timeoutId);
            window.removeEventListener('message', handleMessage);
            reject(new Error(data.message || `OAuth failed for ${platform}`));
          }
        }

        window.addEventListener('message', handleMessage);
      });

      await refreshConnectedAccounts();
    } catch (error) {
      setSocialError(error.message || `Unable to connect ${platform}`);
    } finally {
      setOauthLoading((prev) => ({ ...prev, [platform]: false }));
    }
  };

  const disconnectPlatform = async (platform) => {
    if (!user?.id) return;
    setOauthLoading((prev) => ({ ...prev, [platform]: true }));
    try {
      const response = await fetch(getApiUrl(`/api/social/accounts/${platform}?user_id=${encodeURIComponent(user.id)}`), {
        method: 'DELETE',
        headers: getAuthHeaders(user.id),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Unable to disconnect ${platform}`);
      }
      await refreshConnectedAccounts();
    } catch (error) {
      setSocialError(error.message || `Unable to disconnect ${platform}`);
    } finally {
      setOauthLoading((prev) => ({ ...prev, [platform]: false }));
    }
  };

  return (
    <div className="h-full overflow-y-auto p-8 max-w-3xl mx-auto animate-[fadeIn_0.3s_ease-out]">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">{t('settings.title', 'Paramètres')}</h1>
        <p className="text-slate-500 dark:text-zinc-400 text-sm">{t('settings.subtitle', 'Gère ton compte, l\'apparence et les réseaux connectés')}</p>
      </div>

      {/* Account Section */}
      <div className="glass-panel p-6 mb-6 rounded-xl border border-slate-300 dark:border-white/10">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-blue-500/10 rounded-lg">
            <User size={20} className="text-blue-400" />
          </div>
          <h2 className="text-xl font-semibold">{t('settings.accountSettings', 'Account settings')}</h2>
        </div>

        {/* User ID */}
        <div className="mb-6 pb-6 border-b border-slate-200 dark:border-white/5">
          <label className="block text-sm font-medium text-slate-700 dark:text-zinc-300 mb-3">{t('settings.userId', 'User ID')}</label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={userId}
              disabled
              className="flex-1 px-4 py-2 bg-white/5 border border-slate-300 dark:border-white/10 rounded-lg text-slate-700 dark:text-zinc-300 text-sm"
            />
            <button
              onClick={handleCopyUserId}
              className="p-2 bg-white/10 hover:bg-white/20 border border-slate-300 dark:border-white/10 rounded-lg transition-colors"
              title={t('settings.copyUserId', 'Copy User ID')}
            >
              {copiedId ? (
                <Check size={16} className="text-green-400" />
              ) : (
                <Copy size={16} className="text-slate-500 dark:text-zinc-400" />
              )}
            </button>
          </div>
          <p className="text-xs text-slate-400 dark:text-zinc-500 mt-2">{t('settings.userIdHint', 'Your unique identifier in Vireel')}</p>
        </div>

        {/* Email */}
        <div className="mb-6 pb-6 border-b border-slate-200 dark:border-white/5">
          <label className="block text-sm font-medium text-slate-700 dark:text-zinc-300 mb-3">{t('settings.email', 'Email')}</label>
          <div className="flex items-center gap-2">
            <Mail size={16} className="text-slate-400 dark:text-zinc-500" />
            <input
              type="email"
              value={email}
              disabled
              className="flex-1 px-4 py-2 bg-white/5 border border-slate-300 dark:border-white/10 rounded-lg text-slate-700 dark:text-zinc-300 text-sm"
            />
          </div>
          <p className="text-xs text-slate-400 dark:text-zinc-500 mt-2">{t('settings.emailHint', 'Your login email address')}</p>
        </div>

        {/* Display Name */}
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-zinc-300 mb-3">{t('settings.displayName', 'Display name')}</label>
          {isEditing ? (
            <div className="flex gap-2">
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="flex-1 px-4 py-2 bg-white/10 border border-slate-400 dark:border-white/20 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
                placeholder={t('settings.displayNamePlaceholder', 'Enter your display name')}
              />
              <button
                onClick={() => setIsEditing(false)}
                className="px-4 py-2 text-white/60 hover:text-white transition-colors"
              >
                {t('common.cancel', 'Cancel')}
              </button>
              <button
                onClick={handleSaveProfile}
                disabled={isSaving}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {isSaving ? t('settings.saving', 'Saving...') : t('settings.save', 'Save')}
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between gap-2 p-3 bg-white/5 border border-slate-300 dark:border-white/10 rounded-lg">
              <input
                type="text"
                value={displayName}
                disabled
                className="flex-1 bg-transparent text-white text-sm"
              />
              <button
                onClick={() => setIsEditing(true)}
                className="px-3 py-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                {t('settings.edit', 'Edit')}
              </button>
            </div>
          )}
          {saveSuccess && (
            <p className="text-xs text-green-400 mt-2 flex items-center gap-1">
              <Check size={12} /> {t('settings.nameSaved', 'Name saved successfully')}
            </p>
          )}
        </div>
      </div>

      {/* Theme Section */}
      <div className="glass-panel p-6 mb-6 rounded-xl border border-slate-300 dark:border-white/10">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-purple-500/10 rounded-lg">
            <Moon size={20} className="text-purple-400" />
          </div>
          <h2 className="text-xl font-semibold">{t('settings.appearance', 'Appearance')}</h2>
        </div>

        <p className="text-sm text-slate-500 dark:text-zinc-400 mb-4">{t('settings.appearanceSubtitle', 'Choose how Vireel looks on your device')}</p>

        <div className="grid grid-cols-3 gap-3">
          {/* Light Theme */}
          <button
            onClick={() => setTheme('light')}
            className={`p-4 rounded-lg border-2 transition-all ${
              theme === 'light'
                ? 'border-yellow-400 bg-yellow-400/5'
                : 'border-slate-300 dark:border-white/10 hover:border-slate-400 dark:border-white/20 bg-white/5'
            }`}
          >
            <Sun size={24} className={theme === 'light' ? 'text-yellow-400' : 'text-slate-500 dark:text-zinc-400'} />
            <p className={`text-xs font-medium mt-2 ${theme === 'light' ? 'text-yellow-400' : 'text-slate-500 dark:text-zinc-400'}`}>
              {t('settings.themeLight', 'Light')}
            </p>
          </button>

          {/* Dark Theme */}
          <button
            onClick={() => setTheme('dark')}
            className={`p-4 rounded-lg border-2 transition-all ${
              theme === 'dark'
                ? 'border-blue-400 bg-blue-400/5'
                : 'border-slate-300 dark:border-white/10 hover:border-slate-400 dark:border-white/20 bg-white/5'
            }`}
          >
            <Moon size={24} className={theme === 'dark' ? 'text-blue-400' : 'text-slate-500 dark:text-zinc-400'} />
            <p className={`text-xs font-medium mt-2 ${theme === 'dark' ? 'text-blue-400' : 'text-slate-500 dark:text-zinc-400'}`}>
              {t('settings.themeDark', 'Dark')}
            </p>
          </button>

          {/* System Theme */}
          <button
            onClick={() => setTheme('system')}
            className={`p-4 rounded-lg border-2 transition-all ${
              theme === 'system'
                ? 'border-green-400 bg-green-400/5'
                : 'border-slate-300 dark:border-white/10 hover:border-slate-400 dark:border-white/20 bg-white/5'
            }`}
          >
            <Monitor size={24} className={theme === 'system' ? 'text-green-400' : 'text-slate-500 dark:text-zinc-400'} />
            <p className={`text-xs font-medium mt-2 ${theme === 'system' ? 'text-green-400' : 'text-slate-500 dark:text-zinc-400'}`}>
              {t('settings.themeSystem', 'System')}
            </p>
          </button>
        </div>
      </div>

      {/* Social Networks Section */}
      <div className="glass-panel p-6 rounded-xl border border-slate-300 dark:border-white/10">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-pink-500/10 rounded-lg">
            <Linkedin size={20} className="text-pink-400" />
          </div>
          <h2 className="text-xl font-semibold">{t('settings.connectedNetworks', 'Connected networks')}</h2>
        </div>

        <p className="text-sm text-slate-500 dark:text-zinc-400 mb-6">
          {t('settings.connectedNetworksHint', 'Configure your posting profile here. Reel posting reads connected platforms from this section.')}
        </p>

        {socialError ? (
          <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
            {socialError}
          </div>
        ) : null}


        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {SOCIAL_NETWORKS.map((network) => {
            const NetworkIcon = network.icon;
            const isConnected = Boolean(connectedNetworks[network.id]);
            const account = accountByPlatform[network.id];
            const isBusy = Boolean(oauthLoading[network.id]);

            return (
              <div
                key={network.id}
                className={`p-4 rounded-lg border-2 transition-all ${
                  isConnected
                    ? 'border-green-500/50 bg-green-500/5'
                    : 'border-slate-300 dark:border-white/10 hover:border-slate-400 dark:hover:border-white/20 bg-white/5'
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg bg-gradient-to-br ${network.color}`}>
                      <NetworkIcon size={20} className="text-white" />
                    </div>
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">{network.name}</p>
                      <p className="text-xs text-slate-600 dark:text-zinc-400">{network.description}</p>
                    </div>
                  </div>
                  {isConnected && (
                    <div className="px-2 py-1 rounded text-xs font-medium flex items-center gap-1 bg-emerald-100 dark:bg-green-500/20 border border-emerald-300 dark:border-green-500/30 text-emerald-800 dark:text-green-400">
                      <Check size={12} /> {t('settings.connected', 'Connected')}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs text-slate-600 dark:text-zinc-400 truncate">
                    {account?.platform_account_name || (isConnected ? t('settings.connected', 'Connected') : t('settings.notConnected', 'Not connected'))}
                  </p>
                  {isConnected ? (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => disconnectPlatform(network.id)}
                      className="rounded-md border border-rose-300 dark:border-red-500/30 bg-rose-100 dark:bg-red-500/10 px-2 py-1 text-xs text-rose-800 dark:text-red-300 hover:bg-rose-200 dark:hover:bg-red-500/20 disabled:opacity-60"
                    >
                      {isBusy ? '...' : t('settings.disconnect', 'Disconnect')}
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => connectPlatform(network.id)}
                      className="rounded-md bg-primary px-2 py-1 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-60"
                    >
                      {isBusy ? '...' : t('settings.connect', 'Connect')}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

      </div>

      {/* Subscription Status */}
      <div className="glass-panel p-6 rounded-xl border border-slate-300 dark:border-white/10 mt-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-cyan-500/10 rounded-lg">
            <CreditCardIcon size={20} className="text-cyan-400" />
          </div>
          <h2 className="text-xl font-semibold">{t('settings.serviceUsage', 'Credit Usage')}</h2>
        </div>
        <ServiceUsage />
      </div>

      {/* Subscription management */}
      <div className="glass-panel p-6 rounded-xl border border-slate-300 dark:border-white/10 mt-6">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <CreditCardIcon size={20} className="text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold">{t('settings.subscription', 'Subscription')}</h2>
              <p className="text-xs text-slate-500 dark:text-zinc-400">{t('settings.subscriptionSubtitle', 'Cancel, reactivate, pause, resume, or change plan.')}</p>
            </div>
          </div>
          <button
            onClick={loadSubscriptionState}
            className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-700 dark:text-zinc-300 hover:bg-white/10"
          >
            <span className="inline-flex items-center gap-1"><RefreshCw size={12} /> {t('settings.refresh', 'Refresh')}</span>
          </button>
        </div>

        {subError ? (
          <div className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
            {subError}
          </div>
        ) : null}
        {subMessage ? (
          <div className="mb-3 rounded-lg border border-green-500/30 bg-green-500/10 px-3 py-2 text-xs text-green-300">
            {subMessage}
          </div>
        ) : null}

        {subLoading ? (
            <div className="text-sm text-slate-500 dark:text-zinc-400 inline-flex items-center gap-2">
              <Loader2 size={14} className="animate-spin" /> {t('settings.loadingSubscription', 'Loading subscription...')}
          </div>
        ) : (
          <>
            <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 p-4 mb-4 text-sm">
              <p className="text-slate-700 dark:text-zinc-300">
                {t('settings.status', 'Status')}: <span className="font-semibold text-slate-900 dark:text-white">{subscription ? t('settings.active', 'Active') : t('settings.inactive', 'Inactive')}</span>
              </p>
              {subscription ? (
                <p className="text-slate-600 dark:text-zinc-400 mt-1">
                  {t('abonnement.currentPlan', 'Current plan')}: <span className="text-slate-900 dark:text-white font-medium">{currentPlanLabel}</span>
                </p>
              ) : null}
              {subscription?.payment_end_date ? (
                <p className="text-slate-600 dark:text-zinc-400 mt-1">
                  {t('settings.periodEnd', 'Period end')}: {new Date(subscription.payment_end_date).toLocaleDateString('fr-FR')}
                </p>
              ) : null}
              {subscription?.retention_deadline_at ? (
                <p className="text-amber-700 dark:text-amber-300 mt-1">
                  {t('settings.retentionUntil', 'Content retention until')}: {new Date(subscription.retention_deadline_at).toLocaleDateString('fr-FR')}
                </p>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
              <button
                onClick={() => runSubAction('cancel')}
                disabled={!subscription || subActionLoading === 'cancel'}
                className="rounded-lg border border-rose-300 dark:border-red-500/30 bg-rose-100 dark:bg-red-500/10 px-3 py-2 text-xs text-rose-800 dark:text-red-300 hover:bg-rose-200 dark:hover:bg-red-500/20 disabled:opacity-40"
              >
                {subActionLoading === 'cancel' ? '...' : t('settings.cancelRenewal', 'Cancel renewal')}
              </button>
              <button
                onClick={() => runSubAction('reactivate')}
                disabled={subActionLoading === 'reactivate'}
                className="rounded-lg border border-emerald-300 dark:border-green-500/30 bg-emerald-100 dark:bg-green-500/10 px-3 py-2 text-xs text-emerald-800 dark:text-green-300 hover:bg-emerald-200 dark:hover:bg-green-500/20 disabled:opacity-40"
              >
                {subActionLoading === 'reactivate' ? '...' : t('settings.reactivate', 'Reactivate')}
              </button>
              <button
                onClick={() => runSubAction('pause')}
                disabled={!subscription || subActionLoading === 'pause'}
                className="rounded-lg border border-amber-300 dark:border-amber-500/30 bg-amber-100 dark:bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-500/20 disabled:opacity-40"
              >
                <span className="inline-flex items-center gap-1"><PauseCircle size={12} /> {subActionLoading === 'pause' ? '...' : t('settings.pause', 'Pause')}</span>
              </button>
              <button
                onClick={() => runSubAction('resume')}
                disabled={!subscription || subActionLoading === 'resume'}
                className="rounded-lg border border-sky-300 dark:border-blue-500/30 bg-sky-100 dark:bg-blue-500/10 px-3 py-2 text-xs text-sky-800 dark:text-blue-300 hover:bg-sky-200 dark:hover:bg-blue-500/20 disabled:opacity-40"
              >
                <span className="inline-flex items-center gap-1"><PlayCircle size={12} /> {subActionLoading === 'resume' ? '...' : t('settings.resume', 'Resume')}</span>
              </button>
            </div>

            <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 p-4 mb-4">
              <p className="text-xs text-slate-600 dark:text-zinc-400 mb-2">{t('settings.changePlan', 'Change plan')}</p>
              <div className="flex flex-wrap gap-2">
                <select
                  value={selectedPlan}
                  onChange={(e) => setSelectedPlan(e.target.value)}
                  className="rounded-lg border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 px-3 py-2 text-sm text-slate-900 dark:text-white"
                >
                  <option value="">{t('settings.selectPlan', 'Select a plan')}</option>
                  {subPlans.map((plan) => (
                    <option key={plan.id} value={plan.id}>{plan.name}</option>
                  ))}
                </select>
                <button
                  onClick={() => selectedPlan && runSubAction('change-plan', { plan_id: selectedPlan })}
                  disabled={!selectedPlan || subActionLoading === 'change-plan'}
                  className="rounded-lg border border-blue-700 dark:border-primary/30 bg-blue-600 dark:bg-primary/10 px-3 py-2 text-xs text-white dark:text-primary hover:bg-blue-500 dark:hover:bg-primary/20 disabled:opacity-40"
                >
                  {subActionLoading === 'change-plan' ? '...' : t('settings.change', 'Change')}
                </button>
              </div>
            </div>

            <div className="rounded-lg border border-slate-300 dark:border-white/10 overflow-hidden">
              <div className="px-3 py-2 text-xs text-slate-500 dark:text-zinc-400 border-b border-slate-300 dark:border-white/10">{t('settings.subscriptionHistory', 'Subscription/payment history')}</div>
              {subscriptionHistory.length === 0 ? (
                <p className="px-3 py-4 text-xs text-slate-400 dark:text-zinc-500">{t('settings.noSubscriptionHistory', 'No subscription history.')}</p>
              ) : (
                <div className="max-h-48 overflow-auto">
                  <div className="space-y-2 p-2 md:hidden">
                    {subscriptionHistory.map((row) => (
                      <article key={row.id} className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 p-2 text-xs">
                        <p className="text-slate-700 dark:text-zinc-200 font-medium">{row.abonnement_name || planNameById[String(row.abonnement || '')] || row.abonnement || '-'}</p>
                        <p className="mt-1 text-slate-500 dark:text-zinc-400">{t('settings.date', 'Date')}: {row.payment_start_date ? new Date(row.payment_start_date).toLocaleDateString('fr-FR') : '-'}</p>
                        <div className="mt-1 flex items-center justify-between gap-2">
                          <span className="text-slate-600 dark:text-zinc-300">{Number(row.payment_amount || 0).toFixed(2)} $</span>
                          <span className="text-slate-500 dark:text-zinc-400">{row.payment_status || '-'}</span>
                        </div>
                      </article>
                    ))}
                  </div>

                  <table className="hidden w-full text-xs md:table">
                    <thead>
                      <tr className="text-slate-400 dark:text-zinc-500 border-b border-slate-300 dark:border-white/10">
                        <th className="px-3 py-2 text-left">{t('settings.date', 'Date')}</th>
                        <th className="px-3 py-2 text-left">{t('settings.plan', 'Plan')}</th>
                        <th className="px-3 py-2 text-right">{t('settings.amount', 'Amount')}</th>
                        <th className="px-3 py-2 text-left">{t('settings.state', 'Status')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {subscriptionHistory.map((row) => (
                        <tr key={row.id} className="border-b border-slate-200 dark:border-white/5">
                          <td className="px-3 py-2 text-slate-500 dark:text-zinc-400">{row.payment_start_date ? new Date(row.payment_start_date).toLocaleDateString('fr-FR') : '-'}</td>
                          <td className="px-3 py-2 text-slate-700 dark:text-zinc-300">{row.abonnement_name || planNameById[String(row.abonnement || '')] || row.abonnement || '-'}</td>
                          <td className="px-3 py-2 text-right text-slate-700 dark:text-zinc-300">{Number(row.payment_amount || 0).toFixed(2)} $</td>
                          <td className="px-3 py-2 text-slate-500 dark:text-zinc-400">{row.payment_status || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Buy additional credits */}
      <div className="glass-panel p-6 rounded-xl border border-slate-300 dark:border-white/10 mt-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-yellow-500/10 rounded-lg">
            <Coins size={20} className="text-yellow-400" />
          </div>
          <div>
            <h2 className="text-xl font-semibold">Recharger des crédits</h2>
            <p className="text-xs text-slate-500 dark:text-zinc-400 mt-0.5">1 EUR = {CREDIT_RATE} {t("abonnement.creditRate","crédits · solde actuel ")}: <span className="text-slate-900 dark:text-white font-medium">{credits.toLocaleString()} / {Number(creditMax || 0).toLocaleString()} cr</span></p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          {/* Quick amounts */}
          <div className="flex gap-2">
            {[5, 10, 20, 50].map((amt) => (
              <button
                key={amt}
                onClick={() => setBuyAmount(amt)}
                className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition ${
                  buyAmount === amt
                    ? 'border-amber-300 dark:border-yellow-400 bg-amber-100 dark:bg-yellow-400/10 text-amber-800 dark:text-yellow-300'
                    : 'border-slate-300 dark:border-white/10 bg-white/5 text-slate-700 dark:text-zinc-300 hover:border-slate-400 dark:hover:border-white/20'
                }`}
              >
                {amt}€
              </button>
            ))}
          </div>

          {/* Custom amount */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setBuyAmount(Math.max(1, buyAmount - 1))}
              className="p-1.5 rounded-lg bg-white/5 border border-slate-300 dark:border-white/10 hover:bg-white/10 text-slate-700 dark:text-zinc-300"
            >
              <Minus size={14} />
            </button>
            <input
              type="number"
              min="1"
              value={buyAmount}
              onChange={(e) => setBuyAmount(Math.max(1, Number(e.target.value) || 1))}
              className="w-20 px-3 py-1.5 bg-white/10 border border-slate-400 dark:border-white/20 rounded-lg text-slate-900 dark:text-white text-sm text-center focus:outline-none focus:border-yellow-500/50"
            />
            <button
              onClick={() => setBuyAmount(buyAmount + 1)}
              className="p-1.5 rounded-lg bg-white/5 border border-slate-300 dark:border-white/10 hover:bg-white/10 text-slate-700 dark:text-zinc-300"
            >
              <Plus size={14} />
            </button>
            <span className="text-slate-500 dark:text-zinc-400 text-sm">EUR</span>
          </div>

          {/* Summary + pay button */}
          <div className="ml-auto flex items-center gap-3">
            <span className="text-sm text-slate-500 dark:text-zinc-400">
              = <span className="text-amber-700 dark:text-yellow-300 font-semibold">{creditsToAdd.toLocaleString()} crédits</span>
            </span>
            <button
              onClick={handleBuyCredits}
              disabled={buyLoading || !canBuyCredits}
              className="flex items-center gap-2 px-4 py-2 bg-amber-500 border border-amber-600 hover:bg-amber-400 disabled:opacity-60 text-white dark:bg-yellow-500/20 dark:border-yellow-500/30 dark:hover:bg-yellow-500/30 dark:text-yellow-300 rounded-lg text-sm font-semibold transition"
            >
              {buyLoading ? <Loader2 size={16} className="animate-spin" /> : <CreditCardIcon size={16} />}
              {buyLoading ? 'Redirection...' : 'Payer'}
            </button>
          </div>
        </div>

        {!canBuyCredits && (
          <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
            {t('settings.activeRequiredForTopup', 'Un abonnement actif est requis pour recharger des credits.')}
          </div>
        )}

        {buyError && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
            <AlertTriangle size={14} /> {buyError}
          </div>
        )}
      </div>

      {/* Credit history */}
      <div className="glass-panel p-6 rounded-xl border border-slate-300 dark:border-white/10 mt-6 mb-8">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/10 rounded-lg">
              <History size={20} className="text-indigo-400" />
            </div>
            <h2 className="text-xl font-semibold">{t("settings.historic","Historique des opérations")}</h2>
          </div>
          <button onClick={() => loadHistory(historyPage)} className="text-xs text-slate-500 dark:text-zinc-400 hover:text-white transition">
            {t("settings.refresh","Rafraîchir")}
          </button>
        </div>

        {historyError && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
            <AlertTriangle size={14} /> {historyError}
          </div>
        )}

        {historyLoading ? (
          <div className="flex items-center gap-2 text-slate-500 dark:text-zinc-400 text-sm py-4">
            <Loader2 size={16} className="animate-spin" /> {t('app.loading', 'Chargement..')}
          </div>
        ) : history.length === 0 ? (
          <p className="text-sm text-slate-400 dark:text-zinc-500 py-4 text-center">{t('settings.noOperations', 'Aucune opération enregistrée.')}</p>
        ) : (
          <>
            <div className="overflow-x-auto rounded-lg border border-slate-300 dark:border-white/10">
              <div className="space-y-2 p-2 md:hidden">
                {history.map((row) => {
                  const isInput = row.operation === 'input';
                  return (
                    <article key={row.id} className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/5 p-2 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-slate-500 dark:text-zinc-400">
                          {new Date(row.created_at).toLocaleDateString('fr-FR', {
                            day: '2-digit', month: '2-digit', year: '2-digit',
                            hour: '2-digit', minute: '2-digit',
                          })}
                        </span>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                          isInput
                            ? 'bg-green-500/10 border border-green-500/20 text-green-400'
                            : 'bg-red-500/10 border border-red-500/20 text-red-400'
                        }`}>
                          {isInput ? <Plus size={10} /> : <Minus size={10} />}
                          {isInput ? 'Crédit' : 'Débit'}
                        </span>
                      </div>
                      <p className="mt-1 text-slate-700 dark:text-zinc-300 capitalize">{(row.operation_type || '').replace('_', ' ')}</p>
                      <div className="mt-1 flex items-center justify-between gap-2">
                        <span className={`font-mono font-semibold ${isInput ? 'text-green-400' : 'text-red-400'}`}>
                          {isInput ? '+' : '-'}{Number(row.credit).toLocaleString()} cr
                        </span>
                        <span className="font-mono text-slate-500 dark:text-zinc-400">{Number(row.storage).toFixed(3)} Go</span>
                      </div>
                    </article>
                  );
                })}
              </div>

              <table className="hidden w-full text-xs md:table">
                <thead>
                  <tr className="border-b border-slate-300 dark:border-white/10 text-slate-500 dark:text-zinc-400">
                    <th className="px-3 py-2 text-left">{t("settings.date", "Date")}</th>
                    <th className="px-3 py-2 text-left">{t("settings.type", "Type")}</th>
                    <th className="px-3 py-2 text-left">{t("settings.operation", "Opération")}</th>
                    <th className="px-3 py-2 text-right">{t("settings.credits", "Crédits")}</th>
                    <th className="px-3 py-2 text-right">{t("settings.storage", "Stockage (Go)")}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((row) => {
                    const isInput = row.operation === 'input';
                    return (
                      <tr key={row.id} className="border-b border-slate-200 dark:border-white/5 hover:bg-white/5 transition">
                        <td className="px-3 py-2 text-slate-500 dark:text-zinc-400 whitespace-nowrap">
                          {new Date(row.created_at).toLocaleDateString('fr-FR', {
                            day: '2-digit', month: '2-digit', year: '2-digit',
                            hour: '2-digit', minute: '2-digit',
                          })}
                        </td>
                        <td className="px-3 py-2">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                            isInput
                              ? 'bg-green-500/10 border border-green-500/20 text-green-400'
                              : 'bg-red-500/10 border border-red-500/20 text-red-400'
                          }`}>
                            {isInput ? <Plus size={10} /> : <Minus size={10} />}
                            {isInput ? 'Crédit' : 'Débit'}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-slate-700 dark:text-zinc-300 capitalize">{(row.operation_type || '').replace('_', ' ')}</td>
                        <td className={`px-3 py-2 text-right font-mono font-semibold ${isInput ? 'text-green-400' : 'text-red-400'}`}>
                          {isInput ? '+' : '-'}{Number(row.credit).toLocaleString()} cr
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-slate-500 dark:text-zinc-400">
                          {Number(row.storage).toFixed(3)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {historyTotalPages > 1 && (
              <div className="flex justify-center items-center gap-3 mt-4">
                <button
                  disabled={historyPage <= 1}
                  onClick={() => loadHistory(historyPage - 1)}
                  className="px-3 py-1 rounded-lg border border-slate-300 dark:border-white/10 text-xs text-slate-500 dark:text-zinc-400 hover:bg-white/10 disabled:opacity-40"
                >
                  {t("reels.previous","Précédent")}
                </button>
                <span className="text-xs text-slate-400 dark:text-zinc-500">{historyPage} / {historyTotalPages}</span>
                <button
                  disabled={historyPage >= historyTotalPages}
                  onClick={() => loadHistory(historyPage + 1)}
                  className="px-3 py-1 rounded-lg border border-slate-300 dark:border-white/10 text-xs text-slate-500 dark:text-zinc-400 hover:bg-white/10 disabled:opacity-40"
                >
                  {t("reels.next","Suivant")}
                </button>
              </div>
            )}
          </>
        )}
      </div>

    </div>
  );
}
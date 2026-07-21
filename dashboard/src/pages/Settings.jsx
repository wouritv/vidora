import React, { useState } from 'react';
import {
  User, Mail, Copy, Check, Moon, Sun, Monitor, Linkedin, Twitch, Youtube, Facebook, Instagram,
  CreditCardIcon
} from 'lucide-react';
import { useAuth } from '../state/AuthContext';
import { useTheme } from '../state/ThemeContext';
import ServiceUsage from "../components/ServiceUsage.jsx";

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
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();

  const [displayName, setDisplayName] = useState(user?.user_metadata?.display_name || user?.email?.split('@')[0] || '');
  const [email] = useState(user?.email || '');
  const [userId] = useState(user?.id || '');
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
  const [connectedNetworks, setConnectedNetworks] = useState(() => {
    const stored = localStorage.getItem('openshorts-connected-networks');
    return stored ? JSON.parse(stored) : {};
  });

  const handleSaveProfile = async () => {
    setIsSaving(true);
    try {
      // Save to localStorage as a fallback since we might not have direct profile updates
      localStorage.setItem('openshorts-display-name', displayName);
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

  const handleConnectNetwork = (networkId) => {
    setConnectedNetworks(prev => {
      const updated = {
        ...prev,
        [networkId]: !prev[networkId]
      };
      localStorage.setItem('openshorts-connected-networks', JSON.stringify(updated));
      return updated;
    });
  };

  return (
    <div className="h-full overflow-y-auto p-8 max-w-3xl mx-auto animate-[fadeIn_0.3s_ease-out]">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Settings</h1>
        <p className="text-zinc-400 text-sm">Manage your account, appearance, and connected networks</p>
      </div>

      {/* Account Section */}
      <div className="glass-panel p-6 mb-6 rounded-xl border border-white/10">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-blue-500/10 rounded-lg">
            <User size={20} className="text-blue-400" />
          </div>
          <h2 className="text-xl font-semibold">Account Settings</h2>
        </div>

        {/* User ID */}
        <div className="mb-6 pb-6 border-b border-white/5">
          <label className="block text-sm font-medium text-zinc-300 mb-3">User ID</label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={userId}
              disabled
              className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-zinc-300 text-sm"
            />
            <button
              onClick={handleCopyUserId}
              className="p-2 bg-white/10 hover:bg-white/20 border border-white/10 rounded-lg transition-colors"
              title="Copy User ID"
            >
              {copiedId ? (
                <Check size={16} className="text-green-400" />
              ) : (
                <Copy size={16} className="text-zinc-400" />
              )}
            </button>
          </div>
          <p className="text-xs text-zinc-500 mt-2">Your unique identifier in OpenShorts</p>
        </div>

        {/* Email */}
        <div className="mb-6 pb-6 border-b border-white/5">
          <label className="block text-sm font-medium text-zinc-300 mb-3">Email</label>
          <div className="flex items-center gap-2">
            <Mail size={16} className="text-zinc-500" />
            <input
              type="email"
              value={email}
              disabled
              className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-zinc-300 text-sm"
            />
          </div>
          <p className="text-xs text-zinc-500 mt-2">Your login email address</p>
        </div>

        {/* Display Name */}
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-3">Display Name</label>
          {isEditing ? (
            <div className="flex gap-2">
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="flex-1 px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
                placeholder="Enter your display name"
              />
              <button
                onClick={() => setIsEditing(false)}
                className="px-4 py-2 text-white/60 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveProfile}
                disabled={isSaving}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {isSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between gap-2 p-3 bg-white/5 border border-white/10 rounded-lg">
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
                Edit
              </button>
            </div>
          )}
          {saveSuccess && (
            <p className="text-xs text-green-400 mt-2 flex items-center gap-1">
              <Check size={12} /> Name saved successfully
            </p>
          )}
        </div>
      </div>

      {/* Theme Section */}
      <div className="glass-panel p-6 mb-6 rounded-xl border border-white/10">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-purple-500/10 rounded-lg">
            <Moon size={20} className="text-purple-400" />
          </div>
          <h2 className="text-xl font-semibold">Appearance</h2>
        </div>

        <p className="text-sm text-zinc-400 mb-4">Choose how OpenShorts looks on your device</p>

        <div className="grid grid-cols-3 gap-3">
          {/* Light Theme */}
          <button
            onClick={() => setTheme('light')}
            className={`p-4 rounded-lg border-2 transition-all ${
              theme === 'light'
                ? 'border-yellow-400 bg-yellow-400/5'
                : 'border-white/10 hover:border-white/20 bg-white/5'
            }`}
          >
            <Sun size={24} className={theme === 'light' ? 'text-yellow-400' : 'text-zinc-400'} />
            <p className={`text-xs font-medium mt-2 ${theme === 'light' ? 'text-yellow-400' : 'text-zinc-400'}`}>
              Light
            </p>
          </button>

          {/* Dark Theme */}
          <button
            onClick={() => setTheme('dark')}
            className={`p-4 rounded-lg border-2 transition-all ${
              theme === 'dark'
                ? 'border-blue-400 bg-blue-400/5'
                : 'border-white/10 hover:border-white/20 bg-white/5'
            }`}
          >
            <Moon size={24} className={theme === 'dark' ? 'text-blue-400' : 'text-zinc-400'} />
            <p className={`text-xs font-medium mt-2 ${theme === 'dark' ? 'text-blue-400' : 'text-zinc-400'}`}>
              Dark
            </p>
          </button>

          {/* System Theme */}
          <button
            onClick={() => setTheme('system')}
            className={`p-4 rounded-lg border-2 transition-all ${
              theme === 'system'
                ? 'border-green-400 bg-green-400/5'
                : 'border-white/10 hover:border-white/20 bg-white/5'
            }`}
          >
            <Monitor size={24} className={theme === 'system' ? 'text-green-400' : 'text-zinc-400'} />
            <p className={`text-xs font-medium mt-2 ${theme === 'system' ? 'text-green-400' : 'text-zinc-400'}`}>
              System
            </p>
          </button>
        </div>
      </div>

      {/* Social Networks Section */}
      <div className="glass-panel p-6 rounded-xl border border-white/10">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-pink-500/10 rounded-lg">
            <Linkedin size={20} className="text-pink-400" />
          </div>
          <h2 className="text-xl font-semibold">Connected Networks</h2>
        </div>

        <p className="text-sm text-zinc-400 mb-6">
          Connect your social media accounts to easily share your creations directly from OpenShorts.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {SOCIAL_NETWORKS.map((network) => {
            const NetworkIcon = network.icon;
            const isConnected = connectedNetworks[network.id];

            return (
              <div
                key={network.id}
                className={`p-4 rounded-lg border-2 transition-all cursor-pointer ${
                  isConnected
                    ? 'border-green-500/50 bg-green-500/5'
                    : 'border-white/10 hover:border-white/20 bg-white/5'
                }`}
                onClick={() => handleConnectNetwork(network.id)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg bg-gradient-to-br ${network.color}`}>
                      <NetworkIcon size={20} className="text-white" />
                    </div>
                    <div>
                      <p className="font-medium">{network.name}</p>
                      <p className="text-xs text-zinc-500">{network.description}</p>
                    </div>
                  </div>
                  {isConnected && (
                    <div className="px-2 py-1 bg-green-500/20 border border-green-500/30 rounded text-xs text-green-400 font-medium flex items-center gap-1">
                      <Check size={12} /> Connected
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        
      </div>

      {/* Subscription Status */}
      <div className="glass-panel p-6 rounded-xl border border-white/10 mt-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-cyan-500/10 rounded-lg">
            <CreditCardIcon size={20} className="text-cyan-400" />
          </div>
          <h2 className="text-xl font-semibold">Service Usage</h2>
        </div>
        <ServiceUsage />
      </div>


    </div>
  );
}
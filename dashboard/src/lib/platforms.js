export const SUPPORTED_SOCIAL_PLATFORMS = [
    'tiktok',
    'instagram',
    'youtube',
    'facebook',
    'linkedin',
];

export const PLATFORM_LABELS = {
    tiktok: 'TikTok',
    instagram: 'Instagram',
    youtube: 'YouTube Shorts',
    facebook: 'Facebook',
    linkedin: 'LinkedIn',
};

const CONNECTED_NETWORKS_KEY = 'openshorts-connected-networks';

/**
 * Read connected platforms from localStorage.
 *
 * @param {string[]} fallback - Returned when no platforms are enabled in settings.
 *   Defaults to [] (empty list).
 * @returns {string[]} List of enabled platform ids.
 */
export function getConnectedPlatforms(fallback = []) {
    try {
        const raw = globalThis.localStorage?.getItem(CONNECTED_NETWORKS_KEY) || '{}';
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') return fallback;
        const connected = SUPPORTED_SOCIAL_PLATFORMS.filter((p) => Boolean(parsed[p]));
        return connected.length > 0 ? connected : fallback;
    } catch {
        return fallback;
    }
}


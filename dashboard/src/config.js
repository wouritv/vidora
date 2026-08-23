// Configuration for API endpoints
// If VITE_API_URL is set (e.g. in production), use it.
// Otherwise, default to empty string which means relative paths (proxied in dev).

export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const HIDE_SOCIAL_PLATFORMS_FALLBACK = String(import.meta.env.VITE_HIDE_SOCIAL_PLATFORMS || '').toLowerCase();
const HIDE_SOCIAL_PLATFORMS_FALLBACK_ENABLED = ["1", "true", "yes", "on"].includes(HIDE_SOCIAL_PLATFORMS_FALLBACK);

let appConfigPromise;

export const getApiUrl = (path) => {
    if (path.startsWith('http')) return path;
    // Ensure path starts with / if not present
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${API_BASE_URL}${normalizedPath}`;
};

export const getDefaultHideSocialPlatforms = () => HIDE_SOCIAL_PLATFORMS_FALLBACK_ENABLED;

export const fetchAppConfig = async () => {
    if (!appConfigPromise) {
        appConfigPromise = fetch(getApiUrl('/api/config'))
            .then((response) => (response.ok ? response.json() : null))
            .catch(() => null);
    }
    return appConfigPromise;
};


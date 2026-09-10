import { getCachedAccessToken } from "./apiAuth";

/**
 * Extract the filename portion from a video URL.
 * Returns undefined for blob URLs, empty strings, or parse failures.
 *
 * @param {string} videoUrl
 * @returns {string|undefined}
 */
export function inputFilenameFromVideoUrl(videoUrl) {
    if (!videoUrl || videoUrl.startsWith('blob:')) return undefined;
    try {
        const clean = videoUrl.split('?')[0] || '';
        const filename = clean.split('/').pop();
        return filename || undefined;
    } catch {
        return undefined;
    }
}

/**
 * Return a browser-safe media URL.
 * - blob: URLs are returned as-is.
 * - Relative / same-origin URLs are returned as-is.
 * - External URLs are proxied through the backend to avoid CORS issues
 *   during browser-side Remotion rendering.
 *
 * /api/media/proxy requires an authenticated caller (see app.py's
 * proxy_media -- it's an SSRF-sensitive endpoint). This URL ends up
 * directly in <video>/<img> src attributes and Remotion inputs, which the
 * browser fetches natively without ever attaching an Authorization header,
 * so the caller's JWT is passed as a `token` query parameter instead
 * (accepted by get_user_id_header_or_query_token) -- without it, every
 * such request 401s and playback stays black.
 *
 * @param {string} videoUrl
 * @returns {string}
 */
export function toBrowserSafeMediaUrl(videoUrl) {
    if (!videoUrl) return '';
    if (videoUrl.startsWith('blob:')) return videoUrl;

    try {
        const parsed = new URL(videoUrl, window.location.origin);
        if (parsed.origin === window.location.origin) {
            return parsed.toString();
        }

        const proxyUrl = new URL('/api/media/proxy', window.location.origin);
        proxyUrl.searchParams.set('url', videoUrl);
        const accessToken = getCachedAccessToken();
        if (accessToken) proxyUrl.searchParams.set('token', accessToken);
        return proxyUrl.toString();
    } catch {
        return videoUrl;
    }
}

/**
 * Map a raw reel DB item + its resolved video URL to the shape expected
 * by <ResultCard />.
 *
 * @param {object} item - Raw reel object from the API
 * @param {string} videoUrl - Resolved playback URL
 * @returns {object}
 */
export function toResultCardClip(item, videoUrl) {
    const start = Number.isFinite(Number(item?.reel_start)) ? Number(item.reel_start) : 0;
    const fallbackDuration = Number.isFinite(Number(item?.reel_duration)) ? Number(item.reel_duration) : 30;
    const end = Number.isFinite(Number(item?.reel_end)) ? Number(item.reel_end) : start + fallbackDuration;

    return {
        start,
        end,
        reel_clip_index: Number.isFinite(Number(item?.reel_clip_index)) ? Number(item.reel_clip_index) : undefined,
        reel_job_id: typeof item?.reel_job_id === 'string' ? item.reel_job_id : '',
        video_url:
            videoUrl ||
            item?.media_url ||
            item?.reel_playback_url ||
            item?.reel_download_url ||
            item?.reel_url ||
            '',
        thumbnail_url:
            item?.reel_preview_url ||
            item?.reel_thumbnail_url ||
            '',
        preview_image_url:
            item?.reel_preview_url ||
            item?.reel_thumbnail_url ||
            '',
        video_title_for_youtube_short: item?.reel_title || 'Sans titre',
        video_description_for_tiktok: item?.reel_description || '',
        video_description_for_instagram: item?.reel_description || '',
        viral_hook_text: item?.reel_hook_text || '',
    };
}


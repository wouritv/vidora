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
        video_url:
            videoUrl ||
            item?.media_url ||
            item?.reel_playback_url ||
            item?.reel_download_url ||
            item?.reel_url ||
            '',
        video_title_for_youtube_short: item?.reel_title || 'Sans titre',
        video_description_for_tiktok: item?.reel_description || '',
        video_description_for_instagram: item?.reel_description || '',
        viral_hook_text: item?.reel_hook_text || '',
    };
}


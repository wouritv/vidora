import { describe, it, expect } from 'vitest';
import { inputFilenameFromVideoUrl, toResultCardClip } from '../clips';

describe('inputFilenameFromVideoUrl', () => {
    it('returns undefined for empty string', () => {
        expect(inputFilenameFromVideoUrl('')).toBeUndefined();
    });

    it('returns undefined for blob URLs', () => {
        expect(inputFilenameFromVideoUrl('blob:https://example.com/abc123')).toBeUndefined();
    });

    it('extracts filename from a plain URL', () => {
        expect(inputFilenameFromVideoUrl('https://cdn.example.com/videos/clip.mp4')).toBe('clip.mp4');
    });

    it('strips query string before extracting filename', () => {
        expect(inputFilenameFromVideoUrl('https://cdn.example.com/videos/clip.mp4?token=xyz')).toBe('clip.mp4');
    });

    it('returns undefined when URL has no filename part', () => {
        expect(inputFilenameFromVideoUrl('https://cdn.example.com/')).toBeUndefined();
    });
});

describe('toResultCardClip', () => {
    const BASE_ITEM = {
        reel_start: 10,
        reel_end: 45,
        reel_title: 'My Short',
        reel_description: 'Great content',
        reel_hook_text: 'Watch this!',
        media_url: 'https://cdn.example.com/media.mp4',
    };

    it('maps reel_start → start and reel_end → end', () => {
        const clip = toResultCardClip(BASE_ITEM, '');
        expect(clip.start).toBe(10);
        expect(clip.end).toBe(45);
    });

    it('prefers the explicit videoUrl over item.media_url', () => {
        const clip = toResultCardClip(BASE_ITEM, 'https://override.example.com/video.mp4');
        expect(clip.video_url).toBe('https://override.example.com/video.mp4');
    });

    it('falls back to item.media_url when videoUrl is empty', () => {
        const clip = toResultCardClip(BASE_ITEM, '');
        expect(clip.video_url).toBe('https://cdn.example.com/media.mp4');
    });

    it('uses "Sans titre" as default title', () => {
        const clip = toResultCardClip({ ...BASE_ITEM, reel_title: undefined }, '');
        expect(clip.video_title_for_youtube_short).toBe('Sans titre');
    });

    it('defaults end to start + 30 when reel_end is missing', () => {
        const clip = toResultCardClip({ reel_start: 5 }, '');
        expect(clip.start).toBe(5);
        expect(clip.end).toBe(35);
    });

    it('defaults start to 0 when reel_start is missing', () => {
        const clip = toResultCardClip({}, '');
        expect(clip.start).toBe(0);
    });

    it('copies description to both tiktok and instagram fields', () => {
        const clip = toResultCardClip(BASE_ITEM, '');
        expect(clip.video_description_for_tiktok).toBe('Great content');
        expect(clip.video_description_for_instagram).toBe('Great content');
    });

    it('maps reel_hook_text to viral_hook_text', () => {
        const clip = toResultCardClip(BASE_ITEM, '');
        expect(clip.viral_hook_text).toBe('Watch this!');
    });

    it('preserves reel_clip_index for stable API actions', () => {
        const clip = toResultCardClip({ ...BASE_ITEM, reel_clip_index: 3 }, '');
        expect(clip.reel_clip_index).toBe(3);
    });

    it('preserves reel_job_id when provided', () => {
        const clip = toResultCardClip({ ...BASE_ITEM, reel_job_id: 'job-123' }, '');
        expect(clip.reel_job_id).toBe('job-123');
    });
});


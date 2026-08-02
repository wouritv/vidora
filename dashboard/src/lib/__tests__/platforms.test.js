import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { SUPPORTED_SOCIAL_PLATFORMS, PLATFORM_LABELS, getConnectedPlatforms } from '../platforms';

describe('SUPPORTED_SOCIAL_PLATFORMS', () => {
    it('contains expected platforms', () => {
        expect(SUPPORTED_SOCIAL_PLATFORMS).toContain('tiktok');
        expect(SUPPORTED_SOCIAL_PLATFORMS).toContain('instagram');
        expect(SUPPORTED_SOCIAL_PLATFORMS).toContain('youtube');
        expect(SUPPORTED_SOCIAL_PLATFORMS).toContain('facebook');
        expect(SUPPORTED_SOCIAL_PLATFORMS).toContain('linkedin');
    });
});

describe('PLATFORM_LABELS', () => {
    it('has a label for every supported platform', () => {
        for (const platform of SUPPORTED_SOCIAL_PLATFORMS) {
            expect(PLATFORM_LABELS[platform]).toBeTruthy();
        }
    });
});

describe('getConnectedPlatforms', () => {
    const KEY = 'openshorts-connected-networks';

    afterEach(() => {
        localStorage.removeItem(KEY);
    });

    it('returns the fallback when localStorage is empty', () => {
        expect(getConnectedPlatforms(['tiktok'])).toEqual(['tiktok']);
    });

    it('returns [] (default fallback) when nothing is stored and no fallback given', () => {
        expect(getConnectedPlatforms()).toEqual([]);
    });

    it('returns only enabled platforms', () => {
        localStorage.setItem(KEY, JSON.stringify({ tiktok: true, instagram: false, youtube: true }));
        const result = getConnectedPlatforms();
        expect(result).toContain('tiktok');
        expect(result).toContain('youtube');
        expect(result).not.toContain('instagram');
    });

    it('returns the fallback when all stored platforms are disabled', () => {
        localStorage.setItem(KEY, JSON.stringify({ tiktok: false, instagram: false }));
        expect(getConnectedPlatforms(['youtube'])).toEqual(['youtube']);
    });

    it('ignores unsupported platform keys in storage', () => {
        localStorage.setItem(KEY, JSON.stringify({ tiktok: true, unsupported_platform: true }));
        const result = getConnectedPlatforms();
        expect(result).not.toContain('unsupported_platform');
        expect(result).toContain('tiktok');
    });

    it('returns fallback when stored JSON is malformed', () => {
        localStorage.setItem(KEY, 'not-json{{{');
        expect(getConnectedPlatforms(['instagram'])).toEqual(['instagram']);
    });
});


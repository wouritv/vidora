import { beforeEach, describe, expect, it } from 'vitest';
import {
    getConnectedPlatforms,
    PLATFORM_LABELS,
    SUPPORTED_SOCIAL_PLATFORMS,
} from '../platforms';

const STORAGE_KEY = 'Vireel-connected-networks';

describe('platforms', () => {
    beforeEach(() => {
        const memory = new Map();
        globalThis.localStorage = {
            getItem: (key) => (memory.has(key) ? memory.get(key) : null),
            setItem: (key, value) => {
                memory.set(key, String(value));
            },
            removeItem: (key) => {
                memory.delete(key);
            },
            clear: () => {
                memory.clear();
            },
        };
    });

    it('exposes labels for all supported platforms', () => {
        expect(Object.keys(PLATFORM_LABELS).sort()).toEqual([...SUPPORTED_SOCIAL_PLATFORMS].sort());
    });

    it('returns fallback when storage is empty', () => {
        expect(getConnectedPlatforms(['youtube'])).toEqual(['youtube']);
    });

    it('returns fallback when storage payload is invalid JSON', () => {
        globalThis.localStorage.setItem(STORAGE_KEY, '{bad json');
        expect(getConnectedPlatforms(['instagram'])).toEqual(['instagram']);
    });

    it('filters unknown platforms and keeps supported order', () => {
        globalThis.localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify({
                linkedin: true,
                unknown: true,
                youtube: true,
                tiktok: false,
            }),
        );

        expect(getConnectedPlatforms()).toEqual(['youtube', 'linkedin']);
    });

    it('returns fallback when no platform is enabled', () => {
        globalThis.localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify({ tiktok: false, instagram: 0, youtube: '' }),
        );

        expect(getConnectedPlatforms(['facebook'])).toEqual(['facebook']);
    });
});



import { describe, expect, it } from 'vitest';
import { DASHBOARD_SIDEBAR_ITEMS } from '../dashboard-nav';

describe('DASHBOARD_SIDEBAR_ITEMS', () => {
    it('contains unique keys and paths', () => {
        const keys = DASHBOARD_SIDEBAR_ITEMS.map((item) => item.key);
        const paths = DASHBOARD_SIDEBAR_ITEMS.map((item) => item.path);

        expect(new Set(keys).size).toBe(keys.length);
        expect(new Set(paths).size).toBe(paths.length);
    });

    it('has required fields for each item', () => {
        for (const item of DASHBOARD_SIDEBAR_ITEMS) {
            expect(item.key).toBeTruthy();
            expect(item.title).toBeTruthy();
            expect(item.sidebarLabel).toBeTruthy();
            expect(item.icon).toBeTruthy();
            expect(item.activeClassName).toContain('text-');
            expect(item.inactiveClassName).toContain('text-');
            expect(item.description).toBeTruthy();
            expect(item.badge).toBeTruthy();
            expect(['hub', 'service', 'utility']).toContain(item.category);
            expect(item.path.startsWith('/dashboard')).toBe(true);
        }
    });

    it('exposes expected navigation entries', () => {
        const keys = DASHBOARD_SIDEBAR_ITEMS.map((item) => item.key);
        expect(keys).toEqual([
            'dashboard',
            'reels',
            'captions',
            'social-publications',
            'abonnements',
            'settings',
        ]);
    });
});


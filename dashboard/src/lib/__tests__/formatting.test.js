import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getDayLabel, formatDate, detectTimezone, DAYS, MONTHS } from '../formatting';

// Pin "today" to a fixed date so tests are not calendar-dependent
const FIXED_TODAY = new Date('2026-08-01T12:00:00');

beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(FIXED_TODAY);
});

afterEach(() => {
    vi.useRealTimers();
});

describe('getDayLabel', () => {
    it('returns "Hoy" for today', () => {
        expect(getDayLabel(new Date('2026-08-01'))).toBe('Hoy');
    });

    it('returns "Mañana" for tomorrow', () => {
        expect(getDayLabel(new Date('2026-08-02'))).toBe('Mañana');
    });

    it('returns the abbreviated weekday name for other dates', () => {
        // 2026-08-03 is a Monday
        expect(DAYS).toContain(getDayLabel(new Date('2026-08-03')));
    });

    it('does not return Hoy or Mañana for dates further away', () => {
        const label = getDayLabel(new Date('2026-08-10'));
        expect(label).not.toBe('Hoy');
        expect(label).not.toBe('Mañana');
    });
});

describe('formatDate', () => {
    it('formats a date as "D Mon"', () => {
        expect(formatDate(new Date('2026-07-14'))).toBe('14 Jul');
    });

    it('uses the MONTHS array for month abbreviations', () => {
        for (let m = 0; m < 12; m++) {
            const d = new Date(2026, m, 1);
            expect(formatDate(d)).toContain(MONTHS[m]);
        }
    });
});

describe('detectTimezone', () => {
    it('returns a non-empty string', () => {
        vi.useRealTimers(); // Intl needs real timers
        const tz = detectTimezone();
        expect(typeof tz).toBe('string');
        expect(tz.length).toBeGreaterThan(0);
    });

    it('returns "UTC" when Intl is unavailable', () => {
        vi.useRealTimers();
        const original = globalThis.Intl;
        globalThis.Intl = undefined;
        expect(detectTimezone()).toBe('UTC');
        globalThis.Intl = original;
    });
});


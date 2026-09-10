import { describe, it, expect } from 'vitest';
import { measureTextWidth } from '../textMeasure';

describe('measureTextWidth', () => {
    // jsdom has no native canvas 2D context (the optional `canvas` npm
    // package isn't installed), so getContext('2d') returns null here and
    // every call exercises the character-count fallback estimate.

    it('returns 0 for an empty string', () => {
        expect(measureTextWidth('', "'Arial'", 40, false)).toBe(0);
    });

    it('scales roughly linearly with text length', () => {
        const short = measureTextWidth('hi', "'Arial'", 40, false);
        const long = measureTextWidth('hihihihi', "'Arial'", 40, false);
        expect(long).toBeCloseTo(short * 4, 5);
    });

    it('scales with font size', () => {
        const small = measureTextWidth('hello', "'Arial'", 20, false);
        const large = measureTextWidth('hello', "'Arial'", 40, false);
        expect(large).toBeCloseTo(small * 2, 5);
    });

    it('bold/regular both produce a positive width (fallback ignores weight)', () => {
        expect(measureTextWidth('hello', "'Montserrat'", 40, true)).toBeGreaterThan(0);
        expect(measureTextWidth('hello', "'Montserrat'", 40, false)).toBeGreaterThan(0);
    });
});

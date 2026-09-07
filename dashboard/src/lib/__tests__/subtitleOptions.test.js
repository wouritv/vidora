import { describe, expect, it } from 'vitest';
import {
    ANIMATION_OPTIONS,
    COLOR_PRESETS,
    DEFAULT_SUBTITLE_FORM_STYLE,
    FONT_OPTIONS,
    HIGHLIGHT_COLOR_PRESETS,
} from '../subtitleOptions';

describe('subtitleOptions', () => {
    it('has unique font values and labels', () => {
        const values = FONT_OPTIONS.map((f) => f.value);
        const labels = FONT_OPTIONS.map((f) => f.label);

        expect(new Set(values).size).toBe(values.length);
        expect(new Set(labels).size).toBe(labels.length);
    });

    it('exposes valid default subtitle style', () => {
        expect(DEFAULT_SUBTITLE_FORM_STYLE.fontName).toBe('Verdana');
        expect(DEFAULT_SUBTITLE_FORM_STYLE.fontColor).toMatch(/^#[0-9A-F]{6}$/i);
        expect(DEFAULT_SUBTITLE_FORM_STYLE.highlightColor).toMatch(/^#[0-9A-F]{6}$/i);
        expect(DEFAULT_SUBTITLE_FORM_STYLE.wordsPerLine).toBeGreaterThan(0);
        expect(DEFAULT_SUBTITLE_FORM_STYLE.animation).toBe('pop');
    });

    it('includes required animation options', () => {
        const values = ANIMATION_OPTIONS.map((a) => a.value);

        expect(values).toContain('none');
        expect(values).toContain('pop');
        expect(values).toContain('karaoke');
        expect(new Set(values).size).toBe(values.length);
    });

    it('provides hex color presets for base and highlight palettes', () => {
        for (const preset of [...COLOR_PRESETS, ...HIGHLIGHT_COLOR_PRESETS]) {
            expect(preset.color).toMatch(/^#[0-9A-F]{6}$/i);
            expect(preset.label.length).toBeGreaterThan(0);
        }
    });
});


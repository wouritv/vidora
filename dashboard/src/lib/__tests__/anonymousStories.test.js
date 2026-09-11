import { describe, expect, it, vi } from 'vitest';
import { buildFullText, errorMessageForCode, normalizeStoryJobStatus } from '../anonymousStories';

describe('normalizeStoryJobStatus', () => {
    it('maps backend statuses to the frontend canonical form', () => {
        expect(normalizeStoryJobStatus('completed')).toBe('complete');
        expect(normalizeStoryJobStatus('failed')).toBe('error');
        expect(normalizeStoryJobStatus('queued')).toBe('processing');
        expect(normalizeStoryJobStatus('created')).toBe('processing');
        expect(normalizeStoryJobStatus('retry_wait')).toBe('processing');
        expect(normalizeStoryJobStatus('processing')).toBe('processing');
    });

    it('defaults to idle when status is missing', () => {
        expect(normalizeStoryJobStatus(undefined)).toBe('idle');
        expect(normalizeStoryJobStatus('')).toBe('idle');
    });
});

describe('errorMessageForCode', () => {
    it('maps known backend error codes to their i18n key', () => {
        const t = vi.fn((key) => `translated:${key}`);

        expect(errorMessageForCode(t, 'NOT_A_STORY', 'fallback')).toBe('translated:anonymousStories.errorNotAStory');
        expect(errorMessageForCode(t, 'INVALID_YOUTUBE_URL', 'fallback')).toBe('translated:anonymousStories.errorInvalidYoutubeUrl');
        expect(errorMessageForCode(t, 'TRANSCRIPTION_FAILED', 'fallback')).toBe('translated:anonymousStories.errorTranscriptionFailed');
        expect(errorMessageForCode(t, 'GENERATION_INVALID', 'fallback')).toBe('translated:anonymousStories.errorGenerationInvalid');
        expect(errorMessageForCode(t, 'INSUFFICIENT_CREDITS', 'fallback')).toBe('translated:anonymousStories.errorInsufficientCredits');
        expect(errorMessageForCode(t, 'CANCELLED', 'fallback')).toBe('translated:anonymousStories.errorCancelled');
    });

    it('returns the fallback untouched when no code is given', () => {
        const t = vi.fn();
        expect(errorMessageForCode(t, '', 'fallback text')).toBe('fallback text');
        expect(errorMessageForCode(t, null, 'fallback text')).toBe('fallback text');
        expect(t).not.toHaveBeenCalled();
    });
});

describe('buildFullText', () => {
    it('joins non-empty blocks with blank lines, questions on their own lines', () => {
        const text = buildFullText('Hook', 'Intro', 'Story body', ['Q1?', 'Q2?']);
        expect(text).toBe('Hook\n\nIntro\n\nStory body\n\nQ1?\nQ2?');
    });

    it('skips empty or whitespace-only blocks', () => {
        expect(buildFullText('', '   ', 'Only the story', [])).toBe('Only the story');
    });

    it('filters out blank questions', () => {
        const text = buildFullText('', '', 'Story', ['  ', 'Real question?', '']);
        expect(text).toBe('Story\n\nReal question?');
    });

    it('returns an empty string when everything is empty', () => {
        expect(buildFullText('', '', '', [])).toBe('');
    });
});

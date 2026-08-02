import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { readGenerationSession, SESSION_KEY, SESSION_MAX_AGE } from '../session';

afterEach(() => {
    localStorage.removeItem(SESSION_KEY);
});

describe('readGenerationSession', () => {
    it('returns null when localStorage is empty', () => {
        expect(readGenerationSession()).toBeNull();
    });

    it('returns null for malformed JSON', () => {
        localStorage.setItem(SESSION_KEY, '{{{not-json');
        expect(readGenerationSession()).toBeNull();
    });

    it('returns null when jobId is missing', () => {
        localStorage.setItem(SESSION_KEY, JSON.stringify({ status: 'processing', timestamp: Date.now() }));
        expect(readGenerationSession()).toBeNull();
    });

    it('returns null when status is missing', () => {
        localStorage.setItem(SESSION_KEY, JSON.stringify({ jobId: 'abc123', timestamp: Date.now() }));
        expect(readGenerationSession()).toBeNull();
    });

    it('returns the parsed session for a valid recent entry', () => {
        const session = { jobId: 'abc123', status: 'processing', timestamp: Date.now() };
        localStorage.setItem(SESSION_KEY, JSON.stringify(session));
        const result = readGenerationSession();
        expect(result).not.toBeNull();
        expect(result.jobId).toBe('abc123');
        expect(result.status).toBe('processing');
    });

    it('returns null and clears storage for an expired session', () => {
        const expired = {
            jobId: 'old-job',
            status: 'complete',
            timestamp: Date.now() - SESSION_MAX_AGE - 1,
        };
        localStorage.setItem(SESSION_KEY, JSON.stringify(expired));
        const result = readGenerationSession();
        expect(result).toBeNull();
        expect(localStorage.getItem(SESSION_KEY)).toBeNull();
    });

    it('SESSION_MAX_AGE is one hour in milliseconds', () => {
        expect(SESSION_MAX_AGE).toBe(3_600_000);
    });
});


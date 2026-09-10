import { describe, it, expect, beforeEach } from 'vitest';
import { getAuthHeaders, getCachedAccessToken, setCachedAccessToken } from '../apiAuth';

describe('getAuthHeaders', () => {
    beforeEach(() => {
        setCachedAccessToken(null);
    });

    it('omits Authorization when no token has been cached yet', () => {
        const headers = getAuthHeaders('user-1');
        expect(headers['X-User-Id']).toBe('user-1');
        expect(headers['Authorization']).toBeUndefined();
    });

    it('includes a Bearer Authorization header once a token is cached', () => {
        // Regression test: AuthContext pushes the resolved session's access
        // token here synchronously (setCachedAccessToken), which is what
        // fixed a real race where the first requests fired right after login
        // (credits, subscription, social accounts, history) went out with no
        // Authorization header at all and the backend rejected them with 401
        // -- because this module used to only populate its cache via its own
        // independent, still-pending getSession() call at that same instant.
        setCachedAccessToken('token-abc');
        const headers = getAuthHeaders('user-1');
        expect(headers['Authorization']).toBe('Bearer token-abc');
        expect(headers['X-User-Id']).toBe('user-1');
    });

    it('clears Authorization when the token is reset to null (e.g. logout)', () => {
        setCachedAccessToken('token-abc');
        setCachedAccessToken(null);
        const headers = getAuthHeaders('user-1');
        expect(headers['Authorization']).toBeUndefined();
    });

    it('omits X-User-Id when no userId is provided', () => {
        setCachedAccessToken('token-abc');
        const headers = getAuthHeaders();
        expect(headers['X-User-Id']).toBeUndefined();
        expect(headers['Authorization']).toBe('Bearer token-abc');
    });
});

describe('getCachedAccessToken', () => {
    beforeEach(() => {
        setCachedAccessToken(null);
    });

    it('returns null when no token has been cached', () => {
        expect(getCachedAccessToken()).toBeNull();
    });

    it('returns the cached token', () => {
        setCachedAccessToken('token-abc');
        expect(getCachedAccessToken()).toBe('token-abc');
    });
});

export const SESSION_KEY = 'Vidora_session';
export const SESSION_MAX_AGE = 3_600_000; // 1 hour in ms

/**
 * Read the current generation session from localStorage.
 * Returns null if the session is missing, malformed, or older than SESSION_MAX_AGE.
 *
 * @returns {{ jobId: string, status: string, timestamp: number } | null}
 */
export function readGenerationSession() {
    try {
        const raw = globalThis.localStorage?.getItem(SESSION_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed?.jobId || !parsed?.status) return null;
        if (Date.now() - parsed.timestamp > SESSION_MAX_AGE) {
            globalThis.localStorage.removeItem(SESSION_KEY);
            return null;
        }
        return parsed;
    } catch {
        return null;
    }
}


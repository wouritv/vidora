import { getSupabaseBrowserClient } from "./supabase-browser";

/**
 * The backend verifies a Supabase-issued JWT (`Authorization: Bearer ...`)
 * to determine the caller's identity -- it no longer trusts a plain
 * `X-User-Id` header on its own (that header was spoofable by any client,
 * letting anyone impersonate any other user by simply setting it to
 * someone else's id). This module keeps a small in-memory cache of the
 * current Supabase access token, kept fresh via onAuthStateChange, so that
 * `getAuthHeaders()` can stay a plain synchronous function -- a drop-in
 * replacement for the old `{ 'X-User-Id': user.id }` header objects used
 * throughout the app, including inside non-async contexts like useEffect.
 */

let cachedAccessToken = null;
let initialized = false;

function ensureTokenCacheInitialized() {
    if (initialized) return;
    initialized = true;
    try {
        const supabase = getSupabaseBrowserClient();
        supabase.auth.getSession().then(({ data }) => {
            cachedAccessToken = data?.session?.access_token || null;
        });
        supabase.auth.onAuthStateChange((_event, session) => {
            cachedAccessToken = session?.access_token || null;
        });
    } catch {
        // Supabase not configured / not available in this context (e.g. a
        // unit test) -- requests will simply go out without an
        // Authorization header and the backend will reject them with 401.
    }
}

/**
 * Build request headers carrying the authenticated caller's identity.
 * `X-User-Id` is kept for logging/debugging convenience only; the
 * Authorization Bearer token is what the backend actually verifies.
 *
 * @param {string} [userId]
 * @returns {Record<string, string>}
 */
export function getAuthHeaders(userId) {
    ensureTokenCacheInitialized();
    const headers = {};
    if (userId) headers["X-User-Id"] = userId;
    if (cachedAccessToken) headers["Authorization"] = `Bearer ${cachedAccessToken}`;
    return headers;
}

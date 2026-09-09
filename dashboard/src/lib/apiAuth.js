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

/**
 * Set by AuthContext the moment it resolves a session -- synchronously, in
 * the same callback that flips `isAuthenticated` to true. This is the
 * primary way the cache gets populated: AuthContext already awaits
 * getSession() once at the app root, so components lower in the tree that
 * fetch data as soon as `isAuthenticated` becomes true (in a useEffect keyed
 * on it) would otherwise race a *second*, independent getSession() call
 * started lazily from here on their first getAuthHeaders() call -- which,
 * being a fresh promise, cannot have resolved yet at that same synchronous
 * instant. Sourcing the token from AuthContext's already-resolved session
 * instead removes that race entirely.
 */
export function setCachedAccessToken(token) {
    cachedAccessToken = token || null;
}

function ensureTokenCacheInitialized() {
    if (initialized) return;
    initialized = true;
    try {
        const supabase = getSupabaseBrowserClient();
        // Fallback only, for any caller outside AuthProvider's tree: kept so
        // the cache still eventually settles even without the direct push.
        supabase.auth.getSession().then(({ data }) => {
            if (cachedAccessToken === null) {
                cachedAccessToken = data?.session?.access_token || null;
            }
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

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "./AuthContext";
import { getApiUrl } from "../config";
import { getAuthHeaders } from "../lib/apiAuth";

const UserCreditsContext = createContext(null);

/**
 * Provides the current user's credit/storage balance to the app.
 * Fetches once on mount, refreshes when the window regains focus,
 * and exposes a manual `refresh()` method.
 */
export function UserCreditsProvider({ children }) {
    const { user, isAuthenticated } = useAuth();
    const [credits, setCredits] = useState(null);   // null = not loaded yet
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const fetching = useRef(false);

    const fetch_credits = useCallback(async () => {
        if (!user?.id || fetching.current) return;
        fetching.current = true;
        setLoading(true);
        setError("");
        try {
            const res = await fetch(getApiUrl("/api/user/credits"), {
                headers: getAuthHeaders(user.id),
            });
            if (!res.ok) {
                const text = await res.text();
                throw new Error(text || "Unable to load credits");
            }
            const data = await res.json();
            setCredits(data);
        } catch (err) {
            setError(err.message || "Unable to load credits");
        } finally {
            setLoading(false);
            fetching.current = false;
        }
    }, [user?.id]);

    // Initial load
    useEffect(() => {
        if (isAuthenticated) {
            fetch_credits();
        } else {
            setCredits(null);
        }
    }, [isAuthenticated, fetch_credits]);

    // Refresh when window regains focus
    useEffect(() => {
        const onFocus = () => {
            if (isAuthenticated) fetch_credits();
        };
        window.addEventListener("focus", onFocus);
        return () => window.removeEventListener("focus", onFocus);
    }, [isAuthenticated, fetch_credits]);

    const value = useMemo(() => ({
        credits:          credits?.credit   ?? 0,
        storage:          credits?.stockage ?? 0,
        creditMax:        credits?.credit_max ?? 0,
        storageMax:       credits?.stockage_max ?? 0,
        creditRatio:      (credits?.credit_max ?? 0) > 0 ? (credits?.credit ?? 0) / (credits?.credit_max ?? 1) : 0,
        storageRatio:     (credits?.stockage_max ?? 0) > 0 ? (credits?.stockage ?? 0) / (credits?.stockage_max ?? 1) : 0,
        hasCredits:       credits ? credits.credit > 0 : null,  // null = unknown
        aboCosts:         credits?.abo_costs ?? {},
        defaultCosts:     credits?.default_costs ?? {},
        loading,
        error,
        refresh:          fetch_credits,
        /** Check if user has at least `required` credits (null when not loaded yet). */
        canAfford: (required = 1) => {
            if (credits === null) return null;
            return (credits.credit ?? 0) >= required;
        },
    }), [credits, loading, error, fetch_credits]);

    return (
        <UserCreditsContext.Provider value={value}>
            {children}
        </UserCreditsContext.Provider>
    );
}

export function useUserCredits() {
    const ctx = useContext(UserCreditsContext);
    if (!ctx) throw new Error("useUserCredits must be used inside UserCreditsProvider");
    return ctx;
}


import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getSupabaseBrowserClient } from "../lib/supabase-browser";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [session, setSession] = useState(null);
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const supabase = getSupabaseBrowserClient();
        let mounted = true;

        supabase.auth.getSession().then(({ data, error }) => {
            if (!mounted) return;

            if (error) {
                setSession(null);
                setUser(null);
                setLoading(false);
                return;
            }

            setSession(data.session ?? null);
            setUser(data.session?.user ?? null);
            setLoading(false);
        });

        const { data: authListener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
            setSession(nextSession ?? null);
            setUser(nextSession?.user ?? null);
            setLoading(false);
        });

        return () => {
            mounted = false;
            authListener.subscription.unsubscribe();
        };
    }, []);

    async function logout() {
        const supabase = getSupabaseBrowserClient();
        await supabase.auth.signOut();
        setSession(null);
        setUser(null);
    }

    const value = useMemo(
        () => ({
            session,
            user,
            loading,
            isAuthenticated: Boolean(user),
            logout,
        }),
        [session, user, loading]
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
    const ctx = useContext(AuthContext);

    if (!ctx) {
        throw new Error("useAuth must be used inside AuthProvider");
    }

    return ctx;
}
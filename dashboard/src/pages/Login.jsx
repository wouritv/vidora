import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { getSupabaseBrowserClient } from "../lib/supabase-browser";
import { useAuth } from "../state/AuthContext";
import AuthLayout from "../layouts/AuthLayout";
import "../styles/auth-legacy.css";

export default function Login() {
    const navigate = useNavigate();
    const { isAuthenticated, loading: authLoading } = useAuth();

    const [mode, setMode] = useState("signin");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    useEffect(() => {
        if (!authLoading && isAuthenticated) {
            navigate("/dashboard", { replace: true });
        }
    }, [authLoading, isAuthenticated, navigate]);

    async function handleAuth(event) {
        event.preventDefault();
        setError("");
        setSuccess("");
        setLoading(true);

        try {
            const supabase = getSupabaseBrowserClient();

            if (mode === "signin") {
                const { error: signInError } = await supabase.auth.signInWithPassword({
                    email,
                    password,
                });

                if (signInError) {
                    setError(signInError.message);
                    return;
                }

                navigate("/dashboard", { replace: true });
                return;
            }

            const { error: signUpError } = await supabase.auth.signUp({
                email,
                password,
            });

            if (signUpError) {
                setError(signUpError.message);
                return;
            }

            setSuccess("Compte cree. Verifie ton email si la confirmation est activee.");
        } catch (caughtError) {
            setError(caughtError instanceof Error ? caughtError.message : "Erreur inconnue");
        } finally {
            setLoading(false);
        }
    }

    async function signInWithProvider(provider) {
        setError("");
        setSuccess("");

        try {
            const supabase = getSupabaseBrowserClient();

            const { error: oauthError } = await supabase.auth.signInWithOAuth({
                provider,
                options: {
                    redirectTo: `${window.location.origin}/dashboard`,
                },
            });

            if (oauthError) {
                setError(oauthError.message);
            }
        } catch (caughtError) {
            setError(caughtError instanceof Error ? caughtError.message : "Erreur OAuth inconnue");
        }
    }

    return (
        <AuthLayout title="Connexion" subtitle="Continue avec Google ou Apple">
            <main className="page auth-page">
                <section className="card auth-card auth-surface">
                    <p className="eyebrow">Authentification</p>
                    <h1>{mode === "signin" ? "Connexion" : "Creation de compte"}</h1>
                    <p className="hint">Connecte-toi pour acceder au dashboard.</p>

                    <form onSubmit={handleAuth} className="form auth-form">
                        <label>
                            Email
                            <input
                                type="email"
                                value={email}
                                onChange={(event) => setEmail(event.target.value)}
                                required
                            />
                        </label>

                        <label>
                            Mot de passe
                            <input
                                type="password"
                                value={password}
                                onChange={(event) => setPassword(event.target.value)}
                                required
                                minLength={6}
                            />
                        </label>

                        {mode === "signin" ? (
                            <div className="auth-links-row">
                                <Link to="/reset-password" className="auth-link">
                                    Mot de passe oublie ?
                                </Link>
                            </div>
                        ) : null}

                        <div className="actions auth-actions">
                            <button type="submit" disabled={loading}>
                                {loading ? "Patiente..." : mode === "signin" ? "Se connecter" : "Creer un compte"}
                            </button>

                            <button
                                type="button"
                                className="secondary"
                                onClick={() =>
                                    setMode((currentMode) =>
                                        currentMode === "signin" ? "signup" : "signin"
                                    )
                                }
                                disabled={loading}
                            >
                                {mode === "signin" ? "Passer a inscription" : "Passer a connexion"}
                            </button>
                        </div>

                        <div className="oauth-grid">
                            <button
                                type="button"
                                className="ghost oauth-google"
                                onClick={() => signInWithProvider("google")}
                            >
                                Google
                            </button>

                            <button
                                type="button"
                                className="ghost oauth-apple"
                                onClick={() => signInWithProvider("apple")}
                            >
                                Apple
                            </button>
                        </div>
                    </form>

                    {error ? <p className="error">{error}</p> : null}
                    {success ? <p className="success">{success}</p> : null}
                </section>
            </main>
        </AuthLayout>
    );
}
import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { getSupabaseBrowserClient } from "../lib/supabase-browser";
import { useAuth } from "../state/AuthContext";
import AuthLayout from "../layouts/AuthLayout";
import "../styles/auth-legacy.css";
import { useTranslation } from "../state/LanguageContext";

export default function Login() {
    const { t } = useTranslation();
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

            setSuccess(t("app.accountCreate","Compte cree. Verifie ton email si la confirmation est activee."));
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
            setError(caughtError instanceof Error ? caughtError.message : t("app.erreurAuth","Erreur OAuth inconnue"));
        }
    }

    return (
        <AuthLayout title={t("app.btLogin","Connexion")} subtitle={t("app.authSubtitle","Connecte-toi pour acceder au dashboard.")}>
            <main className="page auth-page">
                <section className="card auth-card auth-surface">
                    <p className="eyebrow">{t("app.authTitle","Authentification")}</p>
                    <h1>{mode === "signin" ? t("app.btLogin","Connexion") : t("app.btRegister","Creation de compte")}</h1>
                    <p className="hint">{t("app.authSubtitle","Connecte-toi pour acceder au dashboard.")}</p>

                    <form onSubmit={handleAuth} className="form auth-form">
                        <label>
                            {t("app.email","Email")}
                            <input
                                type="email"
                                value={email}
                                onChange={(event) => setEmail(event.target.value)}
                                required
                            />
                        </label>

                        <label>
                            {t("app.password","Mot de passe")}
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
                                    {t("app.passwordForgot","Mot de passe oublié ?")}
                                </Link>
                            </div>
                        ) : null}

                        <div className="actions auth-actions">
                            <button type="submit" disabled={loading}>
                                {loading ? t("app.loading","Chargement...") : mode === "signin" ? t("app.connectTitle","Se connecter") : t("app.registerTitle","Créer un compte")}
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
                                {mode === "signin" ? t("app.btRegister2","Passer a inscription") : t("app.btLogin2","Passer a connexion")}
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
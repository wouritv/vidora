import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { getSupabaseBrowserClient } from "../lib/supabase-browser";
import AuthLayout from "../layouts/AuthLayout";
import "../styles/auth-legacy.css";
import { useTranslation } from "../state/LanguageContext";

export default function UpdatePassword() {
    const { t } = useTranslation();
    const navigate = useNavigate();

    const [ready, setReady] = useState(false);
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    useEffect(() => {
        const supabase = getSupabaseBrowserClient();

        supabase.auth.getSession().then(({ data }) => {
            setReady(Boolean(data.session));
        });

        const { data: authListener } = supabase.auth.onAuthStateChange((_event, session) => {
            setReady(Boolean(session));
        });

        return () => {
            authListener.subscription.unsubscribe();
        };
    }, []);

    async function handleUpdate(event) {
        event.preventDefault();
        setError("");
        setSuccess("");

        if (password !== confirmPassword) {
            setError(t("app.errorPassword","Les mots de passe doivent correspondre."));
            return;
        }

        setLoading(true);

        try {
            const supabase = getSupabaseBrowserClient();

            const { error: updateError } = await supabase.auth.updateUser({
                password,
            });

            if (updateError) {
                setError(updateError.message);
                return;
            }

            setSuccess(t("app.resetPasswordSuccess2","Mot de passe mis a jour. Redirection en cours..."));

            setTimeout(() => {
                navigate("/login", { replace: true });
            }, 1000);
        } catch (caughtError) {
            setError(caughtError instanceof Error ? caughtError.message : "Erreur inconnue");
        } finally {
            setLoading(false);
        }
    }

    return (
        <AuthLayout
            title={t("app.resetPwdTitle","Nouveau mot de passe")}
            subtitle={t("app.resetPwdSubtitle","Ouvre le lien recu par email pour finaliser la mise a jour")}
        >
            <main className="page auth-page">
                <section className="card auth-card auth-surface">
                    <p className="eyebrow">{t("app.password","Mot de passe")}</p>
                    <h1>{t("app.resetPwdTitle","Nouveau mot de passe")}</h1>
                    <p className="hint">
                        {t("app.resetPwdSubtitle","Ouvre le lien recu par email pour definir un nouveau mot de passe.")}
                    </p>

                    {!ready ? (
                        <p className="hint">{t("app.waitingRecoverySession","En attente de la session de recuperation...")}</p>
                    ) : null}

                    <form onSubmit={handleUpdate} className="form auth-form">
                        <label>
                            {t("app.newPassword","Nouveau mot de passe")}
                            <input
                                type="password"
                                value={password}
                                onChange={(event) => setPassword(event.target.value)}
                                required
                                minLength={6}
                            />
                        </label>

                        <label>
                            {t("app.confirmPassword","Confirmer le mot de passe")}
                            <input
                                type="password"
                                value={confirmPassword}
                                onChange={(event) => setConfirmPassword(event.target.value)}
                                required
                                minLength={6}
                            />
                        </label>

                        <div className="actions auth-actions">
                            <button type="submit" disabled={loading || !ready}>
                                {loading ? t("app.update","Mise a jour...") : t("app.update2","Mettre a jour")}
                            </button>

                            <Link to="/login" className="link-pill">
                                {t("app.backToLogin","Retour connexion")}
                            </Link>
                        </div>
                    </form>

                    {error ? <p className="error">{error}</p> : null}
                    {success ? <p className="success">{success}</p> : null}
                </section>
            </main>
        </AuthLayout>
    );
}
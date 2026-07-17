import { Link } from "react-router-dom";
import { useState } from "react";
import { getSupabaseBrowserClient } from "../lib/supabase-browser";
import AuthLayout from "../layouts/AuthLayout";
import "../styles/auth-legacy.css";

export default function ResetPassword() {
    const [email, setEmail] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    async function handleReset(event) {
        event.preventDefault();
        setError("");
        setSuccess("");
        setLoading(true);

        try {
            const supabase = getSupabaseBrowserClient();
            const redirectTo = `${window.location.origin}/update-password`;

            const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
                redirectTo,
            });

            if (resetError) {
                setError(resetError.message);
                return;
            }

            setSuccess("Un lien de reinitialisation a ete envoye par email.");
        } catch (caughtError) {
            setError(caughtError instanceof Error ? caughtError.message : "Erreur inconnue");
        } finally {
            setLoading(false);
        }
    }

    return (
        <AuthLayout
            title="Reinitialiser le mot de passe"
            subtitle="Saisis l'email du compte pour recevoir un lien"
        >
            <main className="page auth-page">
                <section className="card auth-card auth-surface">
                    <p className="eyebrow">Mot de passe</p>
                    <h1>Reinitialiser</h1>
                    <p className="hint">
                        Saisis l'adresse email du compte pour recevoir le lien de reinitialisation.
                    </p>

                    <form onSubmit={handleReset} className="form auth-form">
                        <label>
                            Email
                            <input
                                type="email"
                                value={email}
                                onChange={(event) => setEmail(event.target.value)}
                                required
                            />
                        </label>

                        <div className="actions auth-actions">
                            <button type="submit" disabled={loading}>
                                {loading ? "Envoi..." : "Envoyer le lien"}
                            </button>

                            <Link to="/login" className="link-pill">
                                Retour connexion
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
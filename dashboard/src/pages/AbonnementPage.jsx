import React, {useEffect, useState} from "react";
import {Check, CreditCardIcon, Star, Crown, Sparkles, Loader2} from "lucide-react";
import {getApiUrl} from "../config.js";
import { useAuth } from "../state/AuthContext";

const colorStyles = {
    zinc: {
        border: "border-zinc-500/20",
        bg: "bg-zinc-500/10",
        icon: "text-zinc-300",
        button: "border-zinc-500/20 bg-zinc-500/10 text-zinc-300 hover:bg-zinc-500/15",
        check: "text-zinc-400",
    },
    blue: {
        border: "border-blue-500/30",
        bg: "bg-blue-500/10",
        icon: "text-blue-300",
        button: "border-blue-500/20 bg-blue-500/10 text-blue-300 hover:bg-blue-500/15",
        check: "text-blue-400",
    },
    purple: {
        border: "border-purple-500/20",
        bg: "bg-purple-500/10",
        icon: "text-purple-300",
        button: "border-purple-500/20 bg-purple-500/10 text-purple-300 hover:bg-purple-500/15",
        check: "text-purple-400",
    },
};

const iconMap = {
    Crown: Crown,
    star: Star,
    Sparkles: Sparkles,
};

export default function AbonnementPage() {
    const { user } = useAuth();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [souscription, setSouscription] = useState(null);
    const [loadingPlanId, setLoadingPlanId] = useState("");
    const [paymentMessage, setPaymentMessage] = useState("");

    useEffect(() => {
        const params = new URLSearchParams(globalThis.location.search || "");
        const payment = params.get("payment");
        if (payment === "success") {
            setPaymentMessage("Paiement confirme. Votre abonnement sera active sous peu.");
        } else if (payment === "cancel") {
            setPaymentMessage("Paiement annule.");
        }
    }, []);

    const handleCheckout = async (plan) => {
        if (!user?.id || !plan?.id) return;
        setLoadingPlanId(plan.id);
        setError("");
        try {
            const response = await fetch(getApiUrl(`/api/stripe/checkout-session`), {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-User-Id": user.id,
                    ...(user?.email ? { "X-User-Email": user.email } : {}),
                },
                body: JSON.stringify({
                    plan_id: plan.id,
                }),
            });

            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                setError(data?.detail || "Impossible de demarrer le paiement Stripe.");
                return;
            }

            if (!data?.checkout_url) {
                setError("Aucune URL de paiement n'a ete retournee.");
                return;
            }

            globalThis.location.href = data.checkout_url;
        } catch (err) {
            setError(err.message || "Impossible de demarrer le paiement Stripe.");
        } finally {
            setLoadingPlanId("");
        }
    };

    useEffect(() => {
        if (!user?.id) return;
        async function fetchSouscription() {
            try {
                const response = await fetch(getApiUrl(`/api/souscription`), {
                    headers: {
                        "X-User-Id": user.id,
                    },
                });

                if (!response.ok) {
                    return;
                }

                const data = await response.json();
                setSouscription(data);
            } catch (err) {
                console.error("Error fetching souscription:", err);
            }
        }

        fetchSouscription();

    }, [user?.id])

    useEffect(() => {
        async function getItems() {

            setLoading(true);
            setError("");

            try {

                const response = await fetch(getApiUrl(`/api/abonnements`),  null);

                if (!response.ok) {
                    const detail = await response.text();
                    setError(detail || "Unable to load plans");
                    setItems([]);
                    return;
                }

                const data = await response.json();
                setItems(Array.isArray(data.plans) ? data.plans : []);

            } catch (err) {
                setError(err.message || "Unable to load reels");
                setItems([]);
            } finally {
                setLoading(false);
            }
        }

        getItems();

    },[])

    return (
        <div className="h-full overflow-y-auto p-8 max-w-5xl mx-auto animate-[fadeIn_0.3s_ease-out]">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold mb-2">Abonnements</h1>
                <p className="text-zinc-400 text-sm">Découvrez nos formules d'abonnements et choisissez celle qui vous convient</p>
                {paymentMessage ? <p className="mt-3 text-sm text-green-300">{paymentMessage}</p> : null}
            </div>

            {/* Plans */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">

                {loading && (
                    <span className="inline-flex items-center gap-2">
                        <Loader2 size={14} className="animate-spin" /> Chargement...
                    </span>
                )}

                {!loading && error && (
                    <span className="inline-flex items-center gap-2 text-red-300">
                        {error}
                    </span>
                )}

                {!loading && !error && items.length === 0 && (
                    <span className="inline-flex items-center gap-2 text-zinc-400">
                        Aucun abonnement trouve.
                    </span>
                )}

                {items.map((plan) => {
                    const styles = colorStyles[plan.color];
                    const Icon = iconMap[plan.icon] || Star; // Default to Star if icon is not found
                    let buttonLabel = "Choisir";

                    if (souscription && plan.id === souscription.abonnement && plan.ordre < 3) {
                        buttonLabel = "Upgrade";
                    }

                    return (
                        <div
                            key={plan.name}
                            className={`relative flex flex-col rounded-2xl border ${styles.border} ${styles.bg} p-6 ${
                                plan.highlighted ? "ring-2 ring-blue-500/40 scale-[1.03]" : ""
                            } transition`}
                        >
                            {plan.highlighted && (
                                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-500 px-3 py-1 text-xs font-semibold text-white">
                  Populaire
                </span>
                            )}

                            {/* Icon + nom */}
                            <div className="flex items-center gap-3 mb-4">
                                <div className={`p-2 rounded-lg bg-gradient-to-br from-${plan.color}-500/30 to-${plan.color}-700/30`}>
                                    <Icon size={20} className={styles.icon} />
                                </div>
                                <h2 className="text-lg font-bold">{plan.name}</h2>
                            </div>

                            {/* Prix */}
                            <div className="mb-6">
                                <span className="text-3xl font-bold">{plan.price}€</span>
                                <span className="text-zinc-400 text-sm"> / mois</span>
                            </div>

                            {/* Liste des services */}
                            <ul className="flex flex-col gap-3 mb-8 flex-1">
                                {plan.features.map((feature) => (
                                    <li key={feature} className="flex items-start gap-2 text-sm text-zinc-300">
                                        <Check size={16} className={`${styles.check} mt-0.5 shrink-0`} />
                                        <span>{feature}</span>
                                    </li>
                                ))}
                            </ul>

                            {/* Bouton */}
                            <button
                                onClick={() => handleCheckout(plan)}
                                disabled={!user?.id || loadingPlanId === plan.id}
                                className={`mt-auto flex items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-sm font-semibold transition ${styles.button}`}
                            >
                                {loadingPlanId === plan.id ? <Loader2 size={18} className="animate-spin" /> : <CreditCardIcon size={18} />}
                                {loadingPlanId === plan.id ? "Redirection..." : buttonLabel}
                            </button>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
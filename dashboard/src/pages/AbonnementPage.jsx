import React from "react";
import { Check, CreditCardIcon, Star, Crown, Sparkles } from "lucide-react";

const plans = [
    {
        name: "Silver",
        icon: Star,
        price: "9",
        color: "zinc",
        features: [
            "100 tokens / mois",
            "1 projet actif",
            "Support par email",
            "Historique 7 jours",
        ],
        highlighted: false,
    },
    {
        name: "Gold",
        icon: Sparkles,
        price: "29",
        color: "blue",
        features: [
            "500 tokens / mois",
            "5 projets actifs",
            "Support prioritaire",
            "Historique 30 jours",
            "Accès aux modèles avancés",
        ],
        highlighted: true,
    },
    {
        name: "Ultimate",
        icon: Crown,
        price: "79",
        color: "purple",
        features: [
            "Tokens illimités",
            "Projets illimités",
            "Support dédié 24/7",
            "Historique illimité",
            "Accès aux modèles avancés",
            "API personnalisée",
        ],
        highlighted: false,
    },
];

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

export default function AbonnementPage() {
    return (
        <div className="h-full overflow-y-auto p-8 max-w-5xl mx-auto animate-[fadeIn_0.3s_ease-out]">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold mb-2">Abonnements</h1>
                <p className="text-zinc-400 text-sm">Manage your account, appearance, and connected networks</p>
            </div>

            {/* Plans */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
                {plans.map((plan) => {
                    const styles = colorStyles[plan.color];
                    const Icon = plan.icon;

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
                                onClick={() => {
                                    // Handle plan upgrade logic here
                                }}
                                className={`mt-auto flex items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-sm font-semibold transition ${styles.button}`}
                            >
                                <CreditCardIcon size={18} />
                                {plan.highlighted ? "Upgrade" : "Choisir"}
                            </button>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
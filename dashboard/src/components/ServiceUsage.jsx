import React from "react";
import {CreditCardIcon, LogOut} from "lucide-react";

function ProgressBar({ used, total, color = "green", label }) {
    const progress = Math.min(100, Math.round((used / total) * 100));

    const colors = {
        green: "bg-green-500",
        blue: "bg-blue-500",
        red: "bg-red-500",
        purple: "bg-purple-500",
        zinc: "bg-zinc-400",
    };

    return (
        <div className="mb-4">
            <div className="flex justify-between text-xs text-zinc-500 mb-1">
                <span>{label}</span>
                <span>{used} / {total} tokens</span>
            </div>
            <div className="w-full bg-zinc-200 rounded-lg overflow-hidden h-4">
                <div
                    className={`h-full ${colors[color]} transition-all duration-300 ease-out`}
                    style={{ width: `${progress}%` }}
                />
            </div>
        </div>
    );
}

export default function ServiceUsage() {
    return (
        <div className="p-4">
            <ProgressBar label="Clip Generation" used={40} total={100} color="blue"/>
            <ProgressBar label="Caption Generation" used={0} total={100} color="zinc"/>

            <div className="flex items-center justify-between gap-4 mb-3">
                <div className="flex-1 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                    <p className="text-xs text-blue-300 leading-relaxed">
                        💡 <strong>Note:</strong> Vous êtes actuellement au plan basique, la réinitialisation de votre quota est dans 15 jours, vous pouvez changer de formule à tout moment.
                    </p>
                </div>

                <button
                    onClick={() => {
                        // Handle plan change logic here
                    }}
                    className="flex shrink-0 items-center justify-center gap-2 rounded-2xl border border-green-500/20 bg-green-500/10 px-4 py-3 text-sm font-semibold text-green-300 transition hover:bg-green-500/15"
                >
                    <CreditCardIcon size={20} />
                    Changer
                </button>
            </div>
        </div>
    );
}
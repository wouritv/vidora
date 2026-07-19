import { ArrowRight, Sparkles, Image } from "lucide-react";
import { useAuth } from "../state/AuthContext";
import { DASHBOARD_SIDEBAR_ITEMS } from "../lib/dashboard-nav";
import { useNavigate } from "react-router-dom";

export default function Dashboard() {

    const { user } = useAuth();
    const navigate = useNavigate();

    const displayName =
        user?.user_metadata?.full_name ||
        user?.user_metadata?.name ||
        user?.email?.split("@")[0] ||
        "Utilisateur";

    const serviceItems = DASHBOARD_SIDEBAR_ITEMS.filter((item) => item.key !== "dashboard");

    return (
        <div className="flex-1 overflow-y-auto p-8 space-y-10">
            <section className="flex flex-col gap-4 rounded-3xl border border-white/10 bg-gradient-to-br from-primary/15 via-violet-500/10 to-transparent p-6 md:flex-row md:items-end md:justify-between">
                <div className="max-w-2xl space-y-3">
                    <p className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
                        <Sparkles size={14} />
                        Welcome back
                    </p>
                    <h2 className="text-3xl font-black tracking-tight">Bonjour {displayName}</h2>
                    <p className="text-sm leading-6 text-zinc-300">
                        Lance un workflow puis retrouve tous les resultats dans les galeries de services.
                    </p>
                </div>
            </section>

            <section className="space-y-6">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">Demarrer une action</p>
                    <h3 className="mt-2 text-xl font-bold">Parcours de generation</h3>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                    <button
                        onClick={() => navigate("/dashboard/clip-generator")}
                        className="group rounded-2xl border border-white/10 bg-white/5 p-5 text-left hover:bg-white/10 transition"
                    >
                        <div className="flex items-center justify-between">
                            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/10 text-violet-400">
                                <Sparkles size={18} />
                            </span>
                            <ArrowRight size={16} className="text-zinc-500 group-hover:text-white" />
                        </div>
                        <h4 className="mt-5 text-lg font-semibold text-white">Generer des reels</h4>
                        <p className="mt-2 text-sm leading-6 text-zinc-400">Upload une video longue et laisse le systeme extraire les moments reels.</p>
                    </button>

                    <button
                        onClick={() => navigate("/dashboard/youtube-studio")}
                        className="group rounded-2xl border border-white/10 bg-white/5 p-5 text-left hover:bg-white/10 transition"
                    >
                        <div className="flex items-center justify-between">
                            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                                <Image size={18} />
                            </span>
                            <ArrowRight size={16} className="text-zinc-500 group-hover:text-white" />
                        </div>
                        <h4 className="mt-5 text-lg font-semibold text-white">Creer des IA Captions</h4>
                        <p className="mt-2 text-sm leading-6 text-zinc-400">Upload une video, choisis la plateforme cible, ajuste les captions puis rends la version finale.</p>
                    </button>
                </div>
            </section>


        </div>

    );
}
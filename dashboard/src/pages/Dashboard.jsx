import { ArrowRight, Sparkles } from "lucide-react";
import { useAuth } from "../state/AuthContext";
import { DASHBOARD_SIDEBAR_ITEMS } from "../lib/dashboard-nav";
import { useNavigate } from "react-router-dom";

export default function Dashboard() {

    const { user} = useAuth();
    const navigate = useNavigate();

    const displayName =
        user?.user_metadata?.full_name ||
        user?.user_metadata?.name ||
        user?.email?.split("@")[0] ||
        "Utilisateur";

    const serviceItems = DASHBOARD_SIDEBAR_ITEMS.filter((item) => item.key !== "dashboard");

    return (

        <div className="flex-1 overflow-y-auto p-8">

            <section className="flex flex-col gap-4 rounded-3xl border border-white/10 bg-gradient-to-br from-primary/15 via-violet-500/10 to-transparent p-6 md:flex-row md:items-end md:justify-between">

                <div className="max-w-2xl space-y-3">
                    <p className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
                        <Sparkles size={14} />
                        Welcome back
                    </p>
                    <h2 className="text-3xl font-black tracking-tight">Bonjour {displayName}</h2>
                    <p className="text-sm leading-6 text-zinc-300">
                        Cette page sert de hub comme dans `source/dashboard`: elle presente un shell dashboard, un resume du compte,
                        puis des raccourcis vers les outils de production. Chaque outil a maintenant sa propre page sous `dashboard/*`.
                    </p>
                </div>

            </section>

            <section className="space-y-6 mt-8">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">Raccourcis services</p>
                    <h3 className="mt-2 text-xl font-bold">Services actifs</h3>
                </div>

                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {serviceItems.map((item) => {
                        const ItemIcon = item.icon;
                        return (
                            <button
                                key={item.key}
                                onClick={() => navigate(item.path)}
                                className="group rounded-2xl border border-white/10 bg-white/5 p-5 text-left hover:bg-white/10 transition"
                            >
                                <div className="flex items-center justify-between">
                                    <span className={`inline-flex h-10 w-10 items-center justify-center rounded-xl ${item.activeClassName}`}>
                                        <ItemIcon size={18} />
                                    </span>
                                    <ArrowRight size={16} className="text-zinc-500 group-hover:text-white" />
                                </div>

                                <h4 className="mt-5 text-lg font-semibold text-white">{item.title}</h4>
                                <p className="mt-2 text-sm leading-6 text-zinc-400">{item.description}</p>

                            </button>
                        );
                    })}
                </div>

            </section>

        </div>

    );
}
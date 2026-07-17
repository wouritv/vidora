import { ArrowRight, ExternalLink, LogOut, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { DASHBOARD_SIDEBAR_ITEMS, getWorkspacePath } from "../lib/dashboard-nav";
import { useAuth } from "../state/AuthContext";

export default function Dashboard() {
    const navigate = useNavigate();
    const { user, logout } = useAuth();

    const displayName =
        user?.user_metadata?.full_name ||
        user?.user_metadata?.name ||
        user?.email?.split("@")[0] ||
        "Utilisateur";

    const serviceItems = DASHBOARD_SIDEBAR_ITEMS.filter((item) => item.category === "service");
    const utilityItems = DASHBOARD_SIDEBAR_ITEMS.filter((item) => item.category === "utility");

    return (
        <div className="min-h-screen bg-background text-white">
            <div className="mx-auto grid min-h-screen max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[280px_minmax(0,1fr)]">
                <aside className="space-y-6 rounded-3xl border border-white/10 bg-surface/60 p-6 backdrop-blur-xl">
                    <div className="space-y-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Dashboard</p>
                        <h1 className="text-2xl font-bold tracking-tight">Espace de travail</h1>
                        <p className="text-sm leading-6 text-zinc-400">
                            Structure inspiree de `source/dashboard`, avec les services reels conserves depuis la sidebar de `App.jsx`.
                        </p>
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                        <p className="text-sm font-medium text-white">{displayName}</p>
                        <p className="mt-1 text-xs text-zinc-400">{user?.email || "Aucune adresse email"}</p>
                    </div>

                    <div className="space-y-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-zinc-500">Navigation</p>
                        <div className="space-y-2">
                            {DASHBOARD_SIDEBAR_ITEMS.map((item) => {
                                const ItemIcon = item.icon;

                                return (
                                    <button
                                        key={item.key}
                                        type="button"
                                        onClick={() => navigate(getWorkspacePath(item.key))}
                                        className="flex w-full items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-left transition hover:border-white/20 hover:bg-white/10"
                                    >
                                        <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${item.activeClassName}`}>
                                            <ItemIcon size={18} />
                                        </span>
                                        <span className="min-w-0 flex-1">
                                            <span className="block text-sm font-semibold text-white">{item.title}</span>
                                            <span className="block truncate text-xs text-zinc-400">{item.badge}</span>
                                        </span>
                                        <ArrowRight size={16} className="text-zinc-500" />
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    <button
                        type="button"
                        onClick={logout}
                        className="flex w-full items-center justify-center gap-2 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-300 transition hover:bg-red-500/15"
                    >
                        <LogOut size={16} />
                        Deconnexion
                    </button>
                </aside>

                <main className="space-y-6 rounded-3xl border border-white/10 bg-background/80 p-6 lg:p-8">
                    <section className="flex flex-col gap-4 rounded-3xl border border-white/10 bg-gradient-to-br from-primary/15 via-violet-500/10 to-transparent p-6 md:flex-row md:items-end md:justify-between">
                        <div className="max-w-2xl space-y-3">
                            <p className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
                                <Sparkles size={14} />
                                Welcome back
                            </p>
                            <h2 className="text-3xl font-black tracking-tight">Bonjour {displayName}</h2>
                            <p className="text-sm leading-6 text-zinc-300">
                                Cette page sert de hub comme dans `source/dashboard`: elle presente un shell dashboard, un resume du compte,
                                puis des raccourcis vers les outils de production. Le contenu metier reste celui de `App.jsx`.
                            </p>
                        </div>

                        <div className="flex flex-wrap gap-3">
                            <button
                                type="button"
                                onClick={() => navigate(getWorkspacePath("dashboard"))}
                                className="rounded-2xl bg-primary px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-500"
                            >
                                Ouvrir le workspace
                            </button>
                            <a
                                href="https://github.com/mutonby/openshorts"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-zinc-200 transition hover:bg-white/10"
                            >
                                Documentation <ExternalLink size={15} />
                            </a>
                        </div>
                    </section>

                    <section className="space-y-4">
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">Raccourcis services</p>
                            <h3 className="mt-2 text-xl font-bold">Services actifs</h3>
                            <p className="mt-1 text-sm text-zinc-400">
                                Les cartes ci-dessous reprennent les memes services que la sidebar de `App.jsx`, sans reutiliser les services definis dans `source/dashboard/page.tsx`.
                            </p>
                        </div>

                        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                            {serviceItems.map((item) => {
                                const ItemIcon = item.icon;

                                return (
                                    <button
                                        key={item.key}
                                        type="button"
                                        onClick={() => navigate(getWorkspacePath(item.key))}
                                        className="group rounded-3xl border border-white/10 bg-surface/50 p-5 text-left transition hover:-translate-y-0.5 hover:border-white/20 hover:bg-surface/80"
                                    >
                                        <div className="flex items-start justify-between gap-4">
                                            <span className={`flex h-12 w-12 items-center justify-center rounded-2xl ${item.activeClassName}`}>
                                                <ItemIcon size={22} />
                                            </span>
                                            <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-zinc-300">
                                                {item.badge}
                                            </span>
                                        </div>

                                        <h4 className="mt-5 text-lg font-semibold text-white">{item.title}</h4>
                                        <p className="mt-2 text-sm leading-6 text-zinc-400">{item.description}</p>

                                        <span className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-primary transition group-hover:gap-3">
                                            Ouvrir <ArrowRight size={16} />
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                    </section>

                    <section className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(260px,1fr)]">
                        <div className="rounded-3xl border border-white/10 bg-surface/40 p-6">
                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">Structure</p>
                            <h3 className="mt-2 text-xl font-bold">Alignement avec `source/dashboard`</h3>
                            <ul className="mt-4 space-y-3 text-sm leading-6 text-zinc-300">
                                <li>• Une page dashboard distincte sert de hub et ne rend plus directement tout `App.jsx`.</li>
                                <li>• Le workspace complet reste accessible via une route dediee.</li>
                                <li>• Les services disponibles proviennent maintenant d'une config partagee entre `Dashboard.jsx` et `App.jsx`.</li>
                                <li>• Les styles legacy login restent confines aux pages auth uniquement.</li>
                            </ul>
                        </div>

                        <div className="rounded-3xl border border-white/10 bg-surface/40 p-6">
                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">Configuration</p>
                            <h3 className="mt-2 text-xl font-bold">Actions rapides</h3>
                            <div className="mt-4 space-y-3">
                                {utilityItems.map((item) => {
                                    const ItemIcon = item.icon;

                                    return (
                                        <button
                                            key={item.key}
                                            type="button"
                                            onClick={() => navigate(getWorkspacePath(item.key))}
                                            className="flex w-full items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-left transition hover:bg-white/10"
                                        >
                                            <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${item.activeClassName}`}>
                                                <ItemIcon size={18} />
                                            </span>
                                            <span className="flex-1">
                                                <span className="block text-sm font-semibold text-white">{item.title}</span>
                                                <span className="block text-xs text-zinc-400">{item.description}</span>
                                            </span>
                                            <ArrowRight size={16} className="text-zinc-500" />
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    </section>
                </main>
            </div>
        </div>
    );
}
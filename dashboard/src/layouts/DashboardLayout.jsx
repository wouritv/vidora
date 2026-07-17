import { ExternalLink, Globe, LogOut } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { DASHBOARD_SIDEBAR_ITEMS } from "../lib/dashboard-nav";
import { useAuth } from "../state/AuthContext";

export default function DashboardLayout() {
    const { user, logout } = useAuth();

    const displayName =
        user?.user_metadata?.full_name ||
        user?.user_metadata?.name ||
        user?.email?.split("@")[0] ||
        "Utilisateur";

    return (
        <div className="min-h-screen bg-background text-white">
            <div className="mx-auto grid min-h-screen max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[280px_minmax(0,1fr)]">
                <aside className="flex max-h-[calc(100vh-4rem)] flex-col overflow-hidden rounded-3xl border border-white/10 bg-surface/60 backdrop-blur-xl lg:sticky lg:top-8">
                    <div className="border-b border-white/10 p-6">
                        <div className="flex items-center gap-3">
                            <div className="h-10 w-10 overflow-hidden rounded-2xl border border-white/10 bg-white/5">
                                <img src="/logo-openshorts.png" alt="OpenShorts" className="h-full w-full object-cover" />
                            </div>
                            <div>
                                <p className="text-sm font-semibold tracking-tight text-white">OpenShorts</p>
                                <p className="text-xs text-zinc-400">AI video workspace</p>
                            </div>
                        </div>

                        <div className="mt-5 rounded-2xl border border-white/10 bg-white/5 p-4">
                            <p className="text-sm font-medium text-white">{displayName}</p>
                            <p className="mt-1 text-xs text-zinc-400">{user?.email || "Aucune adresse email"}</p>
                        </div>
                    </div>

                    <div className="flex-1 overflow-y-auto px-4 py-5">
                        <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Navigation</p>
                        <nav className="mt-3 space-y-2">
                            {DASHBOARD_SIDEBAR_ITEMS.map((item) => {
                                const ItemIcon = item.icon;

                                return (
                                    <NavLink
                                        key={item.key}
                                        to={item.path}
                                        end={item.key === "dashboard"}
                                        className={({ isActive }) =>
                                            `relative flex items-center gap-3 overflow-hidden rounded-2xl px-4 py-3 transition ${
                                                isActive
                                                    ? "bg-white/10 text-white shadow-lg shadow-black/10"
                                                    : "text-zinc-400 hover:bg-white/5 hover:text-white"
                                            }`
                                        }
                                    >
                                        {({ isActive }) => (
                                            <>
                                                <span
                                                    className={`absolute left-0 top-1/2 h-8 w-1 -translate-y-1/2 rounded-r-full transition ${
                                                        isActive ? "bg-primary opacity-100" : "bg-transparent opacity-0"
                                                    }`}
                                                />
                                                <span
                                                    className={`flex h-11 w-11 items-center justify-center rounded-2xl transition ${
                                                        isActive ? item.activeClassName : "bg-white/5 text-zinc-400"
                                                    }`}
                                                >
                                                    <ItemIcon size={18} />
                                                </span>
                                                <span className="min-w-0 flex-1">
                                                    <span className="block truncate text-sm font-semibold">{item.sidebarLabel}</span>
                                                    <span className="block truncate text-xs text-zinc-500">{item.badge}</span>
                                                </span>
                                            </>
                                        )}
                                    </NavLink>
                                );
                            })}
                        </nav>
                    </div>

                    <div className="border-t border-white/10 p-4 space-y-2">
                        <button
                            type="button"
                            onClick={() => {
                                localStorage.removeItem("openshorts_skip_landing");
                                globalThis.location.href = "/";
                            }}
                            className="flex w-full items-center gap-3 rounded-2xl bg-white/5 px-4 py-3 text-left transition hover:bg-white/10"
                        >
                            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                                <Globe size={18} />
                            </span>
                            <span>
                                <span className="block text-sm font-semibold text-white">Landing Page</span>
                                <span className="block text-xs text-zinc-500">Retour au site</span>
                            </span>
                        </button>

                        <a
                            href="https://github.com/mutonby/openshorts"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-3 rounded-2xl bg-white/5 px-4 py-3 transition hover:bg-white/10"
                        >
                            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-black">
                                <ExternalLink size={18} />
                            </span>
                            <span>
                                <span className="block text-sm font-semibold text-white">Open Source</span>
                                <span className="block text-xs text-zinc-500">GitHub repository</span>
                            </span>
                        </a>

                        <button
                            type="button"
                            onClick={logout}
                            className="flex w-full items-center justify-center gap-2 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-300 transition hover:bg-red-500/15"
                        >
                            <LogOut size={16} />
                            Deconnexion
                        </button>
                    </div>
                </aside>

                <section className="min-h-0">
                    <Outlet />
                </section>
            </div>
        </div>
    );
}


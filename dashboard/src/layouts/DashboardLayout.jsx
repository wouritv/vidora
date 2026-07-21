import {CreditCard, LogOut } from "lucide-react";
import {NavLink, Outlet, useNavigate} from "react-router-dom";
import { DASHBOARD_SIDEBAR_ITEMS } from "../lib/dashboard-nav";
import { useAuth } from "../state/AuthContext";

export default function DashboardLayout() {
    const { user, logout } = useAuth();

    const navigate = useNavigate();
    const displayName =
        user?.user_metadata?.full_name ||
        user?.user_metadata?.name ||
        user?.email?.split("@")[0] ||
        "Utilisateur";

    return (
        <div className="min-h-screen bg-background text-white selection:bg-primary/30">
            <div className="flex h-screen overflow-hidden">
                <aside className="w-20 lg:w-64 bg-surface border-r border-white/5 flex flex-col h-full shrink-0 transition-all duration-300">
                    <div className="p-6 flex items-center gap-3">
                        <div className="w-8 h-8 bg-white/5 rounded-lg flex items-center justify-center shrink-0 overflow-hidden border border-white/5">
                            <img src="/logo-openshorts.png" alt="Logo" className="w-full h-full object-cover" />
                        </div>
                        <span className="font-bold text-lg text-white hidden lg:block tracking-tight">OpenShorts</span>

                    </div>

                    <div className="mt-5 rounded-2xl border border-white/10 bg-white/5 p-4 mx-4 flex flex-col items-start gap-1">
                        <p className="text-sm font-medium text-white">{displayName}</p>
                        <p className="mt-1 text-xs text-zinc-400">{user?.email || "Aucune adresse email"}</p>
                    </div>

                    <nav className="flex-1 px-4 py-4 space-y-2 overflow-y-auto custom-scrollbar">
                        {DASHBOARD_SIDEBAR_ITEMS.map((item) => {
                            const ItemIcon = item.icon;
                            return (
                                <NavLink
                                    key={item.key}
                                    to={item.path}
                                    end={item.path === "/dashboard"}
                                    className={({ isActive }) =>
                                        `w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-colors ${
                                            isActive ? item.activeClassName : item.inactiveClassName
                                        }`
                                    }
                                >
                                    <ItemIcon size={20} />
                                    <span className="font-medium hidden lg:block">{item.sidebarLabel}</span>
                                </NavLink>
                            );
                        })}
                    </nav>

                    <div className="p-4 border-t border-white/5 space-y-2">
                        <button
                            onClick={logout}
                            className="mx-auto mt-2 flex w-[calc(100%-1rem)] items-center justify-center gap-2 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-300 transition hover:bg-red-500/15"
                        >
                            <LogOut size={16} />
                            Logout
                        </button>
                    </div>
                </aside>

                <main className="flex-1 flex flex-col h-full overflow-hidden relative">
                    <div className="absolute inset-0 overflow-hidden -z-10 pointer-events-none">
                        <div className="absolute -top-[10%] -right-[10%] w-[50%] h-[50%] bg-primary/5 rounded-full blur-[120px]" />
                    </div>
                    <Outlet />
                </main>
            </div>
        </div>
    );
}
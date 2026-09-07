import { useEffect, useMemo, useState } from "react";
import { ChevronRight, LogOut, Menu } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { fetchAppConfig, getDefaultHideSocialPlatforms } from "../config";
import { DASHBOARD_SIDEBAR_ITEMS } from "../lib/dashboard-nav";
import { useAuth } from "../state/AuthContext";
import { useTranslation } from "../state/LanguageContext";

export default function DashboardLayout() {
    const { user, logout } = useAuth();
    const { t } = useTranslation();
    const location = useLocation();
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const [isDesktopLike, setIsDesktopLike] = useState(() => {
        if (typeof window === "undefined") return true;
        return window.matchMedia("(min-width: 1024px), ((min-width: 768px) and (orientation: landscape))").matches;
    });
    const [hideSocialPlatforms, setHideSocialPlatforms] = useState(getDefaultHideSocialPlatforms());
    const displayName =
        user?.user_metadata?.full_name ||
        user?.user_metadata?.name ||
        user?.email?.split("@")[0] ||
        t("settings.user", "Utilisateur");

    useEffect(() => {
        let active = true;
        fetchAppConfig()
            .then((cfg) => {
                if (!active || !cfg || typeof cfg.hideSocialPlatforms !== "boolean") return;
                setHideSocialPlatforms(cfg.hideSocialPlatforms);
            })
            .catch(() => {});
        return () => {
            active = false;
        };
    }, []);

    useEffect(() => {
        if (typeof window === "undefined") return undefined;
        const mediaQuery = window.matchMedia("(min-width: 1024px), ((min-width: 768px) and (orientation: landscape))");
        const handleChange = (event) => {
            setIsDesktopLike(event.matches);
        };
        setIsDesktopLike(mediaQuery.matches);
        mediaQuery.addEventListener("change", handleChange);
        return () => mediaQuery.removeEventListener("change", handleChange);
    }, []);

    useEffect(() => {
        if (isDesktopLike) {
            setIsSidebarOpen(false);
        }
    }, [isDesktopLike]);

    useEffect(() => {
        if (!isDesktopLike) {
            setIsSidebarOpen(false);
        }
    }, [location.pathname, location.search, isDesktopLike]);

    useEffect(() => {
        if (isDesktopLike || !isSidebarOpen) return undefined;
        const onEscape = (event) => {
            if (event.key === "Escape") {
                setIsSidebarOpen(false);
            }
        };
        window.addEventListener("keydown", onEscape);
        return () => window.removeEventListener("keydown", onEscape);
    }, [isDesktopLike, isSidebarOpen]);

    const sidebarItems = useMemo(
        () => DASHBOARD_SIDEBAR_ITEMS.filter((item) => !(hideSocialPlatforms && item.key === "social-publications")),
        [hideSocialPlatforms]
    );

    const labelClassName = isDesktopLike ? "font-medium hidden lg:block" : "font-medium";

    return (
        <div className="min-h-screen bg-background text-white selection:bg-primary/30">
            <div className={`relative flex h-screen ${isDesktopLike ? "overflow-hidden" : "overflow-visible"}`}>
                {!isDesktopLike && isSidebarOpen && (
                    <button
                        type="button"
                        aria-label={t("sidebar.close", "Fermer le menu")}
                        onClick={() => setIsSidebarOpen(false)}
                        className="fixed inset-0 z-30 bg-black/55 backdrop-blur-[1px]"
                    />
                )}

                <aside
                    className={`bg-surface border-r border-slate-200 dark:border-white/5 flex flex-col transition-all duration-300 ${
                        isDesktopLike
                            ? "w-20 lg:w-64 h-full shrink-0"
                            : `fixed inset-y-0 left-0 z-40 h-screen w-72 max-w-[85vw] shadow-2xl transform ${
                                  isSidebarOpen ? "translate-x-0" : "-translate-x-full"
                              }`
                    }`}
                >
                    <div className="p-6 flex items-center gap-3">
                        <div className="w-8 h-8 bg-white/5 rounded-lg flex items-center justify-center shrink-0 overflow-hidden border border-slate-200 dark:border-white/5">
                            <img src="/icone.png" alt="Logo" className="w-full h-full object-cover" />
                        </div>
                        <span className={`${isDesktopLike ? "font-bold text-lg text-white hidden lg:block tracking-tight" : "font-bold text-lg text-white tracking-tight"}`}>VIREEL</span>

                    </div>

                    <div className="mt-5 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 mx-4 flex flex-col items-start gap-1">
                        <p className="text-sm font-medium text-white">{displayName}</p>
                        <p className="mt-1 text-xs text-slate-500 dark:text-zinc-400">{user?.email || "Aucune adresse email"}</p>
                    </div>

                    <nav className="flex-1 px-4 py-4 space-y-2 overflow-y-auto custom-scrollbar">
                        {sidebarItems.map((item) => {
                            const ItemIcon = item.icon;
                            if (item.key === "reels" || item.key === "captions") {
                                return (
                                    <div key={item.key} className="rounded-xl border border-slate-200 dark:border-white/5 bg-white/0 p-2">
                                        <div className="flex items-center gap-3 px-1 py-2 text-slate-700 dark:text-zinc-200">
                                            <ItemIcon size={18} />
                                            <span className={labelClassName}>{item.sidebarLabel}</span>
                                        </div>

                                        <NavLink
                                            to={item.path}
                                            onClick={() => {
                                                if (!isDesktopLike) setIsSidebarOpen(false);
                                            }}
                                            className={({ isActive }) =>
                                                `mt-1 flex items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors ${
                                                    isActive ? item.activeClassName : "text-slate-500 dark:text-zinc-400 hover:text-white hover:bg-white/5"
                                                }`
                                            }
                                        >
                                            <span>{isDesktopLike ? "Mes projets" : "Projets"}</span>
                                            <ChevronRight size={14} className="opacity-70" />
                                        </NavLink>
                                    </div>
                                );
                            }

                            return (
                                <NavLink
                                    key={item.key}
                                    to={item.path}
                                    end={item.path === "/dashboard"}
                                    onClick={() => {
                                        if (!isDesktopLike) setIsSidebarOpen(false);
                                    }}
                                    className={({ isActive }) =>
                                        `w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-colors ${
                                            isActive ? item.activeClassName : item.inactiveClassName
                                        }`
                                    }
                                >
                                    <ItemIcon size={20} />
                                    <span className={labelClassName}>{item.sidebarLabel}</span>
                                </NavLink>
                            );
                        })}
                    </nav>

                    <div className="p-4 border-t border-slate-200 dark:border-white/5 space-y-2">
                        <button
                            onClick={logout}
                            className="mx-auto mt-2 flex w-[calc(100%-1rem)] items-center justify-center gap-2 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-300 transition hover:bg-red-500/15"
                        >
                            <LogOut size={16} />
                            {t("settings.logout", "Se déconnecter")}
                        </button>
                    </div>
                </aside>

                <main className={`flex-1 flex flex-col h-full relative ${isDesktopLike ? "overflow-hidden" : "overflow-visible"}`}>
                    {!isDesktopLike && (
                        <button
                            type="button"
                            aria-label={t("sidebar.open", "Ouvrir le menu")}
                            onClick={() => setIsSidebarOpen(true)}
                            className="absolute left-4 top-4 z-20 inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-300 dark:border-white/10 bg-surface/95 text-white shadow-lg backdrop-blur-sm"
                        >
                            <Menu size={18} />
                        </button>
                    )}
                    <div className="absolute inset-0 overflow-hidden -z-10 pointer-events-none">
                        <div className="absolute -top-[10%] -right-[10%] w-[50%] h-[50%] bg-primary/5 rounded-full blur-[120px]" />
                    </div>
                    <div className={isDesktopLike ? "h-full" : "h-full pt-16"}>
                        <Outlet />
                    </div>
                </main>
            </div>
        </div>
    );
}
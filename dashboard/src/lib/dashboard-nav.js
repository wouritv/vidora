import {
    Bot,
    Film,
    Home,
    Image,
    LayoutGrid,
    Settings,
    Sparkles,
} from "lucide-react";

export const DASHBOARD_SIDEBAR_ITEMS = [
    {
        key: "dashboard",
        title: "Dashboard",
        sidebarLabel: "Dashboard",
        description: "Hub principal pour acceder a tous les outils OpenShorts et a ton espace de production.",
        icon: Home,
        activeClassName: "bg-primary/10 text-primary",
        inactiveClassName: "text-zinc-400 hover:text-white hover:bg-white/5",
        badge: "Hub",
        category: "hub",
        path: "/dashboard",
    },
    {
        key: "clip-generator",
        title: "Clip Generator",
        sidebarLabel: "Clip Generator",
        description: "Genere des shorts viraux a partir de videos longues avec l'analyse IA et le split view de production.",
        icon: Film,
        activeClassName: "bg-primary/10 text-primary",
        inactiveClassName: "text-zinc-400 hover:text-white hover:bg-white/5",
        badge: "Core",
        category: "service",
        path: "/dashboard/clip-generator",
    },
    {
        key: "ai-shorts",
        title: "AI Shorts",
        sidebarLabel: "AI Shorts",
        description: "Cree des videos courtes pour produits SaaS avec hooks, scripts et rendus automatises.",
        icon: Sparkles,
        activeClassName: "bg-violet-500/10 text-violet-400",
        inactiveClassName: "text-zinc-400 hover:text-white hover:bg-white/5",
        badge: "New",
        category: "service",
        path: "/dashboard/ai-shorts",
    },
    {
        key: "ai-agent",
        title: "AI Agent",
        sidebarLabel: "AI Agent",
        description: "Pilote le workflow autonome de clipping pour traiter un lot de videos verticales.",
        icon: Bot,
        activeClassName: "bg-emerald-500/10 text-emerald-400",
        inactiveClassName: "text-zinc-400 hover:text-white hover:bg-white/5",
        badge: "Auto",
        category: "service",
        path: "/dashboard/ai-agent",
    },
    {
        key: "ugc-gallery",
        title: "UGC Gallery",
        sidebarLabel: "UGC Gallery",
        description: "Parcours la galerie UGC et les variations creatives generees pour tes campagnes.",
        icon: LayoutGrid,
        activeClassName: "bg-violet-500/10 text-violet-400",
        inactiveClassName: "text-zinc-400 hover:text-white hover:bg-white/5",
        badge: "Gallery",
        category: "service",
        path: "/dashboard/ugc-gallery",
    },
    {
        key: "youtube-studio",
        title: "YouTube Studio",
        sidebarLabel: "YouTube Studio",
        description: "Genere des thumbnails et assets YouTube adaptes a tes clips et contenus longs.",
        icon: Image,
        activeClassName: "bg-primary/10 text-primary",
        inactiveClassName: "text-zinc-400 hover:text-white hover:bg-white/5",
        badge: "Studio",
        category: "service",
        path: "/dashboard/youtube-studio",
    },
    {
        key: "settings",
        title: "Settings",
        sidebarLabel: "Settings",
        description: "Configure les cles Gemini, Upload-Post, ElevenLabs et fal.ai pour activer chaque service.",
        icon: Settings,
        activeClassName: "bg-primary/10 text-primary",
        inactiveClassName: "text-zinc-400 hover:text-white hover:bg-white/5",
        badge: "Config",
        category: "utility",
        path: "/dashboard/settings",
    },
];

const DASHBOARD_KEY_ALIASES = {
    dashboard: "clip-generator",
    saasshorts: "ai-shorts",
    thumbnails: "youtube-studio",
};

export function normalizeDashboardKey(value) {
    if (!value) {
        return "dashboard";
    }
    return DASHBOARD_KEY_ALIASES[value] ?? value;
}

export function isDashboardTab(value) {
    const normalizedValue = normalizeDashboardKey(value);
    return DASHBOARD_SIDEBAR_ITEMS.some((item) => item.key === normalizedValue);
}

export function getWorkspacePath(tabKey = "dashboard") {
    const normalizedValue = normalizeDashboardKey(tabKey);
    const match = DASHBOARD_SIDEBAR_ITEMS.find((item) => item.key === normalizedValue);
    return match?.path ?? "/dashboard";
}

export function getDashboardItem(tabKey = "dashboard") {
    const normalizedValue = normalizeDashboardKey(tabKey);
    return DASHBOARD_SIDEBAR_ITEMS.find((item) => item.key === normalizedValue) ?? DASHBOARD_SIDEBAR_ITEMS[0];
}
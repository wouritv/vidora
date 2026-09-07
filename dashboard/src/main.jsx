import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";

import { AuthProvider, useAuth } from "./state/AuthContext";
import { ThemeProvider } from "./state/ThemeContext";
import { UserCreditsProvider } from "./state/UserCreditsContext";
import { LanguageProvider } from "./state/LanguageContext";
import ProtectedRoute from "./components/ProtectedRoute";
import DashboardLayout from "./layouts/DashboardLayout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import DashboardTabPage from "./pages/DashboardTabPage";
import ReelsProjectsPage from "./pages/ReelsProjectsPage";
import CaptionProjectsPage from "./pages/CaptionProjectsPage";
import ReelProjectDetailPage from "./pages/ReelProjectDetailPage";
import CaptionProjectDetailPage from "./pages/CaptionProjectDetailPage";
import NewCaptionPage from "./pages/NewCaptionPage";
import ResetPassword from "./pages/ResetPassword";
import UpdatePassword from "./pages/UpdatePassword";
import AbonnementPage from "./pages/AbonnementPage";
import SocialPublicationsPage from "./pages/SocialPublicationsPage";
import Landing from "./Landing.jsx";

function RootRedirect() {
    const { isAuthenticated, loading } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center">
                Chargement...
            </div>
        );
    }

    if (isAuthenticated) {
        return <Navigate to="/dashboard" replace />;
    }

    return <Landing />;
}

ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
        <AuthProvider>
            <ThemeProvider>
                <UserCreditsProvider>
                <LanguageProvider>
                <BrowserRouter>
                    <Routes>
                        <Route path="/" element={<RootRedirect />} />
                        <Route path="/login" element={<Login />} />
                        <Route path="/reset-password" element={<ResetPassword />} />
                        <Route path="/update-password" element={<UpdatePassword />} />

                        <Route
                            path="/dashboard"
                            element={
                                <ProtectedRoute>
                                    <DashboardLayout />
                                </ProtectedRoute>
                            }
                        >
                            <Route index element={<Dashboard />} />
                            <Route path="reel-generator" element={<DashboardTabPage tabKey="reel-generator" />} />
                            <Route path="reels" element={<ReelsProjectsPage />} />
                            <Route path="reels/projects/:projectId" element={<ReelProjectDetailPage />} />
                            <Route path="captions" element={<CaptionProjectsPage />} />
                            <Route path="captions/projects/:projectId" element={<CaptionProjectDetailPage />} />
                            <Route path="captions/new" element={<NewCaptionPage />} />
                            <Route path="social-publications" element={<SocialPublicationsPage />} />
                            <Route path="settings" element={<DashboardTabPage tabKey="settings" />} />
                            <Route path="abonnements" element={<AbonnementPage />} />
                        </Route>

                        <Route path="*" element={<RootRedirect />} />
                    </Routes>
                </BrowserRouter>
                </LanguageProvider>
                </UserCreditsProvider>
            </ThemeProvider>
        </AuthProvider>
    </React.StrictMode>
);
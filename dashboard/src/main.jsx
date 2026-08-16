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
import ReelsPage from "./pages/ReelsPage";
import ResetPassword from "./pages/ResetPassword";
import UpdatePassword from "./pages/UpdatePassword";
import CaptionsPage from "./pages/CaptionsPage.jsx";
import AbonnementPage from "./pages/AbonnementPage";
import SocialPublicationsPage from "./pages/SocialPublicationsPage";

function RootRedirect() {
    const { isAuthenticated, loading } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center">
                Chargement...
            </div>
        );
    }

    return <Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />;
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
                            <Route path="reels" element={<ReelsPage />} />
                            <Route path="social-publications" element={<SocialPublicationsPage />} />
                            <Route path="captions" element={<CaptionsPage />} />
                            <Route path="caption-generator" element={<DashboardTabPage tabKey="caption-generator" />} />
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
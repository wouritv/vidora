import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";

import { AuthProvider, useAuth } from "./state/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import DashboardLayout from "./layouts/DashboardLayout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import DashboardTabPage from "./pages/DashboardTabPage";
import ResetPassword from "./pages/ResetPassword";
import UpdatePassword from "./pages/UpdatePassword";

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
                        <Route path="clip-generator" element={<DashboardTabPage tabKey="clip-generator" />} />
                        <Route path="ai-shorts" element={<DashboardTabPage tabKey="ai-shorts" />} />
                        <Route path="ai-agent" element={<DashboardTabPage tabKey="ai-agent" />} />
                        <Route path="ugc-gallery" element={<DashboardTabPage tabKey="ugc-gallery" />} />
                        <Route path="youtube-studio" element={<DashboardTabPage tabKey="youtube-studio" />} />
                        <Route path="settings" element={<DashboardTabPage tabKey="settings" />} />
                    </Route>

                    <Route path="*" element={<RootRedirect />} />
                </Routes>
            </BrowserRouter>
        </AuthProvider>
    </React.StrictMode>
);
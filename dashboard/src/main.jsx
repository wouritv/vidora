import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";

import { AuthProvider, useAuth } from "./state/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
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
                                <Dashboard />
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/dashboard/ai-shorts"
                        element={
                            <ProtectedRoute>
                                <DashboardTabPage tabKey="ai-shorts" />
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/dashboard/ai-agent"
                        element={
                            <ProtectedRoute>
                                <DashboardTabPage tabKey="ai-agent" />
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/dashboard/ugc-gallery"
                        element={
                            <ProtectedRoute>
                                <DashboardTabPage tabKey="ugc-gallery" />
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/dashboard/youtube-studio"
                        element={
                            <ProtectedRoute>
                                <DashboardTabPage tabKey="youtube-studio" />
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/dashboard/settings"
                        element={
                            <ProtectedRoute>
                                <DashboardTabPage tabKey="settings" />
                            </ProtectedRoute>
                        }
                    />

                    <Route path="*" element={<RootRedirect />} />
                </Routes>
            </BrowserRouter>
        </AuthProvider>
    </React.StrictMode>
);
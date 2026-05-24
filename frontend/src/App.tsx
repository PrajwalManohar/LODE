import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import Dashboard from "./pages/Dashboard";
import IntakeChat from "./pages/IntakeChat";
import Instruments from "./pages/Instruments";
import Bookings from "./pages/Bookings";
import Admin from "./pages/Admin";
import PostRun from "./pages/PostRun";
import Governance from "./pages/Governance";
import FitResults from "./pages/FitResults";
import { useAuth } from "./lib/auth";

function Splash({ label }: { label: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-ink-50">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-full border-2 border-navy-200 border-t-navy-800 animate-spin" />
        <p className="text-sm font-medium text-ink-500 tracking-tight">{label}</p>
      </div>
    </div>
  );
}

/** Any signed-in user. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { loading, session } = useAuth();
  const location = useLocation();
  if (loading) return <Splash label="Loading your workspace…" />;
  if (!session) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}

/** Admin role only — otherwise bounce to dashboard. */
function RequireAdmin({ children }: { children: ReactNode }) {
  const { loading, session, isAdmin } = useAuth();
  if (loading) return <Splash label="Loading…" />;
  if (!session) return <Navigate to="/login" replace />;
  if (!isAdmin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/intake" element={<IntakeChat />} />
                <Route path="/fit" element={<FitResults />} />
                <Route path="/instruments" element={<Instruments />} />
                <Route path="/bookings" element={<Bookings />} />
                <Route path="/postrun" element={<PostRun />} />
                <Route path="/profile" element={<Profile />} />
                {/* Admin-only */}
                <Route path="/admin" element={<RequireAdmin><Admin /></RequireAdmin>} />
                <Route path="/governance" element={<RequireAdmin><Governance /></RequireAdmin>} />
                <Route path="/audit" element={<RequireAdmin><Governance /></RequireAdmin>} />
                <Route path="/settings" element={<RequireAdmin><Admin /></RequireAdmin>} />
                {/* Catch-all — never show "page not found", always land on dashboard */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Layout>
          </RequireAuth>
        }
      />
    </Routes>
  );
}

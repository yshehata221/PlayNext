import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, type ServerConfig } from "./lib/api";
import BottomNav from "./components/BottomNav";
import Footer from "./components/Footer";
import VerifyBanner from "./components/VerifyBanner";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import { useAuth } from "./lib/auth";
import Browse from "./pages/Browse";
import BrowseGame from "./pages/BrowseGame";
import Friends from "./pages/Friends";
import GamePage from "./pages/GamePage";
import Library from "./pages/Library";
import Login from "./pages/Login";
import ResetPassword from "./pages/ResetPassword";
import Stats from "./pages/Stats";
import Tonight from "./pages/Tonight";
import Verify from "./pages/Verify";
import Wishlist from "./pages/Wishlist";

export default function App() {
  const { token, loading } = useAuth();
  const { pathname } = useLocation();
  // the library reports its status counts so the sidebar can show them
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [config, setConfig] = useState<ServerConfig | null>(null);

  useEffect(() => { api.config().then(setConfig).catch(() => setConfig(null)); }, []);

  // links from email arrive before anyone is signed in, so these two routes
  // have to work outside the authenticated shell
  if (pathname === "/verify" || pathname === "/reset") {
    return (
      <div className="min-h-screen px-6">
        <Routes>
          <Route path="/verify" element={<Verify />} />
          <Route path="/reset" element={<ResetPassword />} />
        </Routes>
      </div>
    );
  }

  if (loading) return <p className="p-8 text-fog">Loading…</p>;
  if (!token) return <Login />;

  return (
    <div className="flex min-h-screen flex-col">
      <VerifyBanner mailEnabled={config?.email ?? false} />
      <TopBar />
      <div className="flex flex-1">
        <Sidebar counts={counts} />
        <main className="min-w-0 flex-1 px-5 pb-24 pt-8 sm:px-6 sm:pb-8 lg:px-8">
          <Routes>
            <Route path="/" element={<Tonight />} />
            <Route path="/library" element={<Library onCounts={setCounts} />} />
            <Route path="/game/:id" element={<GamePage />} />
            <Route path="/browse" element={<Browse />} />
            <Route path="/browse/game/:id" element={<BrowseGame />} />
            <Route path="/wishlist" element={<Wishlist />} />
            <Route path="/friends" element={<Friends />} />
            <Route path="/stats" element={<Stats />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
      <Footer />
      <BottomNav />
    </div>
  );
}

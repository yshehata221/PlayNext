import { Bell, Search } from "lucide-react";
import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import Mark from "./Mark";

const tab = ({ isActive }: { isActive: boolean }) =>
  `relative px-1 py-5 text-sm font-medium transition-colors ${isActive ? "text-snow after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-amber" : "text-fog hover:text-snow"}`;

export default function TopBar() {
  const { user, signOut } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const initial = (user?.display_name ?? "?").slice(0, 1).toUpperCase();

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-ink/90 backdrop-blur">
      <div className="flex items-center gap-10 px-6">
        <NavLink to="/" className="flex items-center gap-3 py-4">
          <Mark className="h-8 w-8" />
          <span className="text-lg font-extrabold tracking-tight">PlayNext</span>
        </NavLink>
        <nav className="hidden gap-8 sm:flex">
          <NavLink to="/" end className={tab}>Tonight</NavLink>
          <NavLink to="/library" className={tab}>Library</NavLink>
          <NavLink to="/browse" className={tab}>Browse</NavLink>
          <NavLink to="/wishlist" className={tab}>Wishlist</NavLink>
          <NavLink to="/friends" className={tab}>Friends</NavLink>
          <NavLink to="/stats" className={tab}>Stats</NavLink>
        </nav>
        <form className="relative ml-auto hidden w-80 md:block" onSubmit={(e) => { e.preventDefault(); nav(`/library?q=${encodeURIComponent(q)}`); }}>
          <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-fog" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search your library…"
            className="w-full rounded-full border border-line bg-field py-2 pl-10 pr-4 text-sm placeholder:text-fog/70" />
        </form>
        <button className="text-fog hover:text-snow" aria-label="Notifications"><Bell size={18} /></button>
        <button onClick={signOut} className="flex items-center gap-2 text-sm text-fog hover:text-snow" title="Sign out">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-amber font-bold text-ink">{initial}</span>
          <span className="font-medium text-snow">{user?.display_name}</span>
        </button>
      </div>
    </header>
  );
}

import { NavLink } from "react-router-dom";
import { useAuth } from "../lib/auth";

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${isActive ? "bg-snow text-ink" : "text-fog hover:text-snow"}`;

export default function Nav() {
  const { user, signOut } = useAuth();
  return (
    <header className="mx-auto flex max-w-6xl items-center gap-8 px-6 py-6">
      <NavLink to="/" className="flex items-center gap-2.5">
        {/* the mark: a play triangle inside an amber tile */}
        <span className="grid h-7 w-7 place-items-center rounded-md bg-amber">
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden><path d="M3 1.5v9l7-4.5z" fill="#0B141C" /></svg>
        </span>
        <span className="text-xl font-extrabold tracking-tight">PlayNext</span>
      </NavLink>
      <nav className="flex gap-1">
        <NavLink to="/" end className={link}>Tonight</NavLink>
        <NavLink to="/library" className={link}>Library</NavLink>
        <NavLink to="/stats" className={link}>Stats</NavLink>
      </nav>
      <div className="ml-auto flex items-center gap-4 text-sm text-fog">
        <span>{user?.display_name}</span>
        <button onClick={signOut} className="hover:text-snow">Sign out</button>
      </div>
    </header>
  );
}

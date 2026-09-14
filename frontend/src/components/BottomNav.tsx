import { BarChart3, LayoutGrid, Moon, Search, Users } from "lucide-react";
import { NavLink } from "react-router-dom";

// Phone-sized screens get a bottom bar instead of the top tabs, which are
// hidden below `sm`. Nothing is duplicated: only one of the two ever shows.
const items = [
  { to: "/", label: "Tonight", icon: Moon, end: true },
  { to: "/library", label: "Library", icon: LayoutGrid },
  { to: "/browse", label: "Browse", icon: Search },
  { to: "/friends", label: "Friends", icon: Users },
  { to: "/stats", label: "Profile", icon: BarChart3 },
];

export default function BottomNav() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-20 flex border-t border-line bg-ink/95 backdrop-blur sm:hidden">
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end}
          className={({ isActive }) => `flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] ${isActive ? "text-amber" : "text-fog"}`}>
          <Icon size={19} />{label}
        </NavLink>
      ))}
    </nav>
  );
}

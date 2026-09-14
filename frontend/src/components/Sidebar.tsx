import { Bookmark, CheckCircle2, CircleDot, CloudDownload, Gamepad2, PlusCircle, XCircle } from "lucide-react";
import { useLocation, useSearchParams } from "react-router-dom";
import type { Status } from "../lib/api";
import { STATUS_LABEL } from "./StatusChip";
import Mark from "./Mark";

// the wishlist has its own page now, so it isn't a library filter
const ICONS: Record<string, typeof Bookmark> = { backlog: Bookmark, playing: CircleDot, completed: CheckCircle2, abandoned: XCircle };
const LIBRARY_STATUSES: Status[] = ["backlog", "playing", "completed", "abandoned"];

const item = (active: boolean) =>
  `flex items-center gap-3 rounded-lg px-3 py-2 text-left text-sm whitespace-nowrap transition-colors ${active ? "bg-panel text-snow border-l-2 border-amber -ml-px" : "text-fog hover:text-snow"}`;

/**
 * Library-only rail: filters and import actions. Page navigation lives in the
 * top bar, so it isn't repeated here.
 */
export default function Sidebar({ counts }: { counts?: Record<string, number> }) {
  const { pathname } = useLocation();
  const [params, setParams] = useSearchParams();
  const onLibrary = pathname === "/library";
  const filter = params.get("status") ?? "all";

  const setFilter = (s: string) => {
    const next = new URLSearchParams(params);
    if (s === "all") next.delete("status"); else next.set("status", s);
    setParams(next);
  };
  const openModal = (m: string) => {
    const next = new URLSearchParams(params);
    next.set("modal", m);
    setParams(next);
  };

  if (!onLibrary) return null;

  return (
    <aside className="hidden w-52 shrink-0 flex-col border-r border-line px-3 py-6 lg:flex">
      {onLibrary && (
        <>
          <p className="px-3 text-xs text-fog">Store & Import</p>
          <div className="mt-2 space-y-1">
            <button onClick={() => openModal("import")} className={item(false) + " w-full"}><CloudDownload size={18} />Import games</button>
            <button onClick={() => openModal("add")} className={item(false) + " w-full"}><PlusCircle size={18} />Add game</button>
          </div>

          <p className="mt-8 px-3 text-xs text-fog">Filters</p>
          <div className="mt-2 space-y-1">
            <button onClick={() => setFilter("all")} className={item(filter === "all") + " w-full"}>
              <Gamepad2 size={18} />All<span className="ml-auto rounded-full bg-field px-2 py-0.5 text-xs">{counts?.all ?? 0}</span>
            </button>
            {LIBRARY_STATUSES.map((s) => {
              const Icon = ICONS[s];
              return (
                <button key={s} onClick={() => setFilter(s)} className={item(filter === s) + " w-full"}>
                  <Icon size={18} />{STATUS_LABEL[s]}<span className="ml-auto rounded-full bg-field px-2 py-0.5 text-xs">{counts?.[s] ?? 0}</span>
                </button>
              );
            })}
          </div>
        </>
      )}

      <div className="mt-auto pt-10 text-center">
        <p className="text-sm text-fog">Better games.<br />Less guessing.</p>
        <Mark className="mx-auto mt-4 h-9 w-9" />
      </div>
    </aside>
  );
}

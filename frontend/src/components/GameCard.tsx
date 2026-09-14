import { Check, Clock, Play, Star, X } from "lucide-react";
import { Link } from "react-router-dom";
import GameCover from "./GameCover";
import StatusChip from "./StatusChip";
import type { Entry, Status } from "../lib/api";

/**
 * A library tile: artwork, then a compact info strip. Hovering reveals the one
 * or two actions that make sense for the game's current status, so the common
 * case (start playing / mark completed) doesn't need the detail page.
 */
export default function GameCard({ entry, onStatus, onRemove }: {
  entry: Entry;
  onStatus: (e: Entry, status: Status) => void;
  onRemove: (e: Entry) => void;
}) {
  const g = entry.game;
  const progress = g.hours_main && entry.hours_played > 0
    ? Math.min(100, Math.round((100 * entry.hours_played) / g.hours_main)) : null;

  const quick: { label: string; icon: React.ReactNode; status: Status } | null = {
    backlog: { label: "Start playing", icon: <Play size={14} />, status: "playing" as Status },
    playing: { label: "Mark completed", icon: <Check size={14} />, status: "completed" as Status },
    completed: null,
    abandoned: { label: "Give it another go", icon: <Play size={14} />, status: "playing" as Status },
    wishlist: null,
  }[entry.status];

  return (
    <div className="group relative overflow-hidden rounded-2xl border border-line bg-panel transition-transform duration-300 hover:-translate-y-1">
      <button onClick={() => onRemove(entry)} aria-label={`Remove ${g.title}`} title="Remove from library"
        className="absolute right-2.5 top-2.5 z-10 rounded-full bg-ink/85 p-1.5 text-fog opacity-0 backdrop-blur transition hover:bg-coral hover:text-ink group-hover:opacity-100 focus:opacity-100">
        <X size={13} />
      </button>

      <Link to={`/game/${entry.id}`} className="block">
        <div className="relative overflow-hidden">
          <GameCover game={g} platform={entry.platform} className="aspect-[3/4] w-full" />
          <StatusChip status={entry.status} className="absolute left-2.5 top-2.5" dot />

          {quick && (
            <div className="absolute inset-x-0 bottom-0 flex justify-center bg-gradient-to-t from-ink/95 to-transparent p-2.5 pt-10 opacity-0 transition-opacity group-hover:opacity-100">
              <button
                onClick={(ev) => { ev.preventDefault(); onStatus(entry, quick.status); }}
                className="flex items-center gap-1.5 rounded-lg bg-amber px-3 py-1.5 text-xs font-semibold text-ink hover:brightness-110">
                {quick.icon}{quick.label}
              </button>
            </div>
          )}
        </div>

        <div className="px-3 py-3">
          <div className="truncate text-sm font-semibold" title={g.title}>{g.title}</div>
          <p className="mt-0.5 truncate text-xs text-fog">{[g.release_year, entry.platform].filter(Boolean).join(" · ")}</p>

          <div className="mt-2 flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1 text-fog">
              <Star size={12} className={entry.rating != null ? "fill-amber text-amber" : ""} />
              {entry.rating != null ? `${entry.rating}/10` : "–"}
            </span>
            <span className="flex items-center gap-1 text-fog"><Clock size={12} />{Math.round(entry.hours_played)}h</span>
          </div>

          {g.genres.length > 0 && <p className="mt-1.5 truncate text-xs text-fog/80">{g.genres.slice(0, 2).join(" · ")}</p>}

          {progress != null && (
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-field">
              <div className="h-1 rounded-full bg-amber" style={{ width: `${progress}%` }} />
            </div>
          )}
        </div>
      </Link>
    </div>
  );
}

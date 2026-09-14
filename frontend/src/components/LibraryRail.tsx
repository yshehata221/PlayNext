import { ArrowRight, Bookmark, Clock, Gamepad2, Star } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import GameCover from "./GameCover";
import { api, type Entry, type Recommendation, type Stats } from "../lib/api";
import { useAuth } from "../lib/auth";

/**
 * Context panel beside the library: tonight's pick with its reasoning, the
 * backlog as a challenge, and recent activity. On narrow screens it stacks
 * underneath the grid instead of being hidden.
 */
export default function LibraryRail({ entries }: { entries: Entry[] }) {
  const { token } = useAuth();
  const [pick, setPick] = useState<Recommendation | null | undefined>(undefined);
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    if (entries.length === 0) return;
    api.recommendations(token!, "backlog", undefined, undefined, 1).then((r) => setPick(r[0] ?? null)).catch(() => setPick(null));
    api.stats(token!).then(setStats).catch(() => {});
  }, [token, entries.length]);

  const activity = [...entries]
    .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))
    .slice(0, 5)
    .map((e) => {
      const justAdded = Math.abs(Date.parse(e.updated_at) - Date.parse(e.added_at)) < 60_000;
      // pick the most specific thing we can say about the latest change
      const [icon, verb] = justAdded
        ? [<Gamepad2 key="i" size={13} />, "Added"]
        : e.status === "completed" ? [<Star key="i" size={13} />, "Completed"]
        : e.status === "playing" ? [<Clock key="i" size={13} />, "Started playing"]
        : e.status === "abandoned" ? [<Bookmark key="i" size={13} />, "Dropped"]
        : e.rating != null ? [<Star key="i" size={13} />, `Rated ${e.rating}/10`]
        : [<Gamepad2 key="i" size={13} />, "Updated"];
      return { e, icon, verb, when: ago(e.updated_at) };
    });

  const unplayed = entries.filter((e) => e.status === "backlog").length;
  const genreTotal = stats?.by_genre.reduce((a, g) => a + g.games, 0) || 1;
  const cleared = stats ? Math.round((100 * stats.total_hours) / (stats.total_hours + stats.backlog_hours || 1)) : 0;

  return (
    <aside className="space-y-5">
      <section className="rounded-2xl border border-amber/25 bg-gradient-to-br from-panel to-field p-5">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-fog">
          <Gamepad2 size={14} className="text-amber" />Your best match
        </h2>
        {pick === undefined && <p className="mt-4 text-sm text-fog">Thinking…</p>}
        {pick === null && <p className="mt-4 text-sm text-fog">Rate a few games and a pick will appear here.</p>}
        {pick && (
          <>
            <div className="mt-4 flex gap-3">
              <div className="w-16 shrink-0 overflow-hidden rounded-lg"><GameCover game={pick.game} compact className="aspect-[2/3] w-full" /></div>
              <div className="min-w-0">
                <div className="truncate text-lg font-bold leading-tight">{pick.game.title}</div>
                <div className="mt-1 text-xl font-extrabold text-amber">{Math.round(pick.score)}%</div>
                <div className="text-xs text-fog">match</div>
              </div>
            </div>
            {pick.reasons.length > 0 && (
              <p className="mt-3 text-sm leading-relaxed text-fog">
                {pick.reasons.slice(0, 2).map((r) => r.charAt(0).toLowerCase() + r.slice(1)).join(", and ")}.
              </p>
            )}
            <Link to="/" className="mt-4 flex items-center justify-center gap-2 rounded-lg bg-amber py-2.5 text-sm font-semibold text-ink hover:brightness-110">
              View recommendation <ArrowRight size={15} />
            </Link>
          </>
        )}
      </section>

      <section className="rounded-2xl border border-line bg-panel p-5">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-fog"><Bookmark size={14} className="text-amber" />Your backlog</h2>
        <div className="mt-4 flex items-baseline gap-2">
          <span className="text-4xl font-extrabold">{unplayed}</span>
          <span className="text-sm text-fog">unplayed games</span>
        </div>
        {stats && (
          <>
            <p className="mt-1 text-sm text-fog">about {Math.round(stats.backlog_hours)}h of play</p>
            <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-field">
              <div className="h-2.5 rounded-full bg-amber" style={{ width: `${Math.max(2, cleared)}%` }} />
            </div>
            <p className="mt-2 text-xs text-fog">
              {cleared}% played through
              {stats.backlog_months_at_current_pace != null && (
                <> · {stats.backlog_months_at_current_pace >= 24
                  ? `${stats.backlog_years_at_current_pace} years`
                  : `${Math.round(stats.backlog_months_at_current_pace)} months`} to clear</>
              )}
            </p>
            {stats.by_genre.length > 0 && (
              <div className="mt-5 border-t border-line pt-4">
                <h3 className="text-sm font-semibold">Top genres</h3>
                <ul className="mt-3 space-y-2">
                  {stats.by_genre.slice(0, 4).map((g) => (
                    <li key={g.genre} className="flex items-center gap-2 text-sm">
                      <span className="min-w-0 flex-1 truncate text-fog">{g.genre}</span>
                      <span className="h-1.5 w-16 shrink-0 rounded-full bg-field">
                        <span className="block h-1.5 rounded-full bg-amber" style={{ width: `${(100 * g.games) / genreTotal}%` }} />
                      </span>
                      <span className="w-8 shrink-0 text-right text-xs text-fog">{Math.round((100 * g.games) / genreTotal)}%</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </section>

      {activity.length > 0 && (
        <section className="rounded-2xl border border-line bg-panel p-5">
          <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-fog"><Clock size={14} className="text-amber" />Recent activity</h2>
          <ul className="mt-4 space-y-3">
            {activity.map(({ e, icon, verb, when }) => (
              <li key={e.id}>
                <Link to={`/game/${e.id}`} className="flex items-center gap-3 hover:opacity-80">
                  <div className="w-8 shrink-0 overflow-hidden rounded"><GameCover game={e.game} compact className="aspect-square w-full" /></div>
                  <div className="min-w-0 text-sm">
                    <div className="flex items-center gap-1.5 truncate">
                      <span className="text-amber">{icon}</span>{verb} <b className="truncate">{e.game.title}</b>
                    </div>
                    <div className="text-xs text-fog">{when}</div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </aside>
  );
}

function ago(iso: string) {
  const s = (Date.now() - Date.parse(iso)) / 1000;
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} hour${Math.round(s / 3600) === 1 ? "" : "s"} ago`;
  const d = Math.round(s / 86400);
  return d === 1 ? "yesterday" : `${d} days ago`;
}

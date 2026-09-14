import { Bookmark, Clock, Flame, Gamepad2, Library, Star, Target, Trophy } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Donut, { type Slice } from "../components/Donut";
import GameCover from "../components/GameCover";
import { PlatformLabel } from "../components/Platform";
import { STATUS_LABEL } from "../components/StatusChip";
import { api, type Recommendation, type Stats as StatsT, type Status } from "../lib/api";
import { useAuth } from "../lib/auth";

const GENRE_COLORS = ["#F2B441", "#5FD3A5", "#F26D6D", "#7FB2F0", "#C79BF0", "#E8EEF1", "#8FA3AE"];
const STATUS_COLORS: Record<Status, string> = {
  backlog: "#8FA3AE", playing: "#5FD3A5", completed: "#F2B441", abandoned: "#F26D6D", wishlist: "#C79BF0",
};

export default function Stats() {
  const { token } = useAuth();
  const [s, setS] = useState<StatsT | null>(null);
  const [pick, setPick] = useState<Recommendation | null | undefined>(undefined);

  useEffect(() => {
    api.stats(token!).then(setS);
    api.recommendations(token!, "backlog", undefined, undefined, 1)
      .then((r) => setPick(r[0] ?? null))
      .catch(() => setPick(null));
  }, [token]);

  if (!s) return <p className="text-fog">Counting…</p>;
  if (s.total_games === 0) {
    return (
      <div className="mx-auto max-w-lg py-20 text-center">
        <h1 className="text-3xl font-bold">Nothing to profile yet</h1>
        <p className="mt-2 text-fog">Import your library and this page will tell you what kind of gamer you are.</p>
        <Link to="/library" className="mt-6 inline-block rounded-lg bg-amber px-4 py-2 font-semibold text-ink">Go to library</Link>
      </div>
    );
  }

  const p = s.personality;
  const genres = s.by_genre.filter((g) => g.hours > 0 || g.games > 0).slice(0, 6);
  const useHours = s.total_hours > 0;
  const genreSlices: Slice[] = genres.map((g, i) => ({
    label: g.genre, value: useHours ? g.hours : g.games, color: GENRE_COLORS[i % GENRE_COLORS.length],
  }));
  const top = genres[0];
  const statusSlices: Slice[] = s.by_status
    .filter((b) => b.status !== "wishlist" && b.count > 0)
    .map((b) => ({ label: STATUS_LABEL[b.status], value: b.count, color: STATUS_COLORS[b.status] }));
  const platforms = Object.entries(s.by_platform).sort((a, b) => b[1] - a[1]);
  const bestRated = [...s.by_genre].filter((g) => g.avg_rating != null).sort((a, b) => (b.avg_rating ?? 0) - (a.avg_rating ?? 0))[0];
  const [first, ...rest] = s.most_played.filter((e) => e.hours_played > 0);

  return (
    <div className="mx-auto max-w-5xl">
      {/* Level 1: who you are */}
      <section className="overflow-hidden rounded-3xl border border-line bg-gradient-to-br from-panel via-panel to-field p-8 sm:p-10">
        <p className="text-xs font-semibold uppercase tracking-widest text-fog">Your gaming profile</p>
        <h1 className="mt-3 flex items-center gap-3 text-3xl font-extrabold tracking-tight sm:text-5xl">
          <Target className="shrink-0 text-amber" size={34} />{p.title}
        </h1>
        <p className="mt-2 text-lg text-amber">{p.tagline}</p>
        <p className="mt-3 max-w-2xl text-fog">{p.blurb}</p>
        <p className="mt-4 inline-block rounded-full bg-ink/60 px-3 py-1 text-xs text-fog">Because {p.evidence}</p>
      </section>

      {/* Level 2: the numbers, each saying what it came from */}
      <section className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={<Library size={15} />} value={s.total_games} label="Games in library"
          sub={s.added_last_30_days > 0 ? `+${s.added_last_30_days} this month` : "none added this month"} />
        <Stat icon={<Clock size={15} />} value={`${Math.round(s.total_hours).toLocaleString()}h`} label="Time played"
          sub={first ? `${first.game.title} leads` : "no playtime recorded"} />
        <Stat icon={<Trophy size={15} />} value={`${Math.round(s.completion_rate * 100)}%`} label="Completion rate"
          sub={s.started_games ? `${s.completed_games} of ${s.started_games} started` : "nothing started yet"} />
        <Stat icon={<Star size={15} />} value={s.average_rating != null ? `${s.average_rating}/10` : "–"} label="Average rating"
          sub={s.rated_games ? `from ${s.rated_games} rated game${s.rated_games === 1 ? "" : "s"}` : "rate a game to see this"} />
      </section>

      {/* the backlog, as a challenge rather than a sentence */}
      <section className="mt-6 rounded-3xl border border-line bg-panel p-8">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-fog"><Bookmark size={14} />Your backlog</h2>
        <div className="mt-4 flex flex-wrap items-end gap-x-10 gap-y-4">
          <div>
            <div className="text-5xl font-extrabold tracking-tight sm:text-6xl">{Math.round(s.backlog_hours).toLocaleString()}h</div>
            <p className="mt-1 text-fog">{s.backlog_games} unplayed game{s.backlog_games === 1 ? "" : "s"} waiting</p>
          </div>
          {s.backlog_months_at_current_pace != null && (
            <div className="text-right">
              <div className="text-2xl font-bold text-amber">
                {s.backlog_months_at_current_pace >= 24
                  ? `${s.backlog_years_at_current_pace} years`
                  : `${Math.round(s.backlog_months_at_current_pace)} months`}
              </div>
              <p className="text-sm text-fog">at about {s.weekly_hours_pace}h a week</p>
            </div>
          )}
        </div>
        {/* progress toward clearing it: hours played against hours remaining */}
        <div className="mt-6 h-3 overflow-hidden rounded-full bg-field">
          <div className="h-3 rounded-full bg-amber transition-[width] duration-700"
            style={{ width: `${Math.max(2, Math.min(100, (100 * s.total_hours) / (s.total_hours + s.backlog_hours || 1)))}%` }} />
        </div>
        <p className="mt-2 text-xs text-fog">
          {Math.round((100 * s.total_hours) / (s.total_hours + s.backlog_hours || 1))}% of your library's estimated playtime is behind you
        </p>
        <Link to="/" className="mt-6 inline-flex items-center gap-2 rounded-lg bg-amber px-4 py-2 text-sm font-semibold text-ink hover:brightness-110">
          <Flame size={15} />Start clearing it
        </Link>
      </section>

      {/* genres and habits side by side */}
      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="rounded-3xl border border-line bg-panel p-7">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">Your genres</h2>
          {top ? (
            <div className="mt-5 flex flex-wrap items-center gap-7">
              <Donut slices={genreSlices}
                centreTop={`${Math.round(useHours ? top.hours_share : top.games_share)}%`}
                centreSub={top.genre.length > 12 ? top.genre.slice(0, 11) + "…" : top.genre} />
              <ul className="min-w-[150px] flex-1 space-y-2">
                {genres.map((g, i) => (
                  <li key={g.genre} className="flex items-center gap-2.5 text-sm">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: GENRE_COLORS[i % GENRE_COLORS.length] }} />
                    <span className="truncate">{g.genre}</span>
                    <span className="ml-auto shrink-0 text-fog">
                      {useHours ? `${Math.round(g.hours_share)}%` : `${g.games}`}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="mt-4 text-fog">No genre data yet.</p>
          )}
          <p className="mt-5 text-xs text-fog">
            {useHours ? "Share of your recorded playtime." : "By number of games — no playtime recorded yet."}
          </p>
        </div>

        <div className="rounded-3xl border border-line bg-panel p-7">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">Your habits</h2>
          <ul className="mt-5 space-y-3">
            {top && (
              <Insight icon={<Target size={16} />} title={`${top.genre} leads your library`}
                body={useHours ? `${Math.round(top.hours_share)}% of your hours go here.` : `${top.games} of your games are ${top.genre.toLowerCase()}.`} />
            )}
            {bestRated?.avg_rating != null && (
              <Insight icon={<Star size={16} />} title="High standards, clear taste"
                body={`You rate ${bestRated.genre.toLowerCase()} games ${bestRated.avg_rating}/10 on average.`} />
            )}
            {s.avg_hours_per_finished != null && (
              <Insight icon={<Trophy size={16} />} title="How long you stay"
                body={`About ${Math.round(s.avg_hours_per_finished)}h in each game you finish.`} />
            )}
            <Insight icon={<Bookmark size={16} />} title="Backlog builder"
              body={`${s.backlog_games} game${s.backlog_games === 1 ? "" : "s"} waiting, roughly ${Math.round(s.backlog_hours)}h of play.`} />
            {platforms[0] && (
              <Insight icon={<Gamepad2 size={16} />}
                title={<>Mostly on <PlatformLabel platform={platforms[0][0]} size={14} /></>}
                body={platforms[1] ? `${platforms[0][1]} games there, then ${platforms[1][0]} with ${platforms[1][1]}.` : `All ${platforms[0][1]} of your games.`} />
            )}
          </ul>
        </div>
      </section>

      {/* library breakdown and most played */}
      <section className="mt-6 grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="rounded-3xl border border-line bg-panel p-7">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">Where your games stand</h2>
          <div className="mt-5 flex items-center gap-6">
            <Donut slices={statusSlices} size={140} thickness={18} centreTop={String(s.total_games)} centreSub="games" />
            <ul className="flex-1 space-y-1.5 text-sm">
              {s.by_status.filter((b) => b.status !== "wishlist").map((b) => (
                <li key={b.status} className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: STATUS_COLORS[b.status] }} />
                  {STATUS_LABEL[b.status]}<span className="ml-auto font-semibold">{b.count}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="rounded-3xl border border-line bg-panel p-7">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">Most played</h2>
          {!first ? (
            <p className="mt-4 text-fog">No playtime recorded yet. Import from Steam, or add hours by hand.</p>
          ) : (
            <div className="mt-5 flex flex-wrap gap-5">
              <Link to={`/game/${first.id}`} className="w-32 shrink-0 group">
                <div className="overflow-hidden rounded-xl ring-1 ring-white/10 transition-transform group-hover:-translate-y-1">
                  <GameCover game={first.game} compact className="aspect-[2/3] w-full" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-xl font-extrabold text-amber">01</span>
                  <span className="truncate text-sm font-semibold">{first.game.title}</span>
                </div>
                <p className="text-xs text-fog">{Math.round(first.hours_played)}h{first.game.genres[0] ? ` · ${first.game.genres[0]}` : ""}</p>
              </Link>
              <ol className="min-w-[180px] flex-1 space-y-2.5">
                {rest.map((e, i) => (
                  <li key={e.id}>
                    <Link to={`/game/${e.id}`} className="flex items-center gap-3">
                      <span className="w-5 text-sm font-bold text-fog">{String(i + 2).padStart(2, "0")}</span>
                      <div className="w-8 shrink-0 overflow-hidden rounded"><GameCover game={e.game} compact className="aspect-square w-full" /></div>
                      <span className="min-w-0 flex-1 truncate text-sm">{e.game.title}</span>
                      <span className="shrink-0 text-sm text-fog">{Math.round(e.hours_played)}h</span>
                    </Link>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      </section>

      {/* Level 3: back to the point of the app */}
      {pick && (
        <section className="mt-6 overflow-hidden rounded-3xl border border-amber/30 bg-gradient-to-br from-panel to-field p-8">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">What should you play next?</h2>
          <div className="mt-5 flex flex-wrap items-center gap-7">
            <div className="w-36 overflow-hidden rounded-xl ring-1 ring-white/10">
              <GameCover game={pick.game} compact className="aspect-[2/3] w-full" />
            </div>
            <div className="min-w-[240px] flex-1">
              <h3 className="text-2xl font-bold">{pick.game.title}</h3>
              <p className="mt-1 text-lg font-extrabold text-amber">{Math.round(pick.score)}% match</p>
              <p className="mt-2 max-w-prose text-sm text-fog">
                {pick.reasons.length ? pick.reasons.join(" · ") : "The best fit in your backlog right now."}
              </p>
              <Link to="/" className="mt-4 inline-block rounded-lg bg-amber px-4 py-2 text-sm font-semibold text-ink hover:brightness-110">
                See tonight's pick
              </Link>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function Stat({ icon, value, label, sub }: { icon: React.ReactNode; value: string | number; label: string; sub: string }) {
  return (
    <div className="rounded-2xl border border-line bg-panel p-5">
      <div className="flex items-center gap-1.5 text-fog">{icon}<span className="text-xs font-medium">{label}</span></div>
      <div className="mt-2 text-3xl font-extrabold tracking-tight">{value}</div>
      <div className="mt-1 text-xs text-fog">{sub}</div>
    </div>
  );
}

function Insight({ icon, title, body }: { icon: React.ReactNode; title: React.ReactNode; body: string }) {
  return (
    <li className="flex gap-3 rounded-xl bg-field p-3.5">
      <span className="mt-0.5 shrink-0 text-amber">{icon}</span>
      <div>
        <div className="flex flex-wrap items-center gap-1.5 text-sm font-semibold">{title}</div>
        <div className="text-sm text-fog">{body}</div>
      </div>
    </li>
  );
}

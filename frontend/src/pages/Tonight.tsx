import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import GameCover from "../components/GameCover";
import { api, type Mood, type PlanItem, type Recommendation } from "../lib/api";
import { useAuth } from "../lib/auth";

const HOURS = [null, 0.5, 1, 2, 3] as const;
const MOODS: { key: Mood | null; label: string }[] = [
  { key: null, label: "Anything" },
  { key: "story", label: "A story" },
  { key: "relaxing", label: "Something relaxing" },
  { key: "quick", label: "Something quick" },
  { key: "new", label: "Something I haven't started" },
];

function fmt(min: number) {
  const h = Math.floor(min / 60), m = min % 60;
  return h ? `${h}h${m ? ` ${m}m` : ""}` : `${m}m`;
}

export default function Tonight() {
  const { token } = useAuth();
  const [mode, setMode] = useState<"pick" | "plan">("pick");
  const [source, setSource] = useState<"backlog" | "discover">("backlog");
  const [hours, setHours] = useState<number | null>(null);
  const [mood, setMood] = useState<Mood | null>(null);
  const [recs, setRecs] = useState<Recommendation[] | null>(null);
  const [plan, setPlan] = useState<PlanItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    if (mode === "plan") {
      setPlan(null);
      api.plan(token!, hours ?? 2, mood ?? undefined).then(setPlan).catch((e) => setError(e.message));
    } else {
      setRecs(null);
      api.recommendations(token!, source, hours ?? undefined, mood ?? undefined).then(setRecs).catch((e) => setError(e.message));
    }
  }, [token, mode, source, hours, mood]);

  const [pick, ...rest] = recs ?? [];

  const chip = (active: boolean) =>
    `rounded-full px-3.5 py-1.5 text-sm transition-colors ${active ? "bg-snow font-semibold text-ink" : "text-fog hover:text-snow"}`;

  return (
    <div className="mx-auto max-w-3xl text-center">
      <h1 className="text-5xl font-extrabold leading-none tracking-tight sm:text-6xl">
        What should you<br />play tonight?
      </h1>

      <div className="mt-8 flex flex-wrap justify-center gap-1 rounded-full bg-panel p-1">
        <span className="px-3 py-1.5 text-sm text-fog">I've got</span>
        {HOURS.map((h) => (
          <button key={String(h)} className={chip(hours === h)} onClick={() => setHours(h)}>
            {h === null ? "all night" : h < 1 ? "30 min" : `${h}h`}
          </button>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap justify-center gap-1">
        {MOODS.map((m) => (
          <button key={String(m.key)} className={chip(mood === m.key)} onClick={() => setMood(m.key)}>{m.label}</button>
        ))}
      </div>
      <div className="mt-4 flex justify-center gap-6 text-sm">
        <button className={`border-b-2 pb-1 ${mode === "pick" ? "border-amber text-snow" : "border-transparent text-fog hover:text-snow"}`} onClick={() => setMode("pick")}>One pick</button>
        <button className={`border-b-2 pb-1 ${mode === "plan" ? "border-amber text-snow" : "border-transparent text-fog hover:text-snow"}`} onClick={() => setMode("plan")}>Plan my night</button>
        {mode === "pick" && (
          <button className="border-b-2 border-transparent pb-1 text-fog hover:text-snow" onClick={() => setSource(source === "backlog" ? "discover" : "backlog")}>
            {source === "backlog" ? "From my backlog ↺" : "Something I don't own ↺"}
          </button>
        )}
      </div>

      {error && <p className="mt-10 text-coral">{error}</p>}
      {mode === "pick" && recs === null && !error && <p className="mt-12 text-fog">Thinking…</p>}
      {mode === "plan" && plan === null && !error && <p className="mt-12 text-fog">Putting a night together…</p>}

      {mode === "pick" && recs && !pick && (
        <div className="mt-12 rounded-2xl border border-dashed border-line p-10 text-fog">
          {source === "backlog"
            ? <>Nothing in your backlog fits that. <Link to="/library" className="text-amber underline">Add or rate some games</Link>, or loosen the filters.</>
            : "Nothing new fits those filters. Try a longer window or a different mood."}
        </div>
      )}

      {mode === "pick" && pick && (
        <section className="mt-12">
          <Link to={pick.in_library ? `/library` : "#"} className="mx-auto block w-56 overflow-hidden rounded-2xl shadow-2xl shadow-black/60 ring-1 ring-white/10 sm:w-64">
            <GameCover game={pick.game} className="aspect-[2/3] w-full" />
          </Link>
          <h2 className="mt-8 text-3xl font-bold tracking-tight">{pick.game.title}</h2>
          <p className="mt-1 text-4xl font-extrabold text-amber">{Math.round(pick.score)}% match</p>
          <p className="mx-auto mt-4 max-w-md text-fog">
            {pick.reasons.length ? `Because ${pick.reasons.map((r) => r.charAt(0).toLowerCase() + r.slice(1)).join(", and ")}.` : "It's the best fit in your library right now."}
          </p>
          <p className="mt-2 text-sm text-fog">
            {[pick.game.developer, pick.game.release_year].filter(Boolean).join(", ")}
            {pick.hours_remaining != null && ` · about ${Math.round(pick.hours_remaining)}h left`}
          </p>
        </section>
      )}

      {mode === "pick" && pick && (
        <p className="mt-8 text-sm text-fog">
          Playing with someone? <Link to="/friends" className="text-amber underline">Pick a game you both own</Link>.
        </p>
      )}

      {mode === "pick" && rest.length > 0 && (
        <section className="mt-16 text-left">
          <h3 className="text-sm font-semibold text-fog">Or, if not that</h3>
          <div className="mt-4 grid grid-cols-3 gap-5 sm:grid-cols-4 md:grid-cols-5">
            {rest.slice(0, 5).map((r) => (
              <div key={r.game.id}>
                <div className="overflow-hidden rounded-xl ring-1 ring-white/5"><GameCover game={r.game} className="aspect-[2/3] w-full" /></div>
                <div className="mt-2 flex items-baseline justify-between gap-2">
                  <span className="truncate text-sm font-medium">{r.game.title}</span>
                  <span className="shrink-0 text-xs font-semibold text-amber">{Math.round(r.score)}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {mode === "plan" && plan && (
        <section className="mt-12 text-left">
          <h2 className="text-center text-sm font-semibold text-fog">Your {fmt(Math.round((hours ?? 2) * 60))} gaming plan</h2>
          {plan.length === 0 && <p className="mt-6 text-center text-fog">Couldn't fill that window from your backlog. Add a few games or change the mood.</p>}
          <ol className="mt-6 space-y-4">
            {plan.map((p, i) => (
              <li key={p.game.id} className="flex items-center gap-5 rounded-2xl bg-panel p-4">
                <span className="w-6 text-center text-lg font-bold text-fog">{i + 1}</span>
                <div className="w-16 shrink-0 overflow-hidden rounded-lg"><GameCover game={p.game} compact className="aspect-[2/3] w-full" /></div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-lg font-semibold">{p.game.title}</div>
                  <div className="truncate text-sm text-fog">{p.reasons[0]}</div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-xl font-bold text-amber">{fmt(p.minutes)}</div>
                  <div className="text-xs text-fog">{Math.round(p.score)}% match</div>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

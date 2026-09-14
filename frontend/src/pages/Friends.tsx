import { Check, Clock, Search, Star, UserPlus, Users, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import GameCover from "../components/GameCover";
import { api, type CoopPick, type Friend, type FriendSearchResult } from "../lib/api";
import { useAuth } from "../lib/auth";

const HOURS = [null, 1, 2, 3] as const;

export default function Friends() {
  const { token, user } = useAuth();
  const [friends, setFriends] = useState<Friend[] | null>(null);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<FriendSearchResult[]>([]);
  const [selected, setSelected] = useState<Friend | null>(null);
  const [hours, setHours] = useState<number | null>(null);
  const [togetherOnly, setTogetherOnly] = useState(true);
  const [picks, setPicks] = useState<CoopPick[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.friends(token!).then(setFriends);
  useEffect(() => { load(); }, [token]);

  useEffect(() => {
    if (q.trim().length < 2) { setResults([]); return; }
    const id = setTimeout(() => api.searchUsers(token!, q.trim()).then(setResults).catch(() => setResults([])), 300);
    return () => clearTimeout(id);
  }, [q, token]);

  // fetch suggestions whenever the chosen friend or time budget changes
  useEffect(() => {
    if (!selected) { setPicks(null); return; }
    setPicks(null);
    api.coop(token!, selected.user.id, hours ?? undefined, togetherOnly)
      .then(setPicks)
      .catch((e) => setError(e.message));
  }, [selected, hours, togetherOnly, token]);

  const act = async (fn: Promise<unknown>, msg: string) => {
    try {
      await fn;
      setNotice(msg);
      setQ("");
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const accepted = (friends ?? []).filter((f) => f.state === "accepted");
  const incoming = (friends ?? []).filter((f) => f.direction === "incoming");
  const outgoing = (friends ?? []).filter((f) => f.direction === "outgoing");

  const chip = (on: boolean) =>
    `rounded-full px-3.5 py-1.5 text-sm transition-colors ${on ? "bg-amber font-semibold text-ink" : "bg-panel text-fog hover:text-snow"}`;

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Friends</h1>
      <p className="mt-2 text-fog">
        Add people by username and PlayNext can find something you both own and both like.
        {user?.username && <> Yours is <span className="font-semibold text-snow">@{user.username}</span>.</>}
      </p>

      {notice && <p className="mt-5 rounded-lg bg-panel px-4 py-2 text-sm text-mint">{notice}</p>}
      {error && <p className="mt-5 rounded-lg bg-panel px-4 py-2 text-sm text-coral">{error}</p>}

      <div className="relative mt-6 max-w-lg">
        <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-fog" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find someone by username…"
          className="w-full rounded-full border border-line bg-field py-2.5 pl-10 pr-4 text-sm placeholder:text-fog/60" />
      </div>

      {results.length > 0 && (
        <ul className="mt-3 max-w-lg divide-y divide-line rounded-2xl border border-line bg-panel">
          {results.map((r) => (
            <li key={r.user.id} className="flex items-center gap-3 px-4 py-3">
              <Avatar name={r.user.display_name} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">{r.user.display_name}</div>
                <div className="truncate text-xs text-fog">@{r.user.username}</div>
              </div>
              {r.relationship === "none" && (
                <button onClick={() => act(api.addFriend(token!, r.user.username!), `Request sent to @${r.user.username}.`)}
                  className="flex items-center gap-1.5 rounded-lg bg-amber px-3 py-1.5 text-xs font-semibold text-ink hover:brightness-110">
                  <UserPlus size={13} />Add
                </button>
              )}
              {r.relationship === "friends" && <span className="text-xs text-mint">Friends</span>}
              {r.relationship === "pending_out" && <span className="text-xs text-fog">Requested</span>}
              {r.relationship === "pending_in" && <span className="text-xs text-amber">Wants to add you</span>}
              {r.relationship === "self" && <span className="text-xs text-fog">That's you</span>}
            </li>
          ))}
        </ul>
      )}

      {incoming.length > 0 && (
        <section className="mt-8">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">Requests</h2>
          <ul className="mt-3 space-y-2">
            {incoming.map((f) => (
              <li key={f.friendship_id} className="flex items-center gap-3 rounded-2xl border border-amber/30 bg-panel px-4 py-3">
                <Avatar name={f.user.display_name} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{f.user.display_name}</div>
                  <div className="text-xs text-fog">@{f.user.username} · {f.games} games</div>
                </div>
                <button onClick={() => act(api.acceptFriend(token!, f.friendship_id), `You and ${f.user.display_name} are friends.`)}
                  className="flex items-center gap-1.5 rounded-lg bg-amber px-3 py-1.5 text-xs font-semibold text-ink"><Check size={13} />Accept</button>
                <button onClick={() => act(api.removeFriend(token!, f.friendship_id), "Request declined.")}
                  className="rounded-lg border border-line px-3 py-1.5 text-xs text-fog hover:text-coral">Decline</button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-8">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">Your friends</h2>
        {friends === null && <p className="mt-3 text-fog">Loading…</p>}
        {friends && accepted.length === 0 && (
          <div className="mt-3 rounded-2xl border border-dashed border-line p-8 text-center text-fog">
            <Users size={24} className="mx-auto" />
            <p className="mt-3">No friends yet. Share your username and search for theirs above.</p>
          </div>
        )}
        <ul className="mt-3 grid gap-3 sm:grid-cols-2">
          {accepted.map((f) => (
            <li key={f.friendship_id}>
              <button onClick={() => setSelected(f)}
                className={`flex w-full items-center gap-3 rounded-2xl border p-4 text-left transition-colors ${selected?.friendship_id === f.friendship_id ? "border-amber bg-panel" : "border-line bg-panel hover:border-fog/40"}`}>
                <Avatar name={f.user.display_name} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-semibold">{f.user.display_name}</div>
                  <div className="truncate text-xs text-fog">@{f.user.username} · {f.games} games · {f.shared_games} in common</div>
                </div>
                {f.compatibility != null && (
                  <div className="shrink-0 text-right">
                    <div className="text-lg font-extrabold text-amber">{Math.round(f.compatibility)}%</div>
                    <div className="text-[11px] text-fog">taste match</div>
                  </div>
                )}
              </button>
            </li>
          ))}
        </ul>
        {outgoing.length > 0 && (
          <p className="mt-3 text-xs text-fog">
            Waiting on {outgoing.map((f) => `@${f.user.username}`).join(", ")}.
          </p>
        )}
      </section>

      {selected && (
        <section className="mt-10 rounded-3xl border border-line bg-panel p-7">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold">What should you two play?</h2>
              <p className="mt-1 text-fog">
                Games you and {selected.user.display_name} both own, ranked by what you both like.
              </p>
            </div>
            <button onClick={() => setSelected(null)} className="text-fog hover:text-snow" aria-label="Close"><X size={18} /></button>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <div className="flex flex-wrap items-center gap-1 rounded-full bg-field p-1">
              <span className="px-3 py-1 text-sm text-fog">You've got</span>
              {HOURS.map((h) => (
                <button key={String(h)} className={chip(hours === h)} onClick={() => setHours(h)}>
                  {h === null ? "all evening" : `${h}h`}
                </button>
              ))}
            </div>
            <button onClick={() => setTogetherOnly(!togetherOnly)} className={chip(togetherOnly)}>
              {togetherOnly ? "Multiplayer only" : "Including single-player"}
            </button>
          </div>

          {picks === null && <p className="mt-6 text-fog">Looking through both libraries…</p>}
          {picks?.length === 0 && (
            <p className="mt-6 text-fog">
              {selected.shared_games === 0
                ? `You and ${selected.user.display_name} don't own any of the same games yet.`
                : togetherOnly
                  ? "None of your shared games support playing together. Turn off \"Multiplayer only\" to see the rest."
                  : "Nothing shared fits that time slot. Try a longer evening."}
            </p>
          )}

          {picks && picks.length > 0 && (
            <>
              <div className="mt-6 flex flex-wrap gap-6 rounded-2xl bg-field p-5">
                <div className="w-32 shrink-0 overflow-hidden rounded-xl ring-1 ring-white/10">
                  <GameCover game={picks[0].game} compact className="aspect-[2/3] w-full" />
                </div>
                <div className="min-w-[220px] flex-1">
                  <h3 className="flex flex-wrap items-center gap-2 text-2xl font-bold">
                    {picks[0].game.title}
                    {picks[0].plays_together === false && (
                      <span className="rounded-full bg-ink/70 px-2 py-0.5 text-xs font-medium text-fog">Single-player</span>
                    )}
                  </h3>
                  <p className="mt-1 text-xl font-extrabold text-amber">{Math.round(picks[0].score)}% match</p>
                  <ul className="mt-3 space-y-1.5">
                    {picks[0].reasons.map((r) => (
                      <li key={r} className="flex gap-2 text-sm text-fog"><span className="text-mint">✓</span>{r}</li>
                    ))}
                  </ul>
                  <p className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-fog">
                    <span className="flex items-center gap-1"><Star size={12} />You {picks[0].your_rating ?? "–"} · Them {picks[0].their_rating ?? "–"}</span>
                    <span className="flex items-center gap-1"><Clock size={12} />You {Math.round(picks[0].your_hours)}h · Them {Math.round(picks[0].their_hours)}h</span>
                  </p>
                </div>
              </div>

              {picks.length > 1 && (
                <>
                  <h3 className="mt-7 text-xs font-semibold uppercase tracking-widest text-fog">Other options</h3>
                  <ul className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
                    {picks.slice(1, 6).map((p) => (
                      <li key={p.game.id}>
                        <div className="overflow-hidden rounded-xl ring-1 ring-white/5"><GameCover game={p.game} compact className="aspect-[2/3] w-full" /></div>
                        <div className="mt-2 flex items-baseline justify-between gap-2">
                          <span className="truncate text-sm font-medium">{p.game.title}</span>
                          <span className="shrink-0 text-xs font-semibold text-amber">{Math.round(p.score)}</span>
                        </div>
                        {p.plays_together === false && <div className="text-xs text-fog">Single-player</div>}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}

          <button onClick={() => act(api.removeFriend(token!, selected.friendship_id), `Removed ${selected.user.display_name}.`).then(() => setSelected(null))}
            className="mt-7 text-xs text-fog underline hover:text-coral">Remove friend</button>
        </section>
      )}
    </div>
  );
}

function Avatar({ name }: { name: string }) {
  return (
    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-field font-bold text-amber">
      {name.slice(0, 1).toUpperCase()}
    </span>
  );
}

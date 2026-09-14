import { ChevronRight, MoreHorizontal, Play, Plus, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import GameCard from "../components/GameCard";
import GameCover from "../components/GameCover";
import LibraryRail from "../components/LibraryRail";
import { PlatformPicker } from "../components/Platform";
import { LIBRARY_STATUSES, STATUS_LABEL } from "../components/StatusChip";
import { api, type Entry, type Game, type Status } from "../lib/api";
import { parseQuery } from "../lib/filters";
import { useAuth } from "../lib/auth";

// Launcher tooling an early version of the scanner mistook for games. The
// scanner filters these out now; this offers to clear any it already added.
const TOOLING = /\b(launcher|client|app|service|services|sdk|runtime|redistributable|anti-?cheat|overlay|updater|installer|agent|toolkit|framework)\b/i;
const TOOLING_EXACT = /^(battle\.net|epic games|rockstar games|ea|ubisoft connect|gog galaxy|steam|riot games|xbox)$/i;
const isTooling = (title: string) => TOOLING.test(title) || TOOLING_EXACT.test(title.trim());

const RATINGS = [
  { key: "", label: "Any rating" },
  { key: "9", label: "Rated 9+" },
  { key: "7", label: "Rated 7+" },
  { key: "unrated", label: "Not rated" },
];

export default function Library({ onCounts }: { onCounts?: (c: Record<string, number>) => void }) {
  const { token } = useAuth();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [sort, setSort] = useState("added");
  const [genre, setGenre] = useState("");
  const [platform, setPlatform] = useState("");
  const [rating, setRating] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [enriching, setEnriching] = useState(false);
  const [menu, setMenu] = useState(false);
  const [params, setParams] = useSearchParams();

  // status filter, search text and the open dialog live in the URL so the
  // sidebar, the top-bar search and this page can all drive them
  const filter = (params.get("status") ?? "all") as Status | "all";
  const query = params.get("q") ?? "";
  const modal = params.get("modal");
  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next, { replace: true });
  };
  const setFilter = (s: Status | "all") => setParam("status", s === "all" ? null : s);
  const setQuery = (q: string) => setParam("q", q || null);
  const closeModal = () => setParam("modal", null);

  const load = () => { api.library(token!, { sort }).then(setEntries); };
  useEffect(load, [token, sort]);

  useEffect(() => {
    if (params.get("steam") === "ok") {
      setNotice(`Imported ${params.get("imported")} games from Steam${params.get("updated") !== "0" ? `, updated ${params.get("updated")}` : ""}.`);
      setParams({}, { replace: true });
    } else if (params.get("steam") === "error") {
      setNotice(`Steam import failed: ${params.get("message")}`);
      setParams({}, { replace: true });
    }
  }, [params, setParams]);

  // Ask the backend once per visit to fill in missing art, genres and media.
  // It queues the work in the background and decides what needs doing.
  const [triedEnrich, setTriedEnrich] = useState(false);
  useEffect(() => {
    if (triedEnrich || entries.length === 0) return;
    setTriedEnrich(true);
    setEnriching(true);
    api.enrichLibrary(token!)
      .then((r) => {
        if (!r.queued) { setEnriching(false); return; }
        setTimeout(() => { load(); setEnriching(false); }, 8000);
      })
      .catch(() => setEnriching(false));
  }, [entries.length, triedEnrich, token]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: entries.length };
    for (const e of entries) c[e.status] = (c[e.status] ?? 0) + 1;
    return c;
  }, [entries]);
  useEffect(() => { onCounts?.(counts); }, [counts, onCounts]);

  const totalHours = useMemo(() => entries.reduce((a, e) => a + e.hours_played, 0), [entries]);
  const genres = useMemo(() => {
    const seen = new Map<string, number>();
    for (const e of entries) for (const g of e.game.genres) seen.set(g, (seen.get(g) ?? 0) + 1);
    return [...seen.entries()].sort((a, b) => b[1] - a[1]).map(([g]) => g).slice(0, 20);
  }, [entries]);
  const platforms = useMemo(() => [...new Set(entries.map((e) => e.platform))], [entries]);

  const continuePlaying = useMemo(
    () => entries.filter((e) => e.status === "playing").sort((a, b) => b.hours_played - a.hours_played).slice(0, 6),
    [entries],
  );

  const visible = useMemo(() => {
    const q = parseQuery(query);
    return entries.filter((e) => {
      if (filter !== "all" && e.status !== filter) return false;
      if (q.status && e.status !== q.status) return false;
      if (platform && e.platform !== platform) return false;
      if (q.platform && e.platform !== q.platform) return false;
      if (genre && !e.game.genres.includes(genre)) return false;
      if (q.genre && !e.game.genres.some((g) => g.toLowerCase().includes(q.genre!))) return false;
      if (q.year && String(e.game.release_year) !== q.year) return false;
      if (rating === "unrated" && e.rating != null) return false;
      if (rating && rating !== "unrated" && (e.rating ?? 0) < Number(rating)) return false;
      const hay = `${e.game.title} ${e.game.developer ?? ""} ${e.game.genres.join(" ")}`.toLowerCase();
      return q.text.every((t) => hay.includes(t));
    });
  }, [entries, filter, query, genre, platform, rating]);

  const remove = async (e: Entry) => {
    await api.removeEntry(token!, e.id);
    setEntries((xs) => xs.filter((x) => x.id !== e.id));
  };
  const setStatus = async (e: Entry, status: Status) => {
    const updated = await api.updateEntry(token!, e.id, { status });
    setEntries((xs) => xs.map((x) => (x.id === e.id ? updated : x)));
  };

  const junk = entries.filter((e) => isTooling(e.game.title));
  const removeJunk = async () => {
    await Promise.all(junk.map((e) => api.removeEntry(token!, e.id)));
    setEntries((xs) => xs.filter((x) => !junk.some((j) => j.id === x.id)));
    setNotice(`Removed ${junk.length} non-game entr${junk.length === 1 ? "y" : "ies"}.`);
  };

  const tab = (active: boolean) =>
    `rounded-full px-4 py-1.5 text-sm transition-colors ${active ? "bg-amber font-semibold text-ink" : "bg-panel text-fog hover:text-snow"}`;
  const select = "rounded-full border border-line bg-field px-3 py-1.5 text-sm text-snow";
  const filtered = genre || platform || rating || sort !== "added";

  return (
    <div className="grid gap-8 xl:grid-cols-[1fr_300px]">
      <div className="min-w-0">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Your library</h1>
            <p className="mt-2 text-fog">
              <span className="font-semibold text-snow">{counts.all}</span> games ·{" "}
              <span className="font-semibold text-snow">{Math.round(totalHours).toLocaleString()}h</span> played ·{" "}
              {counts.completed ?? 0} completed · {counts.backlog ?? 0} in backlog
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setParam("modal", "add")}
              className="flex items-center gap-2 rounded-lg bg-amber px-4 py-2 text-sm font-semibold text-ink hover:brightness-110">
              <Plus size={16} />Add game
            </button>
            <div className="relative">
              <button onClick={() => setMenu(!menu)} aria-label="Library options"
                className="rounded-lg border border-line p-2 text-fog hover:bg-panel hover:text-snow"><MoreHorizontal size={18} /></button>
              {menu && (
                <div className="absolute right-0 z-20 mt-2 w-52 rounded-xl border border-line bg-panel p-1.5 shadow-2xl shadow-black/60">
                  <button onClick={() => { setMenu(false); setParam("modal", "import"); }}
                    className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-field">Import games…</button>
                  <Link to="/browse" onClick={() => setMenu(false)} className="block rounded-lg px-3 py-2 text-sm hover:bg-field">Browse the catalogue</Link>
                </div>
              )}
            </div>
          </div>
        </div>

        {notice && <p className="mt-5 rounded-lg bg-panel px-4 py-2 text-sm text-mint">{notice}</p>}

        {junk.length > 0 && (
          <div className="mt-5 flex flex-wrap items-center gap-3 rounded-lg border border-line bg-panel px-4 py-3 text-sm">
            <span className="text-fog">
              {junk.length} {junk.length === 1 ? "entry looks" : "entries look"} like launcher software rather than a game
              ({junk.slice(0, 3).map((e) => e.game.title).join(", ")}{junk.length > 3 ? "…" : ""}).
            </span>
            <button onClick={removeJunk} className="rounded-full bg-coral/15 px-3 py-1 font-semibold text-coral hover:bg-coral hover:text-ink">
              Remove {junk.length === 1 ? "it" : "them"}
            </button>
          </div>
        )}

        {/* pick up where you left off, before the wall of backlog */}
        {continuePlaying.length > 0 && filter === "all" && !query && (
          <section className="mt-7">
            <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-fog">
              <Play size={13} className="text-amber" />Continue playing
            </h2>
            <div className="mt-3 flex gap-3 overflow-x-auto pb-2">
              {continuePlaying.map((e) => (
                <Link key={e.id} to={`/game/${e.id}`}
                  className="group flex w-64 shrink-0 items-center gap-3 rounded-2xl border border-line bg-panel p-2.5 hover:border-amber/40">
                  <div className="w-12 shrink-0 overflow-hidden rounded-lg"><GameCover game={e.game} compact platform={e.platform} className="aspect-[2/3] w-full" /></div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold">{e.game.title}</div>
                    <div className="text-xs text-fog">{Math.round(e.hours_played)}h played</div>
                    {e.game.hours_main && (
                      <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-field">
                        <div className="h-1 rounded-full bg-amber" style={{ width: `${Math.min(100, (100 * e.hours_played) / e.game.hours_main)}%` }} />
                      </div>
                    )}
                  </div>
                  <ChevronRight size={16} className="shrink-0 text-fog group-hover:text-amber" />
                </Link>
              ))}
            </div>
          </section>
        )}

        <div className="mt-7 flex flex-wrap items-center gap-2">
          <button className={tab(filter === "all")} onClick={() => setFilter("all")}>All</button>
          {LIBRARY_STATUSES.map((s) => (
            <button key={s} className={tab(filter === s)} onClick={() => setFilter(s)}>{STATUS_LABEL[s]}</button>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <div className="relative min-w-[240px] flex-1">
            <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-fog" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search games…"
              className="w-full rounded-full border border-line bg-field py-2 pl-10 pr-9 text-sm placeholder:text-fog/60" />
            {query && (
              <button onClick={() => setQuery("")} aria-label="Clear search" className="absolute right-3 top-1/2 -translate-y-1/2 text-fog hover:text-snow"><X size={15} /></button>
            )}
          </div>
          {genres.length > 0 && (
            <select value={genre} onChange={(e) => setGenre(e.target.value)} className={select} aria-label="Genre">
              <option value="">Any genre</option>
              {genres.map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
          )}
          {platforms.length > 1 && (
            <select value={platform} onChange={(e) => setPlatform(e.target.value)} className={select} aria-label="Platform">
              <option value="">Any platform</option>
              {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          )}
          <select value={rating} onChange={(e) => setRating(e.target.value)} className={select} aria-label="Rating">
            {RATINGS.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
          </select>
          <select value={sort} onChange={(e) => setSort(e.target.value)} className={select} aria-label="Sort">
            <option value="added">Sort: Recently added</option>
            <option value="title">Sort: Title</option>
            <option value="rating">Sort: Rating</option>
            <option value="hours">Sort: Hours played</option>
            <option value="last_played">Sort: Last played</option>
          </select>
          {filtered && (
            <button onClick={() => { setGenre(""); setPlatform(""); setRating(""); setSort("added"); }}
              className="text-sm text-fog underline hover:text-snow">Clear</button>
          )}
        </div>

        <p className="mt-3 text-xs text-fog">
          {visible.length === entries.length
            ? "Tip: you can also type genre:rpg platform:xbox status:backlog in the search box."
            : `${visible.length} of ${entries.length} games shown`}
        </p>

        {enriching && <p className="mt-3 text-sm text-fog">Filling in artwork and details…</p>}

        {entries.length === 0 && (
          <div className="mt-12 rounded-2xl border border-dashed border-line p-10 text-center text-fog">
            Nothing here yet. Import your Steam library or scan this PC from the ⋯ menu, or add a game by name.
          </div>
        )}
        {entries.length > 0 && visible.length === 0 && (
          <p className="mt-12 text-center text-fog">No games match that. Try fewer words, or clear the filters.</p>
        )}

        <ul className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5">
          {visible.map((e) => (
            <li key={e.id}><GameCard entry={e} onStatus={setStatus} onRemove={remove} /></li>
          ))}
        </ul>
      </div>

      <LibraryRail entries={entries} />

      {modal === "add" && <AddGame onClose={closeModal} onAdded={() => { closeModal(); load(); }} />}
      {modal === "import" && <ImportGames onClose={closeModal} onDone={(msg) => { closeModal(); setNotice(msg); load(); }} />}
    </div>
  );
}

function Modal({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-30 flex items-start justify-center bg-ink/80 p-5 pt-20 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-lg rounded-2xl border border-line bg-panel p-6" onClick={(e) => e.stopPropagation()} role="dialog">
        {children}
      </div>
    </div>
  );
}

function AddGame({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const { token } = useAuth();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Game[]>([]);
  const [platform, setPlatform] = useState("steam");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (q.trim().length < 2) { setResults([]); return; }
    const id = setTimeout(() => api.searchGames(token!, q).then(setResults).catch((e) => setError(e.message)), 300);
    return () => clearTimeout(id);
  }, [q, token]);

  const add = async (g: Game, status: Status) => {
    try {
      await api.addToLibrary(token!, g.id, status, platform);
      onAdded();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <Modal onClose={onClose}>
      <div className="flex gap-2">
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by title"
          className="w-full rounded-full border border-line bg-field px-4 py-2 placeholder:text-fog/60" />
        <PlatformPicker value={platform} onChange={setPlatform} />
      </div>
      {error && <p className="mt-3 text-sm text-coral">{error}</p>}
      <ul className="mt-4 max-h-80 divide-y divide-line overflow-y-auto">
        {results.map((g) => (
          <li key={g.id} className="flex items-center gap-3 py-3">
            <GameCover game={g} compact className="h-14 w-10 rounded" />
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">{g.title}</div>
              <div className="truncate text-xs text-fog">{[g.developer, g.release_year].filter(Boolean).join(", ")}</div>
            </div>
            <button onClick={() => add(g, "backlog")} className="rounded-lg bg-snow px-3 py-1 text-sm font-semibold text-ink">Backlog</button>
            <button onClick={() => add(g, "completed")} className="rounded-lg border border-line px-3 py-1 text-sm">Played it</button>
          </li>
        ))}
        {q.length >= 2 && results.length === 0 && <li className="py-3 text-sm text-fog">No matches for "{q}".</li>}
      </ul>
    </Modal>
  );
}

function ImportGames({ onClose, onDone }: { onClose: () => void; onDone: (msg: string) => void }) {
  const { token } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manual, setManual] = useState(false);
  const [id, setId] = useState("");
  const [paste, setPaste] = useState("");
  const [pastePlatform, setPastePlatform] = useState("playstation");
  const [config, setConfig] = useState<{ steam_import: boolean } | null>(null);

  useEffect(() => { api.config().then(setConfig).catch(() => setConfig({ steam_import: false })); }, []);

  const steam = async () => {
    setBusy(true);
    try {
      const { url } = await api.steamLoginUrl(token!);
      window.location.href = url;
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  const manualImport = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.importSteam(token!, id.trim());
      onDone(`Imported ${r.imported} games from Steam${r.updated ? `, updated ${r.updated}` : ""}.`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const pasteImport = async () => {
    const titles = paste.split("\n").map((l) => l.trim()).filter(Boolean);
    if (titles.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.bulkImport(token!, titles.map((title) => ({ title, platform: pastePlatform })));
      onDone(`Added ${r.imported} games${r.updated ? `, ${r.updated} already there` : ""}. Artwork is filling in now.`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const scanCmd = "python playnext_scan.py";

  return (
    <Modal onClose={onClose}>
      <h2 className="text-xl font-bold">Import games</h2>
      <p className="mt-1 text-sm text-fog">Steam is the only platform that lets apps read your library directly. The routes below cover everything else.</p>

      <div className="mt-5 rounded-xl bg-field p-4">
        <h3 className="font-semibold">Everything you own on Steam</h3>
        {config?.steam_import === false ? (
          <p className="mt-1 text-sm text-fog">
            Not set up on this server. It needs a free{" "}
            <a href="https://steamcommunity.com/dev/apikey" target="_blank" rel="noreferrer" className="text-amber underline">Steam Web API key</a>{" "}
            in <code className="rounded bg-panel px-1.5 py-0.5 font-mono text-xs">backend/.env</code> as{" "}
            <code className="rounded bg-panel px-1.5 py-0.5 font-mono text-xs">STEAM_API_KEY</code>, then a restart.
            Until then, use the PC scanner below — it covers Steam too.
          </p>
        ) : (
          <>
            <p className="mt-1 text-sm text-fog">One click. Steam tells us which games you own and how long you've played each.</p>
            <button onClick={steam} disabled={busy} className="mt-3 rounded-lg bg-amber px-4 py-2 font-semibold text-ink disabled:opacity-50">
              {busy ? "Opening Steam…" : "Sign in with Steam"}
            </button>
          </>
        )}
      </div>

      <div className="mt-3 rounded-xl bg-field p-4">
        <h3 className="font-semibold">Everything installed on this PC</h3>
        <p className="mt-1 text-sm text-fog">
          Epic, GOG, Ubisoft, EA, Battle.net, Xbox and Game Pass don't offer sign-in imports, so a small scanner
          reads what's on your drive, the same way the NVIDIA and Xbox apps do. It only sends game titles.
        </p>
        <ol className="mt-3 space-y-2 text-sm">
          <li><a href={`${import.meta.env.VITE_API_URL ?? "/api"}/scanner/playnext_scan.py`} download className="text-amber underline">Download the scanner</a> (a single Python file)</li>
          <li>
            Double-click it, or run{" "}
            <code className="rounded bg-panel px-1.5 py-0.5 font-mono text-xs">{scanCmd}</code>{" "}
            <button onClick={() => navigator.clipboard.writeText(scanCmd)} className="text-fog underline">copy</button>
          </li>
          <li>It shows what it found, asks for your PlayNext login, and your games appear here.</li>
        </ol>
      </div>

      <div className="mt-3 rounded-xl bg-field p-4">
        <h3 className="font-semibold">PlayStation, Switch and everything else</h3>
        <p className="mt-1 text-sm text-fog">
          Sony, Nintendo, Epic and Blizzard don't publish a way for apps to read your library, so there's nothing
          to sign in to. Paste your titles instead, one per line — artwork and details are filled in automatically.
        </p>
        <div className="mt-3 flex items-center gap-2">
          <span className="text-sm text-fog">These are on</span>
          <PlatformPicker value={pastePlatform} onChange={setPastePlatform} />
        </div>
        <textarea value={paste} onChange={(e) => setPaste(e.target.value)} rows={4}
          placeholder={"God of War Ragnarök\nThe Last of Us Part II\nGran Turismo 7"}
          className="mt-3 w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm placeholder:text-fog/50" />
        <button onClick={pasteImport} disabled={busy || paste.trim().length < 3}
          className="mt-3 rounded-lg bg-snow px-4 py-2 text-sm font-semibold text-ink disabled:opacity-40">
          {busy ? "Importing…" : `Add ${paste.split("\n").filter((l) => l.trim()).length || ""} games`}
        </button>
      </div>

      {error && <p className="mt-3 text-sm text-coral">{error}</p>}

      <button onClick={() => setManual(!manual)} className="mt-4 text-sm text-fog hover:text-snow">
        {manual ? "Hide" : "Steam sign-in not working? Paste your SteamID instead"}
      </button>
      {manual && (
        <div className="mt-2 flex gap-2">
          <input value={id} onChange={(e) => setId(e.target.value)} placeholder="17-digit SteamID64"
            className="w-full rounded-full border border-line bg-field px-4 py-2 font-mono text-sm placeholder:text-fog/60" />
          <button onClick={manualImport} disabled={busy || !/^\d{17}$/.test(id.trim())}
            className="rounded-lg border border-line px-4 py-2 text-sm disabled:opacity-40">Import</button>
        </div>
      )}
    </Modal>
  );
}

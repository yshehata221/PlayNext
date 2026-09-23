/**
 * Static demo mode.
 *
 * With VITE_DEMO_MODE=1 the app runs with no backend at all: reads are served
 * from a snapshot of the real API's responses (captured by
 * `python -m app.snapshot`), and writes are applied to an in-memory copy so the
 * demo still feels interactive. Refreshing resets it.
 *
 * This exists so the GitHub Pages build is a genuinely clickable product rather
 * than a screenshot gallery, without a server to pay for or keep awake.
 */
import snapshot from "./snapshot.json";

type Json = Record<string, any>;

const DEMO_TOKEN = "demo-mode-token";
const data: Record<string, any> = JSON.parse(JSON.stringify(snapshot));

/** Mutations land here and win over the snapshot for the rest of the session. */
const edits = {
  entries: new Map<number, Json>(),
  removed: new Set<number>(),
  added: [] as Json[],
  wishlist: [] as Json[],
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function libraryEntries(): Json[] {
  const base: Json[] = data["/library?sort=added"] ?? [];
  return [...edits.added, ...base]
    .filter((e) => !edits.removed.has(e.id))
    .map((e) => ({ ...e, ...(edits.entries.get(e.id) ?? {}) }));
}

function findEntry(id: number): Json | undefined {
  return libraryEntries().find((e) => e.id === id);
}

/** Recompute the figures an edit would change, so the UI stays coherent. */
function stats(): Json {
  const base: Json = data["/stats"] ?? {};
  const entries = libraryEntries();
  const rated = entries.filter((e) => e.rating != null);
  const counts: Record<string, number> = {};
  for (const e of entries) counts[e.status] = (counts[e.status] ?? 0) + 1;

  return {
    ...base,
    total_games: entries.length,
    total_hours: Math.round(entries.reduce((a, e) => a + e.hours_played, 0) * 10) / 10,
    rated_games: rated.length,
    completed_games: counts.completed ?? 0,
    average_rating: rated.length
      ? Math.round((rated.reduce((a, e) => a + e.rating, 0) / rated.length) * 10) / 10
      : null,
    by_status: (base.by_status ?? []).map((b: Json) => ({ ...b, count: counts[b.status] ?? 0 })),
  };
}

/**
 * The snapshot is keyed by exact path. Real requests vary in parameter order
 * and include some the snapshot doesn't, so fall back progressively rather than
 * 404ing: exact match, then same path with any query, then a sensible default.
 */
function lookup(path: string): unknown | undefined {
  if (path in data) return data[path];

  const [base, query] = path.split("?");
  const params = new URLSearchParams(query ?? "");

  const candidates = Object.keys(data).filter((key) => key.split("?")[0] === base);
  if (candidates.length === 0) return undefined;

  // prefer a snapshot entry whose parameters are the closest match
  let best = candidates[0];
  let bestScore = -1;
  for (const key of candidates) {
    const other = new URLSearchParams(key.split("?")[1] ?? "");
    let score = 0;
    for (const [k, v] of params) if (other.get(k) === v) score += 1;
    for (const [k] of other) if (!params.has(k)) score -= 1;
    if (score > bestScore) {
      best = key;
      bestScore = score;
    }
  }
  return data[best];
}

function handleGet(path: string): Response {
  if (path === "/auth/me") return json({ ...(data["/auth/me"] as Json), email_verified: true });
  if (path.startsWith("/stats")) return json(stats());
  if (path.startsWith("/library/") && !path.includes("import")) {
    const entry = findEntry(Number(path.split("/")[2]));
    return entry ? json(entry) : json({ detail: "Not found" }, 404);
  }
  if (path.startsWith("/library")) {
    const params = new URLSearchParams(path.split("?")[1] ?? "");
    const status = params.get("status");
    let entries = libraryEntries().filter((e) => e.status !== "wishlist");
    if (status) entries = entries.filter((e) => e.status === status);

    const sort = params.get("sort") ?? "added";
    const by: Record<string, (a: Json, b: Json) => number> = {
      title: (a, b) => a.game.title.localeCompare(b.game.title),
      rating: (a, b) => (b.rating ?? -1) - (a.rating ?? -1),
      hours: (a, b) => b.hours_played - a.hours_played,
      last_played: (a, b) => Date.parse(b.last_played ?? 0) - Date.parse(a.last_played ?? 0),
      added: (a, b) => Date.parse(b.added_at) - Date.parse(a.added_at),
    };
    return json([...entries].sort(by[sort] ?? by.added));
  }
  if (path.startsWith("/wishlist")) return json([...(data["/wishlist"] as Json[]), ...edits.wishlist]);

  const hit = lookup(path);
  return hit === undefined ? json({ detail: "Not available in the demo" }, 404) : json(hit);
}

function handleWrite(method: string, path: string, body: Json): Response {
  if (path === "/auth/demo" || path === "/auth/login") return json({ access_token: DEMO_TOKEN });
  if (path === "/auth/register") {
    return json({ detail: "The demo is read-only — sign-up needs the full app." }, 403);
  }
  if (path === "/library/enrich") return json({ queued: 0 });

  // PATCH /library/{id} — rate, change status, log hours
  const patch = path.match(/^\/library\/(\d+)$/);
  if (patch && method === "PATCH") {
    const id = Number(patch[1]);
    const current = findEntry(id);
    if (!current) return json({ detail: "Not found" }, 404);
    const updated = { ...current, ...body, updated_at: new Date().toISOString() };
    edits.entries.set(id, { ...(edits.entries.get(id) ?? {}), ...body, updated_at: updated.updated_at });
    return json(updated);
  }
  if (patch && method === "DELETE") {
    edits.removed.add(Number(patch[1]));
    return new Response(null, { status: 204 });
  }

  if (path === "/wishlist" && method === "POST") {
    const game = findGame(body.game_id);
    if (!game) return json({ detail: "Game not found" }, 404);
    const entry = newEntry(game, "wishlist");
    edits.wishlist.push(entry);
    return json(entry, 201);
  }
  if (path === "/library" && method === "POST") {
    const game = findGame(body.game_id);
    if (!game) return json({ detail: "Game not found" }, 404);
    const entry = newEntry(game, body.status ?? "backlog", body.platform);
    edits.added.unshift(entry);
    return json(entry, 201);
  }

  return json({ detail: "That action needs the full app — this is a static demo." }, 403);
}

/** Every game the snapshot knows about, so additions can reference real data. */
function findGame(id: number): Json | undefined {
  for (const value of Object.values(data)) {
    if (Array.isArray(value)) {
      for (const row of value) {
        if (row?.game?.id === id) return row.game;
        if (row?.id === id && row?.title) return row;
      }
    } else if (value && typeof value === "object") {
      const items = (value as Json).items;
      if (Array.isArray(items)) {
        for (const item of items) if (item?.game?.id === id) return item.game;
      }
      if ((value as Json).game?.id === id) return (value as Json).game;
    }
  }
  return undefined;
}

let nextId = 90000;
function newEntry(game: Json, status: string, platform = "steam"): Json {
  const now = new Date().toISOString();
  return {
    id: nextId++, status, platform, rating: null, review: null, hours_played: 0,
    last_played: null, added_at: now, updated_at: now, game,
  };
}

// Every path the API serves. Used to decide what to intercept, because the
// request prefix depends on how the bundle was built: "/api" behind the dev
// proxy, bare paths when no separate API URL was configured.
const API_ROOTS = [
  "/auth", "/library", "/browse", "/friends", "/wishlist", "/stats",
  "/recommendations", "/games", "/steam", "/config", "/health",
];

/**
 * Work out which API path a request is for, or null if it isn't one of ours.
 * Exported for testing: getting this wrong sends demo traffic to the real
 * network, which is exactly how the first deploy of the demo broke.
 */
export function apiPath(url: string): string | null {
  let path = url;
  try {
    // absolute URLs (the app builds some) reduce to their path
    path = new URL(url, window.location.href).pathname + new URL(url, window.location.href).search;
  } catch {
    /* relative string: use as-is */
  }

  const marker = "/api/";
  const index = path.indexOf(marker);
  if (index !== -1) return path.slice(index + marker.length - 1);

  // no /api prefix: match the API's own roots, ignoring any base path the site
  // is served under (a GitHub Pages project site lives at /<repo>/)
  for (const root of API_ROOTS) {
    const at = path.indexOf(root);
    if (at !== -1) {
      const after = path[at + root.length];
      if (after === undefined || after === "/" || after === "?") return path.slice(at);
    }
  }
  return null;
}

/** Patch fetch so every call the app makes is answered locally. */
export function installDemoApi(): void {
  const original = window.fetch.bind(window);

  window.fetch = async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;

    // only intercept our own API calls; images and fonts still go to the network
    const path = apiPath(url);
    if (path === null) return original(input as RequestInfo, init);

    const method = (init.method ?? "GET").toUpperCase();

    // a touch of latency, so loading states are visible rather than flashing
    await new Promise((resolve) => setTimeout(resolve, 120));

    if (method === "GET") return handleGet(path);
    let body: Json = {};
    try {
      body = init.body && typeof init.body === "string" ? JSON.parse(init.body) : {};
    } catch {
      body = {};
    }
    return handleWrite(method, path, body);
  };
}

export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "1";

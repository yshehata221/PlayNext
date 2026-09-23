// Tiny fetch wrapper. Token lives in memory (auth.tsx) and is passed in per call,
// so this file has no idea about React.

export type Status = "backlog" | "playing" | "completed" | "abandoned" | "wishlist";

export interface Game {
  id: number;
  title: string;
  slug: string;
  steam_appid: number | null;
  developer: string | null;
  release_year: number | null;
  genres: string[];
  themes: string[];
  perspectives: string[];
  modes: string[];
  platforms: string[];
  requirements: { minimum?: string; recommended?: string } | null;
  hours_main: number | null;
  hours_complete: number | null;
  avg_session_minutes: number | null;
  critic_score: number | null;
  cover_url: string | null;
  hero_url: string | null;
  screenshots: string[];
  videos: { kind: "mp4" | "youtube"; src: string; title: string; thumb: string | null }[];
  summary: string | null;
}

export interface Entry {
  id: number;
  status: Status;
  platform: string;
  rating: number | null;
  review: string | null;
  hours_played: number;
  last_played: string | null;
  added_at: string;
  updated_at: string;
  game: Game;
}

export interface Recommendation {
  game: Game;
  score: number;
  reasons: string[];
  in_library: boolean;
  status: Status | null;
  hours_remaining: number | null;
}

export type Mood = "relaxing" | "story" | "quick" | "new";

export interface PlanItem extends Recommendation {
  minutes: number;
}

export interface BrowseItem {
  game: Game;
  in_library: boolean;
  status: Status | null;
  entry_id: number | null;
  match: number | null;
  reasons: string[];
  discount_percent: number | null;
  price: string | null;
}

export interface BrowsePage {
  items: BrowseItem[];
  total: number;
  has_more: boolean;
  genres: string[];
  platforms: { value: string; label: string }[];
  source: "igdb" | "steam";
}

export interface BrowseFilters {
  genre?: string;
  platform?: string;
  year_min?: number;
  year_max?: number;
  sort?: string;
  hide_owned?: boolean;
  section?: string;
}

export interface FriendUser {
  id: number;
  username: string | null;
  display_name: string;
}

export interface Friend {
  friendship_id: number;
  user: FriendUser;
  state: "pending" | "accepted";
  direction: "incoming" | "outgoing" | "mutual";
  games: number;
  shared_games: number;
  compatibility: number | null;
}

export interface FriendSearchResult {
  user: FriendUser;
  relationship: "none" | "pending_in" | "pending_out" | "friends" | "self";
}

export interface CoopPick {
  game: Game;
  score: number;
  reasons: string[];
  plays_together: boolean | null;
  your_rating: number | null;
  their_rating: number | null;
  your_hours: number;
  their_hours: number;
  minutes: number | null;
}

export interface Personality {
  key: string;
  title: string;
  tagline: string;
  blurb: string;
  evidence: string;
}

export interface Stats {
  total_games: number;
  total_hours: number;
  played_games: number;
  rated_games: number;
  added_last_30_days: number;
  by_status: { status: Status; count: number }[];
  by_platform: Record<string, number>;
  by_genre: { genre: string; games: number; hours: number; hours_share: number; games_share: number; avg_rating: number | null }[];
  backlog_hours: number;
  backlog_games: number;
  backlog_years_at_current_pace: number | null;
  backlog_months_at_current_pace: number | null;
  weekly_hours_pace: number;
  average_rating: number | null;
  completion_rate: number;
  completed_games: number;
  started_games: number;
  avg_hours_per_finished: number | null;
  most_played: Entry[];
  personality: Personality;
}

// drop undefined/empty values so we don't send `genre=` and match nothing
function qs(params: Record<string, string | number | boolean | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "" && v !== false) p.set(k, String(v));
  }
  return p.toString();
}

// In development Vite proxies /api to the backend. In production the two are
// usually separate services, so the base URL comes from the build environment.
// `||` not `??`: a build that sets VITE_API_URL to an empty string means "no
// separate API", which should fall back to the proxy path, and an empty string
// is not nullish.
const API_BASE = import.meta.env.VITE_API_URL || "/api";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.body && !(init.body instanceof URLSearchParams)) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // FastAPI puts the message in `detail`; validation errors are an array
    const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
    throw new ApiError(res.status, detail ?? "Something went wrong");
  }
  return data as T;
}

export interface ServerConfig {
  steam_import: boolean;
  igdb_catalogue: boolean;
  email: boolean;
  require_email_verification: boolean;
  demo_login: boolean;
}

export const api = {
  config: () => request<ServerConfig>("/config", null),
  register: (email: string, display_name: string, username: string, password: string) =>
    request<{ access_token: string }>("/auth/register", null, { method: "POST", body: JSON.stringify({ email, display_name, username, password }) }),
  demoLogin: () => request<{ access_token: string }>("/auth/demo", null, { method: "POST" }),
  usernameAvailable: (username: string) =>
    request<{ available: boolean; reason: string | null }>(`/auth/username-available/${encodeURIComponent(username)}`, null),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", null, { method: "POST", body: new URLSearchParams({ username: email, password }) }),
  me: (t: string) => request<{ id: number; email: string; display_name: string; username: string | null; steam_id: string | null; email_verified: boolean }>("/auth/me", t),

  resendVerification: (t: string) => request<{ sent: boolean }>("/auth/verify/resend", t, { method: "POST" }),
  verifyEmail: (token: string) => request<{ email_verified: boolean }>("/auth/verify", null, { method: "POST", body: JSON.stringify({ token }) }),
  forgotPassword: (email: string) => request<{ sent: boolean }>("/auth/forgot-password", null, { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (token: string, new_password: string) =>
    request<{ access_token: string }>("/auth/reset-password", null, { method: "POST", body: JSON.stringify({ token, new_password }) }),
  changePassword: (t: string, current_password: string, new_password: string) =>
    request<void>("/auth/change-password", t, { method: "POST", body: JSON.stringify({ current_password, new_password }) }),

  friends: (t: string) => request<Friend[]>("/friends", t),
  searchUsers: (t: string, q: string) => request<FriendSearchResult[]>(`/friends/search?q=${encodeURIComponent(q)}`, t),
  addFriend: (t: string, username: string) =>
    request<Friend>("/friends/request", t, { method: "POST", body: JSON.stringify({ username }) }),
  acceptFriend: (t: string, id: number) => request<Friend>(`/friends/${id}/accept`, t, { method: "POST" }),
  removeFriend: (t: string, id: number) => request<void>(`/friends/${id}`, t, { method: "DELETE" }),
  coop: (t: string, userId: number, hours?: number, togetherOnly = true) =>
    request<CoopPick[]>(`/friends/${userId}/coop?${qs({ hours, together_only: togetherOnly ? undefined : "false" })}`, t),

  searchGames: (t: string, q: string) => request<Game[]>(`/games/search?q=${encodeURIComponent(q)}`, t),

  library: (t: string, params: Record<string, string> = {}) =>
    request<Entry[]>(`/library?${new URLSearchParams(params)}`, t),
  entry: (t: string, id: number) => request<Entry>(`/library/${id}`, t),
  addToLibrary: (t: string, game_id: number, status: Status = "backlog", platform = "steam") =>
    request<Entry>("/library", t, { method: "POST", body: JSON.stringify({ game_id, status, platform }) }),
  updateEntry: (t: string, id: number, patch: Partial<Pick<Entry, "status" | "rating" | "hours_played" | "review" | "platform">>) =>
    request<Entry>(`/library/${id}`, t, { method: "PATCH", body: JSON.stringify(patch) }),
  removeEntry: (t: string, id: number) => request<void>(`/library/${id}`, t, { method: "DELETE" }),

  recommendations: (t: string, source: "backlog" | "discover" | "all", hours?: number, mood?: Mood, limit = 8) =>
    request<Recommendation[]>(`/recommendations?source=${source}&limit=${limit}${hours ? `&hours=${hours}` : ""}${mood ? `&mood=${mood}` : ""}`, t),
  plan: (t: string, hours: number, mood?: Mood) =>
    request<PlanItem[]>(`/recommendations/plan?hours=${hours}${mood ? `&mood=${mood}` : ""}`, t),

  enrichLibrary: (t: string) => request<{ queued: number }>("/library/enrich", t, { method: "POST" }),

  browseGame: (t: string, gameId: number) => request<BrowseItem>(`/browse/game/${gameId}`, t),
  similarGames: (t: string, gameId: number, limit = 8) => request<BrowseItem[]>(`/browse/game/${gameId}/similar?limit=${limit}`, t),
  browseSearch: (t: string, q: string, f: BrowseFilters = {}, limit = 24, offset = 0) =>
    request<BrowsePage>(`/browse/search?${qs({ q, ...f, limit, offset })}`, t),
  browsePopular: (t: string, f: BrowseFilters = {}, limit = 24, offset = 0) =>
    request<BrowsePage>(`/browse/popular?${qs({ section: f.section, genre: f.genre, platform: f.platform, sort: f.sort, limit, offset })}`, t),
  browseForYou: (t: string, f: BrowseFilters = {}, limit = 24, offset = 0) =>
    request<BrowsePage>(`/browse/for-you?${qs({ genre: f.genre, limit, offset })}`, t),

  wishlist: (t: string) => request<Entry[]>("/wishlist", t),
  addToWishlist: (t: string, game_id: number) =>
    request<Entry>("/wishlist", t, { method: "POST", body: JSON.stringify({ game_id }) }),
  markOwned: (t: string, entry_id: number, platform = "steam") =>
    request<Entry>(`/wishlist/${entry_id}/own?platform=${platform}`, t, { method: "POST" }),

  stats: (t: string) => request<Stats>("/stats", t),

  steamLoginUrl: (t: string) => request<{ url: string }>("/steam/login", t),
  bulkImport: (t: string, games: { title: string; platform: string }[]) =>
    request<{ imported: number; updated: number; skipped: number; unmatched: string[] }>("/library/import", t, {
      method: "POST", body: JSON.stringify({ games }),
    }),
  importSteam: (t: string, steam_id: string) =>
    request<{ imported: number; updated: number; skipped: number }>("/steam/import", t, { method: "POST", body: JSON.stringify({ steam_id }) }),
};

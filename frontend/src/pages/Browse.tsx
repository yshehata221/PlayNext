import { Search, Sparkles, TrendingUp, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import BrowseCard from "../components/BrowseCard";
import { HardwareFilter } from "../components/Platform";
import { api, type BrowseFilters, type BrowseItem } from "../lib/api";
import { useAuth } from "../lib/auth";

const PAGE = 48;
const SORTS = [
  { key: "relevance", label: "Relevance" },
  { key: "title", label: "Title" },
  { key: "year", label: "Newest" },
  { key: "score", label: "Critic score" },
];
const SECTIONS = [
  { key: "all", label: "Everything" },
  { key: "catalogue", label: "Whole catalogue" },
  { key: "top_sellers", label: "Top sellers" },
  { key: "specials", label: "On sale" },
  { key: "new_releases", label: "New releases" },
  { key: "coming_soon", label: "Coming soon" },
];
const DECADES = [
  { key: "", label: "Any year" },
  { key: "2024-2100", label: "2024 and newer" },
  { key: "2020-2023", label: "2020–2023" },
  { key: "2010-2019", label: "2010s" },
  { key: "1990-2009", label: "Before 2010" },
];

type Tab = "results" | "for-you" | "popular";

export default function Browse() {
  const { token } = useAuth();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [tab, setTab] = useState<Tab>("for-you");
  const [genre, setGenre] = useState("");
  const [platform, setPlatform] = useState("");
  const [years, setYears] = useState("");
  const [sort, setSort] = useState("relevance");
  const [section, setSection] = useState("all");
  const [hideOwned, setHideOwned] = useState(false);

  const [items, setItems] = useState<BrowseItem[] | null>(null);
  const [genres, setGenres] = useState<string[]>([]);
  const [platformOpts, setPlatformOpts] = useState<{ value: string; label: string }[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<"igdb" | "steam">("steam");

  useEffect(() => {
    const id = setTimeout(() => setDebounced(q.trim()), 350);
    return () => clearTimeout(id);
  }, [q]);

  // searching takes over the view; clearing the box returns to the last browse tab
  const active: Tab = debounced.length >= 2 ? "results" : tab === "results" ? "for-you" : tab;

  const filters = useCallback((): BrowseFilters => {
    const [min, max] = years ? years.split("-").map(Number) : [undefined, undefined];
    return { genre: genre || undefined, platform: platform || undefined, year_min: min, year_max: max, sort, hide_owned: hideOwned, section };
  }, [genre, platform, years, sort, hideOwned, section]);

  const fetchPage = useCallback(async (offset: number) => {
    const f = filters();
    if (active === "results") return api.browseSearch(token!, debounced, f, PAGE, offset);
    if (active === "popular") return api.browsePopular(token!, f, PAGE, offset);
    return api.browseForYou(token!, f, PAGE, offset);
  }, [active, debounced, filters, token]);

  useEffect(() => {
    setItems(null);
    setError(null);
    fetchPage(0)
      .then((p) => { setItems(p.items); setGenres(p.genres); setPlatformOpts(p.platforms); setTotal(p.total); setHasMore(p.has_more); setSource(p.source); })
      .catch((e) => { setError(e.message); setItems([]); });
  }, [fetchPage]);

  const loadMore = useCallback(async () => {
    if (!items || loadingMore) return;
    setLoadingMore(true);
    try {
      const p = await fetchPage(items.length);
      // de-dupe: a shifting sort can return a game we already have
      const seen = new Set(items.map((i) => i.game.id));
      setItems([...items, ...p.items.filter((i) => !seen.has(i.game.id))]);
      setHasMore(p.has_more);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingMore(false);
    }
  }, [items, loadingMore, fetchPage]);

  // load the next page automatically when the sentinel scrolls into view
  const sentinel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !hasMore) return;
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) loadMore();
    }, { rootMargin: "600px" });
    io.observe(el);
    return () => io.disconnect();
  }, [hasMore, loadMore]);

  const wishlist = async (i: BrowseItem) => { await api.addToWishlist(token!, i.game.id); };
  const own = async (i: BrowseItem) => { await api.addToLibrary(token!, i.game.id, "backlog"); };

  const resetFilters = () => { setGenre(""); setPlatform(""); setYears(""); setSort("relevance"); setHideOwned(false); setSection("all"); };
  const filtered = genre || platform || years || hideOwned || sort !== "relevance" || section !== "all";

  const pill = (on: boolean) =>
    `rounded-full px-4 py-1.5 text-sm transition-colors ${on ? "bg-amber font-semibold text-ink" : "bg-panel text-fog hover:text-snow"}`;
  const select = "rounded-full border border-line bg-field px-3 py-1.5 text-sm text-snow";

  return (
    <div>
      <h1 className="text-4xl font-bold tracking-tight">Browse</h1>
      <p className="mt-1 text-fog">
        {source === "igdb"
          ? "Every game on every platform — search, filter, wishlist."
          : "Find something to play next, whether you own it or not."}
      </p>

      {source === "steam" && (
        <p className="mt-4 max-w-3xl rounded-xl border border-line bg-panel px-4 py-3 text-sm text-fog">
          Browse is currently limited to Steam's catalogue. Add free{" "}
          <a href="https://api-docs.igdb.com/#getting-started" target="_blank" rel="noreferrer" className="text-amber underline">IGDB credentials</a>{" "}
          to <code className="rounded bg-field px-1.5 py-0.5 font-mono text-xs">backend/.env</code> and every console and launcher game becomes searchable — roughly 300,000 titles instead of Steam's.
        </p>
      )}

      <div className="relative mt-6 max-w-2xl">
        <Search size={18} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-fog" />
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search every game — a title, a series, a developer…"
          className="w-full rounded-full border border-line bg-field py-3 pl-11 pr-10 placeholder:text-fog/60" />
        {q && (
          <button onClick={() => setQ("")} aria-label="Clear search" className="absolute right-3.5 top-1/2 -translate-y-1/2 text-fog hover:text-snow"><X size={16} /></button>
        )}
      </div>

      {active !== "results" && (
        <div className="mt-6 flex flex-wrap gap-2">
          <button className={pill(active === "for-you")} onClick={() => setTab("for-you")}>Picked for you</button>
          <button className={pill(active === "popular" && section !== "catalogue")} onClick={() => { setTab("popular"); setSection("all"); }}>Popular right now</button>
          {source === "igdb" && (
            <button className={pill(active === "popular" && section === "catalogue")} onClick={() => { setTab("popular"); setSection("catalogue"); }}>
              Everything
            </button>
          )}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {active === "popular" && (
          <select value={section} onChange={(e) => setSection(e.target.value)} className={select} aria-label="Section">
            {SECTIONS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        )}
        <select value={genre} onChange={(e) => setGenre(e.target.value)} className={select} aria-label="Genre">
          <option value="">Any genre</option>
          {genres.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
        {platformOpts.length > 0 && active !== "for-you" && (
          <HardwareFilter value={platform} options={platformOpts} onChange={setPlatform} />
        )}
        {active === "popular" && section === "catalogue" && (
          <select value={sort} onChange={(e) => setSort(e.target.value)} className={select} aria-label="Sort">
            {SORTS.map((s) => <option key={s.key} value={s.key}>Sort: {s.label}</option>)}
          </select>
        )}
        {active === "results" && (
          <>
            <select value={years} onChange={(e) => setYears(e.target.value)} className={select} aria-label="Release years">
              {DECADES.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
            </select>
            <select value={sort} onChange={(e) => setSort(e.target.value)} className={select} aria-label="Sort">
              {SORTS.map((s) => <option key={s.key} value={s.key}>Sort: {s.label}</option>)}
            </select>
            <button onClick={() => setHideOwned(!hideOwned)} className={pill(hideOwned)}>Hide games I own</button>
          </>
        )}
        {filtered && <button onClick={resetFilters} className="text-sm text-fog underline hover:text-snow">Clear filters</button>}
      </div>

      <h2 className="mt-8 flex flex-wrap items-center gap-2 text-sm font-semibold text-fog">
        {active === "results" && <>{total.toLocaleString()} result{total === 1 ? "" : "s"} for "{debounced}"</>}
        {active === "for-you" && <><Sparkles size={15} className="text-amber" />Picked for you — ranked against what you've rated highly</>}
        {active === "popular" && (
          <><TrendingUp size={15} className="text-amber" />
            {SECTIONS.find((s) => s.key === section)?.label}
            {source === "igdb" && section === "catalogue" && total > 0 && <span className="font-normal">— {total.toLocaleString()} games</span>}
          </>
        )}
        {items && items.length > 0 && <span className="font-normal opacity-70">· showing {items.length.toLocaleString()}</span>}
      </h2>

      {error && <p className="mt-4 text-sm text-coral">{error}</p>}
      {items === null && <p className="mt-6 text-fog">Loading…</p>}
      {items?.length === 0 && !error && (
        <p className="mt-6 text-fog">
          {active === "for-you" ? "Rate a few games in your library and suggestions will appear here." : "Nothing matches. Try clearing a filter or using fewer words."}
        </p>
      )}

      <div className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5 [@media(min-width:1900px)]:grid-cols-6">
        {items?.map((i) => <BrowseCard key={i.game.id} item={i} onWishlist={wishlist} onOwn={own} />)}
      </div>

      <div ref={sentinel} />

      {hasMore && (
        <div className="mt-10 text-center">
          <button onClick={loadMore} disabled={loadingMore}
            className="rounded-full border border-line bg-panel px-6 py-2.5 text-sm font-semibold hover:border-fog/50 disabled:opacity-60">
            {loadingMore ? "Loading more…" : "Load more"}
          </button>
        </div>
      )}
      {!hasMore && (items?.length ?? 0) > PAGE && (
        <p className="mt-10 text-center text-sm text-fog">That's everything matching these filters.</p>
      )}
    </div>
  );
}

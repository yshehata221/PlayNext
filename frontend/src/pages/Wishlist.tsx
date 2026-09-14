import { Heart, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import GameCover from "../components/GameCover";
import { PlatformPicker } from "../components/Platform";
import { api, type Entry } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Wishlist() {
  const { token } = useAuth();
  const [items, setItems] = useState<Entry[] | null>(null);
  const [platform, setPlatform] = useState("steam");
  const [notice, setNotice] = useState<string | null>(null);

  const load = () => api.wishlist(token!).then(setItems);
  useEffect(() => { load(); }, [token]);

  const own = async (e: Entry) => {
    await api.markOwned(token!, e.id, platform);
    setNotice(`${e.game.title} moved to your backlog.`);
    load();
  };
  const remove = async (e: Entry) => { await api.removeEntry(token!, e.id); load(); };

  const hours = (items ?? []).reduce((a, e) => a + (e.game.hours_main ?? 0), 0);

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">Wishlist</h1>
          <p className="mt-1 text-fog">Games you don't own yet.</p>
        </div>
        <Link to="/browse" className="flex items-center gap-2 rounded-lg bg-amber px-4 py-2 text-sm font-semibold text-ink hover:brightness-110">
          <Search size={16} />Find games
        </Link>
      </div>

      {items && items.length > 0 && (
        <dl className="mt-6 flex flex-wrap divide-x divide-line">
          <div className="py-1 pr-8"><dd className="text-2xl font-bold">{items.length}</dd><dd className="text-sm text-fog">On your wishlist</dd></div>
          <div className="px-8 py-1"><dd className="text-2xl font-bold">{Math.round(hours)}h</dd><dd className="text-sm text-fog">If you played them all</dd></div>
          <div className="px-8 py-1">
            <dd className="flex items-center gap-2"><span className="text-sm text-fog">Mark as owned on</span><PlatformPicker value={platform} onChange={setPlatform} /></dd>
          </div>
        </dl>
      )}

      {notice && <p className="mt-6 rounded-lg bg-panel px-4 py-2 text-sm text-mint">{notice}</p>}

      {items === null && <p className="mt-10 text-fog">Loading…</p>}
      {items?.length === 0 && (
        <div className="mt-12 rounded-2xl border border-dashed border-line p-12 text-center">
          <Heart size={28} className="mx-auto text-fog" />
          <p className="mt-4 text-fog">Nothing wishlisted yet.</p>
          <Link to="/browse" className="mt-4 inline-block rounded-lg bg-amber px-4 py-2 text-sm font-semibold text-ink">Browse games</Link>
        </div>
      )}

      <ul className="mt-8 space-y-4">
        {items?.map((e) => (
          <li key={e.id} className="flex items-center gap-5 rounded-2xl border border-line bg-panel p-4">
            <div className="w-16 shrink-0 overflow-hidden rounded-lg"><GameCover game={e.game} compact platform={e.platform} className="aspect-[2/3] w-full" /></div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-lg font-semibold">{e.game.title}</div>
              <p className="truncate text-sm text-fog">
                {[e.game.developer, e.game.release_year, e.game.hours_main ? `${e.game.hours_main}h to beat` : null].filter(Boolean).join(" · ")}
              </p>
              {e.game.genres.length > 0 && <p className="mt-1 truncate text-xs text-fog">{[...e.game.genres, ...e.game.themes].slice(0, 4).join(" · ")}</p>}
              {e.review && <p className="mt-1.5 text-sm italic text-fog">"{e.review}"</p>}
            </div>
            <div className="flex shrink-0 flex-col gap-2">
              <button onClick={() => own(e)} className="rounded-lg bg-amber px-3.5 py-1.5 text-sm font-semibold text-ink hover:brightness-110">I own it now</button>
              <button onClick={() => remove(e)} className="rounded-lg border border-line px-3.5 py-1.5 text-sm text-fog hover:text-coral">Remove</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

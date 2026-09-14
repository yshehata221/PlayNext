import { ArrowLeft, Check, Cpu, Heart, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import GameCover from "../components/GameCover";
import GameHero from "../components/GameHero";
import Media from "../components/Media";
import { PlatformBadges } from "../components/Platform";
import { STATUS_LABEL } from "../components/StatusChip";
import { api, type BrowseItem } from "../lib/api";
import { useAuth } from "../lib/auth";

/** Detail page for a catalogue game, whether or not it's in the library. */
export default function BrowseGame() {
  const { id } = useParams();
  const { token } = useAuth();
  const nav = useNavigate();
  const [item, setItem] = useState<BrowseItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [showSpecs, setShowSpecs] = useState(true);
  const [similar, setSimilar] = useState<BrowseItem[]>([]);

  const load = () => api.browseGame(token!, Number(id)).then(setItem).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    api.similarGames(token!, Number(id), 6).then(setSimilar).catch(() => {});
  }, [id, token]);

  if (error) {
    return (
      <div>
        <button onClick={() => nav(-1)} className="flex items-center gap-2 text-sm text-fog hover:text-snow"><ArrowLeft size={14} />Back</button>
        <p className="mt-6 text-coral">{error}</p>
        <button onClick={() => { setError(null); load(); }} className="mt-3 rounded-lg border border-line px-4 py-2 text-sm hover:bg-panel">Try again</button>
      </div>
    );
  }
  if (!item) return <p className="text-fog">Loading…</p>;

  const g = item.game;
  const act = async (kind: "wish" | "own") => {
    setBusy(kind);
    try {
      if (kind === "wish") await api.addToWishlist(token!, g.id);
      else await api.addToLibrary(token!, g.id, "backlog");
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <button onClick={() => nav(-1)} className="flex items-center gap-2 text-sm text-fog hover:text-snow"><ArrowLeft size={14} />Back</button>

      <div className="mt-4">
        <GameHero game={g}>
          <h1 className="text-3xl font-extrabold leading-tight tracking-tight sm:text-5xl">{g.title}</h1>
          <p className="mt-2 text-fog">
            {[g.developer, g.release_year, g.hours_main ? `${g.hours_main}h to beat` : null, item.price].filter(Boolean).join(" · ")}
            {item.match != null && <span className="ml-2 font-semibold text-amber">{Math.round(item.match)}% match</span>}
          </p>

          {[...g.genres, ...g.themes].length > 0 && (
            <p className="mt-3 text-sm text-fog">{[...g.genres, ...g.themes].slice(0, 6).join(" · ")}</p>
          )}

          {g.platforms.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-fog">Platforms available on</p>
              <div className="mt-2"><PlatformBadges names={g.platforms} max={12} size={16} /></div>
            </div>
          )}

          {g.summary && <p className="mt-4 max-w-2xl text-sm leading-relaxed text-fog">{g.summary}</p>}

          {item.reasons.length > 0 && (
            <ul className="mt-4 space-y-1.5">
              {item.reasons.map((r) => <li key={r} className="flex gap-2 text-sm text-fog"><span className="text-mint">✓</span>{r}</li>)}
            </ul>
          )}

          <div className="mt-6 flex flex-wrap gap-2">
            {item.in_library ? (
              <Link to={item.entry_id ? `/game/${item.entry_id}` : "/library"}
                className="flex items-center gap-2 rounded-lg border border-line bg-ink/50 px-5 py-2.5 text-sm font-semibold text-fog backdrop-blur hover:text-snow">
                <Check size={15} />{item.status ? `In library — ${STATUS_LABEL[item.status]}` : "In your library"}
              </Link>
            ) : (
              <>
                <button onClick={() => act("wish")} disabled={busy !== null}
                  className="flex items-center gap-2 rounded-lg bg-amber px-5 py-2.5 text-sm font-semibold text-ink hover:brightness-110 disabled:opacity-60">
                  <Heart size={15} />{busy === "wish" ? "Adding…" : "Add to wishlist"}
                </button>
                <button onClick={() => act("own")} disabled={busy !== null}
                  className="flex items-center gap-2 rounded-lg border border-line bg-ink/50 px-4 py-2.5 text-sm text-fog backdrop-blur hover:text-snow disabled:opacity-60">
                  <Plus size={15} />I already own this
                </button>
              </>
            )}
          </div>
        </GameHero>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <Media game={g} />
        </div>
        <aside className="space-y-6">
          {g.requirements && (g.requirements.minimum || g.requirements.recommended) ? (
            <section className="rounded-3xl border border-line bg-panel p-6">
              <button onClick={() => setShowSpecs(!showSpecs)} className="flex items-center gap-2 text-sm font-semibold text-fog hover:text-snow">
                <Cpu size={15} />PC system requirements
                <svg width="12" height="12" viewBox="0 0 12 12" className={`transition-transform ${showSpecs ? "rotate-180" : ""}`} aria-hidden><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </button>
              {showSpecs && (
                <div className="mt-3 space-y-4">
                  {(["minimum", "recommended"] as const).map((key) => g.requirements?.[key] && (
                    <div key={key} className="rounded-xl border border-line bg-panel p-4">
                      <h3 className="text-sm font-semibold capitalize">{key}</h3>
                      <pre className="mt-2 whitespace-pre-wrap font-sans text-xs leading-relaxed text-fog">{g.requirements[key]}</pre>
                    </div>
                  ))}
                </div>
              )}
            </section>
          ) : null}
        </aside>
      </div>

      {similar.length > 0 && (
        <section className="mt-8">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">You might also like</h2>
          <div className="mt-4 grid grid-cols-3 gap-4 sm:grid-cols-4 lg:grid-cols-6">
            {similar.map((i) => (
              <Link key={i.game.id} to={i.in_library && i.entry_id ? `/game/${i.entry_id}` : `/browse/game/${i.game.id}`} className="group">
                <div className="overflow-hidden rounded-xl ring-1 ring-white/5 transition-transform group-hover:-translate-y-1">
                  <GameCover game={i.game} compact className="aspect-[2/3] w-full" />
                </div>
                <div className="mt-2 truncate text-sm font-medium">{i.game.title}</div>
                <div className="text-xs text-fog">{i.in_library ? "In your library" : i.match != null ? `${Math.round(i.match)}% similar` : ""}</div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

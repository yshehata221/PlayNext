import { Check, Heart, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { BrowseItem } from "../lib/api";
import GameCover from "./GameCover";
import { PlatformBadges } from "./Platform";
import { STATUS_LABEL } from "./StatusChip";

// A game you might not own: cover, match score if we have one, and the two
// actions that matter - wishlist it, or say you already own it.
export default function BrowseCard({ item, onWishlist, onOwn }: {
  item: BrowseItem;
  onWishlist: (i: BrowseItem) => Promise<void>;
  onOwn: (i: BrowseItem) => Promise<void>;
}) {
  const [busy, setBusy] = useState<"wish" | "own" | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const run = async (kind: "wish" | "own") => {
    setBusy(kind);
    try {
      kind === "wish" ? await onWishlist(item) : await onOwn(item);
      setDone(kind === "wish" ? "Wishlisted" : "In your library");
    } catch (e) {
      setDone((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const owned = item.in_library || done === "In your library";
  const wished = item.status === "wishlist" || done === "Wishlisted";

  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-panel">
      <Link to={`/browse/game/${item.game.id}`} className="block">
      <div className="relative m-2 overflow-hidden rounded-xl">
        <GameCover game={item.game} platform={item.game.steam_appid ? "steam" : "other"} className="aspect-[2/3] w-full" />
        {item.discount_percent ? (
          <span className="absolute left-2.5 top-2.5 rounded-full bg-mint px-2 py-0.5 text-xs font-bold text-ink">-{item.discount_percent}%</span>
        ) : null}
        {item.match != null && (
          <span className="absolute right-2.5 top-2.5 rounded-full bg-ink/85 px-2 py-0.5 text-xs font-bold text-amber backdrop-blur">{Math.round(item.match)}%</span>
        )}
      </div>
      <div className="px-3 pb-1">
        <div className="truncate font-semibold" title={item.game.title}>{item.game.title}</div>
        <p className="mt-0.5 truncate text-xs text-fog">
          {[item.game.release_year, item.price].filter(Boolean).join(" · ") || item.game.developer || "\u00a0"}
        </p>
        {item.game.platforms.length > 0 && <div className="mt-2"><PlatformBadges names={item.game.platforms} max={4} /></div>}
        {item.reasons[0] && <p className="mt-1.5 line-clamp-2 text-xs text-fog">{item.reasons[0]}</p>}
      </div>
      </Link>

      <div className="px-3 pb-3.5">
        <div className="mt-3 flex gap-2">
          {owned ? (
            item.entry_id ? (
              <Link to={`/game/${item.entry_id}`} className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-line py-1.5 text-xs text-fog hover:text-snow">
                <Check size={13} />{item.status ? STATUS_LABEL[item.status] : "In library"}
              </Link>
            ) : (
              <span className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-line py-1.5 text-xs text-fog"><Check size={13} />In your library</span>
            )
          ) : (
            <>
              <button onClick={() => run("wish")} disabled={busy !== null || wished}
                className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-semibold transition-colors ${wished ? "bg-field text-amber" : "bg-amber text-ink hover:brightness-110"} disabled:opacity-70`}>
                <Heart size={13} className={wished ? "fill-amber" : ""} />{wished ? "Wishlisted" : busy === "wish" ? "…" : "Wishlist"}
              </button>
              <button onClick={() => run("own")} disabled={busy !== null} title="I already own this"
                className="flex items-center justify-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs text-fog hover:text-snow disabled:opacity-70">
                <Plus size={13} />Own
              </button>
            </>
          )}
        </div>
        {done && done !== "Wishlisted" && done !== "In your library" && <p className="mt-2 text-xs text-coral">{done}</p>}
      </div>
    </div>
  );
}

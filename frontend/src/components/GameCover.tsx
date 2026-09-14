import { useEffect, useState } from "react";
import type { Game } from "../lib/api";
import { coverCandidates } from "../lib/filters";

type Shape = "portrait" | "landscape" | "square";
import { PlatformIcon } from "./Platform";

export default function GameCover({ game, className = "", compact = false, platform }: { game: Game; className?: string; compact?: boolean; platform?: string }) {
  const [idx, setIdx] = useState(0);
  const [shape, setShape] = useState<Shape | null>(null);
  useEffect(() => { setIdx(0); setShape(null); }, [game.cover_url]);

  const urls = game.cover_url ? coverCandidates(game.cover_url) : [];
  const src = urls[idx];

  // No art at all: show the platform's mark rather than a wall of text. The
  // card underneath already carries the title, so this stays a clean tile.
  if (!src) {
    return (
      <div className={`grid place-items-center overflow-hidden bg-gradient-to-b from-line to-ink ${className}`}>
        <PlatformIcon platform={platform ?? "other"} size={compact ? 20 : 44} className="opacity-40" />
      </div>
    );
  }

  const onLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const { naturalWidth: w, naturalHeight: h } = e.currentTarget;
    setShape(h / w > 1.25 ? "portrait" : w / h > 1.25 ? "landscape" : "square");
  };

  // Proper portrait art (and anything we haven't measured yet) fills the frame.
  if (shape === null || shape === "portrait") {
    return <img src={src} alt="" onError={() => setIdx(idx + 1)} onLoad={onLoad} className={`object-cover ${className}`} loading="lazy" />;
  }

  // Wide banners and square logos get composed into a poster instead of being
  // cropped or floated in dead space: the art sits full-width against a blurred
  // wash of itself, with the title set in the room that's left. Some games (new
  // announcements especially) simply have no portrait capsule on Steam.
  return (
    <div className={`relative overflow-hidden ${className}`}>
      <img src={src} alt="" aria-hidden className="absolute inset-0 h-full w-full scale-150 object-cover opacity-50 blur-2xl" />
      <div className="absolute inset-0 bg-gradient-to-b from-ink/20 via-ink/40 to-ink/90" />
      <div className={`relative flex h-full w-full flex-col ${shape === "square" ? "justify-center" : "justify-start"}`}>
        <img
          src={src} alt="" onError={() => setIdx(idx + 1)}
          className={shape === "landscape"
            ? "w-full object-cover shadow-lg shadow-black/40 ring-1 ring-white/10"
            : "mx-auto w-3/4 object-contain drop-shadow-xl"}
          loading="lazy"
        />
        {!compact && (
          <div className="flex flex-1 items-center px-3 py-3">
            <span className="line-clamp-3 text-balance text-center text-base font-extrabold leading-tight tracking-tight text-snow drop-shadow-md sm:text-lg">
              {game.title}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

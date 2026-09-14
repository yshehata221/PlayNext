import GameCover from "./GameCover";
import type { Game } from "../lib/api";

/**
 * Cinematic header: wide key art behind, portrait cover layered over it, and
 * whatever the page wants to put alongside. Falls back to a flat gradient when
 * a game has no hero art, so the layout never depends on the artwork existing.
 */
export default function GameHero({ game, children, platform }: {
  game: Game;
  children: React.ReactNode;
  platform?: string;
}) {
  const backdrop = game.hero_url ?? game.screenshots[0] ?? null;

  return (
    <section className="relative overflow-hidden rounded-3xl border border-line bg-panel">
      {backdrop ? (
        <>
          <img src={backdrop} alt="" aria-hidden className="absolute inset-0 h-full w-full object-cover object-top opacity-45" />
          <div className="absolute inset-0 bg-gradient-to-t from-ink via-ink/85 to-ink/40" />
        </>
      ) : (
        <div className="absolute inset-0 bg-gradient-to-br from-field via-panel to-ink" />
      )}

      <div className="relative flex flex-col gap-7 p-6 sm:flex-row sm:p-9">
        <div className="w-40 shrink-0 sm:w-52">
          <div className="overflow-hidden rounded-2xl shadow-2xl shadow-black/60 ring-1 ring-white/10">
            <GameCover game={game} platform={platform} className="aspect-[2/3] w-full" />
          </div>
        </div>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </section>
  );
}

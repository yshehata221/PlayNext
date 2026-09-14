import { Play, X } from "lucide-react";
import { useState } from "react";
import type { Game } from "../lib/api";

/**
 * Trailers and screenshots for a game. Steam hosts MP4s we can play directly;
 * IGDB gives YouTube ids, which need an embed. A YouTube iframe is only mounted
 * once the user clicks a thumbnail, so the page doesn't load a tracker-heavy
 * embed (or autoplay anything) just by being opened.
 */
export default function Media({ game }: { game: Game }) {
  const videos = game.videos ?? [];
  const shots = game.screenshots ?? [];
  const [tab, setTab] = useState<"trailers" | "screenshots">(videos.length ? "trailers" : "screenshots");
  const [playing, setPlaying] = useState<number | null>(null);
  const [lightbox, setLightbox] = useState<string | null>(null);

  if (videos.length === 0 && shots.length === 0) return null;

  const seg = (on: boolean) =>
    `rounded-full px-3.5 py-1 text-xs font-semibold transition-colors ${on ? "bg-amber text-ink" : "text-fog hover:text-snow"}`;

  const active = videos[playing ?? -1];

  return (
    <section className="rounded-3xl border border-line bg-panel p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">Media</h2>
        <div className="flex gap-1 rounded-full bg-field p-1">
          {videos.length > 0 && <button className={seg(tab === "trailers")} onClick={() => setTab("trailers")}>Trailers {videos.length}</button>}
          {shots.length > 0 && <button className={seg(tab === "screenshots")} onClick={() => setTab("screenshots")}>Screenshots {shots.length}</button>}
        </div>
      </div>

      {tab === "trailers" && (
        <div className="mt-4">
          {active ? (
            <div className="overflow-hidden rounded-2xl bg-ink ring-1 ring-white/10">
              {active.kind === "mp4" ? (
                <video src={active.src} poster={active.thumb ?? undefined} controls autoPlay className="aspect-video w-full" />
              ) : (
                <iframe
                  src={`https://www.youtube-nocookie.com/embed/${active.src}?autoplay=1&rel=0`}
                  title={active.title} allow="autoplay; encrypted-media; fullscreen" allowFullScreen
                  className="aspect-video w-full" />
              )}
              <div className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
                <span className="truncate text-fog">{active.title}</span>
                <button onClick={() => setPlaying(null)} className="text-fog hover:text-snow">close</button>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {videos.map((v, i) => (
                <button key={v.src} onClick={() => setPlaying(i)} className="group relative overflow-hidden rounded-xl ring-1 ring-white/5">
                  {v.thumb ? (
                    <img src={v.thumb} alt="" loading="lazy" className="aspect-video w-full object-cover transition-transform group-hover:scale-105" />
                  ) : (
                    <div className="aspect-video w-full bg-field" />
                  )}
                  <span className="absolute inset-0 grid place-items-center bg-ink/40">
                    <span className="grid h-11 w-11 place-items-center rounded-full bg-amber text-ink"><Play size={18} className="ml-0.5 fill-ink" /></span>
                  </span>
                  <span className="absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-ink/90 to-transparent px-2.5 pb-2 pt-6 text-left text-xs">{v.title}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "screenshots" && (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {shots.slice(0, 9).map((url) => (
            <button key={url} onClick={() => setLightbox(url)} className="overflow-hidden rounded-xl ring-1 ring-white/5">
              <img src={url} alt="" loading="lazy" className="aspect-video w-full object-cover transition-transform hover:scale-105" />
            </button>
          ))}
        </div>
      )}

      {lightbox && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-ink/90 p-6 backdrop-blur" onClick={() => setLightbox(null)}>
          <button aria-label="Close" className="absolute right-5 top-5 text-fog hover:text-snow"><X size={22} /></button>
          <img src={lightbox} alt="" className="max-h-full max-w-full rounded-2xl ring-1 ring-white/10" />
        </div>
      )}
    </section>
  );
}

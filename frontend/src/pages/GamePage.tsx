import { ArrowLeft, Check, Clock, Dices, Eye, EyeOff, NotebookPen, Play, Star, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import GameCover from "../components/GameCover";
import GameHero from "../components/GameHero";
import Media from "../components/Media";
import { PlatformBadges, PlatformLabel, PlatformPicker, launchersFor } from "../components/Platform";
import { STATUS_LABEL } from "../components/StatusChip";
import { api, type BrowseItem, type Entry, type Status } from "../lib/api";
import { useAuth } from "../lib/auth";

const STATUSES: Status[] = ["backlog", "playing", "completed", "abandoned"];

export default function GamePage() {
  const { id } = useParams();
  const { token } = useAuth();
  const nav = useNavigate();
  const [entry, setEntry] = useState<Entry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [spoiler, setSpoiler] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [hours, setHours] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const [editPlatform, setEditPlatform] = useState(false);
  const [similar, setSimilar] = useState<BrowseItem[]>([]);

  useEffect(() => {
    api.entry(token!, Number(id))
      .then((e) => {
        setEntry(e);
        const raw = e.review ?? "";
        setSpoiler(raw.startsWith("[spoiler]"));
        setNotes(raw.replace(/^\[spoiler]\s*/, ""));
        setHours(String(e.hours_played));
        api.similarGames(token!, e.game.id, 6).then(setSimilar).catch(() => {});
      })
      .catch((e) => setError(e.message));
  }, [id, token]);

  const patch = async (changes: Parameters<typeof api.updateEntry>[2], label: string) => {
    if (!entry) return;
    const updated = await api.updateEntry(token!, entry.id, changes);
    setEntry(updated);
    setSaved(label);
    setTimeout(() => setSaved(null), 1600);
  };

  const saveNotes = (text: string, isSpoiler: boolean) =>
    patch({ review: text ? (isSpoiler ? `[spoiler] ${text}` : text) : null }, "Notes saved");

  if (error) return <p className="text-coral">{error}</p>;
  if (!entry) return <p className="text-fog">Loading…</p>;

  const g = entry.game;
  const progress = g.hours_main && entry.hours_played > 0
    ? Math.min(100, Math.round((100 * entry.hours_played) / g.hours_main)) : null;

  // the primary action depends on where you are with the game
  const primary = {
    backlog: { label: "Start playing", icon: <Play size={16} />, next: "playing" as Status },
    playing: { label: "Mark completed", icon: <Check size={16} />, next: "completed" as Status },
    completed: { label: "Play again", icon: <Play size={16} />, next: "playing" as Status },
    abandoned: { label: "Give it another go", icon: <Play size={16} />, next: "playing" as Status },
    wishlist: { label: "I own it now", icon: <Check size={16} />, next: "backlog" as Status },
  }[entry.status];

  return (
    <div className="mx-auto max-w-6xl">
      <Link to="/library" className="flex w-fit items-center gap-2 text-sm text-fog hover:text-snow"><ArrowLeft size={14} />Back to library</Link>

      <div className="mt-4">
        <GameHero game={g} platform={entry.platform}>
          <h1 className="text-3xl font-extrabold leading-tight tracking-tight sm:text-5xl">{g.title}</h1>
          <p className="mt-2 text-fog">{[g.developer, g.release_year].filter(Boolean).join(" · ")}</p>

          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
            {entry.rating != null && (
              <span className="flex items-center gap-1.5 font-semibold text-amber"><Star size={15} className="fill-amber" />{entry.rating}/10</span>
            )}
            <span className="flex items-center gap-1.5 text-fog"><Clock size={15} />{Math.round(entry.hours_played)}h played</span>
            {entry.status === "playing" && (
              <span className="flex items-center gap-1.5 font-semibold text-mint"><span className="h-2 w-2 rounded-full bg-mint" />Currently playing</span>
            )}
          </div>

          {g.genres.length > 0 && (
            <p className="mt-3 text-sm text-fog">{[...g.genres, ...g.themes].slice(0, 5).join(" · ")}</p>
          )}
          {g.summary && <p className="mt-4 max-w-2xl text-sm leading-relaxed text-fog line-clamp-3">{g.summary}</p>}

          <div className="mt-6 flex flex-wrap gap-2">
            <button onClick={() => patch({ status: primary.next }, "Status saved")}
              className="flex items-center gap-2 rounded-lg bg-amber px-5 py-2.5 text-sm font-semibold text-ink hover:brightness-110">
              {primary.icon}{primary.label}
            </button>
            <Link to="/" className="flex items-center gap-2 rounded-lg border border-line bg-ink/50 px-4 py-2.5 text-sm text-fog backdrop-blur hover:text-snow">
              <Dices size={16} />Pick something else
            </Link>
          </div>

          {/* the status control, as a proper segmented switch */}
          <div className="mt-6">
            <p className="text-xs font-semibold uppercase tracking-widest text-fog">Your status</p>
            <div className="mt-2 inline-flex flex-wrap gap-1 rounded-xl bg-ink/70 p-1 backdrop-blur">
              {STATUSES.map((st) => (
                <button key={st} onClick={() => patch({ status: st }, "Status saved")}
                  className={`rounded-lg px-4 py-1.5 text-sm font-semibold transition-colors ${entry.status === st ? "bg-amber text-ink" : "text-fog hover:text-snow"}`}>
                  {STATUS_LABEL[st]}
                </button>
              ))}
            </div>
          </div>
        </GameHero>
      </div>

      {/* progress and details, filling the width the old layout wasted */}
      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <section className="rounded-3xl border border-line bg-panel p-7">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">Your progress</h2>

            <div className="mt-5 flex flex-wrap items-end gap-10">
              <div>
                <div className="flex items-baseline gap-2">
                  <input type="number" min={0} step={0.5} value={hours} onChange={(e) => setHours(e.target.value)}
                    onBlur={() => Number(hours) !== entry.hours_played && patch({ hours_played: Number(hours) }, "Hours saved")}
                    aria-label="Hours played"
                    className="w-24 rounded-lg border border-line bg-field px-3 py-2 text-2xl font-extrabold" />
                  <span className="text-fog">hours</span>
                </div>
                {g.hours_main && <p className="mt-2 text-xs text-fog">{g.hours_main}h to beat the main story</p>}
              </div>

              {progress != null && (
                <div className="min-w-[180px] flex-1">
                  <div className="flex justify-between text-xs text-fog"><span>Progress</span><span>{progress}%</span></div>
                  <div className="mt-1.5 h-2.5 rounded-full bg-field">
                    <div className="h-2.5 rounded-full bg-amber transition-[width] duration-500" style={{ width: `${progress}%` }} />
                  </div>
                </div>
              )}
            </div>

            <div className="mt-8">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-sm font-semibold">How much did you enjoy it?</h3>
                <span className="text-sm text-fog">{entry.rating != null ? `${entry.rating}/10` : "Not rated"}</span>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <span className="text-xs text-fog">1</span>
                <input type="range" min={0} max={10} step={1} value={entry.rating ?? 0}
                  onChange={(e) => patch({ rating: Number(e.target.value) || null }, "Rating saved")}
                  aria-label="Your rating"
                  className="h-2 flex-1 cursor-pointer appearance-none rounded-full bg-field accent-amber
                             [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:appearance-none
                             [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-amber
                             [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-black/40" />
                <span className="text-xs text-fog">10</span>
              </div>
              <div className="mt-2 flex gap-0.5" aria-hidden>
                {Array.from({ length: 10 }, (_, i) => (
                  <Star key={i} size={14} className={entry.rating != null && i < entry.rating ? "fill-amber text-amber" : "text-line"} />
                ))}
              </div>
              {entry.rating != null && (
                <button onClick={() => patch({ rating: null }, "Rating cleared")} className="mt-2 text-xs text-fog underline hover:text-snow">clear rating</button>
              )}
            </div>
          </section>

          <section className="rounded-3xl border border-line bg-panel p-7">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-fog"><NotebookPen size={14} />Your thoughts</h2>
              <button onClick={() => { setSpoiler(!spoiler); saveNotes(notes, !spoiler); }}
                className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${spoiler ? "bg-coral/15 text-coral" : "text-fog hover:text-snow"}`}>
                {spoiler ? <EyeOff size={13} /> : <Eye size={13} />}{spoiler ? "Marked as spoilers" : "Mark as spoilers"}
              </button>
            </div>
            {spoiler && notes && !revealed ? (
              <button onClick={() => setRevealed(true)} className="mt-4 w-full rounded-2xl border border-dashed border-coral/40 bg-field py-10 text-sm text-coral">
                Spoilers hidden — click to reveal
              </button>
            ) : (
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={5}
                onBlur={() => notes !== (entry.review ?? "").replace(/^\[spoiler]\s*/, "") && saveNotes(notes, spoiler)}
                placeholder="Write down what you think, where you're up to, or what you want to remember…"
                className="mt-4 w-full rounded-2xl border border-line bg-field px-4 py-3.5 leading-relaxed placeholder:text-fog/60" />
            )}
          </section>

          <Media game={g} />
        </div>

        <aside className="space-y-6">
          <section className="rounded-3xl border border-line bg-panel p-6">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">Game details</h2>
            <dl className="mt-4 space-y-4 text-sm">
              <Detail label="Developer" value={g.developer ?? "Unknown"} />
              <Detail label="Released" value={g.release_year ? String(g.release_year) : "Unknown"} />
              {g.critic_score != null && <Detail label="Critic score" value={`${Math.round(g.critic_score)}/100`} />}
              {g.hours_main != null && <Detail label="Length" value={`${g.hours_main}h main · ${g.hours_complete ?? "?"}h completionist`} />}
              <div>
                <dt className="text-xs text-fog">Platforms available on</dt>
                <dd className="mt-1.5">
                  {g.platforms.length > 0
                    ? <PlatformBadges names={g.platforms} max={10} size={15} ownedOn={entry.platform} />
                    : <span className="text-fog">Not known yet</span>}
                </dd>
              </div>
              {g.genres.length > 0 && <Detail label="Genres" value={g.genres.join(" · ")} />}
              <div>
                <dt className="text-xs text-fog">You own it on</dt>
                <dd className="mt-1.5 flex flex-wrap items-center gap-2">
                  <PlatformLabel platform={entry.platform} size={14} />
                  <button onClick={() => setEditPlatform(!editPlatform)} className="text-xs text-fog underline hover:text-snow">
                    {editPlatform ? "cancel" : "change"}
                  </button>
                </dd>
                {editPlatform && (
                  <dd className="mt-2">
                    <PlatformPicker value={entry.platform} allow={g.platforms.length ? launchersFor(g.platforms) : undefined}
                      onChange={(p) => { patch({ platform: p }, "Saved"); setEditPlatform(false); }} />
                  </dd>
                )}
              </div>
            </dl>
          </section>

          {g.requirements && (g.requirements.minimum || g.requirements.recommended) && (
            <section className="rounded-3xl border border-line bg-panel p-6">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">PC requirements</h2>
              <div className="mt-4 space-y-4">
                {(["minimum", "recommended"] as const).map((key) => g.requirements?.[key] && (
                  <div key={key}>
                    <h3 className="text-sm font-semibold capitalize">{key}</h3>
                    <pre className="mt-1.5 whitespace-pre-wrap font-sans text-xs leading-relaxed text-fog">{g.requirements[key]}</pre>
                  </div>
                ))}
              </div>
            </section>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button onClick={async () => { await api.removeEntry(token!, entry.id); nav("/library"); }}
              className="flex items-center gap-2 rounded-full bg-coral/15 px-4 py-2 text-sm font-semibold text-coral transition-colors hover:bg-coral hover:text-ink">
              <Trash2 size={15} />Remove from library
            </button>
            {saved && <span className="text-sm text-mint">{saved}</span>}
          </div>
        </aside>
      </div>

      {similar.length > 0 && (
        <section className="mt-8">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-fog">You might also like</h2>
          <p className="mt-1 text-sm text-fog">Closest matches to {g.title} in the catalogue.</p>
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

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-fog">{label}</dt>
      <dd className="mt-0.5">{value}</dd>
    </div>
  );
}

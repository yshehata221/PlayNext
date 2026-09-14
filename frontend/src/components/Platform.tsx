import { Gamepad2, Monitor } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { siAndroid, siApple, siBattledotnet, siEa, siEpicgames, siGogdotcom, siLinux, siNintendoswitch, siPlaystation, siSteam, siUbisoft, type SimpleIcon } from "simple-icons";

// Brand marks come from the simple-icons package. Windows and Xbox aren't in it
// (Microsoft doesn't license them for redistribution), so those get a drawn
// monitor / controller in the right brand colour.
type Def = { label: string; icon?: SimpleIcon; color: string; fallback?: typeof Gamepad2 };

// launchers a game can be owned on (library platform field)
export const PLATFORMS: Record<string, Def> = {
  steam: { label: "Steam", icon: siSteam, color: "#c7d5e0" },
  xbox: { label: "Xbox", color: "#107C10", fallback: Gamepad2 },
  playstation: { label: "PlayStation", icon: siPlaystation, color: "#2E6DB4" },
  switch: { label: "Nintendo Switch", icon: siNintendoswitch, color: "#E60012" },
  epic: { label: "Epic Games", icon: siEpicgames, color: "#e8eef1" },
  gog: { label: "GOG", icon: siGogdotcom, color: "#B44FCB" },
  ubisoft: { label: "Ubisoft", icon: siUbisoft, color: "#e8eef1" },
  ea: { label: "EA", icon: siEa, color: "#FF4747" },
  battlenet: { label: "Battle.net", icon: siBattledotnet, color: "#4381C3" },
  other: { label: "Other", color: "#8FA3AE", fallback: Monitor },
};
export const PLATFORM_KEYS = Object.keys(PLATFORMS);

// hardware a game is released on (IGDB platform names) -> which mark to draw
const HARDWARE: { match: RegExp; def: Def; short: string }[] = [
  { match: /^PC \(Microsoft Windows\)$|^Windows/i, def: { label: "Windows", color: "#4CC2FF", fallback: Monitor }, short: "PC" },
  { match: /PlayStation 5/i, def: { label: "PlayStation 5", icon: siPlaystation, color: "#2E6DB4" }, short: "PS5" },
  { match: /PlayStation 4/i, def: { label: "PlayStation 4", icon: siPlaystation, color: "#2E6DB4" }, short: "PS4" },
  { match: /PlayStation 3/i, def: { label: "PlayStation 3", icon: siPlaystation, color: "#2E6DB4" }, short: "PS3" },
  { match: /PlayStation/i, def: { label: "PlayStation", icon: siPlaystation, color: "#2E6DB4" }, short: "PS" },
  { match: /Xbox Series/i, def: { label: "Xbox Series X|S", color: "#107C10", fallback: Gamepad2 }, short: "Series X|S" },
  { match: /Xbox One/i, def: { label: "Xbox One", color: "#107C10", fallback: Gamepad2 }, short: "Xbox One" },
  { match: /Xbox 360/i, def: { label: "Xbox 360", color: "#107C10", fallback: Gamepad2 }, short: "360" },
  { match: /Xbox/i, def: { label: "Xbox", color: "#107C10", fallback: Gamepad2 }, short: "Xbox" },
  { match: /Switch 2/i, def: { label: "Nintendo Switch 2", icon: siNintendoswitch, color: "#E60012" }, short: "Switch 2" },
  { match: /Switch|Wii|Nintendo (64|3DS|DS|GameCube)/i, def: { label: "Nintendo", icon: siNintendoswitch, color: "#E60012" }, short: "Nintendo" },
  { match: /^Mac|macOS|OS X/i, def: { label: "Mac", icon: siApple, color: "#E8EEF1" }, short: "Mac" },
  { match: /^iOS|iPad|iPhone/i, def: { label: "iOS", icon: siApple, color: "#E8EEF1" }, short: "iOS" },
  { match: /Linux/i, def: { label: "Linux", icon: siLinux, color: "#FCC624" }, short: "Linux" },
  { match: /Android/i, def: { label: "Android", icon: siAndroid, color: "#34A853" }, short: "Android" },
];

function hardwareDef(name: string): { def: Def; short: string } {
  const hit = HARDWARE.find((h) => h.match.test(name));
  return hit ? { def: hit.def, short: hit.short } : { def: { label: name, color: "#8FA3AE", fallback: Gamepad2 }, short: name };
}

function Icon({ def, size, className = "" }: { def: Def; size: number; className?: string }) {
  if (def.icon) {
    return (
      <svg role="img" aria-label={def.label} width={size} height={size} viewBox="0 0 24 24" className={className} style={{ color: def.color }}>
        <path d={def.icon.path} fill="currentColor" />
      </svg>
    );
  }
  const Fallback = def.fallback ?? Monitor;
  return <Fallback size={size} className={className} style={{ color: def.color }} aria-label={def.label} />;
}

export function PlatformIcon({ platform, size = 16, className = "" }: { platform: string; size?: number; className?: string }) {
  return <Icon def={PLATFORMS[platform] ?? PLATFORMS.other} size={size} className={className} />;
}

export function PlatformLabel({ platform, size = 14 }: { platform: string; size?: number }) {
  const def = PLATFORMS[platform] ?? PLATFORMS.other;
  return <span className="inline-flex items-center gap-1.5"><Icon def={def} size={size} />{def.label}</span>;
}

// Hardware icon for an IGDB platform name, tinted with the brand colour
export function HardwareIcon({ name, size = 14 }: { name: string; size?: number }) {
  const { def } = hardwareDef(name);
  return <Icon def={def} size={size} />;
}

// which launcher key corresponds to which hardware label, so we can mark the
// badge for the platform the user actually owns the game on
const OWNED_MATCH: Record<string, RegExp> = {
  steam: /^(Windows|Mac|Linux)$/,
  epic: /^(Windows|Mac)$/,
  gog: /^(Windows|Mac|Linux)$/,
  ubisoft: /^Windows$/,
  ea: /^Windows$/,
  battlenet: /^(Windows|Mac)$/,
  xbox: /^Xbox/,
  playstation: /^PlayStation/,
  switch: /^Nintendo/,
};

/** Every platform a game is released on, deduped so "PS4 + PS5" doesn't repeat one mark. */
export function PlatformBadges({ names, max = 6, size = 15, ownedOn }: { names: string[]; max?: number; size?: number; ownedOn?: string }) {
  const seen = new Map<string, { def: Def; short: string }>();
  for (const n of names) {
    const entry = hardwareDef(n);
    if (!seen.has(entry.def.label)) seen.set(entry.def.label, entry);
  }
  const list = [...seen.values()];
  if (list.length === 0) return null;
  const ownedPattern = ownedOn ? OWNED_MATCH[ownedOn] : undefined;

  return (
    <span className="flex flex-wrap items-center gap-1.5">
      {list.slice(0, max).map(({ def, short }) => {
        const owned = ownedPattern?.test(def.label) ?? false;
        return (
          <span key={def.label} title={owned ? `${def.label} — you own this here` : def.label}
            className={`flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium ${owned ? "ring-1 ring-amber/70 bg-amber/10" : "bg-ink/70"}`}
            style={{ color: def.color }}>
            <Icon def={def} size={size - 3} />{short}
            {owned && <span className="ml-0.5 font-bold text-amber">OWNED</span>}
          </span>
        );
      })}
      {list.length > max && <span className="text-[11px] text-fog">+{list.length - max}</span>}
    </span>
  );
}

// A rounded dropdown with icons, in place of the native <select>
function Dropdown({ value, options, onChange, renderIcon, placeholder }: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
  renderIcon: (v: string) => React.ReactNode;
  placeholder: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const current = options.find((o) => o.value === value);

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen(!open)} aria-haspopup="listbox" aria-expanded={open}
        className="flex h-full items-center gap-2 rounded-full border border-line bg-field px-3.5 py-1.5 text-sm hover:border-fog/50">
        {renderIcon(value)}
        <span>{current?.label ?? placeholder}</span>
        <svg width="12" height="12" viewBox="0 0 12 12" className={`ml-1 text-fog transition-transform ${open ? "rotate-180" : ""}`} aria-hidden><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      {open && (
        <ul role="listbox" className="absolute left-0 z-30 mt-2 max-h-80 w-56 overflow-y-auto rounded-2xl border border-line bg-panel p-1.5 shadow-2xl shadow-black/60">
          {options.map((o) => (
            <li key={o.value} role="option" aria-selected={o.value === value}>
              <button type="button" onClick={() => { onChange(o.value); setOpen(false); }}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition-colors ${o.value === value ? "bg-amber font-semibold text-ink" : "hover:bg-field"}`}>
                {renderIcon(o.value)}{o.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// A PC release tells you nothing about *which* PC store sells a game, so we
// don't try to infer that. We only narrow the list where hardware genuinely
// rules a store out: a console-only game can't be owned on Steam, and a
// PC-only game can't be owned on PlayStation.
const CONSOLE_KEYS: Record<string, RegExp> = {
  playstation: /PlayStation/i,
  xbox: /Xbox/i,
  switch: /Nintendo|Switch|Wii/i,
};
const PC_KEYS = ["steam", "epic", "gog", "ubisoft", "ea", "battlenet"];
const isPcPlatform = (name: string) => /^(PC \(Microsoft Windows\)|Windows|Mac|Linux)$/i.test(name);

export function launchersFor(platforms: string[]): string[] {
  if (platforms.length === 0) return PLATFORM_KEYS;
  const keys: string[] = [];
  if (platforms.some(isPcPlatform)) keys.push(...PC_KEYS);
  for (const [key, match] of Object.entries(CONSOLE_KEYS)) {
    if (platforms.some((p) => match.test(p))) keys.push(key);
  }
  const ordered = PLATFORM_KEYS.filter((k) => keys.includes(k));
  return ordered.length ? [...ordered, "other"] : PLATFORM_KEYS;
}

export function PlatformPicker({ value, onChange, allow }: {
  value: string;
  onChange: (p: string) => void;
  /** restrict the list, e.g. to the platforms a game is actually released on */
  allow?: string[];
}) {
  // whatever is currently set must stay selectable, even if it's off the list
  const keys = allow ? Array.from(new Set([...allow, value])) : PLATFORM_KEYS;
  return (
    <Dropdown
      value={value} onChange={onChange} placeholder="Platform"
      options={keys.map((k) => ({ value: k, label: PLATFORMS[k]?.label ?? k }))}
      renderIcon={(v) => <PlatformIcon platform={v} size={16} />}
    />
  );
}

/** Filter dropdown over IGDB platform names, with the matching hardware mark. */
export function HardwareFilter({ value, options, onChange }: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <Dropdown
      value={value} onChange={onChange} placeholder="Any platform"
      options={[{ value: "", label: "Any platform" }, ...options]}
      renderIcon={(v) => (v ? <HardwareIcon name={v} size={15} /> : <Monitor size={15} className="text-fog" />)}
    />
  );
}

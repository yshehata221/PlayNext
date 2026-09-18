import { Info } from "lucide-react";
import { useState } from "react";

/**
 * Shown only in the static demo build. Being upfront that this runs on a
 * snapshot is better than letting someone wonder why an edit vanished on
 * refresh, and it points at the parts that need the real backend.
 */
export default function DemoBanner() {
  const [open, setOpen] = useState(true);
  if (!open) return null;

  return (
    <div className="border-b border-amber/20 bg-amber/10 px-6 py-2.5 text-sm">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3">
        <Info size={16} className="text-amber" />
        <span className="text-snow/90">
          You're in a live demo — real data from a sample account, running entirely in your browser.
          Rate things, change statuses and explore; changes reset when you refresh.
        </span>
        <a href="https://github.com/yshehata221/playnext" target="_blank" rel="noreferrer"
          className="font-semibold text-amber underline">Source</a>
        <button onClick={() => setOpen(false)} className="ml-auto text-fog hover:text-snow">Dismiss</button>
      </div>
    </div>
  );
}

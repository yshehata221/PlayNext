import type { Status } from "../lib/api";

// one colour per state; the only place colour carries meaning outside the accent
export const STATUS_STYLE: Record<Status, string> = {
  backlog: "bg-ink/80 text-fog",
  playing: "bg-mint text-ink",
  completed: "bg-snow text-ink",
  abandoned: "bg-coral text-ink",
  wishlist: "bg-amber text-ink",
};

export const STATUSES: Status[] = ["backlog", "playing", "completed", "abandoned", "wishlist"];
// wishlisted games live on their own page, so the library only filters these
export const LIBRARY_STATUSES: Status[] = ["backlog", "playing", "completed", "abandoned"];

// Labels are display-only: the API still stores "abandoned".
export const STATUS_LABEL: Record<Status, string> = {
  backlog: "Backlog", playing: "Playing", completed: "Completed", abandoned: "Dropped", wishlist: "Wishlist",
};

const DOT: Record<Status, string> = { backlog: "bg-fog", playing: "bg-mint", completed: "bg-snow", abandoned: "bg-coral", wishlist: "bg-amber" };

export default function StatusChip({ status, className = "", dot = false }: { status: Status; className?: string; dot?: boolean }) {
  if (dot) {
    return (
      <span className={`flex items-center gap-1.5 rounded-full bg-ink/80 px-2.5 py-1 text-xs font-semibold text-snow backdrop-blur ${className}`}>
        <span className={`h-1.5 w-1.5 rounded-full ${DOT[status]}`} />{STATUS_LABEL[status]}
      </span>
    );
  }
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_STYLE[status]} ${className}`}>{STATUS_LABEL[status]}</span>;
}

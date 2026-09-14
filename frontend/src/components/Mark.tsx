// the PlayNext mark: a play triangle in the accent colour
export default function Mark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <path d="M8 4.5c0-1.6 1.8-2.6 3.2-1.8l17 11.5c1.3.9 1.3 2.7 0 3.6l-17 11.5C9.8 30.1 8 29.1 8 27.5z" fill="#F2B441" />
    </svg>
  );
}

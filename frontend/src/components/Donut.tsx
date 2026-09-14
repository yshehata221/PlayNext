// A donut chart from plain SVG arcs: no chart library, and it degrades to a
// single ring when there's only one non-zero slice.
export interface Slice { label: string; value: number; color: string }

export default function Donut({ slices, size = 170, thickness = 22, centreTop, centreSub }: {
  slices: Slice[];
  size?: number;
  thickness?: number;
  centreTop?: string;
  centreSub?: string;
}) {
  const total = slices.reduce((a, s) => a + s.value, 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  let offset = 0;

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label={slices.map((s) => `${s.label}: ${s.value}`).join(", ")}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#14242F" strokeWidth={thickness} />
      {total > 0 && slices.filter((s) => s.value > 0).map((s) => {
        const len = (s.value / total) * c;
        const dash = <circle key={s.label} cx={size / 2} cy={size / 2} r={r} fill="none" stroke={s.color}
          strokeWidth={thickness} strokeLinecap="butt"
          strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`} />;
        offset += len;
        return dash;
      })}
      {centreTop && (
        <text x={size / 2} y={size / 2 - 2} textAnchor="middle" fill="#E8EEF1" fontSize={size * 0.19} fontWeight="800">{centreTop}</text>
      )}
      {centreSub && (
        <text x={size / 2} y={size / 2 + size * 0.14} textAnchor="middle" fill="#8FA3AE" fontSize={size * 0.075}>{centreSub}</text>
      )}
    </svg>
  );
}

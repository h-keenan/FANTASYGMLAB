import { ToneBadge } from "@/components/ToneBadge";
import { RANGE_CAPTION, formatPoints, leanLabel, type RangeDisplayRow } from "@/lib/startSitRange";

const GRID = "grid grid-cols-[minmax(0,1fr)_2.75rem_2.75rem_2.75rem] gap-x-2 items-baseline";
const HEAD = { color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" } as const;

/**
 * Projected / Low / High for the compared players side by side, with the
 * win-probability lean (Ceiling play / Floor play) and its plain-English why
 * when the matchup stance calls for one. Low and High are a typical-week range,
 * so the caption says exactly that. Renders nothing when no side has a real
 * range. Mirrors mobile/src/components/RangeCompare.tsx.
 */
export function RangeCompare({
  rows,
  lean,
}: {
  rows: RangeDisplayRow[];
  lean: { kind: "ceiling" | "floor"; why: string } | null;
}) {
  if (rows.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5" data-testid="range-compare">
      <div className={`${GRID} text-xs uppercase font-extrabold`} style={HEAD} aria-hidden="true">
        <span />
        <span className="text-right">Proj</span>
        <span className="text-right">Low</span>
        <span className="text-right">High</span>
      </div>
      {rows.map((row) => (
        <div
          key={row.key}
          className={`${GRID} text-sm pl-2`}
          style={{ borderLeft: `var(--border-width-semantic) solid ${row.favored ? "var(--color-accent)" : "transparent"}` }}
        >
          <span className="min-w-0 break-words">
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {row.label}{" "}
            </span>
            <span className="font-bold">{row.name || "Player"}</span>
          </span>
          <span className="text-right tabular-nums font-bold" aria-label={`Projected ${formatPoints(row.range.projected)}`}>
            {formatPoints(row.range.projected)}
          </span>
          <span className="text-right tabular-nums" aria-label={`Low ${formatPoints(row.range.low)}`}>
            {formatPoints(row.range.low)}
          </span>
          <span className="text-right tabular-nums" aria-label={`High ${formatPoints(row.range.high)}`}>
            {formatPoints(row.range.high)}
          </span>
        </div>
      ))}
      {lean ? (
        <div className="flex flex-col gap-1 pt-0.5" data-testid="range-lean">
          <span className="self-start">
            <ToneBadge label={leanLabel(lean.kind)} color="var(--color-accent)" />
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {lean.why}
          </span>
        </div>
      ) : null}
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {RANGE_CAPTION}
      </span>
    </div>
  );
}

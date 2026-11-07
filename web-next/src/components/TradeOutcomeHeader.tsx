import type { ReactNode } from "react";

/**
 * Shared header pieces for the Trade History and Community trade cards:
 * a tinted swap-arrows glyph tile (or a letter pair for anonymous teams)
 * and a centered net-edge bar for the since-the-trade value trend.
 */

export function TradeSwapGlyph({ color, size = 36 }: { color: string; size?: number }) {
  return (
    <span
      className="inline-flex items-center justify-center shrink-0"
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        color,
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${color} 35%, transparent)`,
      }}
      aria-hidden="true"
    >
      <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 5.5h9.5M10 3l2.5 2.5L10 8M13 10.5H3.5M6 8l-2.5 2.5L6 13" />
      </svg>
    </span>
  );
}

/** Two small lettered circles ("A" / "B") for the anonymous community teams. */
export function AnonymousTeamPair({ color }: { color: string }) {
  const dot = (letter: string, offset: boolean) => (
    <span
      className="inline-flex items-center justify-center text-xs font-extrabold"
      style={{
        width: 28,
        height: 28,
        borderRadius: "50%",
        marginLeft: offset ? -8 : 0,
        color,
        background: `color-mix(in srgb, ${color} 18%, var(--color-surface-raised))`,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${color} 45%, transparent)`,
      }}
    >
      {letter}
    </span>
  );
  return (
    <span className="inline-flex items-center shrink-0" aria-hidden="true">
      {dot("A", false)}
      {dot("B", true)}
    </span>
  );
}

/** Centered bar: fills right (success) for a positive net %, left (danger) for negative. */
export function NetEdgeBar({ netPct, label }: { netPct: number; label?: ReactNode }) {
  const clamped = Math.max(-50, Math.min(50, netPct));
  const color = netPct > 0 ? "var(--color-success)" : netPct < 0 ? "var(--color-danger)" : "var(--color-text-muted)";
  return (
    <div className="flex flex-col gap-1">
      <div
        role="img"
        aria-label={`Value trend edge ${netPct > 0 ? "+" : ""}${netPct.toFixed(0)} percent`}
        className="relative w-full"
        style={{ height: 6, borderRadius: "var(--radius-pill)", background: "var(--color-surface-muted)" }}
      >
        <span
          aria-hidden="true"
          className="absolute top-0 bottom-0"
          style={{ left: "50%", width: 2, background: "var(--color-border-strong)", transform: "translateX(-1px)" }}
        />
        <span
          aria-hidden="true"
          className="absolute top-0 bottom-0"
          style={{
            background: color,
            borderRadius: "var(--radius-pill)",
            width: `${Math.abs(clamped)}%`,
            left: clamped >= 0 ? "50%" : `${50 - Math.abs(clamped)}%`,
          }}
        />
      </div>
      {label ? (
        <div className="flex justify-between text-xs" style={{ color: "var(--color-text-muted)" }}>
          {label}
        </div>
      ) : null}
    </div>
  );
}

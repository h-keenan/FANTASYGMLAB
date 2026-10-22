/**
 * Tinted verdict box (label + optional detail line) under a trade card —
 * extracted from identical inline copies in TradeHistoryContent and
 * CommunityTradesContent. `color` is the verdict's semantic tone token
 * (e.g. from verdictToneColorVar); the box border and fill are fixed
 * 35% / 8% mixes of it.
 */
export function VerdictCallout({ color, label, detail }: { color: string; label?: string | null; detail?: string | null }) {
  return (
    <div
      className="flex flex-col gap-0.5 px-3 py-2"
      style={{
        border: `1px solid color-mix(in srgb, ${color} 35%, transparent)`,
        background: `color-mix(in srgb, ${color} 8%, transparent)`,
      }}
    >
      <span className="text-sm font-bold" style={{ color }}>
        {label}
      </span>
      {detail ? (
        <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {detail}
        </span>
      ) : null}
    </div>
  );
}

import { SnapshotTileGlyph, type SnapshotGlyphName } from "@/components/SnapshotTileGlyph";

function formatRank(rank: number | null, tied: boolean): string {
  if (rank === null || rank === undefined) return "—";
  return tied ? `T-${rank}` : `#${rank}`;
}

export function SnapshotTile({
  label,
  value,
  tone = "neutral",
  note,
  glyph,
}: {
  label: string;
  value: string;
  // "premium" (Revision 14, Draft Center) is the gold highlight for a #1
  // league rank — same --color-premium lane the Teams screen's power-rank
  // trophy treatment uses on mobile, not a new color concept.
  tone?: "neutral" | "risk" | "positive" | "premium";
  /** Optional caption line under the value — e.g. "42 total capital". */
  note?: string;
  /** coridian_, 2026-10-17: "the dashboard needs more glyph icons... so
   * people can quickly scan the page" — every tile had a plain text label
   * and no icon at all before this. Optional so a caller with no sensible
   * glyph (rare) can omit it. */
  glyph?: SnapshotGlyphName;
}) {
  const toneColor =
    tone === "risk"
      ? "var(--color-danger)"
      : tone === "positive"
        ? "var(--color-success)"
        : tone === "premium"
          ? "var(--color-premium)"
          : "var(--color-text-primary)";

  return (
    <div
      className="flex flex-col gap-1 p-3 min-w-[7rem]"
      style={{
        background: "var(--color-surface-secondary)",
        border: `var(--border-width-default) solid ${tone === "premium" ? "var(--color-premium)" : "var(--color-border)"}`,
      }}
    >
      <span className="flex items-center gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
        {glyph ? <SnapshotTileGlyph name={glyph} /> : null}
        {label}
      </span>
      <span style={{ font: "var(--type-primary-metric)", color: toneColor }}>{value}</span>
      {note ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {note}
        </span>
      ) : null}
    </div>
  );
}

export { formatRank };

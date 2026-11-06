import { compactValueFontSize } from "@/lib/snapshotTileSizing";
import { SnapshotTileGlyph, type SnapshotGlyphName } from "@/components/SnapshotTileGlyph";

function formatRank(rank: number | null, tied: boolean): string {
  if (rank === null || rank === undefined) return "—";
  return tied ? `T-${rank}` : `#${rank}`;
}

// coridian_, 2026-10-18 (screenshot): "team snapshot still has no color" —
// every glyph inherited the label's --color-text-muted, so the whole
// section read as flat grayscale regardless of tone. A fixed accent per
// metric (reusing this app's existing semantic color lanes, not new ones)
// gives each tile its own identity even when tone is "neutral", matching
// the FantasyDesk visual-identity mockup's per-tile snapshot coloring.
const GLYPH_ACCENT: Record<SnapshotGlyphName, string> = {
  record: "var(--color-accent)",
  power: "var(--color-premium)",
  franchise: "var(--color-diagnostic)",
  starter: "var(--color-success)",
  bench: "var(--color-opportunity)",
  age: "var(--color-text-secondary)",
  injury: "var(--color-danger)",
};

export function SnapshotTile({
  label,
  value,
  tone = "neutral",
  note,
  glyph,
  wrapNote = false,
  compact = false,
  reserveLabelLines = false,
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
  /** Caps the tile's width so a longer caption (e.g. beginner helper text
   * from lib/experienceCopy.ts) wraps instead of stretching the tile
   * across the whole row. Off by default, so existing callers keep their
   * current layout. */
  wrapNote?: boolean;
  /** Equal-column strip form: no min width, tighter padding, smaller value. */
  compact?: boolean;
  /** Reserves two label lines so wrapped labels (Power Rank) and one-line
   * ones (Record) keep their values on the same line across a 4-up strip. */
  reserveLabelLines?: boolean;
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
      className={`glass-surface flex flex-col gap-1 ${compact ? "px-1.5 py-2 min-w-0 items-center text-center" : `p-3 min-w-[7rem]${note && wrapNote ? " max-w-[16rem]" : ""}`}`}
      style={tone === "premium" ? { borderColor: "var(--color-premium)" } : undefined}
    >
      <span
        className={compact ? "flex flex-col items-center gap-0.5 text-[0.6875rem] leading-tight text-center min-w-0 max-w-full" + (reserveLabelLines ? " min-h-[3.25rem]" : "") : "flex items-center gap-1 text-xs"}
        style={{ color: "var(--color-text-muted)" }}
      >
        {glyph ? (
          <span className={compact ? "shrink-0" : undefined} style={{ color: tone === "neutral" ? GLYPH_ACCENT[glyph] : toneColor }}>
            <SnapshotTileGlyph name={glyph} />
          </span>
        ) : null}
        {label}
      </span>
      <span
        className={compact ? "flex h-6 max-w-full items-center justify-center overflow-hidden text-ellipsis whitespace-nowrap tabular-nums" : undefined}
        style={{ font: "var(--type-primary-metric)", color: toneColor, ...(compact ? { fontSize: compactValueFontSize(value) } : {}) }}
      >
        {value}
      </span>
      {note ? (
        <span className={compact ? "text-xs text-center" : "text-xs"} style={{ color: "var(--color-text-muted)" }}>
          {note}
        </span>
      ) : null}
    </div>
  );
}

export { formatRank };

import { SnapshotTile } from "@/components/SnapshotTile";
import type { SnapshotGlyphName } from "@/components/SnapshotTileGlyph";

export type StatStripItem = {
  glyph: SnapshotGlyphName;
  label: string;
  value: string;
  tone?: "neutral" | "risk" | "positive" | "premium";
  /** Beginner-only plain-language caption (omit for advanced). */
  note?: string;
};

/**
 * One row of compact stat tiles (equal columns, never wraps to a second
 * row). The Dashboard's Record / Power Rank / Franchise Rank / Avg Age
 * strip and its Team Snapshot row both render through this, so a tile looks
 * the same in both.
 */
export function StatStrip({ items, columns }: { items: StatStripItem[]; columns: 3 | 4 }) {
  return (
    <div className={`grid gap-2 ${columns === 4 ? "grid-cols-4" : "grid-cols-3"}`}>
      {items.map((item) => (
        <SnapshotTile key={item.label} compact wrapNote reserveLabelLines={columns === 4} {...item} />
      ))}
    </div>
  );
}

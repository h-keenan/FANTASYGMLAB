import { SnapshotTile } from "@/components/SnapshotTile";
import type { SnapshotGlyphName } from "@/components/SnapshotTileGlyph";
import { InsightLink } from "@/components/ui/InsightLink";
import type { InsightKey } from "@/lib/insightLinks";

export type StatStripItem = {
  glyph: SnapshotGlyphName;
  label: string;
  value: string;
  tone?: "neutral" | "risk" | "positive" | "premium";
  /** Beginner-only plain-language caption (omit for advanced). */
  note?: string;
  /** 0..1 standing drawn as a thin meter under the value (see SnapshotTile). */
  fill?: number | null;
  /** What this tile states (lib/insightLinks.ts). With `league` on the strip the tile becomes a link to where it is explained. */
  insight?: InsightKey;
};

/**
 * One row of compact stat tiles (equal columns, never wraps to a second
 * row). The Dashboard's Record / Power Rank / Franchise Rank / Avg Age
 * strip and its Team Snapshot row both render through this, so a tile looks
 * the same in both.
 */
export function StatStrip({ items, columns, league }: { items: StatStripItem[]; columns: 3 | 4; league?: { id: string; name: string } }) {
  return (
    <div className={`grid gap-2 ${columns === 4 ? "grid-cols-4" : "grid-cols-3"}`}>
      {items.map(({ insight, ...item }) => {
        const tile = <SnapshotTile key={item.label} compact wrapNote reserveLabelLines={columns === 4} {...item} />;
        if (!insight || !league) return tile;
        return (
          <InsightLink key={item.label} insight={insight} league={league} spoken={[item.label, item.value, item.note]}>
            {tile}
          </InsightLink>
        );
      })}
    </div>
  );
}

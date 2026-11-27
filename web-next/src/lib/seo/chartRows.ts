import type { ValueRow } from "@/components/seo/ValueTable";
import { CHART_ROWS, isPageEligible } from "@/lib/seo/content";
import { fetchBoard, formatUpdated } from "@/lib/seo/publicValues";
import { assignSlugs } from "@/lib/seo/slug";

export interface ChartData {
  rows: ValueRow[];
  /** Human "updated" label and the raw ISO instant it came from. */
  updated: string;
  updatedAt: string;
}

/** Top-N dynasty chart rows (1QB value + Superflex column), or null when the board is too thin to show. Shared by the SEO chart page and /try/dynasty-values. */
export async function loadChartRows(): Promise<ChartData | null> {
  const [oneQb, superflex] = await Promise.all([fetchBoard("1qb"), fetchBoard("superflex")]);
  const top = oneQb.players.slice(0, CHART_ROWS);
  if (top.length < CHART_ROWS / 2) return null;
  const slugs = assignSlugs(oneQb.players.filter(isPageEligible));
  const sfById = new Map(superflex.players.map((p) => [p.player_id, p]));
  const rows: ValueRow[] = top.map((player) => {
    const sf = sfById.get(player.player_id);
    return {
      rank: player.overall_rank,
      player,
      slug: isPageEligible(player) ? (slugs.get(player.player_id) ?? null) : null,
      extra: sf ? { value: sf.score, rank: sf.overall_rank } : null,
    };
  });
  return { rows, updated: formatUpdated(oneQb.source_updated_at), updatedAt: oneQb.source_updated_at };
}

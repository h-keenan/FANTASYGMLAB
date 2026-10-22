/**
 * Short reason chips for a waiver recommendation, mirroring web-next's
 * waiverReasonChips (lib/waiversPresentation.ts). Mapped ONLY from signals
 * the server already computed (modules/faab.py `reasons`: breakout, usage/
 * role trend, depth-chart move, Sleeper trending adds, own need, wire depth,
 * competition; plus injury_replacement_fit). A signal that isn't present
 * produces no chip — nothing is invented. Rule order is display priority
 * (catalysts before own-need).
 */
const CHIP_RULES: Array<[RegExp, (match: RegExpMatchArray) => string]> = [
  [/^Trending on Sleeper/i, () => 'Trending'],
  [/^Usage up (\d+)%/i, (m) => `Usage +${m[1]}%`],
  [/^Breakout/i, () => 'Breakout'],
  [/^Role rising/i, () => 'Role rising'],
  [/^Moved up/i, () => 'Depth chart up'],
  [/^Fills a starting/i, () => 'Fills need'],
  [/^Would start/i, () => 'Would start'],
  [/^Clear best/i, () => 'Best on wire'],
  [/^\d+ teams? (need|needs) /i, () => 'Rival demand'],
];

export function waiverReasonChips(
  player: {
    faab?: { reasons?: string[] } | null;
    sleeper_trending_add?: boolean;
    injury_replacement_fit?: boolean;
  },
  max = 2,
): string[] {
  const hits = new Map<string, number>();
  if (player.sleeper_trending_add) hits.set('Trending', 0);
  for (const reason of player.faab?.reasons ?? []) {
    CHIP_RULES.some(([pattern, toChip], index) => {
      const match = reason.match(pattern);
      if (match) {
        const chip = toChip(match);
        hits.set(chip, Math.min(index, hits.get(chip) ?? index));
      }
      return Boolean(match);
    });
  }
  if (player.injury_replacement_fit) hits.set('Injury cover', CHIP_RULES.length);
  return [...hits.entries()]
    .sort((a, b) => a[1] - b[1])
    .map(([chip]) => chip)
    .slice(0, max);
}

export type WaiverRecFilter = 'all' | 'Add' | 'Stash' | 'Watch';

/** Filter pills for "More recommended adds" — by the server's own
 * recommendation_label (waiver_recommendation_label: Add / Stash / Watch). */
export function filterByRecommendation<T extends { recommendation_label: string }>(
  rows: T[],
  filter: WaiverRecFilter,
): T[] {
  return filter === 'all' ? rows : rows.filter((row) => row.recommendation_label === filter);
}

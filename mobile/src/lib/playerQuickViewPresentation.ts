// Pure presentation helpers for the Player Quick View sheet. Ports of
// web-next/src/lib/playerQuickViewPresentation.ts (seasonStatGroups,
// tierOpportunityMismatchCaption) so the app's sheet reads the same as the
// site's PQV: same group order, same caveat caption, same rank line.
import type { QuickViewSeason, QuickViewStatItem } from './api.ts';

export interface StatGroup {
  title: string;
  items: QuickViewStatItem[];
}

/** Groups to render for one season, in the web PQV's order (Production,
 * Fantasy, Usage, Efficiency), skipping empty groups. */
export function seasonStatGroups(
  season: Pick<QuickViewSeason, 'key_stats' | 'fantasy' | 'usage' | 'efficiency'>,
): StatGroup[] {
  return [
    { title: 'Production', items: season.key_stats },
    { title: 'Fantasy', items: season.fantasy },
    { title: 'Usage', items: season.usage },
    { title: 'Efficiency', items: season.efficiency },
  ].filter((group) => (group.items?.length ?? 0) > 0);
}

// Season-long tier and right-now opportunity label can legitimately
// disagree (an injury-driven promotion); web names that combination instead
// of showing two silently contradicting chips. Same rule, same copy.
const LOW_PLAYER_TIERS = new Set(['Contributor', 'Depth', 'Developmental']);
const HIGH_OPPORTUNITY_LABELS = new Set(['Elite Opportunity', 'Strong Opportunity']);

export function tierOpportunityMismatchCaption(
  tier: string | null | undefined,
  opportunityLabel: string | null | undefined,
): string | null {
  if (!tier || !opportunityLabel) return null;
  if (!LOW_PLAYER_TIERS.has(tier) || !HIGH_OPPORTUNITY_LABELS.has(opportunityLabel)) return null;
  return `${tier} reflects value over the full season — this role read (${opportunityLabel}) is about right now, and can jump ahead of it fast (e.g. an injury-driven promotion).`;
}

/** "Overall #12 · WR #4" under the header; null when neither rank is known. */
export function rankLine(
  position: string | null | undefined,
  overallRank: number | null | undefined,
  positionRank: number | null | undefined,
): string | null {
  const bits = [
    overallRank ? `Overall #${Math.round(overallRank)}` : null,
    positionRank ? `${position || 'Position'} #${Math.round(positionRank)}` : null,
  ].filter(Boolean);
  return bits.length ? bits.join(' · ') : null;
}

/** Radar needs a real point on every axis (a missing factor plotted as 0
 * would read as "worst", not "no read"). Returns null otherwise and the
 * caller falls back to the chip row, same split as web. */
export function radarPoints(
  ratings: Array<{ label: string; rating: number | null | undefined }>,
): Array<{ label: string; value: number }> | null {
  if (ratings.length < 3) return null;
  const points: Array<{ label: string; value: number }> = [];
  for (const item of ratings) {
    if (item.rating == null || !Number.isFinite(item.rating)) return null;
    points.push({ label: item.label, value: Math.max(0, Math.min(99, item.rating)) });
  }
  return points;
}

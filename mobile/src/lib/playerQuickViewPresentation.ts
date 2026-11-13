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

/**
 * ROOKIE badge for the Player Quick View / Profile header. Rookie status is
 * the backend's `bio.is_rookie` (years_exp === 0, the same definition live
 * draft rookie rankings use); this never re-derives it from age or draft
 * year. `detail` is a one-line "2026 · Round 1 · Pick 12 · College" built only
 * from bio fields that are actually present, or null when none are.
 */
export function rookieBadge(
  bio: { is_rookie?: boolean | null; draft_capital?: string | null; college?: string | null } | null | undefined,
): { label: 'ROOKIE'; detail: string | null } | null {
  if (!bio || bio.is_rookie !== true) return null;
  const parts = [
    ...(bio.draft_capital ?? '').split('/'),
    bio.college ?? '',
  ]
    .map((part) => part.trim())
    .filter(Boolean);
  return { label: 'ROOKIE', detail: parts.length > 0 ? parts.join(' · ') : null };
}

/** The opportunity chip is a depth-chart role read (modules/rankings
 * .opportunity_profile); the usage tile is the recent workload trend. A lead
 * role with a confirmed usage drop reads as two opposing headline signals, so
 * name the combination and say what each one measures. */
export function opportunityUsageCaption(
  opportunityLabel: string | null | undefined,
  trend: { direction: 'up' | 'down'; trend_pct: number; confidence_label: string } | null | undefined,
): string | null {
  if (!opportunityLabel || !trend || trend.direction !== "down") return null;
  if (opportunityLabel !== 'Elite Opportunity' && opportunityLabel !== 'Strong Opportunity') return null;
  const highConfidence = trend.confidence_label.trim().toLowerCase().startsWith("high");
  const pct = Math.abs(Math.round(trend.trend_pct));
  if (!highConfidence && pct < 20) return null;
  return `${opportunityLabel} is his depth-chart role; usage is down ${pct}% recently, so the role has not translated into recent workload.`;
}

/** Two-letter initials for the hero avatar when there is no photo ("Brock Briggs" -> "BB"). */
export function heroInitials(name: string | null | undefined): string {
  const words = (name ?? '').replace(/[^A-Za-z\s'-]/g, ' ').split(/\s+/).filter(Boolean);
  if (words.length === 0) return '';
  if (words.length === 1) return words[0][0].toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

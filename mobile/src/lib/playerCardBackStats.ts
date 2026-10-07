/**
 * Pure mapping from Trade Hub's `PresentationAsset` wire shape to the
 * shared `PlayerCard`'s generic back-face stat rows.
 *
 * coridian_ (Discord, this pass, re: the Trade Hub "YOU SEND"/"YOU RECEIVE"
 * card): "...whenever you tap on it, the card flips... and you see other
 * pertinent stats very quickly." `PlayerCard` itself stays data-source
 * agnostic (any future screen can hand it its own `backStats` array), so
 * this module is the one place that knows how to turn a Trade Hub asset
 * into those rows — and it deliberately surfaces only fields
 * `PresentationAsset` ALREADY carries over the wire but nothing on the old
 * Trade Hub card ever rendered: `score` (the asset's own value score —
 * only the trade's aggregate `trade_gain` showed anywhere before),
 * `injury_level` (severity, alongside the status text), and
 * `opportunity_explanation` (the role's own one-line rationale). No new
 * backend field was added to produce this.
 *
 * Kept free of `theme.ts`/any `react-native` import (same reasoning as
 * `bestAvailableCardVisual.ts`'s doc comment: `theme.ts` transitively pulls
 * in the real `react-native` package, whose Flow syntax can't be loaded by
 * plain Node) so this stays unit-testable with this project's
 * `node --experimental-strip-types --test` convention — see
 * playerCardBackStats.test.ts.
 */

import type { PresentationAsset } from './api.ts';

export interface PlayerCardBackStat {
  key: string;
  label: string;
  value: string;
  tone?: 'default' | 'positive' | 'negative' | 'warning';
}

export interface PlayerCardBackContent {
  /** Longer free-text line shown above the stat rows (e.g. the role's own
   * rationale sentence) — null when the asset carries none. */
  note: string | null;
  stats: PlayerCardBackStat[];
}

/** 'Out'/'IR'/'Doubtful'-caliber statuses read as more severe (red) than a
 * lighter flag like 'Questionable' (amber) — same risk/watch split
 * `PlayerIdentityRow`'s `injuryTone` already draws, just derived here from
 * the status text itself since this module has no access to that prop. */
function injuryTone(injuryStatus: string): 'negative' | 'warning' {
  const normalized = injuryStatus.toLowerCase();
  if (normalized.includes('out') || normalized.includes('ir') || normalized.includes('doubtful')) {
    return 'negative';
  }
  return 'warning';
}

export function presentationAssetBackStats(asset: PresentationAsset): PlayerCardBackContent {
  const stats: PlayerCardBackStat[] = [];

  if (asset.tier) {
    stats.push({ key: 'tier', label: 'Tier', value: asset.tier });
  }
  if (asset.role) {
    stats.push({ key: 'role', label: 'Role', value: asset.role });
  }
  if (asset.injury_status) {
    const severity = asset.injury_level ? ` (${asset.injury_level})` : '';
    stats.push({
      key: 'injury',
      label: 'Injury',
      value: `${asset.injury_status}${severity}`,
      tone: injuryTone(asset.injury_status),
    });
  }
  if (asset.score != null) {
    stats.push({ key: 'score', label: 'Value Score', value: String(Math.round(asset.score)) });
  }
  const teamAge = [asset.team, asset.age != null ? `Age ${asset.age}` : null].filter(Boolean).join(' · ');
  if (teamAge) {
    stats.push({ key: 'team_age', label: 'Team', value: teamAge });
  }

  return {
    note: asset.opportunity_explanation ?? null,
    stats,
  };
}

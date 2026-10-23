/**
 * Live Draft presentation helpers: pure display transforms, a port of
 * web-next/src/lib/liveDraftPresentation.ts (keep in lockstep). Every
 * score/rank/recommendation is computed server-side; nothing here re-derives
 * one. Rank movement is the one piece of client state: the endpoint is
 * stateless, so the screen diffs two consecutive polls itself.
 */

interface RankRow {
  player_id: string;
  overall_rank: number | null;
  is_rookie: boolean;
  position: string;
}

export const LIVE_DRAFT_RANK_FILTERS = ['Overall', 'QB', 'RB', 'WR', 'TE', 'Rookies', 'Veterans'] as const;
export type LiveDraftRankFilter = (typeof LIVE_DRAFT_RANK_FILTERS)[number];

/** Veterans only appears once the board has a non-rookie in it. */
export function liveDraftRankFilterOptions(rows: Pick<RankRow, 'is_rookie'>[]): LiveDraftRankFilter[] {
  const base: LiveDraftRankFilter[] = ['Overall', 'QB', 'RB', 'WR', 'TE', 'Rookies'];
  return rows.some((row) => !row.is_rookie) ? [...base, 'Veterans'] : base;
}

export function filterLiveDraftRankings<T extends Pick<RankRow, 'is_rookie' | 'position'>>(
  rows: T[],
  filter: LiveDraftRankFilter,
): T[] {
  if (filter === 'Overall') return rows;
  if (filter === 'Rookies') return rows.filter((row) => row.is_rookie);
  if (filter === 'Veterans') return rows.filter((row) => !row.is_rookie);
  return rows.filter((row) => (row.position || '').toUpperCase() === filter);
}

/** previous_rank - current_rank: positive means the player climbed. */
export function diffRankMovement(
  current: { player_id: string; overall_rank: number | null }[],
  previousRanksById: Record<string, number>,
): Record<string, number> {
  const movement: Record<string, number> = {};
  for (const row of current) {
    const previous = previousRanksById[row.player_id];
    if (previous !== undefined && row.overall_rank !== null) movement[row.player_id] = previous - row.overall_rank;
  }
  return movement;
}

export function ranksById(rows: { player_id?: string; overall_rank?: number | null }[]): Record<string, number> {
  const ranks: Record<string, number> = {};
  for (const row of rows) {
    if (row.player_id && row.overall_rank != null) ranks[row.player_id] = row.overall_rank;
  }
  return ranks;
}

export function diffTeamRankMovement(
  current: { roster_id: number; team_rank: number }[],
  previousRanksByRosterId: Record<string, number>,
): Record<string, number> {
  const movement: Record<string, number> = {};
  for (const row of current) {
    const key = String(row.roster_id);
    const previous = previousRanksByRosterId[key];
    if (previous !== undefined) movement[key] = previous - row.team_rank;
  }
  return movement;
}

export function teamRanksById(rows: { roster_id: number; team_rank: number }[]): Record<string, number> {
  const ranks: Record<string, number> = {};
  for (const row of rows) ranks[String(row.roster_id)] = row.team_rank;
  return ranks;
}

/** Same glyph + +/-2 threshold as the web and the Streamlit original. */
export function movementGlyph(movement: number | undefined): string {
  if (movement === undefined) return '—';
  if (movement >= 2) return `▲ ${movement}`;
  if (movement <= -2) return `▼ ${Math.abs(movement)}`;
  return '—';
}

export function formatLiveDraftScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '0.0';
  return value.toFixed(1);
}

/** Already-drafted players for the trade evaluator, deduped, from pick_rows. */
export function liveDraftDraftedPlayerOptions(
  rows: { player_id: string; player_name: string; position: string; fantasy_team: string }[],
): { key: string; label: string }[] {
  const seen = new Set<string>();
  const options: { key: string; label: string }[] = [];
  for (const row of rows) {
    if (!row.player_id || seen.has(row.player_id)) continue;
    seen.add(row.player_id);
    options.push({
      key: row.player_id,
      label: `${row.player_name || 'Unknown Player'} (${row.position || 'UNK'} · ${row.fantasy_team || 'Unknown team'})`,
    });
  }
  return options;
}

/** Fairness band (server-computed) -> semantic tone name. */
export type FairnessTone = 'success' | 'neutral' | 'warning' | 'danger';
export function fairnessBandTone(band: string | null | undefined): FairnessTone {
  switch ((band || '').trim().toLowerCase()) {
    case 'favorable':
      return 'success';
    case 'slight overpay':
      return 'warning';
    case 'major overpay':
      return 'danger';
    default:
      return 'neutral';
  }
}

/** trade_gain (signed) -> "+150" / "-800" / "Even". */
export function formatTradeGain(gain: number): string {
  if (gain > 0) return `+${Math.round(gain).toLocaleString('en-US')}`;
  if (gain < 0) return `-${Math.round(Math.abs(gain)).toLocaleString('en-US')}`;
  return 'Even';
}

export function toggleKey(set: Set<string>, key: string): Set<string> {
  const next = new Set(set);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  return next;
}

/** Referral reward line for the Account card. */
export function referralRewardCopy(r: { referrals_per_comp_month: number; max_comp_months: number }): string {
  return `For every ${r.referrals_per_comp_month} friends who connect their Sleeper account through your link, you earn a free month of GM Pro, up to ${r.max_comp_months} free months total.`;
}

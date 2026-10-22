/**
 * Pure helpers for the Percentile Explorer sheet (tap a stat tile in the
 * player view). Mirrors mobile/src/lib/percentileExplorer.ts: same stat keys,
 * same formatting, same marker lanes, so the two apps read identically.
 */

export interface ExplorerPlayer {
  player_id: string;
  name: string;
  team: string;
  position: string;
  value: number;
  percentile: number;
}

export interface ExplorerBin {
  count: number;
  pct_start: number;
  pct_end: number;
  value_start: number;
  value_end: number;
}

export type ExplorerReason = '' | 'unknown_stat' | 'insufficient_pool' | 'no_data' | 'season_unavailable';
export type ExplorerFormat = 'ppg' | 'points' | 'count' | 'yards' | 'td' | 'share' | 'rate';

/** GET /v1/players/{id}/percentile-explorer */
export interface PercentileExplorerResponse {
  ok: boolean;
  reason: ExplorerReason;
  stat: string;
  label?: string;
  format?: ExplorerFormat;
  pool: 'position' | 'all';
  position?: string;
  season?: number | null;
  scopes: string[];
  pool_size?: number;
  bins?: ExplorerBin[];
  player?: ExplorerPlayer | null;
  nearby?: ExplorerPlayer[];
}

/** Tile label (as shown on the Stats tab) -> backend stat key. Labels with no
 * entry (Games, college stats) are not tappable. Mirrors
 * modules/percentile_explorer.py. */
const STAT_KEY_BY_LABEL: Record<string, string> = {
  'PPR PPG': 'ppr_ppg',
  PPR: 'ppr',
  'Half PPR': 'half_ppr',
  Standard: 'standard',
  'Fantasy Points': 'fantasy_points',
  Targets: 'targets',
  Receptions: 'receptions',
  'Rec Yards': 'rec_yards',
  'Rec TDs': 'rec_tds',
  'Rush Att': 'rush_att',
  'Rush Yards': 'rush_yards',
  'Rush TDs': 'rush_tds',
  'Pass Att': 'pass_att',
  'Pass Yards': 'pass_yards',
  'Pass TDs': 'pass_tds',
  'Snap %': 'snap',
  'Route %': 'route',
  'Target Share': 'target_share',
  'Carry Share': 'carry_share',
  Opportunity: 'opportunity',
  'Targets/Gm': 'targets_gm',
  'Rec/Gm': 'rec_gm',
  'Yards/Catch': 'yards_catch',
  'Carries/Gm': 'carries_gm',
  'Yards/Carry': 'yards_carry',
};

export function explorerStatKey(label: string): string | null {
  return STAT_KEY_BY_LABEL[label] ?? null;
}

export function formatExplorerValue(value: number, format: ExplorerFormat | undefined): string {
  if (format === 'count' || format === 'yards' || format === 'td') return String(Math.round(value));
  if (format === 'share') return `${Math.round(value)}%`;
  return value.toFixed(1);
}

/** "+3.1" / "-2.0" / "0.0": left minus right, in the stat's own units. */
export function formatExplorerDelta(left: number, right: number, format: ExplorerFormat | undefined): string {
  const whole = format === 'count' || format === 'yards' || format === 'td' || format === 'share';
  const decimals = whole ? 0 : 1;
  const diff = Number((left - right).toFixed(decimals));
  const unit = format === 'share' ? ' pts' : '';
  return `${diff > 0 ? '+' : ''}${diff.toFixed(decimals)}${unit}`;
}

/** Assign each marker (ascending percentile) a vertical lane so neighbours
 * closer than `minGap` percentile points never sit on the same row. */
export function assignMarkerLanes(percentiles: number[], minGap = 18, laneCount = 3): number[] {
  const lastInLane: number[] = Array(laneCount).fill(-Infinity);
  return percentiles.map((pct) => {
    let lane = lastInLane.findIndex((last) => pct - last >= minGap);
    if (lane < 0) {
      // Crowded: use the lane whose last marker is furthest away.
      lane = lastInLane.reduce((best, last, index) => (pct - last > pct - lastInLane[best] ? index : best), 0);
    }
    lastInLane[lane] = pct;
    return lane;
  });
}

/** Default comparison: the closest real player above the subject, else below. */
export function defaultComparison(player: ExplorerPlayer, nearby: ExplorerPlayer[]): ExplorerPlayer | null {
  if (nearby.length === 0) return null;
  const above = nearby.filter((p) => p.value >= player.value);
  const pool = above.length > 0 ? above : nearby;
  return [...pool].sort((a, b) => Math.abs(a.value - player.value) - Math.abs(b.value - player.value))[0] ?? null;
}

/** Which of the sheet's states to draw. Mirrors the web sheet's branches. */
export type ExplorerViewState = 'loading' | 'error' | 'chart' | 'insufficient_pool' | 'season_unavailable' | 'no_data';

export function explorerViewState(
  status: 'loading' | 'error' | 'ready',
  data: PercentileExplorerResponse | null,
): ExplorerViewState {
  if (status === 'loading') return 'loading';
  if (status === 'error' || !data) return 'error';
  if (data.reason === 'insufficient_pool') return 'insufficient_pool';
  if (data.reason === 'season_unavailable') return 'season_unavailable';
  if (data.reason !== '' || !data.player) return 'no_data';
  return 'chart';
}

/** One-line reason shown instead of a chart. Never a placeholder number. */
export function explorerEmptyCopy(
  reason: ExplorerReason,
  position?: string,
): { title: string; subtitle: string } {
  if (reason === 'insufficient_pool') {
    return {
      title: 'Not enough players to rank',
      subtitle: `Too few ${position || 'position'} players have this stat for a trustworthy percentile.`,
    };
  }
  if (reason === 'season_unavailable') {
    return { title: 'Season not available', subtitle: 'Only the current season is loaded.' };
  }
  return { title: 'No data for this stat', subtitle: 'This player has no ranked value for it yet.' };
}

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
  /** Who the percentile is measured against and over what (usage stats). */
  sample_note?: string;
  bins?: ExplorerBin[];
  player?: ExplorerPlayer | null;
  nearby?: ExplorerPlayer[];
  /** Every ranked pool member (value desc), only when requested with `full`. */
  pool_players?: ExplorerPlayer[];
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
  'Snap Share': 'snap',
  'Air Yards Share': 'air_yards_share',
  'Opportunity Share': 'opportunity',
  'Red-Zone Looks / Game': 'red_zone_looks',
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
export function assignMarkerLanes(percentiles: number[], minGap = 30, laneCount = 5): number[] {
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

// ---------------------------------------------------------------------------
// Interactive explorer helpers (identical on mobile; pinned by each platform's
// percentileExplorer tests).
// ---------------------------------------------------------------------------

export interface ExplorerMetric {
  key: string;
  label: string;
}

const RECEIVER_METRICS: ExplorerMetric[] = [
  { key: 'ppr_ppg', label: 'PPR PPG' },
  { key: 'target_share', label: 'Target Share' },
  { key: 'air_yards_share', label: 'Air Yards Share' },
  { key: 'opportunity', label: 'Opportunity Share' },
  { key: 'snap', label: 'Snap Share' },
  { key: 'red_zone_looks', label: 'Red-Zone Looks / Game' },
  { key: 'targets_gm', label: 'Targets/Gm' },
  { key: 'rec_yards', label: 'Rec Yards' },
  { key: 'yards_catch', label: 'Yards/Catch' },
];
const BACK_METRICS: ExplorerMetric[] = [
  { key: 'ppr_ppg', label: 'PPR PPG' },
  { key: 'opportunity', label: 'Opportunity Share' },
  { key: 'snap', label: 'Snap Share' },
  { key: 'red_zone_looks', label: 'Red-Zone Looks / Game' },
  { key: 'carries_gm', label: 'Carries/Gm' },
  { key: 'yards_carry', label: 'Yards/Carry' },
  { key: 'targets_gm', label: 'Targets/Gm' },
  { key: 'rush_yards', label: 'Rush Yards' },
];
const QB_METRICS: ExplorerMetric[] = [
  { key: 'ppr_ppg', label: 'PPR PPG' },
  { key: 'pass_yards', label: 'Pass Yards' },
  { key: 'pass_tds', label: 'Pass TDs' },
  { key: 'pass_att', label: 'Pass Att' },
  { key: 'rush_yards', label: 'Rush Yards' },
];

/** Metrics worth switching to for a position (all supported by the endpoint). The
 * current metric is always included so the active chip never disappears. */
export function explorerMetricsFor(position: string | undefined, current: { key: string; label: string }): ExplorerMetric[] {
  const pos = (position ?? '').toUpperCase();
  const base = pos === 'QB' ? QB_METRICS : pos === 'RB' ? BACK_METRICS : RECEIVER_METRICS;
  return base.some((m) => m.key === current.key) ? base : [current, ...base];
}

/** Index of the histogram bin holding a percentile (the last bin is inclusive). */
export function binIndexAtPercentile(bins: ExplorerBin[], pct: number): number {
  if (bins.length === 0) return -1;
  const found = bins.findIndex((bin, index) => pct >= bin.pct_start && (pct < bin.pct_end || index === bins.length - 1));
  return found < 0 ? bins.length - 1 : found;
}

/** The exact players behind one histogram bar. `pool` is value-descending; bins
 * count ascending values, so each bin is a contiguous slice (ties never split a
 * bin). Returned best-first. */
export function bucketPlayers(pool: ExplorerPlayer[], bins: ExplorerBin[], index: number): ExplorerPlayer[] {
  if (index < 0 || index >= bins.length) return [];
  let below = 0;
  for (let i = 0; i < index; i += 1) below += bins[i].count;
  const total = pool.length;
  const from = total - below - bins[index].count;
  const to = total - below;
  return pool.slice(Math.max(0, from), Math.max(0, to));
}

/** Players closest to a scrubbed percentile, nearest first. */
export function playersNearPercentile(pool: ExplorerPlayer[], pct: number, limit = 5): ExplorerPlayer[] {
  return [...pool]
    .sort((a, b) => Math.abs(a.percentile - pct) - Math.abs(b.percentile - pct) || b.value - a.value)
    .slice(0, limit);
}

/** Name search inside the pool: prefix, then word-prefix, then substring. */
export function searchExplorerPool(pool: ExplorerPlayer[], query: string, limit = 8): ExplorerPlayer[] {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  const starts: ExplorerPlayer[] = [];
  const wordStarts: ExplorerPlayer[] = [];
  const contains: ExplorerPlayer[] = [];
  for (const player of pool) {
    const name = player.name.toLowerCase();
    if (name.startsWith(q)) starts.push(player);
    else if (name.split(/[\s.'-]+/).some((word) => word.startsWith(q))) wordStarts.push(player);
    else if (name.includes(q)) contains.push(player);
  }
  return [...starts, ...wordStarts, ...contains].slice(0, limit);
}

export function poolMedian(pool: ExplorerPlayer[]): number | null {
  if (pool.length === 0) return null;
  const values = pool.map((p) => p.value).sort((a, b) => a - b);
  const mid = Math.floor(values.length / 2);
  return values.length % 2 ? values[mid] : (values[mid - 1] + values[mid]) / 2;
}

/** Sleeper roster ids from the my-roster payload (`players` is a list of ids). */
export function rosterIdsFromRoster(roster: Record<string, unknown> | null | undefined): Set<string> {
  const players = roster && Array.isArray(roster.players) ? roster.players : [];
  return new Set(players.filter((id): id is string => typeof id === 'string').map(String));
}

/** Add a player to the charted set, dropping the oldest pin when over the cap. */
export function addPin(pins: string[], playerId: string, cap = 7): string[] {
  if (pins.includes(playerId)) return pins;
  const next = [...pins, playerId];
  return next.length > cap ? next.slice(next.length - cap) : next;
}

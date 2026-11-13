import type { QuickViewModel, RankedPlayer, ScheduleWeek, WeeklyStatPoint } from './api';

/**
 * Pure helpers for the Player Compare head-to-head grid (mirrors the "v2"
 * helpers at the end of web-next's lib/playerComparePresentation.ts): PPG,
 * next-game projection, schedule outlook, headline rows with a winner, and
 * one-tap suggestions. Type-only imports so node --test can run it.
 */

export interface HeadlineRow {
  label: string;
  a: number | null;
  b: number | null;
  format: (value: number) => string;
  lowerIsBetter?: boolean;
  /** Shown side by side with no better side (age: which is better depends on the league). */
  neutral?: boolean;
}

export interface HeadlineTextRow {
  label: string;
  a: string | null;
  b: string | null;
  winner?: 'a' | 'b' | null;
}

export interface ScheduleOutlook {
  /** Soft minus tough matchups over the next games; higher is the easier road. */
  score: number;
  text: string;
}

export interface CompareExtras {
  ppg: number | null;
  projection: number | null;
  schedule: ScheduleOutlook | null;
}

export const NO_EXTRAS: CompareExtras = { ppg: null, projection: null, schedule: null };

export function headlineWinner(row: HeadlineRow): 'a' | 'b' | null {
  if (row.neutral || row.a === null || row.b === null || row.a === row.b) return null;
  const aWins = row.lowerIsBetter ? row.a < row.b : row.a > row.b;
  return aWins ? 'a' : 'b';
}

/** Points per game from the weekly PPR series (null before any game is played). */
export function ppgFromWeeks(weeks: WeeklyStatPoint[]): number | null {
  const played = weeks.filter((w): w is WeeklyStatPoint & { fantasy_points_ppr: number } => w.fantasy_points_ppr != null);
  if (played.length === 0) return null;
  return played.reduce((sum, w) => sum + w.fantasy_points_ppr, 0) / played.length;
}

/** The next game's projected points: the first unplayed, non-bye week that carries a point estimate. */
export function nextProjection(weeks: ScheduleWeek[]): number | null {
  for (const week of weeks) {
    if (week.played || week.bye) continue;
    const estimate = week.projection?.point_estimate;
    if (week.projection?.status === 'ok' && estimate != null) return estimate;
  }
  return null;
}

/** The next four games by opponent defense tier, e.g. "2 soft · 1 avg · 1 tough". Null when no tiers are known. */
export function scheduleOutlook(weeks: ScheduleWeek[], games = 4): ScheduleOutlook | null {
  const upcoming = weeks.filter((w) => !w.played && !w.bye).slice(0, games);
  const tiers = upcoming.map((w) => w.opponent_defense_tier).filter((t): t is NonNullable<typeof t> => t != null);
  if (tiers.length === 0) return null;
  const count = (tier: string) => tiers.filter((t) => t === tier).length;
  const parts = [
    count('weak') ? `${count('weak')} soft` : '',
    count('average') ? `${count('average')} avg` : '',
    count('tough') ? `${count('tough')} tough` : '',
  ].filter(Boolean);
  return { score: count('weak') - count('tough'), text: parts.join(' · ') };
}

const formatPoints = (value: number) => (Math.round(value * 10) / 10).toFixed(1);

/** Value, ranks, age, PPG and next-game projection (numeric, winner marked except age). */
export function buildHeadlineRows(a: RankedPlayer, b: RankedPlayer, extrasA: CompareExtras, extrasB: CompareExtras): HeadlineRow[] {
  return [
    { label: 'Value Score', a: a.score, b: b.score, format: (v) => Math.round(v).toLocaleString() },
    { label: 'Overall Rank', a: a.overall_rank, b: b.overall_rank, format: (v) => `#${v}`, lowerIsBetter: true },
    { label: 'Position Rank', a: a.position_rank, b: b.position_rank, format: (v) => `#${v}`, lowerIsBetter: true },
    { label: 'Age', a: a.age, b: b.age, format: (v) => String(Math.round(v)), neutral: true },
    { label: 'PPG', a: extrasA.ppg, b: extrasB.ppg, format: formatPoints },
    { label: 'Next game', a: extrasA.projection, b: extrasB.projection, format: formatPoints },
  ];
}

function usageText(model: QuickViewModel | null): string | null {
  const trend = model?.usage_trend;
  if (!trend) return null;
  const pct = Math.round(trend.trend_pct);
  return `${trend.arrow} ${pct > 0 ? '+' : ''}${pct}% (${trend.confidence_label})`;
}

/** Usage trend and the schedule outlook as text rows; only the schedule has a winner. */
export function buildHeadlineTextRows(modelA: QuickViewModel | null, modelB: QuickViewModel | null, extrasA: CompareExtras, extrasB: CompareExtras): HeadlineTextRow[] {
  const rows: HeadlineTextRow[] = [];
  const ua = usageText(modelA);
  const ub = usageText(modelB);
  if (ua !== null || ub !== null) rows.push({ label: 'Trend', a: ua, b: ub });
  if (extrasA.schedule || extrasB.schedule) {
    const sa = extrasA.schedule?.score ?? null;
    const sb = extrasB.schedule?.score ?? null;
    rows.push({
      label: 'Next 4 games',
      a: extrasA.schedule?.text ?? null,
      b: extrasB.schedule?.text ?? null,
      winner: sa === null || sb === null || sa === sb ? null : sa > sb ? 'a' : 'b',
    });
  }
  return rows;
}

/** One-tap suggestions: same position, nearest value, never the base player or anyone excluded. */
export function suggestedOpponents(pool: RankedPlayer[], base: RankedPlayer, exclude: string[] = [], limit = 4): RankedPlayer[] {
  const skip = new Set([base.player_id, ...exclude]);
  const candidates = pool.filter((p) => !skip.has(p.player_id));
  const scoped = base.position ? candidates.filter((p) => p.position === base.position) : candidates;
  const baseScore = base.score;
  if (baseScore == null) return scoped.slice(0, limit);
  return [...scoped]
    .sort((x, y) => {
      const dx = x.score == null ? Infinity : Math.abs(x.score - baseScore);
      const dy = y.score == null ? Infinity : Math.abs(y.score - baseScore);
      return dx - dy;
    })
    .slice(0, limit);
}

const RECENT_MAX = 6;

/** Newest-first, deduped, capped list of recent opponent ids. */
export function pushRecent(existing: string[], playerId: string): string[] {
  return [playerId, ...existing.filter((id) => id !== playerId)].slice(0, RECENT_MAX);
}

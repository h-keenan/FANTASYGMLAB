/**
 * NFL season phase from a league's current week — the client-side port of
 * the one existing season-phase helper, modules/gm_plan.py's
 * derive_season_phase(). Same input (Sleeper's league `leg`/`week`, which
 * GET .../matchup already returns as `week`), same constants, same buckets,
 * so mobile never carries its own calendar dates. Pure, so the node test
 * runner covers it.
 */

// Mirrors modules/gm_plan.py.
export const MAX_LEAGUE_WEEK = 18;
export const DEFAULT_PLAYOFF_WEEK_START = 15;
const PLAYOFF_PUSH_LOOKBACK_WEEKS = 3;
const EARLY_SEASON_WEEK_CEILING = 3;

export type SeasonPhase = 'early_season' | 'trade_deadline_approach' | 'playoff_push' | 'offseason_adjacent';

function safeWeek(value: unknown): number {
  const parsed = typeof value === 'number' ? value : Number.parseInt(String(value ?? ''), 10);
  return Number.isFinite(parsed) ? Math.trunc(parsed) : 0;
}

export function deriveSeasonPhase(currentWeek: unknown, playoffWeekStart?: unknown): SeasonPhase {
  const week = safeWeek(currentWeek);
  if (week <= 0 || week > MAX_LEAGUE_WEEK) return 'offseason_adjacent';
  let pws = safeWeek(playoffWeekStart);
  if (pws <= 0) pws = DEFAULT_PLAYOFF_WEEK_START;
  if (week >= Math.max(1, pws - PLAYOFF_PUSH_LOOKBACK_WEEKS)) return 'playoff_push';
  if (week <= EARLY_SEASON_WEEK_CEILING) return 'early_season';
  return 'trade_deadline_approach';
}

/** Regular season or playoffs — anything but the offseason bucket. */
export function isInSeason(currentWeek: unknown): boolean {
  return deriveSeasonPhase(currentWeek) !== 'offseason_adjacent';
}

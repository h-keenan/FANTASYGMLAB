/**
 * Bounded concurrency for the progressive Portfolio rows (mirrors
 * web-next/src/lib/portfolioLoader.ts).
 *
 * Each league's row is expensive server-side, so at most
 * PORTFOLIO_LEAGUE_CONCURRENCY row queries are enabled at a time, in saved
 * order. A row that has finished a fetch this mount (success OR error) frees
 * its slot, so one failing league never blocks the others.
 */

/** Max per-league requests in flight at once. */
export const PORTFOLIO_LEAGUE_CONCURRENCY = 3;
/** Show the branded spinner only if the first paint is still empty after this. */
export const PORTFOLIO_SPLASH_DELAY_MS = 300;
/** Shared by the real row and its skeleton so a row never changes height when it fills in. */
export const PORTFOLIO_ROW_MIN_HEIGHT = 120;
/** Skeleton rows shown before the index says how many leagues there are. */
export const PORTFOLIO_SHELL_SKELETON_COUNT = 3;

/**
 * Which leagues may fetch right now: the first `cap` leagues (saved order)
 * that have not yet finished a fetch this mount.
 */
export function enabledLeagueIds(
  order: string[],
  fetchedThisMount: Record<string, boolean | undefined>,
  cap: number = PORTFOLIO_LEAGUE_CONCURRENCY,
): Set<string> {
  const enabled = new Set<string>();
  for (const leagueId of order) {
    if (enabled.size >= cap) break;
    if (!fetchedThisMount[leagueId]) enabled.add(leagueId);
  }
  return enabled;
}

// Shared (web + mobile twin): the "as-of" cut for real data shown inside Fantasy Sim, in the spirit of 2K. The sim starts
// at the end of the last fully finished real season; every real-data section (season stats, awards, charts) is cut to
// seasons up to that one. Nothing from the in-progress real season (stats, game logs, trends, news) may appear: the sim's
// own seasons replace it. Pure and import-free.

/** The calendar label of the NFL season in progress or next up (Jan-Feb still belongs to the season just played).
 * Mirrors modules/sim/game_api.default_start_year, the label a fresh sim's season 1 plays under. */
export function simDefaultStartYear(today: Date = new Date()): number {
  return today.getFullYear() - (today.getMonth() >= 2 ? 0 : 1);
}

/** The last fully finished real season at the sim's start: the season before the one the sim replays. */
export function simAsOfSeason(startYear?: number | null, today: Date = new Date()): number {
  return (startYear && startYear > 0 ? startYear : simDefaultStartYear(today)) - 1;
}

/** Rows up to `asOf`. A row whose season is unknown cannot be placed in time, so it is dropped, never guessed. */
export function rowsAsOf<T extends { season: number | null }>(rows: readonly T[], asOf: number): T[] {
  return rows.filter((r) => r.season != null && r.season <= asOf);
}

/** Real career seasons the sim's player sheet may show: up to the as-of season, newest first. The season in progress never shows. */
export function simCareerAsOf<T extends { season: number }>(seasons: readonly T[], asOf: number): T[] {
  return seasons.filter((s) => s.season <= asOf).sort((a, b) => b.season - a.season);
}

export interface SimGameLogSummary<T> {
  weeks: T[];
  games: number;
  total: number;
  avg: number | null;
  best: T | null;
}

/** The real game log of the last finished season: weeks he scored in, ascending, with games / total / average / best week. */
export function simGameLog<T extends { week: number; fantasy_points_ppr: number | null }>(weeks: readonly T[]): SimGameLogSummary<T> {
  const played = weeks.filter((w) => w.week > 0 && w.fantasy_points_ppr != null).sort((a, b) => a.week - b.week);
  const total = played.reduce((sum, w) => sum + (w.fantasy_points_ppr ?? 0), 0);
  const best = played.reduce<T | null>((top, w) => (top == null || (w.fantasy_points_ppr ?? 0) > (top.fantasy_points_ppr ?? 0) ? w : top), null);
  return { weeks: played, games: played.length, total, avg: played.length ? total / played.length : null, best };
}

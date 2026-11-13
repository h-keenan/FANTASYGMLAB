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

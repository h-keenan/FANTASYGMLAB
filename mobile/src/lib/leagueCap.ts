/**
 * Copy for the saved-league cap (modules/saved_leagues.py). The server refuses
 * the save with `reason: 'at_cap'`; the client must show this and never open
 * the league as if it had been added.
 */
export const LEAGUE_CAP_MESSAGE = 'Free includes 1 league. Pro supports up to 5.';

export function leagueCapMessage(): string {
  return LEAGUE_CAP_MESSAGE;
}

/** True only for a save the server actually accepted. */
export function saveSucceeded(result: { ok?: boolean } | null | undefined): boolean {
  return result?.ok === true;
}

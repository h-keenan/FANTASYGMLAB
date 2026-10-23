/**
 * Which platform a saved league comes from, and which screens it can open.
 *
 * ESPN leagues are saved under the id "espn:{espnLeagueId}:{season}"
 * (modules/espn_leagues.py on the API side), so the id itself carries the
 * platform marker. They can feed only the screens in
 * ESPN_SUPPORTED_ROUTES; every other league screen shows "Not available for
 * ESPN leagues yet" (EspnUnavailableScreen) instead of loading, and the API
 * refuses those routes for ESPN ids too. Same rules as web-next's
 * lib/leaguePlatform.ts.
 */

export const ESPN_NOT_AVAILABLE_MESSAGE = 'Not available for ESPN leagues yet.';

/**
 * Fleaflicker ("fleaflicker:{id}:{season}") and MFL ("mfl:{id}:{season}")
 * leagues (modules/fleaflicker_leagues.py, modules/mfl_leagues.py) follow the
 * exact ESPN pattern, so `isEspnLeagueId` (kept under its old name for its
 * many callers) is true for every imported, non-Sleeper league.
 */
const IMPORTED_PLATFORM_LABELS: Record<string, string> = { espn: 'ESPN', fleaflicker: 'Fleaflicker', mfl: 'MFL' };

/** 'ESPN' | 'Fleaflicker' | 'MFL' for an imported league id, '' for Sleeper. */
export function importedPlatformLabel(leagueId: string | null | undefined): string {
  if (typeof leagueId !== 'string' || !leagueId.includes(':')) return '';
  return IMPORTED_PLATFORM_LABELS[leagueId.split(':', 1)[0]] ?? '';
}

export function isEspnLeagueId(leagueId: string | null | undefined): boolean {
  return importedPlatformLabel(leagueId) !== '';
}

/** "Not available for MFL leagues yet." for the league's own platform. */
export function notAvailableMessage(leagueId: string | null | undefined): string {
  return `Not available for ${importedPlatformLabel(leagueId) || 'ESPN'} leagues yet.`;
}

/** League-scoped stack routes an ESPN league can open. Trades opens on its
 * "Make a Trade" (Trade Analyzer) tab only. */
export const ESPN_SUPPORTED_ROUTES = new Set([
  'MyTeam',
  'Trades',
  'Players',
  'PlayerDetail',
  'PlayerCompare',
  'Teams',
  'TeamRoster',
]);

export function espnRouteSupported(routeName: string): boolean {
  return ESPN_SUPPORTED_ROUTES.has(routeName);
}

/** Where opening a league lands: Dashboard for Sleeper, My Team for ESPN
 * (ESPN leagues have no Dashboard yet). */
export function leagueHomeRoute(leagueId: string): 'Dashboard' | 'MyTeam' {
  return isEspnLeagueId(leagueId) ? 'MyTeam' : 'Dashboard';
}

/** Seasons offered in the ESPN import, newest first. */
export function espnSeasonOptions(now: Date = new Date()): number[] {
  const year = now.getFullYear();
  return [year, year - 1, year - 2];
}

/** Customer copy for POST /v1/espn/leagues/preview and /v1/leagues/save
 * failure reasons that the server doesn't already send a message for. */
export const ESPN_SAVE_FAILURE_COPY: Record<string, string> = {
  league_not_found: "That league didn't load just now. Please try again.",
  espn_team_not_selected: 'Pick which team is yours first.',
  mapping_too_low: "Too few of this league's players matched FantasyDesk's player list to value it accurately.",
};

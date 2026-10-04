/**
 * Shared React Query key factories — kept in one place so two screens that
 * fetch the same endpoint (e.g. Dashboard's matchup card and MatchupScreen
 * itself both call getLeagueMatchup) land on the exact same cache entry
 * instead of each keeping its own copy.
 */
export const queryKeys = {
  dashboard: (leagueId: string) => ['dashboard', leagueId] as const,
  teamRankings: (leagueId: string) => ['team-rankings', leagueId] as const,
  matchup: (leagueId: string) => ['matchup', leagueId] as const,
};

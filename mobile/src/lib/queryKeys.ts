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
  // TeamsScreen's own metric-independent roster data (re-derived per-metric
  // client-side rather than refetched — see that screen's `baseRows` memo).
  teamProfiles: (leagueId: string) => ['team-profiles', leagueId] as const,
  leagueRosters: (leagueId: string) => ['league-rosters', leagueId] as const,
  myRoster: (leagueId: string) => ['my-roster', leagueId] as const,
  // MyTeamScreen's suggested starters/bench — also the same endpoint
  // PlayerDetailScreen's roster-recommendation enrichment fetch hits, though
  // that one's still a plain fetch-on-mount (out of scope for this pass).
  myTeam: (leagueId: string) => ['my-team', leagueId] as const,
  // PlayerDetailScreen's Stats tab payload — keyed by player id only, since
  // getPlayerQuickView takes no other params that affect the response.
  playerQuickView: (playerId: string) => ['player-quick-view', playerId] as const,
};

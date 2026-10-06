// NOTE: the `.ts` extension here is required, not stylistic — this module
// is also imported by queryKeys.test.ts, which runs directly under plain
// Node's own module loader (no bundler to resolve an extensionless
// specifier). See tsconfig.json's `allowImportingTsExtensions` comment and
// backgroundRetry.ts for the same pattern.
import { userScopeKey } from './authScope.ts';

/**
 * Shared React Query key factories — kept in one place so two screens that
 * fetch the same endpoint (e.g. Dashboard's matchup card and MatchupScreen
 * itself both call getLeagueMatchup) land on the exact same cache entry
 * instead of each keeping its own copy.
 *
 * Every key below is rooted at `userScopeKey()` — `['user', <supabase user
 * id>]` — centrally, here, rather than each screen interpolating a user id
 * by hand. This is what prevents cross-account cache leakage: two different
 * Supabase users requesting the same league id land on two structurally
 * different cache entries (`['user', 'alice-id', 'league', '123', ...]` vs
 * `['user', 'bob-id', 'league', '123', ...]`), so switching accounts can
 * never read back a previous account's cached response just because a
 * league id matches. See authScope.ts for how the scope id itself is
 * tracked, and AuthContext.tsx for the sign-out/account-switch cache
 * clearing that backs this up as defense in depth.
 */
export const queryKeys = {
  dashboard: (leagueId: string) =>
    [...userScopeKey(), 'league', leagueId, 'dashboard'] as const,
  teamRankings: (leagueId: string) =>
    [...userScopeKey(), 'league', leagueId, 'team-rankings'] as const,
  matchup: (leagueId: string) => [...userScopeKey(), 'league', leagueId, 'matchup'] as const,
  // TeamsScreen's own metric-independent roster data (re-derived per-metric
  // client-side rather than refetched — see that screen's `baseRows` memo).
  teamProfiles: (leagueId: string) =>
    [...userScopeKey(), 'league', leagueId, 'team-profiles'] as const,
  leagueRosters: (leagueId: string) =>
    [...userScopeKey(), 'league', leagueId, 'league-rosters'] as const,
  myRoster: (leagueId: string) => [...userScopeKey(), 'league', leagueId, 'my-roster'] as const,
  // MyTeamScreen's suggested starters/bench — also the same endpoint
  // PlayerDetailScreen's roster-recommendation enrichment fetch hits, though
  // that one's still a plain fetch-on-mount (out of scope for this pass).
  myTeam: (leagueId: string) => [...userScopeKey(), 'league', leagueId, 'my-team'] as const,
  // PlayerDetailScreen's Stats tab payload — keyed by player id only (no
  // other params affect the response), but still user-scoped: the response
  // includes user-specific fields (e.g. premium-entitlement gating), so a
  // free account must never read back a premium account's cached payload
  // for the same player, or vice versa, on a shared device.
  playerQuickView: (playerId: string) =>
    [...userScopeKey(), 'player-quick-view', playerId] as const,
};

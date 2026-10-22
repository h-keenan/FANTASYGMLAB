/**
 * Where a league switch lands (tap-depth audit 2026-10, proposal #5).
 *
 * Mirrors web-next's swapLeagueIdInPath: switching leagues from a
 * league-scoped screen stays on that screen with the new league's params;
 * anywhere else (or a screen whose other params belong to the old league)
 * goes to the new league's home (Dashboard, or My Team for ESPN). Pure, so
 * the node test runner covers it.
 */
import { espnRouteSupported, isEspnLeagueId, leagueHomeRoute } from './leaguePlatform.ts';

export interface LeagueTarget {
  leagueId: string;
  leagueName: string;
}

/** League-scoped screens whose params are just the league (plus optional
 * league-independent extras like a player or a tab), so swapping the league
 * keeps them meaningful. PickDetail (a pick) and TeamRoster (a roster id)
 * are left out on purpose: those belong to the old league. */
const KEEP_SCREEN_ROUTES = new Set([
  'LeagueDetail',
  'Dashboard',
  'Players',
  'PlayerDetail',
  'PlayerCompare',
  'GmTargets',
  'TeamStance',
  'GmPlan',
  'Waivers',
  'Recap',
  'Trades',
  'Teams',
  'PlayoffOdds',
  'DraftCenter',
  'MyTeam',
  'Matchup',
  'Alerts',
]);

/** Params that only make sense for the old league and are dropped. */
const OLD_LEAGUE_PARAMS = ['tradePlayer'];

export interface LeagueSwitchDestination {
  name: string;
  params: Record<string, unknown>;
}

export function leagueSwitchDestination(
  current: { name: string; params?: object | undefined } | null | undefined,
  currentLeagueId: string | null | undefined,
  target: LeagueTarget,
): LeagueSwitchDestination {
  const home: LeagueSwitchDestination = { name: leagueHomeRoute(target.leagueId), params: { ...target } };
  if (!current || !KEEP_SCREEN_ROUTES.has(current.name)) return home;
  const params = (current.params ?? {}) as Record<string, unknown>;
  // Only a screen that's actually showing the league being switched away
  // from (never Home/Portfolio/More or a stale param).
  if (!currentLeagueId || params.leagueId !== currentLeagueId) return home;
  if (isEspnLeagueId(target.leagueId) && !espnRouteSupported(current.name)) return home;
  const next: Record<string, unknown> = { ...params, ...target };
  for (const key of OLD_LEAGUE_PARAMS) delete next[key];
  // ESPN leagues open Trades on Make a Trade only.
  if (current.name === 'Trades' && isEspnLeagueId(target.leagueId)) next.initialTab = 'make';
  return { name: current.name, params: next };
}

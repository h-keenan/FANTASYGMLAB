/**
 * One landing screen (Dashboard) and one GM Plan screen.
 *
 * League Overview (`LeagueDetail`), GM Targets (`GmTargets`) and Team
 * Situation (`TeamStance`) used to be separate screens. Their content now lives
 * on Dashboard and GM Plan (matching web), but the route names stay registered
 * so deep links, push taps, stale navigation state and older callers keep
 * working: each one replaces itself with its new home. Pure, so the node test
 * runner covers it.
 */

export type GmPlanTab = 'overview' | 'trades' | 'core' | 'watching';

export interface LegacyRedirect {
  name: 'Dashboard' | 'GmPlan';
  params: Record<string, unknown>;
}

const TARGETS: Record<string, { name: 'Dashboard' | 'GmPlan'; extra: Record<string, unknown> }> = {
  LeagueDetail: { name: 'Dashboard', extra: {} },
  GmTargets: { name: 'GmPlan', extra: { initialTab: 'watching' } },
  TeamStance: { name: 'GmPlan', extra: { initialTab: 'overview' } },
};

/** Routes that only redirect (rendered for one frame, never a real view). */
export const LEGACY_REDIRECT_ROUTES: readonly string[] = Object.keys(TARGETS);

export function isLegacyRedirectRoute(routeName: string | null | undefined): boolean {
  return typeof routeName === 'string' && Object.prototype.hasOwnProperty.call(TARGETS, routeName);
}

/** Where a legacy route lands, carrying the league params over. */
export function resolveLegacyRedirect(
  routeName: string,
  params: { leagueId: string; leagueName: string } & Record<string, unknown>,
): LegacyRedirect | null {
  if (!isLegacyRedirectRoute(routeName)) return null;
  const target = TARGETS[routeName];
  return { name: target.name, params: { ...params, ...target.extra } };
}

const GM_PLAN_TABS: readonly GmPlanTab[] = ['overview', 'trades', 'core', 'watching'];

/** Validates a GM Plan `initialTab` param, defaulting to Overview. */
export function normalizeGmPlanTab(value: unknown): GmPlanTab {
  return GM_PLAN_TABS.includes(value as GmPlanTab) ? (value as GmPlanTab) : 'overview';
}

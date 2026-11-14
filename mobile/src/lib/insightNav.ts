import { insightTarget, type InsightKey } from './insightLinks.ts';

/**
 * App navigation for an insight (lib/insightLinks.ts decides the page/metric;
 * this maps it to this app's screens and params). Mirrors web's
 * lib/insightHref.ts so a stat opens the same place on both platforms.
 */
export type InsightRoute = { screen: string; params: Record<string, unknown> };

export function insightRoute(key: InsightKey, leagueId: string, leagueName: string): InsightRoute {
  const target = insightTarget(key);
  const base = { leagueId, leagueName };
  switch (target.page) {
    case 'league-rankings':
      return { screen: 'Teams', params: target.metric ? { ...base, metric: target.metric } : base };
    case 'alerts':
      return { screen: 'Alerts', params: base };
    case 'my-team':
      return { screen: 'MyTeam', params: base };
    case 'gm-plan':
      return { screen: 'GmPlan', params: base };
    case 'league-recaps':
      return { screen: 'Recap', params: base };
  }
}

/** `onPress` handler for an insight, given any `navigate(screen, params)` function. */
export function openInsight(
  navigate: (screen: string, params?: object) => void,
  key: InsightKey,
  leagueId: string,
  leagueName: string,
): () => void {
  return () => {
    const { screen, params } = insightRoute(key, leagueId, leagueName);
    navigate(screen, params);
  };
}

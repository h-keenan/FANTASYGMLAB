/**
 * GM orb "Where to go" search: the tabs of the multi-tab screens, each its own
 * searchable destination ("Draft Center > Scouting") that opens that exact tab.
 * Web twin: the `tabs` of web-next/src/lib/navDestinations.ts (a web test pins
 * the labels; tabs open through `?tab=` there and route params here).
 *
 * Pure data + search, no react-native imports, so it runs under node:test.
 * `params` are the route params the screen reads for its tab (checked against
 * RootNavigator.tsx by orbTabs.test.ts). The normal (non-search) menu never
 * lists tabs.
 */
export interface OrbTab {
  label: string;
  subtitle: string;
  /** Extra search terms beyond the label. */
  keywords?: string[];
  /** Tab param(s) merged into the league params. */
  params?: Record<string, string>;
  /** Own screen instead of the parent's (Trade Hub > History). */
  route?: string;
  /** Own screen that needs no league. Only meaningful with `route`. */
  needsLeague?: boolean;
  /** Defaults to the page's own `pro` flag. */
  pro?: boolean;
}

/** Keyed by the parent destination's route. */
/* prettier-ignore */
export const ORB_TABS: Readonly<Record<string, readonly OrbTab[]>> = {
  Trades: [
    { label: 'Hub', subtitle: 'Trade ideas built for your roster', keywords: ['trade ideas', 'trade block', 'offers'], params: { initialTab: 'block' } },
    { label: 'Finder', subtitle: 'Shop a player or pick and see what partners pay', keywords: ['trade finder', 'shop', 'search', 'partners'], params: { initialTab: 'search' }, pro: true },
    { label: 'Analyzer', subtitle: 'Grade any deal against your lineup', keywords: ['trade analyzer', 'calculator', 'make a trade', 'grade', 'evaluate'], params: { initialTab: 'make' } },
    { label: 'History', subtitle: 'Trades you have shared and confirmed', keywords: ['trade history', 'past trades'], route: 'TradeHistory', needsLeague: false },
  ],
  Teams: [
    { label: 'Rankings', subtitle: 'Power rankings across the league', keywords: ['power rankings', 'teams'], params: { initialTab: 'rankings' } },
    { label: 'Playoff Odds', subtitle: "Every team's chance at the playoffs", keywords: ['playoffs', 'odds', 'chance', 'seeding'], params: { initialTab: 'playoff' }, pro: true },
  ],
  DraftCenter: [
    { label: 'Overview', subtitle: 'Draft posture and pick decisions', keywords: ['posture', 'capital'], params: { tab: 'overview' } },
    { label: 'Picks', subtitle: 'Every pick you own', keywords: ['draft picks', 'order'], params: { tab: 'picks' } },
    { label: 'Scouting', subtitle: 'Grade incoming prospects', keywords: ['college', 'prospects', 'rookies'], params: { tab: 'scouting' } },
  ],
  GmPlan: [
    { label: 'Overview', subtitle: 'Stance, roadmap, and plan snapshot', keywords: ['stance', 'roadmap', 'rebuild', 'compete'], params: { initialTab: 'overview' } },
    { label: 'Trades', subtitle: 'Trade moves your plan calls for', keywords: ['trade window'], params: { initialTab: 'trades' } },
    { label: 'Core', subtitle: 'Players your plan is built around', keywords: ['protected', 'keep'], params: { initialTab: 'core' } },
    { label: 'Watching', subtitle: 'Players you are targeting', keywords: ['targets', 'gm targets', 'watchlist'], params: { initialTab: 'watching' } },
  ],
  Waivers: [
    { label: 'Recommended', subtitle: 'Ranked pickups for your roster', keywords: ['adds', 'faab', 'pickups'], params: { tab: 'recommended' } },
    { label: 'Explore', subtitle: 'Browse every free agent', keywords: ['free agents', 'search'], params: { tab: 'explore' } },
    { label: 'Watchlist', subtitle: 'Free agents you are tracking', keywords: ['targets', 'tracking'], params: { tab: 'watchlist' } },
  ],
  Recap: [
    { label: 'Roundup', subtitle: 'Your lineup vs the best possible one, and what you left on the bench', keywords: ['bench', 'optimal lineup', 'weekly roundup', 'bench regret', 'missed swaps'], params: { initialTab: 'roundup' } },
  ],
  Games: [
    { label: 'Season Sim', subtitle: 'Season simulator', keywords: ['simulator', 'simulation', 'playoff odds', 'what if'], params: { tab: 'sim' } },
    { label: "Pick'em", subtitle: "Weekly pick'em in your league", keywords: ['pickem', 'picks', 'weekly'], params: { tab: 'pickem' } },
  ],
};

export interface OrbSearchable {
  label: string;
  subtitle: string;
  route: string;
  needsLeague?: boolean;
  pro?: boolean;
}

/** A search hit: the page itself (`tab` unset) or one of its tabs. */
export interface OrbSearchHit<D extends OrbSearchable> {
  key: string;
  destination: D;
  tab?: OrbTab;
  /** "Page" or "Page > Tab". */
  label: string;
  subtitle: string;
  route: string;
  needsLeague: boolean;
  pro: boolean;
  /** Extra route params for a tab hit. */
  params?: Record<string, string>;
}

/** Every token of the query must appear (so "draft center picks" finds Picks). */
export function searchOrbDestinations<D extends OrbSearchable>(destinations: readonly D[], rawQuery: string): OrbSearchHit<D>[] {
  const tokens = rawQuery.toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return [];
  const matches = (text: string) => {
    const hay = text.toLowerCase();
    return tokens.every((token) => hay.includes(token));
  };
  const pageMatches = new Set(destinations.filter((d) => matches(`${d.label} ${d.subtitle}`)).map((d) => d.route));
  const hits: OrbSearchHit<D>[] = [];
  const seen = new Set<string>();
  for (const destination of destinations) {
    if (pageMatches.has(destination.route) && !seen.has(destination.route)) {
      seen.add(destination.route);
      hits.push({
        key: destination.route,
        destination,
        label: destination.label,
        subtitle: destination.subtitle,
        route: destination.route,
        needsLeague: Boolean(destination.needsLeague),
        pro: Boolean(destination.pro),
      });
    }
    for (const tab of ORB_TABS[destination.route] ?? []) {
      const route = tab.route ?? destination.route;
      const key = `${route}:${tab.label}`;
      // A tab that is just another page row (Trade Hub > History) yields to it.
      if (seen.has(key) || (tab.route && pageMatches.has(tab.route))) continue;
      if (!matches(`${destination.label} ${tab.label} ${(tab.keywords ?? []).join(' ')}`)) continue;
      seen.add(key);
      hits.push({
        key,
        destination,
        tab,
        label: `${destination.label} > ${tab.label}`,
        subtitle: tab.subtitle,
        route,
        needsLeague: tab.route ? Boolean(tab.needsLeague) : Boolean(destination.needsLeague),
        pro: tab.pro ?? Boolean(destination.pro),
        params: tab.params,
      });
    }
  }
  return hits;
}

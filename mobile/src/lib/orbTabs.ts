/**
 * GM orb "Where to go" search: the tabs of the multi-tab screens, each its own
 * searchable destination ("Draft Center > Scouting") that opens that exact tab.
 * Tab labels, subtitles, keywords and Pro flags come from lib/navCatalog.ts, the
 * one list shared byte-for-byte with web (tabs open through `?tab=` there and
 * route params here).
 *
 * Pure data + search, no react-native imports, so it runs under node:test.
 * `params` are the route params the screen reads for its tab (checked against
 * RootNavigator.tsx by orbTabs.test.ts). The normal (non-search) menu never
 * lists tabs.
 */
import { NAV_PAGES } from './navCatalog.ts';

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

/** The app route each catalog page (lib/navCatalog.ts, shared with web) opens. */
export const ROUTE_BY_PAGE: Readonly<Record<string, string>> = {
  dashboard: 'Dashboard',
  alerts: 'Alerts',
  'my-team': 'MyTeam',
  matchup: 'Matchup',
  waivers: 'Waivers',
  'league-rankings': 'Teams',
  players: 'Players',
  'trade-hub': 'Trades',
  'gm-plan': 'GmPlan',
  'draft-center': 'DraftCenter',
  'live-draft': 'LiveDraft',
  'league-recaps': 'Recap',
  games: 'Games',
  commissioner: 'Commissioner',
  portfolio: 'Portfolio',
  'gm-game': 'GmGame',
  news: 'News',
  community: 'Community',
};

interface TabTarget {
  params?: Record<string, string>;
  route?: string;
  needsLeague?: boolean;
}

/** Where each catalog tab opens in the app: route params the screen reads
 * for its tab, or its own screen. Keyed by page key, then tab label. */
/* prettier-ignore */
const TAB_TARGETS: Readonly<Record<string, Readonly<Record<string, TabTarget>>>> = {
  'trade-hub': {
    Hub: { params: { initialTab: 'block' } },
    Finder: { params: { initialTab: 'search' } },
    Analyzer: { params: { initialTab: 'make' } },
    History: { route: 'TradeHistory', needsLeague: false },
  },
  'league-rankings': {
    Rankings: { params: { initialTab: 'rankings' } },
    'Playoff Odds': { params: { initialTab: 'playoff' } },
  },
  'draft-center': {
    Overview: { params: { tab: 'overview' } },
    Picks: { params: { tab: 'picks' } },
    Scouting: { params: { tab: 'scouting' } },
  },
  'gm-plan': {
    Overview: { params: { initialTab: 'overview' } },
    Trades: { params: { initialTab: 'trades' } },
    Core: { params: { initialTab: 'core' } },
    Watching: { params: { initialTab: 'watching' } },
    'Season Outlook': { route: 'FantasySim' },
  },
  waivers: {
    Recommended: { params: { tab: 'recommended' } },
    Explore: { params: { tab: 'explore' } },
    Watchlist: { params: { tab: 'watchlist' } },
  },
  'league-recaps': { Roundup: { params: { initialTab: 'roundup' } } },
  games: {
    'Season Sim': { params: { tab: 'sim' } },
    "Pick'em": { params: { tab: 'pickem' } },
  },
};

/** Keyed by the parent destination's route; built from the shared catalog. */
export const ORB_TABS: Readonly<Record<string, readonly OrbTab[]>> = Object.fromEntries(
  NAV_PAGES.filter((page) => page.tabs?.length).map((page) => [
    ROUTE_BY_PAGE[page.key],
    page.tabs!.map((tab): OrbTab => {
      const target = TAB_TARGETS[page.key]?.[tab.label] ?? {};
      return {
        label: tab.label,
        subtitle: tab.subtitle,
        keywords: tab.keywords ? [...tab.keywords] : undefined,
        pro: tab.pro,
        ...target,
      };
    }),
  ]),
);

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

/**
 * Mobile adapter for lib/pageFamilies.ts (the byte-identical twin of web's family strip data): turns a family tab
 * into the app screen that shows it, so every member screen can render the same single tab row as web's PageTabBar.
 *
 * Pure data (no react-native imports) so it runs under node:test. Imported (ESPN/Fleaflicker/MFL) leagues only
 * get the tabs whose screen they can open (lib/leaguePlatform.ts ESPN_SUPPORTED_ROUTES), so a tab never opens onto
 * "Not available".
 */
import { PAGE_TAB_FAMILIES, pageTabFamily, type PageTabDef, type PageTabFamilyKey } from './pageFamilies.ts';
import { espnRouteSupported, isEspnLeagueId } from './leaguePlatform.ts';
import type { TabIconName } from './tabIcons.ts';

export type FamilyRoute = { name: string; params?: Record<string, unknown> };

/** The Trades host screen shows Hub / Finder / Analyzer itself; Trade History is a separate screen. */
const TRADES_HOST_TAB: Record<string, 'block' | 'search' | 'make'> = {
  trade_hub: 'block',
  trade_finder: 'search',
  trade_analyzer: 'make',
};

export function familyRoute(tab: PageTabDef, leagueId: string, leagueName: string): FamilyRoute {
  const base = { leagueId, leagueName };
  switch (tab.key) {
    case 'trade_hub':
    case 'trade_finder':
    case 'trade_analyzer':
      return { name: 'Trades', params: { ...base, initialTab: TRADES_HOST_TAB[tab.key] } };
    case 'trade_history':
      return { name: 'TradeHistory' };
    case 'roster':
      return { name: 'MyTeam', params: base };
    case 'players':
      return { name: 'Players', params: base };
    case 'waivers':
      return { name: 'Waivers', params: base };
    case 'matchup':
      return { name: 'Matchup', params: base };
    case 'rankings':
      return { name: 'Teams', params: base };
    case 'recaps':
      return { name: 'Recap', params: base };
    case 'games':
      return { name: 'Games', params: base };
    default:
      return { name: 'Dashboard', params: base };
  }
}

export type FamilyTabOption = { key: string; label: string; glyph: TabIconName };

/** The strip's options for a league: all tabs for Sleeper, only openable ones for imported leagues. */
export function familyTabOptions(family: PageTabFamilyKey, leagueId: string): FamilyTabOption[] {
  const imported = isEspnLeagueId(leagueId);
  return pageTabFamily(family)
    .tabs.filter((tab) => {
      if (!imported) return true;
      // The Trades host only has Trade Analyzer for imported leagues (Hub and Finder need Sleeper data).
      if (family === 'trades') return tab.key === 'trade_analyzer';
      return espnRouteSupported(familyRoute(tab, leagueId, '').name);
    })
    .map((tab) => ({ key: tab.key, label: tab.label, glyph: tab.glyph as TabIconName }));
}

/** Every family tab key, for tests. */
export function allFamilyTabKeys(): string[] {
  return PAGE_TAB_FAMILIES.flatMap((f) => f.tabs.map((t) => t.key));
}

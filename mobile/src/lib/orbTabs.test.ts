// Run with: node --experimental-strip-types --test src/lib/orbTabs.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { ORB_TABS, ROUTE_BY_PAGE, searchOrbDestinations } from './orbTabs.ts';
import { NAV_PAGES } from './navCatalog.ts';

const here = dirname(fileURLToPath(import.meta.url));
const read = (...p: string[]) => readFileSync(join(here, '..', ...p), 'utf8');
const navigator = read('navigation', 'RootNavigator.tsx');
const orb = read('components', 'GmOrb.tsx');

// Screen file per parent route, and the tab values it accepts for each param.
const SCREEN: Record<string, string> = {
  Trades: 'TradesScreen', Teams: 'TeamsScreen', DraftCenter: 'DraftCenterScreen',
  GmPlan: 'GmPlanScreen', Waivers: 'WaiversScreen', Games: 'GamesScreen', Dashboard: 'DashboardScreen',
  Players: 'PlayersScreen', News: 'NewsScreen',
};

test('every tab opens a registered route, with a param the route accepts', () => {
  for (const [parent, tabs] of Object.entries(ORB_TABS)) {
    assert.ok(Object.values(ROUTE_BY_PAGE).includes(parent), `${parent} is a GM orb destination`);
    const screen = read('screens', `${SCREEN[parent]}.tsx`);
    for (const tab of tabs) {
      const route = tab.route ?? parent;
      assert.match(navigator, new RegExp(`AppStack\\.Screen\\s+name="${route}"`), `${parent} > ${tab.label}`);
      const decl = navigator.match(new RegExp(`^  ${route}: ([^\\n]*(?:\\n(?!  \\w+:)[^\\n]*)*)`, 'm'));
      assert.ok(decl, `${route} param list`);
      for (const [key, value] of Object.entries(tab.params ?? {})) {
        assert.match(decl![1], new RegExp(`${key}\\?: [^;]*'${value}'`), `${parent} > ${tab.label}: ${key}='${value}' in RootStackParamList`);
        assert.ok(screen.includes(`'${value}'`), `${SCREEN[parent]} knows tab '${value}'`);
      }
    }
  }
});

test('the orb lists no tab rows outside search (the menu stays one row per page)', () => {
  assert.ok(!/ORB_TABS/.test(orb), 'GmOrb only reaches tabs through searchOrbDestinations');
});

const pages = [
  { label: 'Waivers', route: 'Waivers', subtitle: 'Top adds, trends, and free agents', needsLeague: true },
  { label: 'League Rankings', route: 'Teams', subtitle: 'Power rankings and playoff odds', needsLeague: true },
  { label: 'Trade Hub', route: 'Trades', subtitle: 'Trade ideas, trade finder, and trade analyzer', needsLeague: true },
  { label: 'Draft', route: 'DraftCenter', subtitle: 'Picks, draft tools, and the live draft room', needsLeague: true, pro: true },
  { label: 'Today', route: 'Dashboard', subtitle: 'Personalized insights, recommendations, and alerts', needsLeague: true },
  { label: 'Players', route: 'Players', subtitle: 'Search, rankings, player insights, and college prospects', needsLeague: true },
  { label: 'Games', route: 'Games', subtitle: "Season simulator and weekly pick'em", needsLeague: true },
  { label: 'News', route: 'News', subtitle: "NFL news and your league's weekly recap" },
];
const labels = (q: string) => searchOrbDestinations(pages, q).map((h) => h.label);

test('search finds tabs by label and keyword, shown as "Page > Tab"', () => {
  assert.ok(labels('scouting').includes('Players > Prospects'));
  assert.ok(labels('finder').includes('Trade Hub > Finder'));
  assert.ok(labels('pickem').includes("Games > Pick'em"));
  assert.ok(labels('bench regret').includes('News > My League'));
  assert.ok(labels('playoff odds').includes('League Rankings > Playoff Odds'));
  assert.deepEqual(labels('draft live room'), ['Draft', 'Draft > Live room']);
  assert.deepEqual(labels('  '), []);
});

test('a tab hit carries its params; the page hit carries none', () => {
  const live = searchOrbDestinations(pages, 'live room').find((h) => h.tab?.label === 'Live room')!;
  assert.equal(live.route, 'DraftCenter');
  assert.deepEqual(live.params, { tab: 'live' });
  const odds = searchOrbDestinations(pages, 'playoff odds').find((h) => h.tab)!;
  assert.deepEqual(odds.params, { initialTab: 'playoff' });
  const page = searchOrbDestinations(pages, 'draft').find((h) => !h.tab)!;
  assert.equal(page.params, undefined);
});

test('Pro and needsLeague follow the page unless the tab overrides', () => {
  const find = (q: string, label: string) => searchOrbDestinations(pages, q).find((h) => h.label === label)!;
  assert.equal(find('live room', 'Draft > Live room').pro, true);
  assert.equal(find('live room', 'Draft > Live room').needsLeague, true);
  assert.equal(find('scouting', 'Players > Prospects').pro, true);
  assert.equal(find('finder', 'Trade Hub > Finder').pro, true);
  assert.equal(find('analyzer', 'Trade Hub > Grade a trade').pro, false);
  assert.equal(find('playoff odds', 'League Rankings > Playoff Odds').pro, true);
  const history = find('past trades', 'Trade Hub > History');
  assert.equal(history.route, 'TradeHistory');
  assert.equal(history.needsLeague, false);
});

test('no league pages means no tab hits (callers pass only reachable pages)', () => {
  assert.deepEqual(searchOrbDestinations([pages[4]], 'scouting'), []);
});

test('every catalog page has an app route registered in the navigator and an orb icon', () => {
  for (const page of NAV_PAGES) {
    const route = ROUTE_BY_PAGE[page.key];
    assert.ok(route, `${page.key} has a route`);
    assert.match(navigator, new RegExp(`AppStack\\.Screen\\s+name="${route}"`), `${page.key} -> ${route}`);
    assert.ok(orb.includes(`'${page.key}':`) || orb.includes(`  ${page.key}:`), `${page.key} has an orb icon`);
  }
});

test('Trade History, College Scouting and Playoff Odds are tabs, not menu pages', () => {
  const labels = NAV_PAGES.map((p) => p.label);
  for (const tabOnly of ['Trade History', 'College Scouting', 'Playoff Odds', 'Trade Finder', 'Trade Analyzer', 'Alerts', 'Live Draft', 'League Recaps', 'Portfolio']) {
    assert.ok(!labels.includes(tabOnly), tabOnly);
  }
  assert.ok(ORB_TABS.Trades.some((t) => t.label === 'History' && t.route === 'TradeHistory'));
});

test('the season simulation is a GM Plan tab, not its own orb destination', () => {
  assert.ok(!('fantasy-sim' in ROUTE_BY_PAGE));
  assert.ok(!NAV_PAGES.some((p) => p.key === 'fantasy-sim'));
  const tab = ORB_TABS.GmPlan.find((t) => t.label === 'Season Outlook');
  assert.equal(tab?.route, 'FantasySim');
});

test('retired pages are tabs/sections reached through the orb search, and the pages total 14', () => {
  assert.equal(NAV_PAGES.length, 14);
  for (const retired of ['alerts', 'live-draft', 'league-recaps', 'portfolio']) assert.ok(!(retired in ROUTE_BY_PAGE), retired);
  const hit = (q: string, label: string) => searchOrbDestinations(pages, q).find((h) => h.label === label)!;
  assert.deepEqual(hit('alerts', 'Today > Alerts').params, { focus: 'alerts' });
  assert.deepEqual(hit('college scouting', 'Players > Prospects').params, { tab: 'prospects' });
  assert.deepEqual(hit('live draft', 'Draft > Live room').params, { tab: 'live' });
  assert.deepEqual(hit('recap', 'News > My League').params, { initialTab: 'league' });
  assert.deepEqual(hit('nfl', 'News > NFL').params, { initialTab: 'nfl' });
});

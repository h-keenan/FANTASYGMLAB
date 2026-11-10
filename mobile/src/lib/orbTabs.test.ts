// Run with: node --experimental-strip-types --test src/lib/orbTabs.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { ORB_TABS, searchOrbDestinations } from './orbTabs.ts';

const here = dirname(fileURLToPath(import.meta.url));
const read = (...p: string[]) => readFileSync(join(here, '..', ...p), 'utf8');
const navigator = read('navigation', 'RootNavigator.tsx');
const orb = read('components', 'GmOrb.tsx');

// Screen file per parent route, and the tab values it accepts for each param.
const SCREEN: Record<string, string> = {
  Trades: 'TradesScreen', Teams: 'TeamsScreen', DraftCenter: 'DraftCenterScreen',
  GmPlan: 'GmPlanScreen', Waivers: 'WaiversScreen', Games: 'GamesScreen', Recap: 'RecapScreen',
};

test('every tab opens a registered route, with a param the route accepts', () => {
  for (const [parent, tabs] of Object.entries(ORB_TABS)) {
    assert.ok(orb.includes(`route: '${parent}'`), `${parent} is a GM orb destination`);
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
  { label: 'Draft Center', route: 'DraftCenter', subtitle: 'Picks, order, and draft tools', needsLeague: true, pro: true },
  { label: 'Games', route: 'Games', subtitle: "Season simulator and weekly pick'em", needsLeague: true },
  { label: 'League Recaps', route: 'Recap', subtitle: 'Weekly league recap, stories, and your lineup roundup', needsLeague: true },
  { label: 'Portfolio', route: 'Portfolio', subtitle: 'Your standing across every saved league' },
];
const labels = (q: string) => searchOrbDestinations(pages, q).map((h) => h.label);

test('search finds tabs by label and keyword, shown as "Page > Tab"', () => {
  assert.ok(labels('scouting').includes('Draft Center > Scouting'));
  assert.ok(labels('finder').includes('Trade Hub > Finder'));
  assert.ok(labels('pickem').includes("Games > Pick'em"));
  assert.ok(labels('bench regret').includes('League Recaps > Roundup'));
  assert.ok(labels('playoff odds').includes('League Rankings > Playoff Odds'));
  assert.deepEqual(labels('draft center scouting'), ['Draft Center > Scouting']);
  assert.deepEqual(labels('  '), []);
});

test('a tab hit carries its params; the page hit carries none', () => {
  const scouting = searchOrbDestinations(pages, 'scouting').find((h) => h.tab?.label === 'Scouting')!;
  assert.equal(scouting.route, 'DraftCenter');
  assert.deepEqual(scouting.params, { tab: 'scouting' });
  const odds = searchOrbDestinations(pages, 'playoff odds').find((h) => h.tab)!;
  assert.deepEqual(odds.params, { initialTab: 'playoff' });
  const page = searchOrbDestinations(pages, 'draft').find((h) => !h.tab)!;
  assert.equal(page.params, undefined);
});

test('Pro and needsLeague follow the page unless the tab overrides', () => {
  const find = (q: string, label: string) => searchOrbDestinations(pages, q).find((h) => h.label === label)!;
  assert.equal(find('scouting', 'Draft Center > Scouting').pro, true);
  assert.equal(find('scouting', 'Draft Center > Scouting').needsLeague, true);
  assert.equal(find('finder', 'Trade Hub > Finder').pro, true);
  assert.equal(find('analyzer', 'Trade Hub > Analyzer').pro, false);
  assert.equal(find('playoff odds', 'League Rankings > Playoff Odds').pro, true);
  const history = find('past trades', 'Trade Hub > History');
  assert.equal(history.route, 'TradeHistory');
  assert.equal(history.needsLeague, false);
});

test('no league pages means no tab hits (callers pass only reachable pages)', () => {
  assert.deepEqual(labels('portfolio'), ['Portfolio']);
  assert.deepEqual(searchOrbDestinations([pages[5]], 'scouting'), []);
});

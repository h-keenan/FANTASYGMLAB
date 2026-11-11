// Run with: node --experimental-strip-types --test src/lib/featureCatalog.test.ts
import { NAV_PAGES } from './navCatalog.ts';
import { ROUTE_BY_PAGE } from './orbTabs.ts';
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { accentFor } from './destinationAccents.generated.ts';
import { FEATURE_GROUPS, FEATURE_ITEMS, featureTarget } from './featureCatalog.ts';

const here = dirname(fileURLToPath(import.meta.url));
const navigator = readFileSync(join(here, '..', 'navigation', 'RootNavigator.tsx'), 'utf8');
const orb = readFileSync(join(here, '..', 'components', 'GmOrb.tsx'), 'utf8');
const more = readFileSync(join(here, '..', 'screens', 'MoreScreen.tsx'), 'utf8');

test('ids are unique, groups are known and none is empty', () => {
  assert.equal(new Set(FEATURE_ITEMS.map((i) => i.id)).size, FEATURE_ITEMS.length);
  const groups = new Set(FEATURE_GROUPS.map((g) => g.id));
  for (const item of FEATURE_ITEMS) assert.ok(groups.has(item.group), item.id);
  for (const g of FEATURE_GROUPS) assert.ok(FEATURE_ITEMS.some((i) => i.group === g.id), g.id);
});

test('every item opens a screen that is registered in the navigator', () => {
  for (const item of FEATURE_ITEMS) {
    assert.match(navigator, new RegExp(`AppStack\\.Screen\\s+name="${item.route}"`), `${item.id} -> ${item.route}`);
    assert.match(navigator, new RegExp(`^  ${item.route}: `, 'm'), `${item.id} param list entry`);
  }
});

test('items reuse the icon, accent color and Pro flag the GM orb gives the same screen', () => {
  for (const item of FEATURE_ITEMS) {
    // Playoff Odds is a tab of League Rankings; the orb has one League Rankings row.
    if (item.id === 'playoff-odds') continue;
    if (item.route === 'CollegeProspects') continue; // not in the orb; icon matches More's College Scouting row
    const page = NAV_PAGES.find((p) => ROUTE_BY_PAGE[p.key] === item.route);
    if (!page) continue; // Trade History is a Trade Hub tab, not a menu page
    // The orb takes each page's icon from ICON_BY_PAGE and its color from the shared accent map by label.
    assert.ok(orb.includes(`'${page.key}': '${item.icon}'`) || orb.includes(`  ${page.key}: '${item.icon}'`), `${item.id} icon`);
    assert.equal(item.color, accentFor(page.label), `${item.id} color`);
    // Trades hosts three items; only Trade Finder is Pro and the orb row is not.
    if (item.route !== 'Trades' && item.route !== 'Teams') assert.equal(Boolean(page.pro), Boolean(item.pro), `${item.id} pro`);
  }
  assert.match(more, /icon="school-outline"[\s\S]{0,80}colors\.accent[\s\S]{0,80}label="College Scouting"/);
});

test('league items need a league; others open with no params', () => {
  const league = { leagueId: 'L1', leagueName: 'Test' };
  const finder = FEATURE_ITEMS.find((i) => i.id === 'trade-finder')!;
  assert.deepEqual(featureTarget(finder, league), { name: 'Trades', params: { ...league, initialTab: 'search' } });
  assert.equal(featureTarget(finder, null), null);
  const news = FEATURE_ITEMS.find((i) => i.id === 'news')!;
  assert.deepEqual(featureTarget(news, null), { name: 'News', params: undefined });
  const waivers = FEATURE_ITEMS.find((i) => i.id === 'waivers')!;
  assert.deepEqual(featureTarget(waivers, league), { name: 'Waivers', params: league });
});

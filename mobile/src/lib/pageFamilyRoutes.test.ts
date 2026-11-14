import assert from 'node:assert/strict';
import test from 'node:test';

import { pageTabFamily } from './pageFamilies.ts';
import { allFamilyTabKeys, familyRoute, familyTabOptions } from './pageFamilyRoutes.ts';

test('every family tab maps to a real screen and never falls through to the Dashboard', () => {
  for (const key of allFamilyTabKeys()) {
    const tab = [pageTabFamily('trades'), pageTabFamily('team'), pageTabFamily('league')].flatMap((f) => f.tabs).find((t) => t.key === key)!;
    assert.notEqual(familyRoute(tab, 'L1', 'League').name, 'Dashboard', key);
  }
});

test('Trades hub/finder/analyzer open the Trades host on the matching tab; history is its own screen', () => {
  const tabs = pageTabFamily('trades').tabs;
  assert.deepEqual(familyRoute(tabs[1], 'L1', 'N').params?.initialTab, 'search');
  assert.deepEqual(familyRoute(tabs[2], 'L1', 'N').params?.initialTab, 'make');
  assert.equal(familyRoute(tabs[3], 'L1', 'N').name, 'TradeHistory');
});

test('a Sleeper league gets the whole strip, an imported league only the screens it can open', () => {
  assert.equal(familyTabOptions('team', '123').length, 4);
  assert.deepEqual(familyTabOptions('team', 'espn:1:2026').map((o) => o.key), ['roster', 'players', 'matchup']);
  assert.deepEqual(familyTabOptions('league', 'espn:1:2026').map((o) => o.key), ['rankings']);
  assert.deepEqual(familyTabOptions('trades', 'espn:1:2026').map((o) => o.key), ['trade_analyzer']);
});

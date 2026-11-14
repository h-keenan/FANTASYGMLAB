// Run with: node --experimental-strip-types --test src/lib/insightNav.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { INSIGHT_TARGETS, type InsightKey } from './insightLinks.ts';
import { insightRoute, openInsight } from './insightNav.ts';

test('the Roster Age insight opens the Teams screen on the age board', () => {
  assert.deepEqual(insightRoute('age', 'L1', 'My League'), {
    screen: 'Teams',
    params: { leagueId: 'L1', leagueName: 'My League', metric: 'age' },
  });
});

test('every insight resolves to a registered screen with league params', () => {
  const screens = new Set(['Teams', 'Alerts', 'MyTeam', 'GmPlan', 'Recap']);
  for (const key of Object.keys(INSIGHT_TARGETS) as InsightKey[]) {
    const route = insightRoute(key, 'L1', 'N');
    assert.ok(screens.has(route.screen), key);
    assert.equal(route.params.leagueId, 'L1');
  }
});

test('openInsight navigates when pressed', () => {
  const calls: Array<[string, object | undefined]> = [];
  openInsight((screen, params) => calls.push([screen, params]), 'injury', 'L1', 'N')();
  assert.deepEqual(calls, [['Alerts', { leagueId: 'L1', leagueName: 'N' }]]);
});

// Run with: node --experimental-strip-types --test src/lib/simLayout.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SIM_ASSET_ALL,
  SIM_REVIEW_VIEWS,
  simAdvanceState,
  simAutoSetMessage,
  simFilterGroups,
  simGroupByPosition,
  simLineupDiff,
  simOpenKey,
  simParseOpen,
  simPreview,
  simReviewViewFor,
  simSeeAllLabel,
  simSideSummary,
  simTradeFit,
  simWindow,
} from './simLayout.ts';

test('open state keys and parsing', () => {
  assert.equal(simOpenKey('home.injuries'), 'fgl:sim-open:home.injuries');
  assert.equal(simParseOpen('1', false), true);
  assert.equal(simParseOpen('0', true), false);
  assert.equal(simParseOpen(null, true), true);
});

test('previews and windows long lists', () => {
  assert.deepEqual(simPreview([1, 2, 3, 4, 5], false, 3), { shown: [1, 2, 3], hidden: 2 });
  assert.equal(simPreview([1, 2], false, 3).hidden, 0);
  assert.equal(simSeeAllLabel(2, false, 'players'), 'See all (2 players)');
  assert.equal(simSeeAllLabel(2, true), 'Show less');
  assert.equal(simWindow(Array.from({ length: 50 }, (_, i) => i), 20).remaining, 30);
});

test('every review section lands on a tab', () => {
  const tabs = new Set(SIM_REVIEW_VIEWS.map((v) => v.value));
  for (const id of ['grade', 'decisions', 'moves', 'swings', 'injuries', 'champion-path', 'your-path', 'journey', 'stats', 'leaders', 'your-leaders', 'closest-yours', 'closest-league']) {
    assert.ok(tabs.has(simReviewViewFor(id)));
  }
  assert.equal(simReviewViewFor('swings'), 'awards');
  assert.equal(simReviewViewFor('mystery'), 'overview');
});

test('trade picker groups, filters and fit', () => {
  const roster = [
    { id: '1', name: 'Quinn Back', pos: 'QB', value: 80 },
    { id: '2', name: 'Ray Runner', pos: 'RB', value: 60.4 },
    { id: '3', name: 'Rob Rush', pos: 'RB', value: 40 },
  ];
  const groups = simGroupByPosition(roster, ['QB', 'RB', 'WR']);
  assert.deepEqual(groups.map((g) => [g.key, g.items.length]), [['QB', 1], ['RB', 2]]);
  assert.deepEqual(simFilterGroups(groups, SIM_ASSET_ALL, 'rush').map((g) => g.items[0].id), ['3']);
  assert.deepEqual(simSideSummary(roster.slice(0, 2)), { count: 2, value: 140 });
  assert.deepEqual(simTradeFit(16, 16, 1, 3), { after: 18, room: 0, over: 2 });
});

test('auto-set message and advance state', () => {
  const a = (id: string, name: string) => ({ id, name });
  const before = [{ slot: 'RB', player: a('2', 'Hurt Harry') }];
  const after = [{ slot: 'RB', player: a('3', 'Wally Wire') }];
  assert.equal(simAutoSetMessage(simLineupDiff(before, after, 100, 107.54)), 'Swapped Hurt Harry for Wally Wire, +7.5 proj');
  assert.equal(simAutoSetMessage(simLineupDiff(after, after, 1, 1)), 'Lineup is optimal');
  assert.equal(simAdvanceState({ phase: 'regular_season', week: 4 }, 1).reason, 'Fill 1 empty slot');
  assert.equal(simAdvanceState({ phase: 'regular_season', week: 4, pending: { cuts_needed: 2 } }, 0).reason, 'Cut 2 players first');
});

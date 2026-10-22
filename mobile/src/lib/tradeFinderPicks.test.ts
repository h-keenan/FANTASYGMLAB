// Run with: node --experimental-strip-types --test src/lib/tradeFinderPicks.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { TRADE_FINDER_MAX_PICKS, ownedPicksForRoster, toggleCappedSelection } from './tradeFinderPicks.ts';

const picks = [
  { pick_id: '2028:1:1', owner_roster_id: '1', season: 2028, round: 1 },
  { pick_id: '2027:2:4', owner_roster_id: '1', season: 2027, round: 2 },
  { pick_id: '2027:1:1', owner_roster_id: '1', season: 2027, round: 1 },
  { pick_id: '2027:1:2', owner_roster_id: '2', season: 2027, round: 1 },
];

test('ownedPicksForRoster keeps only the roster owner picks, earliest first', () => {
  assert.deepEqual(
    ownedPicksForRoster(picks, '1').map((p) => p.pick_id),
    ['2027:1:1', '2027:2:4', '2028:1:1'],
  );
});

test('ownedPicksForRoster returns nothing without a known roster id', () => {
  assert.deepEqual(ownedPicksForRoster(picks, ''), []);
  assert.deepEqual(ownedPicksForRoster(picks, undefined), []);
});

test('toggleCappedSelection adds, removes, and refuses past the cap', () => {
  let selected = new Set<string>();
  for (let i = 0; i < TRADE_FINDER_MAX_PICKS + 2; i += 1) selected = toggleCappedSelection(selected, `p${i}`);
  assert.equal(selected.size, TRADE_FINDER_MAX_PICKS);
  assert.ok(!selected.has(`p${TRADE_FINDER_MAX_PICKS}`));
  selected = toggleCappedSelection(selected, 'p0');
  assert.ok(!selected.has('p0'));
  assert.equal(selected.size, TRADE_FINDER_MAX_PICKS - 1);
});

// Run with: node --experimental-strip-types --test src/lib/draftSignals.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { cardRows, seeAllLabel, signalPills, strategyTone, visibleSignalRows } from './draftSignals.ts';

const ranks = { draft_rank: 10, draft_rank_tied: false, future_rank: 10, future_rank_tied: false };

test('equal draft and future ranks collapse into one Picks pill', () => {
  assert.deepEqual(signalPills(ranks), [{ key: 'picks', label: 'Picks #10' }]);
});

test('different ranks keep two pills; ties are marked; missing ranks are skipped', () => {
  assert.deepEqual(signalPills({ ...ranks, future_rank: 7, draft_rank_tied: true }), [
    { key: 'draft', label: 'Draft T-#10' },
    { key: 'future', label: 'Future #7' },
  ]);
  assert.deepEqual(signalPills({ ...ranks, draft_rank: null, future_rank: null }), []);
});

test('top 3 and See all (n)', () => {
  assert.deepEqual(visibleSignalRows([1, 2, 3, 4], false), [1, 2, 3]);
  assert.equal(seeAllLabel(4), 'See all (4)');
  assert.equal(seeAllLabel(3), null);
});

test('strategy tone and legacy fallback', () => {
  assert.equal(strategyTone('fringe_contender'), 'success');
  assert.equal(strategyTone('rebuild'), 'accent');
  assert.equal(cardRows({}), null);
});

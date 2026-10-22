import assert from 'node:assert/strict';
import test from 'node:test';

import { buildPlanSnapshot, deadlineWeek } from './gmPlanSnapshot.ts';

const ranking = {
  power_rank: 3,
  draft_capital_rank: 7,
  starter_rank: 3,
  bench_rank: 12,
  age_rank: 2,
  wins: 2,
  losses: 4,
  ties: 0,
};

test('builds every tile from real rows, with the seed note only when present', () => {
  const tiles = buildPlanSnapshot(ranking, 12, { playoff_probability: 55.4, median_seed: 6 });
  assert.deepEqual(
    tiles.map((t) => t.key),
    ['power', 'capital', 'odds', 'record', 'starter', 'bench', 'age'],
  );
  assert.equal(tiles[0].value, '3 of 12');
  assert.equal(tiles[2].note, 'Proj. 6-seed');
  assert.equal(tiles[3].value, '2 - 4');
  const noSeed = buildPlanSnapshot(ranking, 12, { playoff_probability: 10, median_seed: 0 });
  assert.equal(noSeed.find((t) => t.key === 'odds')?.note, undefined);
});

test('omits tiles whose data is missing', () => {
  assert.deepEqual(buildPlanSnapshot(null, 12, null), []);
  assert.equal(buildPlanSnapshot({ ...ranking, draft_capital_rank: null }, 12, null).some((t) => t.key === 'capital'), false);
});

test('deadline banner week disappears after the deadline', () => {
  assert.equal(deadlineWeek({ trade_deadline_week: 11, trade_deadline_passed: false }), 11);
  assert.equal(deadlineWeek({ trade_deadline_week: 11, trade_deadline_passed: true }), null);
  assert.equal(deadlineWeek({ trade_deadline_week: null, trade_deadline_passed: false }), null);
  assert.equal(deadlineWeek(undefined), null);
});

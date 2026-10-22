import test from 'node:test';
import assert from 'node:assert/strict';

import { applySwap, emptySlotsOf, plannerBase, sleeperLeagueUrl, slotIndexFor, winPercent } from './matchupPlanner.ts';

const player = (id: string, slot: string) => ({ player_id: id, slot, name: id }) as never;

function matchup(overrides: Record<string, unknown> = {}, live = false): never {
  return {
    ok: true,
    best_ball: false,
    my_team: {
      starters: [player('a', 'QB'), player('b', 'WR')],
      open_slots: ['FLEX'],
      real_starters: [player('c', 'QB')],
      real_empty_slots: [],
      has_live_data: live,
    },
    ...overrides,
  } as never;
}

const cand = (id: string) => ({ player: { player_id: id }, selectable: true }) as never;

test('starts from the suggested lineup and keeps open slots', () => {
  const base = plannerBase(matchup(), 'suggested')!;
  assert.deepEqual(base.slots, [
    { slot: 'QB', player_id: 'a' },
    { slot: 'WR', player_id: 'b' },
    { slot: 'FLEX', player_id: null },
  ]);
  assert.deepEqual(emptySlotsOf(base.slots), ['FLEX']);
});

test("uses Sleeper's lineup only when it is posted", () => {
  assert.equal(plannerBase(matchup(), 'actual')!.slots[0].player_id, 'a');
  assert.deepEqual(plannerBase(matchup({}, true), 'actual')!.slots, [{ slot: 'QB', player_id: 'c' }]);
});

test('is hidden for best ball', () => {
  assert.equal(plannerBase(matchup({ best_ball: true }), 'suggested'), null);
});

test('swaps a bench player in and trades places with a starter', () => {
  const slots = [
    { slot: 'RB', player_id: 'r1' },
    { slot: 'FLEX', player_id: 'w1' },
  ];
  assert.equal(applySwap(slots, 0, cand('bench'))[0].player_id, 'bench');
  assert.deepEqual(applySwap(slots, 0, cand('w1')), [
    { slot: 'RB', player_id: 'w1' },
    { slot: 'FLEX', player_id: 'r1' },
  ]);
});

test('finds lineup indexes and formats win percent and the Sleeper link', () => {
  const slots = [
    { slot: 'WR', player_id: 'x' },
    { slot: 'FLEX', player_id: null },
    { slot: 'FLEX', player_id: null },
  ];
  assert.equal(slotIndexFor(slots, player('x', 'WR'), 'WR', 0), 0);
  assert.equal(slotIndexFor(slots, 'empty', 'FLEX', 1), 2);
  assert.equal(winPercent({ available: true, probability: 0.644 }), 64);
  assert.equal(winPercent({ available: false }), null);
  assert.equal(sleeperLeagueUrl('123'), 'https://sleeper.com/leagues/123');
});

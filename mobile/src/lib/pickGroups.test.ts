// Run with: node --experimental-strip-types --test src/lib/pickGroups.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { groupPicksForList, ordinal, pickProvenance, roundGroupDefaultOpen, type GroupablePick } from './pickGroups.ts';

function pick(season: number, round: number, extra: Partial<GroupablePick> = {}): GroupablePick {
  return {
    pick_id: `${season}:${round}:${extra.original_roster_id ?? '1'}`,
    score: 100,
    season,
    round,
    original_roster_id: '1',
    owner_roster_id: '1',
    original_team_name: null,
    owner_team_name: null,
    ...extra,
  };
}

test('groups by season then round with counts, ascending', () => {
  const groups = groupPicksForList([pick(2028, 2), pick(2027, 2), pick(2027, 1), pick(2027, 2, { original_roster_id: '4' })]);
  assert.deepEqual(groups.map((g) => [g.label, g.count]), [['2027', 3], ['2028', 1]]);
  assert.deepEqual(groups[0].rounds.map((r) => [r.label, r.picks.length]), [['1st round', 1], ['2nd round', 2]]);
});

test('unknown season sorts last as Future', () => {
  const groups = groupPicksForList([{ ...pick(0, 1), season: null }, pick(2027, 1)]);
  assert.deepEqual(groups.map((g) => g.label), ['2027', 'Future']);
});

test('ordinals and provenance', () => {
  assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21].map(ordinal), ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st']);
  assert.equal(pickProvenance(pick(2027, 1)), 'Own');
  assert.equal(pickProvenance(pick(2027, 1, { original_roster_id: '2', original_team_name: 'Team X' })), 'From Team X');
  assert.equal(pickProvenance(pick(2027, 1, { owner_team_name: 'Me' }), { showOwner: true }), 'Me · Own');
});

test('default open rule', () => {
  const big = { round: 2, label: '2nd round', picks: [1, 2, 3, 4].map((i) => pick(2027, 2, { original_roster_id: String(i) })) };
  assert.equal(roundGroupDefaultOpen(big, false), false);
  assert.equal(roundGroupDefaultOpen(big, true), true);
  assert.equal(roundGroupDefaultOpen(big, false, new Set([big.picks[2].pick_id])), true);
});

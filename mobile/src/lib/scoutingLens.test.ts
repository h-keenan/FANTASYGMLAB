// Run with: node --experimental-strip-types --test src/lib/scoutingLens.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { needPositionsFrom, prospectFit, rankByFit } from './scoutingLens.ts';

const prospect = (id: string, position: string, round: number | null, year = 2027) => ({
  id, position, draft_year: year, aggregate: { avg_round_projection: round },
});
const group = (position: string, classification: string) => ({ position, classification });
const lens = {
  needPositions: needPositionsFrom([group('WR', 'short_term_need'), group('QB', 'covered')]),
  myPicks: [{ season: 2027, round: 2 }],
};

test('flags need and pick fit', () => {
  assert.deepEqual(prospectFit(prospect('a', 'WR', 2.2), lens), { needsPosition: true, pickNote: 'Fits your 2nd (2027)' });
  assert.deepEqual(prospectFit(prospect('b', 'QB', 1), lens), { needsPosition: false, pickNote: null });
  assert.equal(prospectFit(prospect('c', 'WR', null), lens).pickNote, null);
  assert.equal(prospectFit(prospect('d', 'RB', 2, 2028), lens).pickNote, null);
});

test('ranks fits first, stable otherwise', () => {
  const list = [prospect('b', 'QB', 1), prospect('n', 'WR', 3), prospect('both', 'WR', 2), prospect('z', 'TE', 4)];
  assert.deepEqual(rankByFit(list, lens).map((p) => p.id), ['both', 'n', 'b', 'z']);
});

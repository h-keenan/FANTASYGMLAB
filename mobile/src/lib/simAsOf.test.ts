// Run with: node --experimental-strip-types --test src/lib/simAsOf.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { rowsAsOf, simAsOfSeason, simDefaultStartYear } from './simAsOf.ts';

test('the sim replays the season in progress or next up; real data stops at the season before', () => {
  assert.equal(simDefaultStartYear(new Date(2026, 10, 13)), 2026);
  assert.equal(simDefaultStartYear(new Date(2027, 0, 20)), 2026);
  assert.equal(simDefaultStartYear(new Date(2027, 2, 1)), 2027);
  assert.equal(simAsOfSeason(2026), 2025);
  assert.equal(simAsOfSeason(0, new Date(2026, 10, 13)), 2025);
});

test('keeps seasons up to the cut, drops later and unplaceable rows', () => {
  const rows = [{ season: 2024, n: 'a' }, { season: 2025, n: 'b' }, { season: 2026, n: 'c' }, { season: null, n: 'd' }];
  assert.deepEqual(rowsAsOf(rows, 2025).map((r) => r.n), ['a', 'b']);
});

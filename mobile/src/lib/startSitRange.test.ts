// Run with: node --experimental-strip-types --test src/lib/startSitRange.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { formatPoints, leanLabel, rangeDisplayRows } from './startSitRange.ts';

test('lean labels', () => {
  assert.equal(leanLabel('ceiling'), 'Ceiling play');
  assert.equal(leanLabel('floor'), 'Floor play');
});

test('formatPoints uses one decimal', () => {
  assert.equal(formatPoints(12), '12.0');
});

test('rangeDisplayRows drops sides without a range and marks the favored one', () => {
  const a = { name: 'A', projected: 10, low: 5, high: 15 };
  const rows = rangeDisplayRows(
    [
      { key: 'start', label: 'Start', range: a },
      { key: 'over', label: 'Over', range: null },
    ],
    'start',
  );
  assert.equal(rows.length, 1);
  assert.equal(rows[0].favored, true);
});

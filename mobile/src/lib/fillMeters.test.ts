import assert from 'node:assert/strict';
import { test } from 'node:test';

import { rankFill, winShare } from './percentile.ts';

test('rankFill maps 1st to 1 and last to 0', () => {
  assert.equal(rankFill(1, 12), 1);
  assert.equal(rankFill(12, 12), 0);
  assert.equal(rankFill(2, 3), 0.5);
});

test('rankFill is null when unknown or out of range', () => {
  assert.equal(rankFill(null, 12), null);
  assert.equal(rankFill(3, null), null);
  assert.equal(rankFill(13, 12), null);
  assert.equal(rankFill(1, 1), null);
});

test('winShare counts ties as half and is null before games', () => {
  assert.equal(winShare(0, 0, 0), null);
  assert.equal(winShare(3, 1, 0), 0.75);
  assert.equal(winShare(1, 1, 2), 0.5);
});

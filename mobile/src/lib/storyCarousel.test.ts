// Run with: node --experimental-strip-types --test src/lib/storyCarousel.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { storyInitial, storyIsLast, storyKeyAction, storyReducer, storySegmentFill, storySwipeAction, storyTapAction } from './storyCarousel.ts';

test('moves one page at a time and clamps at both ends', () => {
  let s = storyInitial(3);
  s = storyReducer(s, { type: 'prev' });
  assert.equal(s.index, 0);
  s = storyReducer(storyReducer(s, { type: 'next' }), { type: 'next' });
  assert.equal(s.index, 2);
  assert.equal(storyIsLast(s), true);
  assert.equal(storyReducer(s, { type: 'next' }), s);
  assert.equal(storyReducer(s, { type: 'goto', index: 0 }).direction, 'prev');
  assert.equal(storyReducer(s, { type: 'count', count: 2 }).index, 1);
});

test('tap zones, swipes, keys and segments', () => {
  assert.equal(storyTapAction(10, 390), 'prev');
  assert.equal(storyTapAction(300, 390), 'next');
  assert.equal(storySwipeAction(-80, 5), 'next');
  assert.equal(storySwipeAction(80, 0), 'prev');
  assert.equal(storySwipeAction(-80, 70), null);
  assert.equal(storyKeyAction('ArrowRight'), 'next');
  assert.equal(storyKeyAction('Escape'), 'close');
  assert.deepEqual([0, 1, 2].map((i) => storySegmentFill(i, 1)), [1, 1, 0]);
});

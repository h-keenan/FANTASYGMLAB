// Run with: node --experimental-strip-types --test src/lib/swipeTabs.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { decideSwipe, lockSwipeAxis, swipeMayStart, swipeProgress, swipeTargetKey } from './swipeTabs.ts';

const start = { startX: 200, viewportWidth: 390, inHorizontalScroller: false, edgeGuard: 0 };

test('swipeMayStart: scroller blocks, edge guard only when set', () => {
  assert.equal(swipeMayStart(start), true);
  assert.equal(swipeMayStart({ ...start, inHorizontalScroller: true }), false);
  assert.equal(swipeMayStart({ ...start, startX: 4 }), true);
  assert.equal(swipeMayStart({ ...start, startX: 4, edgeGuard: 20 }), false);
});

test('lockSwipeAxis', () => {
  assert.equal(lockSwipeAxis(6, 4), 'undecided');
  assert.equal(lockSwipeAxis(-40, 10), 'horizontal');
  assert.equal(lockSwipeAxis(8, 30), 'vertical');
  assert.equal(lockSwipeAxis(30, 25), 'undecided');
});

test('decideSwipe', () => {
  assert.equal(decideSwipe(-80, 5, 0, true, true), 'next');
  assert.equal(decideSwipe(80, 5, 0, true, true), 'prev');
  assert.equal(decideSwipe(-30, 2, 0.1, true, true), 'none');
  assert.equal(decideSwipe(-30, 2, -0.8, true, true), 'next');
  assert.equal(decideSwipe(-80, 70, -1, true, true), 'none');
  assert.equal(decideSwipe(-80, 0, 0, true, false), 'none');
  assert.equal(decideSwipe(80, 0, 0, false, true), 'none');
});

test('swipeProgress', () => {
  assert.equal(swipeProgress(-195, 390, true, true), -0.5);
  assert.equal(swipeProgress(-900, 390, true, true), -1);
  assert.ok(Math.abs(swipeProgress(-390, 390, true, false) + 1 / 3) < 1e-9);
  assert.equal(swipeProgress(10, 0, true, true), 0);
});

test('swipeTargetKey', () => {
  const keys = ['a', 'b', 'c'];
  assert.equal(swipeTargetKey(keys, 'b', 'next'), 'c');
  assert.equal(swipeTargetKey(keys, 'b', 'prev'), 'a');
  assert.equal(swipeTargetKey(keys, 'c', 'next'), 'c');
  assert.equal(swipeTargetKey(keys, 'b', 'none'), 'b');
});

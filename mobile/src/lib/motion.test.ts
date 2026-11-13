// Run with: node --experimental-strip-types --test src/lib/motion.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { COUNT_MS, MAX_ANIMATED_ROWS, MAX_STAGGER_MS, MOTION_MS, confettiAllowed, countUpValue, flashDirection, motionMs, shouldAnimateList, staggerDelay } from './motion.ts';

test('durations stay in 120-300ms and reduced motion zeroes them', () => {
  const all = Object.values(MOTION_MS);
  assert.ok(Math.min(...all) >= 120 && Math.max(...all) <= 300);
  assert.ok(COUNT_MS < 500);
  assert.equal(motionMs('base', false), 240);
  assert.equal(motionMs('slow', true), 0);
});

test('stagger is capped, long lists do not animate, flash and count-up rules', () => {
  for (const count of [3, 8, 24, 100]) assert.ok(staggerDelay(count - 1, count) <= MAX_STAGGER_MS);
  assert.equal(staggerDelay(0, 5), 0);
  assert.equal(shouldAnimateList(MAX_ANIMATED_ROWS), true);
  assert.equal(shouldAnimateList(MAX_ANIMATED_ROWS + 1), false);
  assert.equal(flashDirection(10, 12), 'up');
  assert.equal(flashDirection(12, 10), 'down');
  assert.equal(flashDirection(10, 10), null);
  assert.equal(countUpValue(0, 100, 1), 100);
  assert.ok(countUpValue(0, 100, 0.5) > 50);
  assert.equal(confettiAllowed({ wonTitle: true, reduced: true }), false);
  assert.equal(confettiAllowed({ wonTitle: true, reduced: false }), true);
});

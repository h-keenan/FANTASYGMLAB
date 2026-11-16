// Run with: node --experimental-strip-types --test src/lib/motion.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { COUNT_MS, PRESS, TRANSITION_MS, pressFeedback, MAX_ANIMATED_ROWS, MAX_STAGGER_MS, MOTION_MS, confettiAllowed, countUpValue, flashDirection, motionMs, shouldAnimateList, staggerDelay } from './motion.ts';

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

test('press feedback: shrink and fade pressed, fade only under reduced motion, nothing idle or disabled', () => {
  assert.deepEqual(pressFeedback(true, false), { scale: PRESS.scale, opacity: PRESS.opacity });
  assert.deepEqual(pressFeedback(false, false), { scale: 1, opacity: 1 });
  assert.deepEqual(pressFeedback(true, false, true), { scale: 1, opacity: 1 });
  assert.deepEqual(pressFeedback(true, true), { scale: 1, opacity: PRESS.opacity });
  for (const ms of Object.values(TRANSITION_MS)) assert.ok(Object.values(MOTION_MS).includes(ms as never));
});

import { MAX_CONCURRENT_TWEENS, MAX_FLIP_ROWS, MOTION_ROLE, PROGRESS_MS, SPRING, acquireTween, activeTweenCount, flipOffset, progressScale, rankChange } from './motion.ts';

test('motion roles map onto existing durations and progress clamps', () => {
  assert.deepEqual({ ...MOTION_ROLE }, { micro: 120, standard: 180, emphasized: 300 });
  assert.equal(PROGRESS_MS, 300);
  assert.equal(progressScale(50), 0.5);
  assert.equal(progressScale(140), 1);
  assert.equal(progressScale(null), 0);
});

test('flip offsets, rank change and the tween cap', () => {
  assert.deepEqual(flipOffset({ x: 0, y: 100 }, { x: 0, y: 40 }), { dx: 0, dy: 60 });
  assert.equal(flipOffset({ x: 0, y: 100 }, { x: 0, y: 99 }), null);
  assert.equal(MAX_FLIP_ROWS, 24);
  assert.deepEqual(rankChange(5, 3), { dir: 'up', by: 2 });
  assert.deepEqual(rankChange(2, 6), { dir: 'down', by: 4 });
  assert.equal(rankChange(3, 3), null);
  const held = Array.from({ length: MAX_CONCURRENT_TWEENS }, () => acquireTween());
  assert.ok(held.every(Boolean));
  assert.equal(acquireTween(), null);
  held[0]?.();
  held[0]?.();
  assert.equal(activeTweenCount(), MAX_CONCURRENT_TWEENS - 1);
  held.slice(1).forEach((release) => release?.());
  assert.equal(activeTweenCount(), 0);
  assert.ok(SPRING.press.stiffness > SPRING.sheet.stiffness);
});

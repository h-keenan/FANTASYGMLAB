// Run with: node --experimental-strip-types --test src/lib/hapticCore.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { HAPTIC_INTENTS, HAPTIC_THROTTLE_MS, createHaptics, type HapticIntent, type HapticStep } from './hapticCore.ts';

function rig(enabled = () => true) {
  let t = 1000;
  const played: HapticStep[] = [];
  const timers: { fn: () => void; ms: number }[] = [];
  const fire = createHaptics({ driver: (s) => void played.push(s), isEnabled: enabled, now: () => t, schedule: (fn, ms) => void timers.push({ fn, ms }) });
  return { fire, played, timers, advance: (ms: number) => void (t += ms) };
}

test('the intent map matches the plan', () => {
  assert.deepEqual(HAPTIC_INTENTS.tap[0].step, { kind: 'impact', style: 'light' });
  assert.deepEqual(HAPTIC_INTENTS.select[0].step, { kind: 'selection' });
  assert.deepEqual(HAPTIC_INTENTS.commit[0].step, { kind: 'impact', style: 'medium' });
  assert.deepEqual(HAPTIC_INTENTS.snap[0].step, { kind: 'impact', style: 'rigid' });
  assert.deepEqual(HAPTIC_INTENTS.success[0].step, { kind: 'notification', type: 'success' });
  assert.deepEqual(HAPTIC_INTENTS.warn[0].step, { kind: 'notification', type: 'warning' });
  assert.deepEqual(HAPTIC_INTENTS.error[0].step, { kind: 'notification', type: 'error' });
  assert.equal(Object.keys(HAPTIC_INTENTS).length, 11);
  assert.deepEqual(HAPTIC_INTENTS.epic.map((p) => p.delayMs), [0, 120]);
});

test('an intent plays its step; the epic crescendo schedules the second hit', () => {
  const r = rig();
  r.fire('commit');
  assert.deepEqual(r.played, [{ kind: 'impact', style: 'medium' }]);
  r.advance(500);
  r.fire('epic');
  assert.equal(r.played.length, 2);
  assert.equal(r.timers[0].ms, 120);
  r.timers[0].fn();
  assert.deepEqual(r.played[2], { kind: 'notification', type: 'success' });
});

test('fires closer than the throttle are dropped', () => {
  const r = rig();
  r.fire('select');
  r.advance(HAPTIC_THROTTLE_MS - 1);
  r.fire('select');
  assert.equal(r.played.length, 1);
  r.advance(1);
  r.fire('select');
  assert.equal(r.played.length, 2);
});

test('the kill switch silences everything, including a scheduled second step', () => {
  let on = true;
  const r = rig(() => on);
  r.fire('epic');
  on = false;
  r.timers[0].fn();
  assert.equal(r.played.length, 1);
  r.advance(500);
  r.fire('tap' as HapticIntent);
  assert.equal(r.played.length, 1);
});

test('a throwing or rejecting driver never throws', () => {
  const fire = createHaptics({ driver: () => { throw new Error('no haptics'); }, isEnabled: () => true });
  assert.doesNotThrow(() => fire('success'));
  const fire2 = createHaptics({ driver: () => Promise.reject(new Error('no')), isEnabled: () => true });
  assert.doesNotThrow(() => fire2('success'));
});

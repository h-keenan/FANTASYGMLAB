// Run with: node --experimental-strip-types --test src/lib/liveScores.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { dataAgeSeconds, freshnessLabel, nextPollDelayMs, projFinalLabel, shouldPoll } from './liveScores.ts';

const noJitter = () => 0;

test('polls only when live, visible and online', () => {
  assert.equal(shouldPoll({ live: true, visible: true, online: true }), true);
  assert.equal(shouldPoll({ live: false, visible: true, online: true }), false);
  assert.equal(shouldPoll({ live: true, visible: false, online: true }), false);
  assert.equal(shouldPoll({ live: true, visible: true, online: false }), false);
});

test('clamps the server interval to 30-60s', () => {
  assert.equal(nextPollDelayMs(10, 0, undefined, noJitter), 30_000);
  assert.equal(nextPollDelayMs(500, 0, undefined, noJitter), 60_000);
  assert.equal(nextPollDelayMs(null, 0, undefined, noJitter), 30_000);
});

test('backs off exponentially, capped, honoring Retry-After', () => {
  assert.equal(nextPollDelayMs(30, 1, undefined, noJitter), 60_000);
  assert.equal(nextPollDelayMs(30, 2, undefined, noJitter), 120_000);
  assert.equal(nextPollDelayMs(30, 9, undefined, noJitter), 300_000);
  assert.equal(nextPollDelayMs(30, 0, 90, noJitter), 90_000);
});

test('labels freshness and projected final', () => {
  assert.equal(freshnessLabel(2), 'Updated just now');
  assert.equal(freshnessLabel(12), 'Updated 12s ago');
  assert.equal(freshnessLabel(190), 'Updated 3m ago');
  assert.equal(dataAgeSeconds(8, 1_000, 5_000), 12);
  assert.equal(projFinalLabel(18.44), 'Proj final 18.4');
  assert.equal(projFinalLabel(null), null);
});

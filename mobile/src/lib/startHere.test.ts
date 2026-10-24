// Run with: node --experimental-strip-types --test src/lib/startHere.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  EMPTY_START_HERE_STATE,
  START_HERE_STEPS,
  markStartHereStepDone,
  parseStartHereState,
  shouldShowStartHere,
} from './startHere.ts';

const NOW = Date.parse('2026-10-23T00:00:00Z');
const DAY = 24 * 60 * 60 * 1000;

test('three steps in order', () => {
  assert.deepEqual(START_HERE_STEPS.map((s) => s.key), ['matchup', 'trade_hub', 'waivers']);
});

test('shows only for recent accounts, hides when dismissed or done', () => {
  const recent = new Date(NOW - 2 * DAY).toISOString();
  assert.equal(shouldShowStartHere(EMPTY_START_HERE_STATE, recent, NOW), true);
  assert.equal(shouldShowStartHere(EMPTY_START_HERE_STATE, new Date(NOW - 30 * DAY).toISOString(), NOW), false);
  assert.equal(shouldShowStartHere({ dismissed: true, done: [] }, recent, NOW), false);
  let state = EMPTY_START_HERE_STATE;
  for (const step of START_HERE_STEPS) state = markStartHereStepDone(state, step.key);
  assert.equal(shouldShowStartHere(state, recent, NOW), false);
});

test('bad storage parses safely', () => {
  assert.deepEqual(parseStartHereState('{nope'), EMPTY_START_HERE_STATE);
  assert.deepEqual(parseStartHereState(JSON.stringify({ done: ['waivers', 'x'] })).done, ['waivers']);
});

test('stays identical to the web copy', () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const web = readFileSync(join(here, '../../../web-next/src/lib/startHere.ts'), 'utf8');
  const mobile = readFileSync(join(here, 'startHere.ts'), 'utf8');
  assert.equal(mobile, web);
});

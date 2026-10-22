// Run with: node --experimental-strip-types --test src/lib/seasonPhase.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { deriveSeasonPhase, isInSeason } from './seasonPhase.ts';

// Same cases as modules/gm_plan.py's derive_season_phase.
test('buckets weeks like gm_plan.derive_season_phase', () => {
  assert.equal(deriveSeasonPhase(1), 'early_season');
  assert.equal(deriveSeasonPhase(3), 'early_season');
  assert.equal(deriveSeasonPhase(4), 'trade_deadline_approach');
  assert.equal(deriveSeasonPhase(11), 'trade_deadline_approach');
  assert.equal(deriveSeasonPhase(12), 'playoff_push');
  assert.equal(deriveSeasonPhase(17), 'playoff_push');
  assert.equal(deriveSeasonPhase(10, 14), 'trade_deadline_approach');
  assert.equal(deriveSeasonPhase(11, 14), 'playoff_push');
});

test('no usable week is the offseason bucket', () => {
  for (const week of [null, undefined, 0, -1, 19, 'x', '']) {
    assert.equal(deriveSeasonPhase(week), 'offseason_adjacent', String(week));
  }
});

test('isInSeason covers the regular season and playoffs only', () => {
  assert.equal(isInSeason(1), true);
  assert.equal(isInSeason(18), true);
  assert.equal(isInSeason('7'), true);
  assert.equal(isInSeason(0), false);
  assert.equal(isInSeason(null), false);
  assert.equal(isInSeason(19), false);
});

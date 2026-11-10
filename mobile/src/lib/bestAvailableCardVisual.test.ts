// Run with: node --experimental-strip-types --test src/lib/bestAvailableCardVisual.test.ts
// (mobile has no jest/test runner configured yet — see backgroundRetry.test.ts
// for why plain Node's built-in test runner is used instead. This module
// deliberately avoids theme.ts/positionRankPrestige.ts's runtime import of
// `react-native` — see bestAvailableCardVisual.ts's doc comment for why that
// import can't be loaded outside Metro — so it's testable the same way.)
import test from 'node:test';
import assert from 'node:assert/strict';

import { bestAvailableCardVisual } from './bestAvailableCardVisual.ts';

test('tiered player with position + rank -> plain "QB1 in league" label, glow on', () => {
  const visual = bestAvailableCardVisual('gold', 'qb', 1);
  assert.equal(visual.prestigeLabel, 'QB1 in league');
  assert.equal(visual.glow, true);
  assert.equal(bestAvailableCardVisual('silver', 'WR', 3).prestigeLabel, 'WR3 in league');
  assert.equal(bestAvailableCardVisual('bronze', 'RB', 5).prestigeLabel, 'RB5 in league');
});

test('tiered player without position/rank falls back to "Top-5 at position"', () => {
  assert.equal(bestAvailableCardVisual('gold').prestigeLabel, 'Top-5 at position');
});

test('never emits the medal words', () => {
  for (const tier of ['gold', 'silver', 'bronze'] as const) {
    assert.doesNotMatch(bestAvailableCardVisual(tier, 'QB', 2).prestigeLabel ?? '', /gold|silver|bronze/i);
  }
});

test('null/undefined tier (outside the top 5 at position, or no rank at all) -> no label, no glow', () => {
  for (const tier of [null, undefined]) {
    const visual = bestAvailableCardVisual(tier);
    assert.equal(visual.prestigeLabel, null);
    assert.equal(visual.glow, false);
  }
});

test('glow is only ever true when a label is present (never a glow with no visible reason)', () => {
  for (const tier of ['gold', 'silver', 'bronze', null, undefined] as const) {
    const visual = bestAvailableCardVisual(tier);
    assert.equal(visual.glow, visual.prestigeLabel !== null);
  }
});

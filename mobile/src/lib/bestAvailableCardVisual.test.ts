// Run with: node --experimental-strip-types --test src/lib/bestAvailableCardVisual.test.ts
// (mobile has no jest/test runner configured yet — see backgroundRetry.test.ts
// for why plain Node's built-in test runner is used instead. This module
// deliberately avoids theme.ts/positionRankPrestige.ts's runtime import of
// `react-native` — see bestAvailableCardVisual.ts's doc comment for why that
// import can't be loaded outside Metro — so it's testable the same way.)
import test from 'node:test';
import assert from 'node:assert/strict';

import { bestAvailableCardVisual } from './bestAvailableCardVisual.ts';

test('gold tier -> "GOLD" label, glow on', () => {
  const visual = bestAvailableCardVisual('gold');
  assert.equal(visual.prestigeLabel, 'GOLD');
  assert.equal(visual.glow, true);
});

test('silver tier -> "SILVER" label, glow on', () => {
  const visual = bestAvailableCardVisual('silver');
  assert.equal(visual.prestigeLabel, 'SILVER');
  assert.equal(visual.glow, true);
});

test('bronze tier -> "BRONZE" label, glow on', () => {
  const visual = bestAvailableCardVisual('bronze');
  assert.equal(visual.prestigeLabel, 'BRONZE');
  assert.equal(visual.glow, true);
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

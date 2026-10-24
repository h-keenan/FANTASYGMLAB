// Run with: node --experimental-strip-types --test src/lib/overallRatingColor.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { overallRatingColor } from './percentile.ts';

// Anchors are the theme's own danger/premium/success (dark AND light differ).
const dark = { danger: '#FF4D4D', premium: '#E8B13A', success: '#22C55E', accent: '#00D4FF' };
const light = { danger: '#D92D2D', premium: '#8A6508', success: '#178A43', accent: '#0077aa' };

for (const [name, c] of [['dark', dark], ['light', light]] as const) {
  test(`overallRatingColor anchors danger/premium/success (${name})`, () => {
    const colors = c as never;
    assert.equal(overallRatingColor(0, colors).toLowerCase(), c.danger.toLowerCase());
    assert.equal(overallRatingColor(50, colors).toLowerCase(), c.premium.toLowerCase());
    assert.equal(overallRatingColor(100, colors).toLowerCase(), c.success.toLowerCase());
  });
}

test('overallRatingColor falls back to accent when unrankable', () => {
  assert.equal(overallRatingColor(null, dark as never), dark.accent);
});

test('overallRatingColor clamps out-of-range ratings', () => {
  assert.equal(overallRatingColor(150, dark as never).toLowerCase(), dark.success.toLowerCase());
});

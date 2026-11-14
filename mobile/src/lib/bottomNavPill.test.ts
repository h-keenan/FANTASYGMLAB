// Run with: node --experimental-strip-types --test src/lib/bottomNavPill.test.ts
import assert from 'node:assert/strict';
import test from 'node:test';

import { pillPrimaryCompact, pillScrollTarget, pillTabText, PILL_SCROLL_MARGIN } from './bottomNav.ts';

const four = ['Hub', 'Finder', 'Analyzer', 'History'].map((label, i) => ({ key: `k${i}`, label, ...(label === 'History' ? { short: 'Hist.' } : {}) }));
const primary = { key: 'p', label: 'New trade', glyph: 'trades' as const, onPress: () => {} };

test('short label where defined', () => {
  assert.equal(pillTabText(four[3]), 'Hist.');
  assert.equal(pillTabText(four[0]), 'Hub');
});
test('scroll target keeps the lit tab visible and clear of the fade', () => {
  assert.equal(pillScrollTarget(10, 50, 200, 0, 400), 0);
  assert.equal(pillScrollTarget(300, 60, 200, 0, 400), 300 + 60 + PILL_SCROLL_MARGIN - 200);
  assert.equal(pillScrollTarget(340, 60, 200, 0, 400), 200);
  assert.equal(pillScrollTarget(20, 50, 200, 150, 400), 2);
});
test('primary chip collapses to the icon with 4+ tabs or when it would not fit; never without a glyph', () => {
  assert.equal(pillPrimaryCompact({ tabs: four, primary }, 900), true);
  assert.equal(pillPrimaryCompact({ tabs: four.slice(0, 3), primary }, 900), false);
  assert.equal(pillPrimaryCompact({ tabs: four.slice(0, 3), primary }, 200), true);
  assert.equal(pillPrimaryCompact({ tabs: four, primary: { ...primary, glyph: undefined } }, 100), false);
});

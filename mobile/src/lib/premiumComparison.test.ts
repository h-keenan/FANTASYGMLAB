import { test } from 'node:test';
import assert from 'node:assert/strict';

import { FALLBACK_PREMIUM_COMPARISON, normalizePremiumComparison } from './premiumComparison.ts';

test('uses the fallback for missing, empty or malformed input', () => {
  assert.equal(normalizePremiumComparison(undefined), FALLBACK_PREMIUM_COMPARISON);
  assert.equal(normalizePremiumComparison([]), FALLBACK_PREMIUM_COMPARISON);
  assert.equal(normalizePremiumComparison([{ key: 'x' }]), FALLBACK_PREMIUM_COMPARISON);
});

test('keeps valid server rows and drops malformed ones', () => {
  const rows = normalizePremiumComparison([
    { key: 'gm_targets', label: 'GM Targets', free: '3 players', pro: '50 players' },
    { nope: true },
  ]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].pro, '50 players');
});

test('fallback rows are all complete', () => {
  for (const r of FALLBACK_PREMIUM_COMPARISON) assert.ok(r.key && r.label && r.free && r.pro);
});

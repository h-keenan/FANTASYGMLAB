// Run with: node --experimental-strip-types --test src/lib/usageProfile.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { formatUsageDelta, formatUsageValue, hasUsageContent, usageDataNote } from './usageProfile.ts';
import type { UsageMetric, UsageProfile } from './api.ts';

const share: UsageMetric = {
  key: 'snap_share', label: 'Snap share', unit: 'pct', source: 'sleeper',
  last4: 0.783, last8: 0.66, prior: 0.55, season: 0.66, delta_last4_vs_prior: 0.233,
  direction: 'up', games_with_data: 8,
};
const count: UsageMetric = { ...share, key: 'opportunities', unit: 'count', last4: 12.54, delta_last4_vs_prior: -2.04 };

test('formats shares, counts and missing values', () => {
  assert.equal(formatUsageValue(share, share.last4), '78%');
  assert.equal(formatUsageValue(count, count.last4), '12.5');
  assert.equal(formatUsageValue(count, null), '–');
  assert.equal(formatUsageDelta(share), '+23 pts');
  assert.equal(formatUsageDelta(count), '-2.0');
});

test('data note distinguishes available, missing and unknown advanced coverage', () => {
  const base: UsageProfile = { status: 'ok', metrics: [share], flags: [] };
  assert.match(usageDataNote({ ...base, advanced: { available: true, through_week: 8 } }) ?? '', /through Week 8/);
  assert.match(usageDataNote({ ...base, advanced: { available: false } }) ?? '', /not available/);
  assert.equal(usageDataNote(base), null);
});

test('only renders when there is something honest to show', () => {
  assert.equal(hasUsageContent(null), false);
  assert.equal(hasUsageContent({ status: 'not_covered', metrics: [], flags: [] }), false);
  assert.equal(hasUsageContent({ status: 'unavailable', metrics: [], flags: [] }), true);
  assert.equal(hasUsageContent({ status: 'ok', metrics: [share], flags: [] }), true);
});

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

import { headlineRows, poolCaption, statItemRows, usageCardCoversLegacyTiles, usageRows } from './statRows.ts';

test('stat rows name the pool once and only carry an explorer key when a percentile exists', () => {
  const profile: UsageProfile = {
    status: 'ok', season: 2026,
    metrics: [{ ...share, explorer_key: 'snap', percentile: 83 }, { ...count, explorer_key: undefined }],
    flags: [],
  };
  const rows = usageRows(profile, 'WR');
  assert.equal(rows.length, 1);
  assert.equal(rows[0].explorerKey, 'snap');
  assert.equal(rows[0].caption, 'vs WRs · 2026');
  assert.match(rows[0].trend ?? '', /Last 4: 78% \(\+23 pts vs earlier\)/);
  const thin = usageRows({ ...profile, metrics: [{ ...share, explorer_key: 'snap', percentile: null }] }, 'WR');
  assert.equal(thin[0].explorerKey, null);
  assert.equal(thin[0].percentile, null);
  assert.equal(usageCardCoversLegacyTiles(profile), true);
  assert.equal(poolCaption('rb', 2026), 'vs RBs · 2026');
});

test('headline tiles take PPR PPG then the position usage numbers; Games is never a row', () => {
  const items = [
    { label: 'Games', value: '8', note: '', tone: 'x', percentile: null },
    { label: 'PPR PPG', value: '14.6', note: '', tone: 'x', percentile: 88 },
  ];
  assert.deepEqual(statItemRows(items, 'RB', 2026).map((r) => r.label), ['PPR PPG']);
  const profile: UsageProfile = {
    status: 'ok', season: 2026, flags: [],
    metrics: [
      { ...share, key: 'snap_share', explorer_key: 'snap', percentile: 83 },
      { ...share, key: 'opportunity_share', label: 'Opportunity share', explorer_key: 'opportunity', percentile: 93 },
    ],
  };
  const heads = headlineRows({ position: 'RB', seasons: [{ season: 2026, fantasy: items }] }, profile);
  assert.deepEqual(heads.map((r) => r.key), ['PPR PPG', 'opportunity_share', 'snap_share']);
});

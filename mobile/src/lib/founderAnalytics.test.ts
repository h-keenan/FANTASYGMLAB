import assert from 'node:assert/strict';
import test from 'node:test';

import {
  errorRows,
  featureUseRows,
  funnelRows,
  funnelSummary,
  isFounderSession,
  moduleRows,
  performanceRows,
  platformLine,
  storageBadge,
  summaryTiles,
} from './founderAnalytics.ts';
import type { FounderAnalyticsReport } from './api.ts';

test('isFounderSession requires the strict founder_ops === true claim', () => {
  assert.equal(isFounderSession({ user: { app_metadata: { founder_ops: true } } }), true);
  assert.equal(isFounderSession({ user: { app_metadata: { founder_ops: 'true' } } }), false);
  assert.equal(isFounderSession({ user: { app_metadata: {} } }), false);
  assert.equal(isFounderSession({ user: { app_metadata: null } }), false);
  assert.equal(isFounderSession({ user: null }), false);
  assert.equal(isFounderSession(null), false);
  assert.equal(isFounderSession(undefined), false);
});

const report = {
  event_count: 12345,
  sessions: 10,
  anonymous_users: 3,
  hashed_accounts: 7,
  product_modules: [{ module: 'trade_analyzer', users: 2, sessions: 3, views: 4000, meaningful_interactions: 1 }],
  feature_use: [{ feature: 'gm_plan', action: 'open_tab', total: 5, web: 1, ios: 2, android: 2, free: 3, pro: 2 }],
  onboarding_funnel: {
    started_users: 10,
    completed_users: 6,
    completion_rate_pct: 60,
    skipped_users: 1,
    skip_rate_pct: null,
    steps: [
      { step: 'connect_league', step_index: 1, users: 8, drop_off_pct: 20, skipped_users: 1 },
      { step: 'value', step_index: 0, users: 10, drop_off_pct: null, skipped_users: 0 },
    ],
    experience: {},
  },
  platforms: { ios: 1000, android: 20 },
  errors: { TimeoutError: 4 },
  performance: { cold_start: { p50: 100, p90: null, p95: 300, n: 9 } },
  storage: { kind: 'host_local_jsonl', multi_instance: 'Single host.', retention_days: 30, writes_enabled: false },
} as unknown as FounderAnalyticsReport;

test('formatters render real counts without inventing values', () => {
  assert.deepEqual(summaryTiles(report)[0], { key: 'events', label: 'Events', value: '12,345' });
  assert.equal(moduleRows(report)[0].label, 'trade analyzer');
  assert.equal(moduleRows(report)[0].value, '4,000 views · 2 users · 3 sessions');
  assert.equal(featureUseRows(report)[0].label, 'gm plan · open tab');
  assert.equal(funnelSummary(report), '10 users started · completion 60%');
  assert.equal(funnelRows(report)[0].value, '8 users · drop-off 20% · skipped 1');
  assert.equal(funnelRows(report)[1].value, '10 users');
  assert.deepEqual(errorRows(report), [{ key: 'TimeoutError', label: 'TimeoutError', value: '4' }]);
  assert.equal(performanceRows(report)[0].value, 'p50 100 · p90 — · p95 300 (n=9)');
  assert.equal(platformLine(report), 'Events by platform: ios 1,000 · android 20');
});

test('absent optional sections yield nothing', () => {
  const bare = { ...report, feature_use: undefined, onboarding_funnel: null, platforms: undefined } as FounderAnalyticsReport;
  assert.deepEqual(featureUseRows(bare), []);
  assert.equal(funnelSummary(bare), null);
  assert.deepEqual(funnelRows(bare), []);
  assert.equal(platformLine(bare), null);
});

test('storageBadge flags host-local storage as non-durable', () => {
  const b = storageBadge(report.storage);
  assert.equal(b.durable, false);
  assert.equal(b.title, 'Host-local only');
  assert.match(b.detail, /Writes disabled/);
  assert.equal(storageBadge({ ...report.storage, kind: 'supabase' }).durable, true);
});

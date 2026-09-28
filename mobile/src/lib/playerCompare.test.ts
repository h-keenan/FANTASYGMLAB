// Run with: node --experimental-strip-types --test src/lib/playerCompare.test.ts
// (mobile has no jest/test runner configured yet — see backgroundRetry.test.ts
// for why plain Node's built-in test runner is used instead.)
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildModelRows,
  buildNarrativePair,
  buildStatusRows,
  buildTrendRows,
  buildValueRows,
  LOWER_IS_BETTER,
  type CompareSide,
} from './playerCompare.ts';
import type { RankedPlayer, QuickViewModel } from './api.ts';

function player(overrides: Partial<RankedPlayer> = {}): RankedPlayer {
  return {
    player_id: 'p1',
    name: 'Test Player',
    position: 'WR',
    team: 'SF',
    age: 25,
    status: 'Active',
    injury_status: null,
    tier: null,
    score: 80,
    overall_rank: 10,
    position_rank: 3,
    rank_unavailable_reason: null,
    opportunity_label: null,
    ...overrides,
  };
}

function model(overrides: Partial<QuickViewModel> = {}): QuickViewModel {
  return {
    market_score: 70,
    opportunity_score: 60,
    scarcity_score: 50,
    role_score: 40,
    age_score: 90,
    age_score_label: 'Age Score',
    opportunity_confidence: 75,
    workload_trend: null,
    usage_trend: null,
    decision_fit_narrative: null,
    ...overrides,
  };
}

function side(playerOverrides: Partial<RankedPlayer>, modelOverrides: Partial<QuickViewModel> | null = {}): CompareSide {
  return {
    player: player(playerOverrides),
    overallRating: null,
    model: modelOverrides === null ? null : model(modelOverrides),
  };
}

test('buildValueRows includes Value Score, Overall Rank, Position Rank, and Age straight off RankedPlayer', () => {
  const a = side({ score: 80, overall_rank: 10, position_rank: 3, age: 25 });
  const b = side({ score: 60, overall_rank: 20, position_rank: 8, age: 29 });
  const rows = buildValueRows(a, b);
  assert.deepEqual(
    rows.map((r) => r.label),
    ['Value Score', 'Overall Rank', 'Position Rank', 'Age'],
  );
  const overallRankRow = rows.find((r) => r.label === 'Overall Rank')!;
  assert.equal(overallRankRow.a, 10);
  assert.equal(overallRankRow.b, 20);
});

test('Overall Rank and Position Rank are lower-is-better; Value Score and Age are not', () => {
  assert.equal(LOWER_IS_BETTER.has('Overall Rank'), true);
  assert.equal(LOWER_IS_BETTER.has('Position Rank'), true);
  assert.equal(LOWER_IS_BETTER.has('Value Score'), false);
  assert.equal(LOWER_IS_BETTER.has('Age'), false);
});

test('buildModelRows adds the 5th age subscore (with its real label) and Confidence alongside the original four', () => {
  const a = side({}, { age_score: 90, age_score_label: 'Age Lens', opportunity_confidence: 55 });
  const b = side({}, { age_score: 40, opportunity_confidence: 80 });
  const rows = buildModelRows(a, b);
  assert.deepEqual(
    rows.map((r) => r.label),
    ['Market', 'Opportunity', 'Scarcity', 'Role', 'Age Lens', 'Confidence'],
  );
  const confidenceRow = rows.find((r) => r.label === 'Confidence')!;
  assert.equal(confidenceRow.format!(55), '55%');
});

test('buildModelRows falls back to the other side\'s age_score_label when one side has no model at all', () => {
  const a = side({}, null);
  const b = side({}, { age_score_label: 'Age Score' });
  const rows = buildModelRows(a, b);
  const ageRow = rows.find((r) => r.label === 'Age Score' || r.label === 'Age Lens')!;
  assert.equal(ageRow.label, 'Age Score');
  assert.equal(ageRow.a, null);
});

test('buildTrendRows reduces usage_trend to its real signed trend_pct, formatted with an explicit sign', () => {
  const a = side({}, { usage_trend: { direction: 'up', trend: 0.18, trend_pct: 18, magnitude_pct: 18, confidence: 0.8, confidence_key: 'high', confidence_label: 'High', sample_n: 6, window: 4, usage_rate: 0.5, baseline_rate: 0.4, arrow: '↑', tone: 'positive', label: 'Usage rising', summary: '', detail: '' } });
  const b = side({}, { usage_trend: null });
  const rows = buildTrendRows(a, b);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].label, 'Usage Trend');
  assert.equal(rows[0].a, 18);
  assert.equal(rows[0].b, null);
  assert.equal(rows[0].format!(18), '+18%');
  assert.equal(rows[0].format!(-12), '-12%');
});

test('buildStatusRows always includes Status/Injury Status as plain text pairs, and Role Trend only when at least one side has a workload_trend', () => {
  const a = side({ status: 'Active', injury_status: 'Questionable' }, { workload_trend: 'rising' });
  const b = side({ status: 'Injured Reserve', injury_status: null }, { workload_trend: null });
  const rows = buildStatusRows(a, b);
  assert.deepEqual(
    rows.map((r) => r.label),
    ['Status', 'Injury Status', 'Role Trend'],
  );
  const roleTrendRow = rows.find((r) => r.label === 'Role Trend')!;
  assert.equal(roleTrendRow.a, 'rising');
  assert.equal(roleTrendRow.b, null);
});

test('buildStatusRows omits Role Trend entirely when neither side has a workload_trend', () => {
  const a = side({}, { workload_trend: null });
  const b = side({}, { workload_trend: null });
  const rows = buildStatusRows(a, b);
  assert.equal(rows.some((r) => r.label === 'Role Trend'), false);
});

test('buildNarrativePair pairs both real sentences and is null (not two empty blocks) when neither side has one', () => {
  const a = side({}, { decision_fit_narrative: 'Elite market value, thin opportunity.' });
  const b = side({}, { decision_fit_narrative: null });
  const pair = buildNarrativePair(a, b);
  assert.deepEqual(pair, { a: 'Elite market value, thin opportunity.', b: null });

  const neither = buildNarrativePair(side({}, { decision_fit_narrative: null }), side({}, { decision_fit_narrative: null }));
  assert.equal(neither, null);
});

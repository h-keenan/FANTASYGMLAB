// Run with: node --experimental-strip-types --test src/lib/compareHeadToHead.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { buildHeadlineRows, buildHeadlineTextRows, headlineWinner, nextProjection, ppgFromWeeks, pushRecent, scheduleOutlook, suggestedOpponents } from './compareHeadToHead.ts';

const rp = (id: string, position: string, score: number, over: Record<string, unknown> = {}) =>
  ({ player_id: id, name: id, position, team: 'KC', age: 25, status: null, injury_status: null, tier: null, score, overall_rank: 1, position_rank: 1, rank_unavailable_reason: null, opportunity_label: null, ...over }) as never;
const game = (over: Record<string, unknown> = {}) =>
  ({ week: 10, opponent: 'DAL', is_home: true, spread_line: null, total_line: null, played: false, team_score: null, opponent_score: null, bye: false, opponent_defense_tier: null, projection: null, ...over }) as never;

test('ppg averages played weeks', () => {
  assert.equal(ppgFromWeeks([{ week: 1, fantasy_points_ppr: 10, snap_share: null }, { week: 2, fantasy_points_ppr: 20, snap_share: null }, { week: 3, fantasy_points_ppr: null, snap_share: null }]), 15);
  assert.equal(ppgFromWeeks([]), null);
});

test('next projection skips played, bye and non-ok', () => {
  const ok = { status: 'ok', point_estimate: 13.5, low: 1, high: 2, confidence: 'high', opponent: 'DAL' };
  assert.equal(nextProjection([game({ played: true, projection: ok }), game({ bye: true }), game({ projection: { ...ok, status: 'no_team' } }), game({ projection: ok })]), 13.5);
});

test('schedule outlook and winner', () => {
  const a = scheduleOutlook([game({ opponent_defense_tier: 'weak' }), game({ opponent_defense_tier: 'weak' }), game({ opponent_defense_tier: 'tough' })]);
  assert.deepEqual(a, { score: 1, text: '2 soft · 1 tough' });
  const rows = buildHeadlineTextRows(null, null, { ppg: null, projection: null, schedule: a }, { ppg: null, projection: null, schedule: { score: -1, text: '1 tough' } });
  assert.equal(rows.find((r) => r.label === 'Next 4 games')?.winner, 'a');
});

test('headline rows mark winners but never age', () => {
  const rows = buildHeadlineRows(rp('a', 'WR', 100, { age: 22 }), rp('b', 'WR', 90, { age: 30 }), { ppg: 12, projection: null, schedule: null }, { ppg: 14, projection: null, schedule: null });
  const by = Object.fromEntries(rows.map((r) => [r.label, headlineWinner(r)]));
  assert.equal(by['Value Score'], 'a');
  assert.equal(by['PPG'], 'b');
  assert.equal(by['Age'], null);
});

test('suggestions are same position, nearest value, excluding the base and excluded ids', () => {
  const base = rp('base', 'WR', 1000);
  const pool = [base, rp('far', 'WR', 100), rp('near', 'WR', 990), rp('nearer', 'WR', 1005), rp('rb', 'RB', 1000), rp('skip', 'WR', 999)];
  assert.deepEqual(suggestedOpponents(pool, base, ['skip'], 2).map((p: { player_id: string }) => p.player_id), ['nearer', 'near']);
});

test('recents are newest first, deduped and capped', () => {
  let r: string[] = [];
  for (const id of ['1', '2', '3', '4', '5', '6', '7', '2']) r = pushRecent(r, id);
  assert.deepEqual(r, ['2', '7', '6', '5', '4', '3']);
});

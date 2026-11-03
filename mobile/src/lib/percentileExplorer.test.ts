// Run with: node --experimental-strip-types --test src/lib/percentileExplorer.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  addPin,
  assignMarkerLanes,
  binIndexAtPercentile,
  bucketPlayers,
  explorerMetricsFor,
  playersNearPercentile,
  poolMedian,
  rosterIdsFromRoster,
  searchExplorerPool,
  defaultComparison,
  explorerEmptyCopy,
  explorerStatKey,
  explorerViewState,
  formatExplorerDelta,
  formatExplorerValue,
  type ExplorerPlayer,
  type PercentileExplorerResponse,
} from './percentileExplorer.ts';

const p = (id: string, value: number, percentile: number): ExplorerPlayer => ({
  player_id: id,
  name: id,
  team: 'CIN',
  position: 'WR',
  value,
  percentile,
});

const ready = (overrides: Partial<PercentileExplorerResponse> = {}): PercentileExplorerResponse => ({
  ok: true,
  reason: '',
  stat: 'ppr_ppg',
  pool: 'position',
  scopes: ['season'],
  player: p('me', 16.7, 88),
  nearby: [],
  bins: [],
  ...overrides,
});

test('view state covers loading, error, chart and the empty reasons', () => {
  assert.equal(explorerViewState('loading', null), 'loading');
  assert.equal(explorerViewState('error', null), 'error');
  assert.equal(explorerViewState('ready', ready()), 'chart');
  assert.equal(explorerViewState('ready', ready({ reason: 'insufficient_pool', player: null })), 'insufficient_pool');
  assert.equal(explorerViewState('ready', ready({ reason: 'season_unavailable' })), 'season_unavailable');
  assert.equal(explorerViewState('ready', ready({ reason: 'no_data', player: null })), 'no_data');
  assert.equal(explorerViewState('ready', ready({ player: null })), 'no_data');
});

test('empty copy names the position for a thin pool', () => {
  assert.match(explorerEmptyCopy('insufficient_pool', 'WR').subtitle, /WR/);
  assert.equal(explorerEmptyCopy('no_data').title, 'No data for this stat');
});

test('stat keys skip Games and unknown labels', () => {
  assert.equal(explorerStatKey('PPR PPG'), 'ppr_ppg');
  assert.equal(explorerStatKey('Snap %'), 'snap');
  assert.equal(explorerStatKey('Games'), null);
});

test('values and deltas format by unit', () => {
  assert.equal(formatExplorerValue(16.7, 'ppg'), '16.7');
  assert.equal(formatExplorerValue(251, 'yards'), '251');
  assert.equal(formatExplorerValue(70, 'share'), '70%');
  assert.equal(formatExplorerDelta(16.7, 13.6, 'ppg'), '+3.1');
  assert.equal(formatExplorerDelta(13.6, 16.7, 'ppg'), '-3.1');
  assert.equal(formatExplorerDelta(70, 60, 'share'), '+10 pts');
});

test('close markers get different lanes', () => {
  const lanes = assignMarkerLanes([20, 24, 28, 60]);
  assert.equal(new Set(lanes.slice(0, 3)).size, 3);
  assert.equal(lanes[3], 0);
});

test('default comparison is the nearest player above, else nearest', () => {
  const me = p('me', 10, 50);
  assert.equal(defaultComparison(me, [p('a', 12, 60), p('b', 11, 55), p('c', 9, 45)])?.player_id, 'b');
  assert.equal(defaultComparison(me, [p('c', 9, 45)])?.player_id, 'c');
  assert.equal(defaultComparison(me, []), null);
});

test('buckets players exactly by histogram counts', () => {
  const pool = [p('e', 9, 90), p('d', 8, 70), p('c', 5, 50), p('b', 2, 30), p('a', 1, 10)];
  const bins = [
    { count: 2, pct_start: 0, pct_end: 40, value_start: 1, value_end: 4 },
    { count: 1, pct_start: 40, pct_end: 60, value_start: 4, value_end: 6 },
    { count: 2, pct_start: 60, pct_end: 100, value_start: 6, value_end: 9 },
  ];
  assert.deepEqual(bucketPlayers(pool, bins, 0).map((x) => x.player_id), ['b', 'a']);
  assert.deepEqual(bucketPlayers(pool, bins, 1).map((x) => x.player_id), ['c']);
  assert.deepEqual(bucketPlayers(pool, bins, 2).map((x) => x.player_id), ['e', 'd']);
  assert.deepEqual(bucketPlayers(pool, bins, 3), []);
  assert.equal(binIndexAtPercentile(bins, 0), 0);
  assert.equal(binIndexAtPercentile(bins, 40), 1);
  assert.equal(binIndexAtPercentile(bins, 100), 2);
  assert.deepEqual(playersNearPercentile(pool, 68, 2).map((x) => x.player_id), ['d', 'c']);
});

test('search, median, roster ids, pins and metrics', () => {
  const named = (id: string, name: string): ExplorerPlayer => ({ ...p(id, 1, 1), name });
  const pool = [named('1', 'Amon-Ra St. Brown'), named('2', 'Marvin Brownlee'), named('3', 'Cobrown Smith')];
  assert.deepEqual(searchExplorerPool(pool, 'st').map((x) => x.player_id), ['1']);
  assert.deepEqual(searchExplorerPool(pool, 'brown').map((x) => x.player_id), ['1', '2', '3']);
  assert.deepEqual(searchExplorerPool(pool, 'b'), []);
  assert.equal(poolMedian([p('1', 1, 1), p('2', 5, 2), p('3', 9, 3)]), 5);
  assert.equal(poolMedian([]), null);
  assert.deepEqual([...rosterIdsFromRoster({ players: ['1', '2', 3] })], ['1', '2']);
  assert.equal(rosterIdsFromRoster(null).size, 0);
  assert.deepEqual(addPin(['a', 'b'], 'c', 2), ['b', 'c']);
  assert.deepEqual(addPin(['a'], 'a'), ['a']);
  assert.ok(explorerMetricsFor('QB', { key: 'ppr_ppg', label: 'PPR PPG' }).some((m) => m.key === 'pass_yards'));
  assert.equal(explorerMetricsFor('WR', { key: 'carry_share', label: 'Carry Share' })[0].key, 'carry_share');
});

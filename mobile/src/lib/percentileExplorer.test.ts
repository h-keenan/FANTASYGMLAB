// Run with: node --experimental-strip-types --test src/lib/percentileExplorer.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  assignMarkerLanes,
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

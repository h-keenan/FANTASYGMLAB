import test from 'node:test';
import assert from 'node:assert/strict';

import type { PortfolioExposurePlayer } from './api.ts';
import { sortExposurePlayers } from './portfolioExposure.ts';

const p = (name: string, leagues_owned: number, value: number): PortfolioExposurePlayer => ({
  player_id: name,
  name,
  position: 'RB',
  team: '',
  leagues_owned,
  league_names: [],
  leagues: [],
  share_of_leagues: 0,
  value,
  share_of_value: 0,
});

test('sorts by leagues owned then value, or by value', () => {
  const players = [p('A', 1, 300), p('B', 3, 100), p('C', 3, 200)];
  assert.deepEqual(sortExposurePlayers(players, 'leagues').map((x) => x.name), ['C', 'B', 'A']);
  assert.deepEqual(sortExposurePlayers(players, 'value').map((x) => x.name), ['A', 'C', 'B']);
});

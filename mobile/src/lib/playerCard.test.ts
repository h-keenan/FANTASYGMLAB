// Run with: node --experimental-strip-types --test src/lib/playerCard.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  estimatedQuarter,
  headlinePoints,
  playerCardFromStarter,
  playerGameLine,
  playerStatusChips,
  trendVsProjection,
  type PlayerCardSource,
} from './playerCard.ts';

const base: PlayerCardSource = {
  player_id: '1',
  name: 'Cam Skattebo',
  position: 'RB',
  team: 'NYG',
  projection: { status: 'ok', point_estimate: 14, opponent: 'DAL' },
};
const live: PlayerCardSource = {
  ...base,
  game_status: 'in_progress',
  game_started: true,
  actual_points: 11.2,
  projected_final: 17.4,
  game_progress: 0.55,
  game_opponent: 'DAL',
  game_is_home: false,
};

test('live model: points, projected final, game line, chip', () => {
  const model = playerCardFromStarter(live);
  assert.deepEqual(headlinePoints(model), { value: 11.2, kind: 'pts' });
  assert.equal(model.expectedFinal, 17.4);
  assert.equal(playerGameLine(model), '@ DAL · ~Q3');
  assert.deepEqual(playerStatusChips(model).map((c) => c.kind), ['live']);
});

test('pre-kickoff 0.0 is not a score', () => {
  const model = playerCardFromStarter({ ...base, game_status: 'scheduled', game_started: false, actual_points: 0 });
  assert.equal(model.points, null);
  assert.deepEqual(headlinePoints(model), { value: 14, kind: 'proj' });
});

test('final line shows score and result', () => {
  const model = playerCardFromStarter({
    ...base,
    game_status: 'final',
    game_started: true,
    actual_points: 20.4,
    game_is_home: true,
    game_team_score: 24,
    game_opponent_score: 17,
  });
  assert.equal(playerGameLine(model), 'vs DAL · Final 24-17 W');
});

test('bye / out / questionable chips', () => {
  const bye = playerCardFromStarter({ ...base, projection: { status: 'bye_week', point_estimate: null } });
  assert.deepEqual(playerStatusChips(bye).map((c) => c.kind), ['bye']);
  const out = playerCardFromStarter({ ...base, injury_label: 'Out', game_status: 'scheduled' });
  assert.deepEqual(playerStatusChips(out).map((c) => c.kind), ['out']);
  const q = playerCardFromStarter({ ...base, injury_label: 'Questionable', game_status: 'scheduled' });
  assert.deepEqual(playerStatusChips(q).map((c) => c.kind), ['upcoming', 'questionable']);
});

test('trend vs projection', () => {
  assert.deepEqual(trendVsProjection(playerCardFromStarter(live)), { dir: 'up', delta: 3.4 });
  assert.equal(trendVsProjection(playerCardFromStarter({ ...live, projected_final: 9 }))?.dir, 'down');
  assert.equal(trendVsProjection(playerCardFromStarter({ ...base, game_status: 'scheduled' })), null);
  assert.equal(estimatedQuarter(0.3), '~Q2');
});

// Run with: node --experimental-strip-types --test src/lib/playerCard.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  estimatedQuarter,
  headlinePoints,
  playerCardFromStarter,
  playerGameLine,
  playerGameStatusLine,
  liveStatLine,
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

const qb: PlayerCardSource = { ...live, position: 'QB', game_opponent: 'IND', game_is_home: true, game_team_score: 14, game_opponent_score: 3, game_clock_label: 'Q2 5:54', stats: { pass_att: 14, pass_cmp: 11, pass_yd: 118, pass_td: 2, pass_int: 2, rush_att: 1, rush_yd: 4 } };

test('inline status uses the real clock and own score first; wall-clock only as fallback', () => {
  assert.equal(playerGameStatusLine(playerCardFromStarter(qb)), 'Q2 5:54 \u00b7 14-3 vs IND');
  assert.match(playerGameStatusLine(playerCardFromStarter({ ...qb, game_clock_label: null })) ?? '', /^~Q\d/);
  assert.match(playerGameStatusLine(playerCardFromStarter({ ...qb, game_clock_label: 'Half' })) ?? '', /^Half/);
  assert.equal(playerGameStatusLine(playerCardFromStarter({ ...qb, game_status: 'final', game_clock_label: 'Final' })), 'Final 14-3 W');
  assert.equal(playerGameStatusLine(playerCardFromStarter({ ...base, projection: { status: 'bye_week', point_estimate: null } })), 'Bye');
});

test('live stat line by position, only while live or final', () => {
  assert.equal(playerCardFromStarter(qb).statLine, '11/14 CMP, 118 YD, 2 TD, 2 INT, 1 CAR, 4 YD');
  assert.equal(playerCardFromStarter({ ...qb, game_status: 'scheduled', game_started: false }).statLine, null);
  assert.equal(liveStatLine({ rush_att: 6, rush_yd: 14, rec: 1, rec_tgt: 2, rec_yd: -1 }, 'RB'), '6 CAR, 14 YD, 1/2 REC, -1 YD');
  assert.equal(liveStatLine({}, 'WR'), null);
});

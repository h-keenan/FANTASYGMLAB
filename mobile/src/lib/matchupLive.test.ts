// Run with: node --experimental-strip-types --test src/lib/matchupLive.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { liveGamesFromStarters, mergeLivePlays, quietLabel } from './matchupLive.ts';

test('one row per game, live first, situation only while live', () => {
  const games = liveGamesFromStarters([
    { team: 'HOU', game_status: 'in_progress', game_clock_label: 'Q2 5:54', game_situation: '2nd & 7 at HOU 25', game_opponent: 'IND', game_is_home: true, game_team_score: 14, game_opponent_score: 3 },
    { team: 'IND', game_status: 'in_progress', game_clock_label: 'Q2 5:54', game_opponent: 'HOU', game_is_home: false, game_team_score: 3, game_opponent_score: 14 },
    { team: 'KC', game_status: 'final', game_opponent: 'LV', game_is_home: true, game_team_score: 27, game_opponent_score: 20, game_situation: 'ignored' },
    { team: 'SF', game_status: 'scheduled', game_opponent: 'MIN' },
  ]);
  assert.equal(games.length, 2);
  assert.equal(games[0].score, 'IND 3 - 14 HOU');
  assert.equal(games[0].situation, '2nd & 7 at HOU 25');
  assert.equal(games[1].clock, 'Final');
  assert.equal(games[1].situation, null);
});

test('merges server and client plays, dedupes, so-far sorts last', () => {
  const rows = mergeLivePlays(
    [
      { id: 's1', at: 10, player_id: '1', name: 'A B', side: 'mine', points: 6, description: 'TD catch', clock: 'Q1 3:00' },
      { id: 's2', at: 99, player_id: '2', name: 'C D', side: 'mine', points: 6, description: '1 TD so far', so_far: true },
    ],
    [
      { id: 'c1', at: 20, playerId: '1', name: 'A B', side: 'mine', points: 6, detail: 'TD catch', approx: false },
      { id: 'c2', at: 30, playerId: '3', name: 'E F', side: 'opponent', points: 4, detail: '22-yd run', approx: false },
    ],
  );
  assert.deepEqual(rows.map((r) => r.id), ['c2', 's1', 's2']);
  assert.equal(rows[2].soFar, true);
});

test('quiet label', () => {
  assert.equal(quietLabel(null), 'All quiet');
  assert.equal(quietLabel(12), 'All quiet \u00b7 last checked 12s ago');
});

// Run with: node --experimental-strip-types --test src/lib/newsIdentity.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { newsPlayerIdentities } from './newsIdentity.ts';

test('no match fields yields no identity (never invented)', () => {
  assert.deepEqual(newsPlayerIdentities({}), []);
  assert.deepEqual(newsPlayerIdentities({ matched_player: null, matched_player_id: '1' }), []);
});

test('single match maps through with nulls for missing optionals', () => {
  const out = newsPlayerIdentities({ matched_player: 'Justin Jefferson', matched_player_id: '6794', matched_player_position: 'WR' });
  assert.deepEqual(out, [
    { matched_player: 'Justin Jefferson', matched_player_id: '6794', matched_player_position: 'WR', matched_player_team: null },
  ]);
});

test('exactly two matched_players take precedence over single fields', () => {
  const pair = [
    { matched_player: 'A', matched_player_id: '1', matched_player_position: 'WR', matched_player_team: 'LAR' },
    { matched_player: 'B', matched_player_id: '2', matched_player_position: 'WR', matched_player_team: null },
  ];
  assert.equal(newsPlayerIdentities({ matched_player: 'X', matched_players: pair }).length, 2);
});

test('a matched_players list that is not exactly two is ignored', () => {
  const one = [{ matched_player: 'A', matched_player_id: '1', matched_player_position: 'WR', matched_player_team: null }];
  assert.deepEqual(newsPlayerIdentities({ matched_players: one }), []);
});

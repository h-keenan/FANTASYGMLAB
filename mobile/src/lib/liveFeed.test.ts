// Run with: node --experimental-strip-types --test src/lib/liveFeed.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { MAX_FEED_EVENTS, deriveStatPieces, diffSnapshots, liveFeedStore, mergeFeed, snapshotFromMatchup, type FeedEvent } from './liveFeed.ts';

const texts = (prev: Record<string, number> | null, next: Record<string, number>) =>
  deriveStatPieces(prev, next).map((piece) => piece.text);

test('stat deltas: TD, FG, INT, fumble, reception + yards', () => {
  assert.deepEqual(texts({ rush_yd: 50 }, { rush_yd: 54, rush_td: 1 }), ['rushing TD, 4 yds']);
  assert.deepEqual(texts({ fgm: 1 }, { fgm: 2 }), ['field goal']);
  assert.deepEqual(texts({}, { pass_int: 1 }), ['interception thrown']);
  assert.deepEqual(texts({}, { fum_lost: 1 }), ['fumble lost']);
  assert.deepEqual(texts({ rec: 4, rec_yd: 40 }, { rec: 5, rec_yd: 52 }), ['catch, 12 yds']);
});

function matchup(points: number, stats: Record<string, number>) {
  return {
    game_state: 'live',
    my_team: {
      has_live_data: true,
      real_starters: [
        { player_id: '1', name: 'A Back', position: 'RB', team: 'NYG', actual_points: points, game_started: true, game_status: 'in_progress', game_opponent: 'DAL', game_is_home: true, stats },
      ],
    },
    opponent: { has_live_data: true, real_starters: [] },
  };
}

test('store: baseline yields nothing, next poll yields an event, cap holds', () => {
  liveFeedStore.reset();
  assert.deepEqual(liveFeedStore.ingest('k', matchup(5, { rush_yd: 30 }), 1), []);
  const [event] = liveFeedStore.ingest('k', matchup(11, { rush_yd: 34, rush_td: 1 }), 2);
  assert.equal(event.points, 6);
  assert.equal(event.detail, 'rushing TD, 4 yds');
  assert.equal(event.gameLabel, 'DAL @ NYG');
  assert.equal(snapshotFromMatchup(matchup(1, {})).size, 1);
  let feed: FeedEvent[] = [];
  for (let i = 0; i < 60; i += 1) feed = mergeFeed(feed, [{ ...event, id: `e${i}`, at: i }]);
  assert.equal(feed.length, MAX_FEED_EVENTS);
  assert.deepEqual(diffSnapshots(null, snapshotFromMatchup(matchup(1, {})), 3), []);
});

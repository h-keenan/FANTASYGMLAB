import assert from 'node:assert/strict';
import { test } from 'node:test';

import { hasTradePackage, portfolioMetadata, showSignalReason, signalPlayers } from './portfolioSignals.ts';

const base = { category: 'watch', headline: 'H', reason: 'R' };

test('route player first, mentioned players deduped', () => {
  const players = signalPlayers({
    ...base,
    route_player_id: '1',
    route_player_name: 'A',
    route_player_tier: 'Elite',
    mentioned_players: [
      { player_id: '1', name: 'A', position: 'RB', team: 'X', player_tier: 'Elite' },
      { player_id: '2', name: 'B', position: 'WR', team: 'Y', player_tier: '', injury_status: 'Out' },
    ],
  });
  assert.deepEqual(players.map((p) => p.player_id), ['1', '2']);
  assert.equal(players[1].injury_status, 'Out');
});

test('mentioned players alone render without a route player', () => {
  const players = signalPlayers({ ...base, mentioned_players: [{ player_id: '9', name: 'Z', position: 'QB', team: 'T', player_tier: '' }] });
  assert.equal(players.length, 1);
});

test('trade package items yield no player rows', () => {
  const item = { ...base, route_player_id: '1', route_player_name: 'A', presentation: { trade_package: { send: [{}], receive: [] } } };
  assert.equal(hasTradePackage(item), true);
  assert.deepEqual(signalPlayers(item), []);
});

test('reason hidden when equal to headline or an identity dump on a watch item', () => {
  assert.equal(showSignalReason({ category: 'watch', headline: 'X', reason: 'X' }), false);
  assert.equal(showSignalReason({ category: 'watch', headline: 'X', reason: 'A | B', route_player_id: '1', route_player_name: 'A' }), false);
  assert.equal(showSignalReason({ category: 'watch', headline: 'X', reason: 'Usage down' }), true);
  assert.equal(showSignalReason({ category: 'watch', headline: 'X', reason: '' }), false);
});

test('metadata shows rank text only outside the top 3', () => {
  assert.deepEqual(portfolioMetadata('5-2', 2, false), { showRankBadge: true, metadata: '5-2', rankText: '#2' });
  assert.deepEqual(portfolioMetadata('5-2', 7, true), { showRankBadge: false, metadata: '5-2 · Roster Power T-7', rankText: 'T-7' });
  assert.deepEqual(portfolioMetadata('', null, false), { showRankBadge: false, metadata: '', rankText: '' });
});

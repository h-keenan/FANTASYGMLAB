// Run with: node --experimental-strip-types --test src/lib/pushRouting.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { resolvePushTapTarget } from './pushRouting.ts';

test('trade follow-up push routes to Trade History even without league_id', () => {
  assert.deepEqual(resolvePushTapTarget({ type: 'trade_outcome_followup', outcome_id: 'o1' }), {
    screen: 'TradeHistory',
  });
});

test('trade follow-up push with league_id still routes to Trade History', () => {
  assert.deepEqual(
    resolvePushTapTarget({
      type: 'trade_outcome_followup',
      category: 'trade_followup',
      outcome_id: 'o1',
      league_id: 'L1',
    }),
    { screen: 'TradeHistory' },
  );
});

test('player pushes deep-link to PlayerDetail', () => {
  assert.deepEqual(
    resolvePushTapTarget({
      league_id: 'L1',
      league_name: 'Dynasty One',
      category: 'injury',
      player_id: 'p9',
      player_name: 'Hurt Guy',
    }),
    { screen: 'PlayerDetail', leagueId: 'L1', leagueName: 'Dynasty One', playerId: 'p9', playerName: 'Hurt Guy' },
  );
});

test('league-level pushes route to LeagueDetail', () => {
  assert.deepEqual(resolvePushTapTarget({ league_id: 'L1', league_name: 'X', category: 'recap' }), {
    screen: 'LeagueDetail',
    leagueId: 'L1',
    leagueName: 'X',
  });
});

test('payloads with no usable target return null', () => {
  assert.equal(resolvePushTapTarget(null), null);
  assert.equal(resolvePushTapTarget('nope'), null);
  assert.equal(resolvePushTapTarget({ category: 'watch' }), null);
});

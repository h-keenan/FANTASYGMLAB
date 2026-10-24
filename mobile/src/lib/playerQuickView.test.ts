import assert from 'node:assert/strict';
import test from 'node:test';

import { buildQuickViewRequest, fullProfileTarget, leagueScopedIdentity, stubPlayer } from './playerQuickView.ts';

const player = stubPlayer({ player_id: '4046', name: 'Patrick Mahomes', position: 'QB', team: 'KC' });

test('stubPlayer leaves unknown fields null', () => {
  assert.equal(player.age, null);
  assert.equal(player.tier, null);
  assert.equal(player.score, null);
  assert.equal(stubPlayer({ player_id: '1', name: '' }).name, null);
});

test('buildQuickViewRequest rejects a player without an id', () => {
  assert.equal(buildQuickViewRequest({ ...player, player_id: '' }, { leagueId: 'L', leagueName: 'N' }), null);
});

test('buildQuickViewRequest keeps league when present, drops it when blank', () => {
  assert.deepEqual(buildQuickViewRequest(player, { leagueId: 'L1', leagueName: 'Dynasty' })?.league, {
    leagueId: 'L1',
    leagueName: 'Dynasty',
  });
  assert.equal(buildQuickViewRequest(player, { leagueId: '', leagueName: '' })?.league, null);
  assert.equal(buildQuickViewRequest(player)?.league, null);
});

test('fullProfileTarget prefers the tap league, falls back to last league, else null', () => {
  const withLeague = buildQuickViewRequest(player, { leagueId: 'L1', leagueName: 'A' })!;
  const noLeague = buildQuickViewRequest(player)!;
  const fallback = { leagueId: 'L2', leagueName: 'B' };
  assert.equal(fullProfileTarget(withLeague, fallback)?.leagueId, 'L1');
  assert.equal(fullProfileTarget(noLeague, fallback)?.leagueId, 'L2');
  assert.equal(fullProfileTarget(noLeague, null), null);
});

test('leagueScopedIdentity never surfaces opportunity label without league', () => {
  const p = { ...player, tier: 'Elite', opportunity_label: 'Elite Opportunity', overall_rank: 3 };
  assert.equal(leagueScopedIdentity(buildQuickViewRequest(p)!).opportunityLabel, null);
  const inLeague = leagueScopedIdentity(buildQuickViewRequest(p, { leagueId: 'L', leagueName: 'N' })!);
  assert.equal(inLeague.opportunityLabel, 'Elite Opportunity');
});

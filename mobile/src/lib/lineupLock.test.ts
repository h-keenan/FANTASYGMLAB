// Run with: node --experimental-strip-types --test src/lib/lineupLock.test.ts
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { isActionableLineupIssue, isLineupLocked, leftGame } from './lineupLock.ts';
import { buildTeamStatusHeader, ordinalRank, rosterAttentionItems, teamValueRingLabel } from './statusHeader.ts';

const base = { player_id: 'a', name: 'A', position: 'TE', team: 'LV', tier: null, injury_label: '', injury_status: null, ruled_out: false, slot: 'FLEX' };
const out = { ...base, player_id: 'l', name: 'Loveland', ruled_out: true, injury_label: 'Out' };

describe('lock-aware lineup issues', () => {
  it('injured mid-game is not flagged and reads as left game', () => {
    const hurt = { ...out, game_started: true, game_locked: true };
    assert.deepEqual(rosterAttentionItems([hurt]), []);
    assert.equal(isActionableLineupIssue(hurt), false);
    assert.equal(leftGame(hurt), true);
  });
  it('Out before kickoff is flagged', () => {
    const pre = { ...out, game_started: false };
    assert.deepEqual(rosterAttentionItems([pre]).map((r) => r.name), ['Loveland']);
    assert.equal(isActionableLineupIssue(pre), true);
  });
  it('game final is not flagged', () => {
    assert.equal(isActionableLineupIssue({ ...out, game_started: true }), false);
  });
  it('missing kickoff time never invents a lock; bye is never locked', () => {
    assert.equal(isLineupLocked({ ...out, game_started: null }), false);
    assert.equal(isLineupLocked({ on_bye: true, game_started: true }), false);
  });
  it('mixed lineup flags only unstarted players', () => {
    const rows = rosterAttentionItems([{ ...out, player_id: '1', name: 'Locked', game_started: true }, { ...out, player_id: '2', name: 'Open', game_started: false }]);
    assert.deepEqual(rows.map((r) => r.name), ['Open']);
  });
  it('team value label is a rank of N teams', () => {
    assert.equal(ordinalRank(8), '8th');
    assert.equal(teamValueRingLabel(22.2, 8, 10), 'Team value rank 8th of 10 teams');
    const ring = buildTeamStatusHeader({ teamValue: '1', valuePercentile: 22.2, valueRank: 8, leagueSize: 10, context: null, openSlots: 0, flaggedStarters: 0, injuredStarters: 0, attention: [], hrefs: { lineup: 'Matchup' } }).ring;
    assert.equal(ring?.label, 'Team value rank 8th of 10 teams');
    assert.doesNotMatch(ring?.label ?? '', /percentile/);
  });
});

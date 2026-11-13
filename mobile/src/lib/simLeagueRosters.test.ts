// Run with: node --experimental-strip-types --test src/lib/simLeagueRosters.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { simBlockEntryCount, simBlockNote, simGroupBenchByPosition, simOverallLabel, simRosterEntries, simRosterPositions, simTeamChips, simTeamRecordLine, simValueLabel } from './simLeagueRosters.ts';
import type { SimGamePlayer, SimLeagueRosterTeam } from './simGame.ts';

const pl = (id: string, pos: SimGamePlayer['pos'], name: string, value: number, team = 'KC') => ({ id, pos, name, value, team, ros_mean: value / 10, projection: 10, status: 'healthy' }) as unknown as SimGamePlayer;
const t = (id: string, players: SimGamePlayer[]) => ({ team_id: id, name: `T${id}`, is_you: false, players }) as unknown as SimLeagueRosterTeam;

test('filters by position and search and sorts best value first across teams', () => {
  const teams = [t('1', [pl('a', 'QB', 'Alpha', 50), pl('b', 'RB', 'Bravo', 90)]), t('2', [pl('c', 'QB', 'Charlie', 70, 'BUF')])];
  assert.deepEqual(simRosterEntries(teams, 'ALL', '').map((e) => e.player.id), ['b', 'c', 'a']);
  assert.deepEqual(simRosterEntries(teams, 'QB', '').map((e) => [e.player.id, e.team.team_id]), [['c', '2'], ['a', '1']]);
  assert.deepEqual(simRosterEntries(teams, 'ALL', 'buf').map((e) => e.player.id), ['c']);
  assert.deepEqual(simRosterPositions(teams), ['QB', 'RB']);
});
test('chips, record line and value label', () => {
  assert.deepEqual(simTeamChips({ needs: ['QB'], surplus: ['RB', 'WR'] }).map((c) => c.label), ['Needs QB', 'Deep RB', 'Deep WR']);
  const rec = (w: number, l: number) => ({ record: { wins: w, losses: l, ties: 0, pf: 10, pa: 9, rank: 2 }, power_rank: 4 }) as never;
  assert.equal(simTeamRecordLine(rec(3, 0)), '3-0 · #2 · 10.0 PF');
  assert.equal(simTeamRecordLine(rec(0, 0)), '0-0 · Power #4');
  assert.equal(simTeamRecordLine({ record: null, power_rank: 4 }), 'Power #4');
  assert.deepEqual([0, 0.4, 71.6, null].map(simValueLabel), ['—', '—', '72', '—']);
});
test('labels overall and groups the bench by position', () => {
  assert.deepEqual([null, 0, 71.6].map(simOverallLabel), ['—', '0', '72']);
  const g = simGroupBenchByPosition([pl('a', 'WR', 'A', 1), pl('b', 'QB', 'B', 1), pl('c', 'WR', 'C', 1)], ['QB', 'RB', 'WR']);
  assert.deepEqual(g.map((x) => [x.pos, x.players.length]), [['QB', 1], ['WR', 2]]);
});

test('filters to what is on a trade block and notes what the team says about itself', () => {
  const withBlock = (p: SimGamePlayer): SimGamePlayer => ({ ...p, block: { by: '1', mine: false, looking_for: 'RB', why: 'Selling depth' } });
  const teams = [
    { ...t('1', [withBlock(pl('a', 'QB', 'Alpha', 50)), pl('b', 'RB', 'Bravo', 90)]), needs: ['RB', 'WR'], block: { stance: 'contending', looking_for: 'RB', items: [{ id: 'a', why: 'Selling depth' }] } },
    t('2', [pl('c', 'QB', 'Charlie', 70)]),
  ] as unknown as SimLeagueRosterTeam[];
  assert.deepEqual(simRosterEntries(teams, 'ALL', '', true).map((e) => e.player.id), ['a']);
  assert.equal(simBlockEntryCount(teams), 1);
  assert.equal(simBlockNote(teams[0], 'Selling depth'), 'Selling depth · looking for RB · needs RB, WR');
});

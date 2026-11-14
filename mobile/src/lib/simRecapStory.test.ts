// Run with: node --experimental-strip-types --test src/lib/simRecapStory.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { simLeagueHighlights, simNextWeekModel, simPositionTotals, simRecapInjuryModel, simRecapOutcome, simRecapPageKeys, simRecapProj, simRecapResultModel, simRecapSeasonModel } from './simRecapStory.ts';

const p = (id: string, name: string, pos: string) => ({ id, name, pos, projection: 10 });
const st = (slot: string, player: ReturnType<typeof p> | null, pts: number, flag: string | null = null) => ({ slot, player, pts, flag });
const recap: any = {
  week: 4, kind: 'regular', round: null,
  your_game: { opponent_id: '7', opponent_name: 'Rats', your_pts: 128.4, opp_pts: 109.7, result: 'win', starters: [st('QB', p('q', 'Quinn', 'QB'), 25), st('FLEX', p('w', 'Wade', 'RB'), 8), st('WR', p('x', 'Xan', 'WR'), 0, 'bye')] },
  scores: [{ home: '1', away: '2', home_pts: 102, away_pts: 95, winner: '1' }, { home: '3', away: '4', home_pts: 140.7, away_pts: 68.9, winner: '3' }],
  injuries: [], season_complete: false, champion: null, next_week: 5,
};
const facts = { youId: '9', names: { '1': 'Goats', '2': 'Brigade', '3': 'Flex', '4': 'Boom' }, lineupWarnings: 0, offers: 0 };

test('page order is Result, Matchup, Injuries, League, Next and empty pages drop out', () => {
  assert.deepEqual(simRecapPageKeys(recap, facts), ['result', 'matchup', 'injuries', 'league', 'next']);
  assert.deepEqual(simRecapPageKeys({ ...recap, your_game: null, scores: [] }, facts), ['result', 'next']);
  assert.equal(simRecapPageKeys({ ...recap, season_complete: true, next_week: null }, facts).includes('next'), false);
});

test('page models: result margin, positions, injuries, league and next week', () => {
  const r = simRecapResultModel(recap);
  assert.equal(r.margin, 'Won by 18.7');
  assert.equal(r.worst?.name, 'Wade');
  assert.deepEqual(simPositionTotals(recap.your_game.starters).map((t) => [t.pos, t.pts]), [['QB', 25], ['RB', 8], ['WR', 0]]);
  assert.deepEqual(simRecapInjuryModel(recap).zeroStarters, [{ name: 'Xan', flag: 'bye' }]);
  const h = simLeagueHighlights(recap, facts.names);
  assert.equal(h.hero?.who, 'Flex');
  assert.equal(h.items[0].detail, 'Goats beat Brigade by 7.0');
  const n = simNextWeekModel(recap, { ...facts, lineupWarnings: 1, offers: 2, nextOpponent: 'Titans', nextProjection: { yours: 121.4, theirs: 117.9 }, tradeDeadlineWeek: 10 });
  assert.equal(n.edge, 'You are favored by 3.5');
  assert.deepEqual(n.notes.map((x) => x.label), ['Lineup', 'Offers', 'Deadline']);
});

test("matchup row PROJ is the projection the server stamped for that week, never a guess", () => {
  assert.equal(simRecapProj({ proj: 14.23 }), 14.23);
  assert.equal(simRecapProj({ proj: 0 }), 0);
  assert.equal(simRecapProj({}), null); // a recap saved before the server sent it
  assert.equal(simRecapProj({ proj: null }), null);
  assert.equal(simRecapProj({ proj: Number.NaN }), null);
});

test('result variants: regular, playoff advance/eliminated/bye, champion and runner-up', () => {
  const g = (result: string) => ({ ...recap.your_game, result });
  assert.equal(simRecapOutcome(recap, '9').variant, 'win');
  assert.equal(simRecapOutcome({ ...recap, your_game: g('loss') }, '9').variant, 'loss');
  const po = { ...recap, kind: 'playoff', round: 1 };
  assert.deepEqual([simRecapOutcome(po, '9').variant, simRecapOutcome(po, '9').trophy, simRecapOutcome(po, '9').celebrate], ['advance', true, false]);
  assert.equal(simRecapOutcome({ ...po, your_game: g('loss') }, '9').variant, 'eliminated');
  assert.equal(simRecapOutcome({ ...po, your_game: null }, '9').variant, 'playoff_bye');
  const final = { ...po, season_complete: true, next_week: null, champion: '9' };
  assert.deepEqual([simRecapOutcome(final, '9').variant, simRecapOutcome(final, '9').celebrate], ['champion', true]);
  assert.equal(simRecapOutcome({ ...final, champion: '7', your_game: g('loss') }, '9').variant, 'runner_up');
  assert.equal(simRecapOutcome({ ...recap, season_complete: true, champion: '9' }, '9').celebrate, false);
});

test('season page: last, champion/finish/record, and injuries carry one marker per player', () => {
  const rows = [
    { rank: 1, team_id: '9', name: 'You', is_you: true, wins: 11, losses: 3, ties: 0, pf: 1800.4, pa: 1500 },
    { rank: 2, team_id: '7', name: 'Rats', is_you: false, wins: 10, losses: 4, ties: 0, pf: 1900.2, pa: 1400 },
  ];
  const done = { ...recap, kind: 'playoff', season_complete: true, next_week: null, champion: '7', standings: rows, your_game: { ...recap.your_game, result: 'loss' } };
  assert.equal(simRecapPageKeys(done, facts).at(-1), 'season');
  const m = simRecapSeasonModel(done, { ...facts, names: { '7': 'Rats' } });
  assert.deepEqual([m.finish, m.record, m.championName], ['Runner-up', '11-3', 'Rats']);
  assert.deepEqual(m.items.map((i) => i.key), ['champion', 'record', 'top']);
  const inj = simRecapInjuryModel({ ...recap, injuries: [{ player: p('a', 'Alf', 'WR'), weeks: 4, team_id: '9', is_yours: true }] });
  assert.equal(inj.items[0].detail, '4 weeks · yours');
});

// Run with: node --experimental-strip-types --test src/lib/simRecapStory.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { simLeagueHighlights, simNextWeekModel, simPositionTotals, simRecapInjuryModel, simRecapPageKeys, simRecapProj, simRecapResultModel } from './simRecapStory.ts';

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

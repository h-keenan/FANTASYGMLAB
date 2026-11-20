import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  defaultMatchupWeek,
  leagueMatchupsHidden,
  leagueMatchupsSummaryParts,
  leagueMatchupWeeks,
  pairAriaLabel,
  pairTones,
  sideSubline,
  winBarSplit,
  winPercent,
  type LeagueMatchupPairView,
  type LeagueMatchupSideView,
} from './leagueMatchups.ts';

const side = (over: Partial<LeagueMatchupSideView>): LeagueMatchupSideView => ({
  roster_id: '1',
  team_name: 'Squad',
  owner_name: 'me',
  avatar_url: '',
  record_label: '5-2',
  streak: 3,
  streak_label: '▲3W',
  standing_rank: 2,
  points: 80,
  projected_total: 118.4,
  win_probability: 0.7,
  is_mine: false,
  ...over,
});
const pair = (a: Partial<LeagueMatchupSideView>, b: Partial<LeagueMatchupSideView>, game_state: LeagueMatchupPairView['game_state'] = 'live'): LeagueMatchupPairView => ({
  matchup_id: 1,
  game_state,
  sides: [side(a), side({ roster_id: '2', win_probability: 0.3, points: 60, ...b })],
});

test('winPercent rounds and rejects missing', () => {
  assert.equal(winPercent(0.704), 70);
  assert.equal(winPercent(null), null);
  assert.equal(winPercent(Number.NaN), null);
});

test('pairTones: leader by win chance, trailing is never an alarm tone', () => {
  assert.deepEqual(pairTones(pair({}, {})), ['leader', 'trailing']);
  assert.deepEqual(pairTones(pair({ win_probability: 0.4 }, { win_probability: 0.6 })), ['trailing', 'leader']);
  assert.deepEqual(pairTones(pair({ win_probability: 0.5 }, { win_probability: 0.5 })), ['even', 'even']);
});

test('pairTones falls back to points, then even', () => {
  assert.deepEqual(pairTones(pair({ win_probability: null, points: 90 }, { win_probability: null, points: 60 })), ['leader', 'trailing']);
  assert.deepEqual(pairTones(pair({ win_probability: null, points: null }, { win_probability: null, points: null })), ['even', 'even']);
});

test('winBarSplit sums to 100 and is even when unmodeled', () => {
  assert.deepEqual(winBarSplit(pair({}, {})), [70, 30]);
  assert.deepEqual(winBarSplit(pair({ win_probability: null }, { win_probability: null })), [50, 50]);
});

test('sideSubline keeps standing, record and streak and drops unknowns', () => {
  assert.equal(sideSubline(side({})), '#2 · 5-2 · ▲3W');
  assert.equal(sideSubline(side({ standing_rank: null, streak_label: '' })), '5-2');
});

test('summary parts: week, count, live and your score', () => {
  const mine = pair({ is_mine: true, points: 98.2, win_probability: 0.71 }, { points: 84.1 });
  const parts = leagueMatchupsSummaryParts(11, [mine, pair({}, {}, 'final')]);
  assert.deepEqual(
    parts.map((p) => p.text),
    ['Wk 11', '2 matchups', '1 live', 'You 98.2-84.1 (71%)'],
  );
  assert.equal(leagueMatchupsSummaryParts(null, [])[0].text, 'Not available yet');
  assert.equal(leagueMatchupsSummaryParts(4, [])[1].text, 'No matchups yet');
});

test('weeks, default week and hidden reasons', () => {
  assert.deepEqual(leagueMatchupWeeks(3), [1, 2, 3]);
  assert.equal(defaultMatchupWeek(11), 11);
  assert.equal(defaultMatchupWeek(0), null);
  assert.equal(defaultMatchupWeek(40), 18);
  assert.equal(leagueMatchupsHidden('unsupported_platform'), true);
  assert.equal(leagueMatchupsHidden('no_matchup_data'), false);
});

test('aria label names both teams, state and chances', () => {
  const label = pairAriaLabel(pair({ team_name: 'A' }, { team_name: 'B' }));
  assert.match(label, /^Live: A 80\.0, 70 percent to win versus B 60\.0, 30 percent to win$/);
});

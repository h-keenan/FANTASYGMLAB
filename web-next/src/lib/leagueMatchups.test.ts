import { expect, test } from 'vitest';

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
} from './leagueMatchups';

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
  expect(winPercent(0.704)).toBe(70);
  expect(winPercent(null)).toBe(null);
  expect(winPercent(Number.NaN)).toBe(null);
});

test('pairTones: leader by win chance, trailing is never an alarm tone', () => {
  expect(pairTones(pair({}, {}))).toEqual(['leader', 'trailing']);
  expect(pairTones(pair({ win_probability: 0.4 }, { win_probability: 0.6 }))).toEqual(['trailing', 'leader']);
  expect(pairTones(pair({ win_probability: 0.5 }, { win_probability: 0.5 }))).toEqual(['even', 'even']);
});

test('pairTones falls back to points, then even', () => {
  expect(pairTones(pair({ win_probability: null, points: 90 }, { win_probability: null, points: 60 }))).toEqual(['leader', 'trailing']);
  expect(pairTones(pair({ win_probability: null, points: null }, { win_probability: null, points: null }))).toEqual(['even', 'even']);
});

test('winBarSplit sums to 100 and is even when unmodeled', () => {
  expect(winBarSplit(pair({}, {}))).toEqual([70, 30]);
  expect(winBarSplit(pair({ win_probability: null }, { win_probability: null }))).toEqual([50, 50]);
});

test('sideSubline keeps standing, record and streak and drops unknowns', () => {
  expect(sideSubline(side({}))).toBe('#2 · 5-2 · ▲3W');
  expect(sideSubline(side({ standing_rank: null, streak_label: '' }))).toBe('5-2');
});

test('summary parts: week, count, live and your score', () => {
  const mine = pair({ is_mine: true, points: 98.2, win_probability: 0.71 }, { points: 84.1 });
  const parts = leagueMatchupsSummaryParts(11, [mine, pair({}, {}, 'final')]);
  expect(parts.map((p) => p.text)).toEqual(['Wk 11', '2 matchups', '1 live', 'You 98.2-84.1 (71%)']);
  expect(leagueMatchupsSummaryParts(null, [])[0].text).toBe('Not available yet');
  expect(leagueMatchupsSummaryParts(4, [])[1].text).toBe('No matchups yet');
});

test('weeks, default week and hidden reasons', () => {
  expect(leagueMatchupWeeks(3)).toEqual([1, 2, 3]);
  expect(defaultMatchupWeek(11)).toBe(11);
  expect(defaultMatchupWeek(0)).toBe(null);
  expect(defaultMatchupWeek(40)).toBe(18);
  expect(leagueMatchupsHidden('unsupported_platform')).toBe(true);
  expect(leagueMatchupsHidden('no_matchup_data')).toBe(false);
});

test('aria label names both teams, state and chances', () => {
  const label = pairAriaLabel(pair({ team_name: 'A' }, { team_name: 'B' }));
  expect(label).toBe('Live: A 80.0, 70 percent to win versus B 60.0, 30 percent to win');
});

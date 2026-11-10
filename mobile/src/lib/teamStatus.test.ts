import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

import {
  buildTeamStatusLineup,
  buildTeamStatusMatchup,
  buildTeamStatusPositions,
  buildTeamStatusStanding,
  type TeamStatusMatchupInput,
} from './teamStatus.ts';

function shared(path: string): string {
  const text = readFileSync(resolve(process.cwd(), path), 'utf8');
  const start = text.indexOf('// SHARED BEGIN');
  const end = text.indexOf('// SHARED END');
  assert.ok(start >= 0 && end > start, `${path} missing SHARED markers`);
  return text.slice(start, end);
}

test('web and app share one team-status block', () => {
  assert.equal(shared('src/lib/teamStatus.ts'), shared('../web-next/src/lib/teamStatus.ts'));
});

const matchup: TeamStatusMatchupInput = {
  week: 9,
  my_team: { roster_id: '3', team_name: 'Ringer', avatar_url: null },
  opponent: { team_name: 'Rival', owner_name: 'r', avatar_url: 'x.png' },
  win_probability: { available: true, probability: 0.634, my_projected_total: 101.26, opponent_projected_total: 96.04 },
  suggested_moves: [],
  open_slots: [],
};

test('matchup: win percent and projections are rounded from the model', () => {
  const line = buildTeamStatusMatchup(matchup)!;
  assert.equal(line.winPercent, 63);
  assert.equal(line.myProjected, 101.3);
  assert.equal(line.opponentProjected, 96);
  assert.equal(line.opponentName, 'Rival');
});

test('matchup: unavailable model keeps the opponent but no numbers', () => {
  const line = buildTeamStatusMatchup({ ...matchup, win_probability: { available: false } })!;
  assert.equal(line.winPercent, null);
  assert.equal(line.myProjected, null);
});

test('matchup: hidden offseason, with a reason, or without an opponent', () => {
  assert.equal(buildTeamStatusMatchup(null), null);
  assert.equal(buildTeamStatusMatchup({ ...matchup, reason: 'no_matchup' }), null);
  assert.equal(buildTeamStatusMatchup({ ...matchup, opponent: null }), null);
});

test('matchup: live points only when Sleeper reports both sides', () => {
  const line = buildTeamStatusMatchup({ ...matchup, real_comparison: { my_points: 40.04, opponent_points: 22 }, game_state: 'live' })!;
  assert.deepEqual(line.live, { mine: 40, opponent: 22 });
  assert.equal(line.stateLabel, 'Live');
});

test('lineup: bye/out starters and the best swap', () => {
  const line = buildTeamStatusLineup(
    {
      ...matchup,
      suggested_moves: [
        { slot: 'RB', start: { name: 'A' }, over: { name: 'B' }, over_reason: 'ruled_out', gain: 6.24, locked: false },
        { slot: 'WR', start: { name: 'C' }, over: { name: 'D' }, over_reason: null, gain: 1, locked: false },
      ],
    },
    0,
  )!;
  assert.equal(line.tone, 'risk');
  assert.equal(line.headline, "1 starter can't play (bye or out)");
  assert.equal(line.detail, 'Best swap: start A over B (+6.2 pts)');
});

test('lineup: set, no swaps; locked moves ignored', () => {
  const locked = { slot: 'RB', start: { name: 'A' }, over: { name: 'B' }, over_reason: 'bye_week' as const, gain: 3, locked: true };
  assert.equal(buildTeamStatusLineup({ ...matchup, suggested_moves: [locked] }, 0)!.tone, 'positive');
});

test('lineup: injured count alone, and unknown hides the row', () => {
  assert.equal(buildTeamStatusLineup(null, 2)!.headline, '2 injured starters on your roster');
  assert.equal(buildTeamStatusLineup(null, null), null);
  assert.equal(buildTeamStatusLineup({ ...matchup, best_ball: true }, undefined), null);
});

const rankings = [
  { roster_id: '1', wins: 5, losses: 3, standing_rank: 2, playoff_status: 'In playoff position', power_rank: 4 },
  { roster_id: '3', wins: 3, losses: 5, standing_rank: 11, playoff_status: 'Outside', power_rank: 11 },
];

test('standing: record, place of N, odds', () => {
  const row = buildTeamStatusStanding({
    snapshot: { wins: 3, losses: 5, ties: 0 },
    rankings,
    standingsAvailable: true,
    myRosterId: '3',
    odds: { playoffOdds: '0%', projectedRecord: '4-10', clinched: false, eliminated: false },
  })!;
  assert.equal(row.record, '3-5');
  assert.equal(row.place, '11th of 2');
  assert.equal(row.powerRank, 11);
  assert.equal(row.playoffOdds, '0%');
});

test('standing: preseason 0-0 with nothing else hides the row', () => {
  assert.equal(
    buildTeamStatusStanding({ snapshot: { wins: 0, losses: 0, ties: 0 }, rankings: [], standingsAvailable: false, myRosterId: null, odds: null }),
    null,
  );
});

test('standing: place needs standings_available and a matched roster', () => {
  const row = buildTeamStatusStanding({
    snapshot: { wins: 3, losses: 5, ties: null },
    rankings,
    standingsAvailable: false,
    myRosterId: '3',
    odds: null,
  })!;
  assert.equal(row.place, null);
  assert.equal(row.record, '3-5');
});

const needs = {
  strengths: ['QB'],
  weaknesses: ['RB', 'TE'],
  position_groups: [
    { position: 'QB', classification: 'covered', upgrade_opportunity: false, temporary_injury_pressure: false },
    { position: 'RB', classification: 'short_term_need', upgrade_opportunity: false, temporary_injury_pressure: false },
    { position: 'WR', classification: 'future_risk', upgrade_opportunity: false, temporary_injury_pressure: false },
    { position: 'TE', classification: 'short_term_need', upgrade_opportunity: true, temporary_injury_pressure: false },
  ],
};

test('positions: labels, order, and the one weakest room', () => {
  const rows = buildTeamStatusPositions(needs);
  assert.deepEqual(rows.map((r) => [r.position, r.label]), [
    ['QB', 'Strength'],
    ['RB', 'Needs help'],
    ['WR', 'Aging risk'],
    ['TE', 'Needs help'],
  ]);
  assert.deepEqual(rows.filter((r) => r.weakest).map((r) => r.position), ['RB']);
});

test('positions: nothing flagged when no room needs help; empty input hides', () => {
  const calm = buildTeamStatusPositions({ ...needs, weaknesses: [], position_groups: [needs.position_groups[0]] });
  assert.equal(calm.some((r) => r.weakest), false);
  assert.deepEqual(buildTeamStatusPositions(null), []);
});

test('odds: clinched/out/percent, and hidden when the simulator has nothing', async () => {
  const { buildTeamStatusOdds } = await import('./teamStatus.ts');
  const base = { playoff_probability: 41.6, median_final_wins: 8, median_final_losses: 6, clinched: false, eliminated: false };
  assert.equal(buildTeamStatusOdds({ my_team: base })!.playoffOdds, '42%');
  assert.equal(buildTeamStatusOdds({ my_team: { ...base, clinched: true } })!.playoffOdds, 'Clinched');
  assert.equal(buildTeamStatusOdds({ my_team: { ...base, eliminated: true } })!.playoffOdds, 'Out');
  assert.equal(buildTeamStatusOdds({ my_team: base })!.projectedRecord, '8-6');
  assert.equal(buildTeamStatusOdds({ reason: 'offseason', my_team: base }), null);
  assert.equal(buildTeamStatusOdds(null), null);
});

test('league average age needs at least three real ages', async () => {
  const { leagueAverageAge } = await import('./teamStatus.ts');
  assert.equal(leagueAverageAge([{ average_age: 25 }, { average_age: 26 }, { average_age: null }]), null);
  assert.equal(leagueAverageAge([{ average_age: 25 }, { average_age: 26 }, { average_age: 27.5 }]), '26.2');
  assert.equal(leagueAverageAge(null), null);
});

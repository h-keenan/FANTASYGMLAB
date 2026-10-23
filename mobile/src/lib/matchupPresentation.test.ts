import test from 'node:test';
import assert from 'node:assert/strict';

import {
  matchupActionLabel,
  matchupNextAction,
  edgeExplanation,
  formatSigned,
  lineupComparisonRows,
  lineupPlayerPoints,
  matchupVerdict,
  moveOverLine,
} from './matchupPresentation.ts';

const edge = (position: string, value: number, count = 2) => ({
  position,
  my_points: 0,
  opponent_points: 0,
  edge: value,
  my_count: count,
  opponent_count: count,
  unmodeled: 0,
});

test('formatSigned', () => {
  assert.equal(formatSigned(12.44), '+12.4');
  assert.equal(formatSigned(-8.2), '-8.2');
  assert.equal(formatSigned(0.01), '0.0');
});

test('edgeExplanation is built from the real position edges', () => {
  const text = edgeExplanation([edge('WR', 12.4), edge('TE', 4.8, 1), edge('RB', -8.2), edge('QB', -2.1, 1)]);
  assert.match(text ?? '', /WRs \(\+12\.4\)/);
  assert.match(text ?? '', /RBs \(-8\.2\)/);
  assert.equal(edgeExplanation([]), null);
});

test('matchupVerdict follows the win probability', () => {
  const base = { game_state: 'pregame', real_comparison: null } as never;
  const favored = { ...(base as object), win_probability: { available: true, probability: 0.64 } } as never;
  const under = { ...(base as object), win_probability: { available: true, probability: 0.3 } } as never;
  assert.equal(matchupVerdict(favored).headline, "You're favored to win.");
  assert.equal(matchupVerdict(under).tone, 'risk');
});

test('lineupPlayerPoints: real points once started, projection before, bye noted', () => {
  const proj = { status: 'ok', point_estimate: 12.5 };
  assert.deepEqual(lineupPlayerPoints({ game_started: true, actual_points: 3, projection: proj } as never), {
    value: 3,
    kind: 'pts',
    note: null,
  });
  assert.equal(lineupPlayerPoints({ game_started: false, actual_points: 0, projection: proj } as never).value, 12.5);
  assert.equal(lineupPlayerPoints({ projection: { status: 'bye_week' } } as never).note, 'bye');
});

test('lineupComparisonRows zips by slot and keeps empty slots', () => {
  const p = (id: string, slot: string) => ({ player_id: id, slot }) as never;
  const rows = lineupComparisonRows([p('a', 'QB'), p('b', 'RB')], [p('c', 'QB')], ['WR'], []);
  assert.deepEqual(
    rows.map((r) => [r.slot, r.mine === 'empty' ? 'empty' : (r.mine as never as { player_id: string } | null)?.player_id ?? null]),
    [['QB', 'a'], ['RB', 'b'], ['WR', 'empty']],
  );
});

test('moveOverLine covers empty slot, bye and projection', () => {
  const start = { player_id: 'x', name: 'X' } as never;
  assert.match(moveOverLine({ slot: 'RB', start, over: null, over_reason: 'empty_slot', gain: 5, locked: false }), /empty RB/);
  const over = { name: 'Y', points: 7.4, injury_label: '' } as never;
  assert.equal(
    moveOverLine({ slot: 'RB', start, over, over_reason: null, gain: 1, locked: false }),
    'Over Y (Proj 7.4)',
  );
  assert.equal(
    moveOverLine({ slot: 'RB', start, over, over_reason: 'bye_week', gain: 1, locked: false }),
    'Over Y (on bye)',
  );
});

test("matchupNextAction gives every dead end one next step", () => {
  assert.equal(matchupNextAction("no_current_week").action, "dashboard");
  assert.equal(matchupNextAction("no_current_week").subtitle, "Check back when the season starts.");
  assert.equal(matchupNextAction("not_a_member_of_league").action, "connect");
  assert.equal(matchupNextAction("something_new").action, "retry");
  assert.equal(matchupActionLabel("retry"), "Try again");
});

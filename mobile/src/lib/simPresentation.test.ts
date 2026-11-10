// Run with: node --experimental-strip-types --test src/lib/simPresentation.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_SIM_STRATEGY,
  isSimOffError,
  simCompareHeadline,
  simCompareRows,
  simGate,
  simGradeTone,
  simLevelLabel,
  simNoteMessages,
  simReasonMessage,
  simRoundLabel,
  simStrategyEqual,
  simStrategySummary,
  simTeamNames,
  simTimeline,
  type SimResult,
} from './simPresentation.ts';

function result(overrides: Partial<SimResult> & { wins?: number; letter?: string; playoff?: string }): SimResult {
  const { wins = 8, letter = 'B', playoff = 'semifinal', ...rest } = overrides;
  return {
    engine_version: 'sim-1.0.0',
    seed: 1,
    mode: 'remaining',
    strategy: DEFAULT_SIM_STRATEGY,
    standings: [
      { team_id: '1', name: 'Mine', is_user: true, wins, losses: 14 - wins, ties: 0, pf: 1500, pa: 1400, made_playoffs: true, playoff_result: playoff },
      { team_id: '2', name: 'Theirs', is_user: false, wins: 7, losses: 7, ties: 0, pf: 1400, pa: 1450, made_playoffs: false, playoff_result: 'missed' },
    ],
    playoffs: [],
    events: [],
    personas: [],
    user: { team_id: '1', wins, losses: 14 - wins, ties: 0, pf: 1500, pa: 1400, playoff_result: playoff, made_playoffs: true },
    grade: { letter, score: 70, grade_points: letter === 'A' ? 95 : 80, components: [], summary: {} },
    decisions_that_mattered: [],
    ...rest,
  };
}

test('gate: Pro upsell, unavailable, and ready', () => {
  assert.deepEqual(simGate({ ok: true, reason: 'premium_required', is_premium: false, upsell: { title: 't', body: 'b' } }), {
    kind: 'premium',
    upsell: { title: 't', body: 'b' },
  });
  assert.equal(simGate({ ok: true, reason: 'sim_storage_unavailable' }).kind, 'unavailable');
  assert.equal(simGate({ ok: true, reason: '', is_premium: true, enabled: true }).kind, 'ready');
  assert.equal(simGate(null).kind, 'unavailable');
});

test('a 404 means the sim is off', () => {
  assert.equal(isSimOffError({ status: 404 }), true);
  assert.equal(isSimOffError({ status: 500 }), false);
  assert.equal(isSimOffError(new Error('x')), false);
});

test('reason copy is plain and empty on success', () => {
  assert.equal(simReasonMessage(''), '');
  assert.match(simReasonMessage('world_limit_reached'), /Delete one/);
  assert.match(simReasonMessage('totally_new_code'), /Try again/);
});

test('level labels and strategy summary', () => {
  assert.equal(simLevelLabel(0), 'Off');
  assert.equal(simLevelLabel(0.25), 'Low');
  assert.equal(simLevelLabel(0.5), 'Medium');
  assert.equal(simLevelLabel(0.75), 'High');
  assert.equal(simLevelLabel(1), 'Max');
  assert.equal(simStrategySummary({ ...DEFAULT_SIM_STRATEGY, protected_player_ids: ['a'] }), 'Balanced, trades medium, waivers medium, auto lineup, 1 protected');
});

test('strategy equality ignores protected order', () => {
  const a = { ...DEFAULT_SIM_STRATEGY, protected_player_ids: ['1', '2'] };
  assert.equal(simStrategyEqual(a, { ...a, protected_player_ids: ['2', '1'] }), true);
  assert.equal(simStrategyEqual(a, { ...a, posture: 'rebuild' }), false);
});

test('grade tone is centred on a C', () => {
  assert.equal(simGradeTone('A-'), 'success');
  assert.equal(simGradeTone('B+'), 'accent');
  assert.equal(simGradeTone('C'), 'warning');
  assert.equal(simGradeTone('F'), 'danger');
});

test('timeline names teams, filters to the user, and orders by week', () => {
  const r = result({
    events: [
      { week: 9, seq: 2, type: 'waiver', team: '2', involves_user: false, add: { name: 'Zed', pos: 'WR' }, drop: null },
      { week: 8, seq: 1, type: 'trade', team: '1', partner: '2', involves_user: true, gives: [{ name: 'A', pos: 'RB' }], gets: [{ name: 'B', pos: 'WR' }] },
    ],
  });
  const names = simTeamNames(r);
  const all = simTimeline(r.events, names);
  assert.equal(all[0].title, 'Mine (you) traded with Theirs');
  assert.equal(all[0].detail, 'Sent A (RB), got B (WR).');
  assert.equal(all.length, 2);
  assert.equal(simTimeline(r.events, names, { onlyUser: true }).length, 1);
});

test('round labels count back from the final', () => {
  assert.deepEqual([0, 1, 2].map((i) => simRoundLabel(i, 3)), ['Quarterfinals', 'Semifinals', 'Championship']);
});

test('A/B compare reports direction and a headline', () => {
  const before = result({ wins: 7, letter: 'C', playoff: 'missed' });
  const after = result({ wins: 9, letter: 'A', playoff: 'champion' });
  const rows = simCompareRows(before, after);
  assert.equal(rows.find((r) => r.key === 'record')?.direction, 1);
  assert.equal(rows.find((r) => r.key === 'playoffs')?.direction, 1);
  assert.match(simCompareHeadline(before, after), /2 wins more.*deeper playoff run/);
  assert.match(simCompareHeadline(before, before), /finished the same/);
});

test('world notes become plain caveats', () => {
  const lines = simNoteMessages(['bye_weeks_not_modeled', 'schedule_estimated_weeks:9,10', 'projection_fallback_players:4']);
  assert.equal(lines[0], 'Bye weeks are not modeled.');
  assert.equal(lines[1], 'The schedule for weeks 9,10 is estimated.');
  assert.equal(lines[2], '4 players use estimated scoring.');
});

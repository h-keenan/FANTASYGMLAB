import test from 'node:test';
import assert from 'node:assert/strict';
import { depthChange, depthChartParts, depthRowKind, injuryHistoryRows, injurySummaryParts, weeksLabel, type DepthChartData, type InjuryRecordData } from './playerDepthInjury.ts';
import { compactSummaryText } from './compactModule.ts';

const chart: DepthChartData = {
  ok: true, team: 'KC', slot: 'RB', slot_label: 'Running backs', self_order: 2, total: 3,
  entries: [
    { player_id: 'a', name: 'Starter', order: 1, is_self: false, change: 0 },
    { player_id: 'b', name: 'Me', order: 2, is_self: true, change: -1 },
    { player_id: 'c', name: 'Third', order: 4, is_self: false, change: null },
  ],
};

const record: InjuryRecordData = {
  ok: true, current_season: 2026, since_season: 2021, career_games_missed: 5,
  current: { label: 'Questionable', status: 'Questionable', severity: 'question', unavailable: false, body_part: 'Hamstring', practice: 'Limited in practice', report: null, line: 'Hamstring · Questionable' },
  seasons: [
    { season: 2026, games_missed: 2, stints: [{ start_week: 1, end_week: 1, games_missed: 1, injury: 'Ankle' }, { start_week: 9, end_week: 9, games_missed: 1, injury: null }] },
    { season: 2023, games_missed: 3, stints: [{ start_week: 4, end_week: 6, games_missed: 3, injury: 'Foot' }] },
  ],
};

test('a depth slot summary names his role, team, who is ahead and his weekly move', () => {
  assert.equal(compactSummaryText(depthChartParts(chart)), 'RB2 · KC · 1 ahead · Down 1');
  assert.deepEqual(depthChartParts({ ...chart, self_order: null }), []);
});

test('rows are classified ahead/self/behind and moves have a direction', () => {
  assert.deepEqual(chart.entries.map((e) => depthRowKind(e, 2)), ['ahead', 'self', 'behind']);
  assert.equal(depthChange(2)?.arrow, 'up');
  assert.equal(depthChange(0), null);
  assert.equal(depthChange(null), null);
});

test('the injury summary leads with the current line, this season and career games missed', () => {
  assert.equal(compactSummaryText(injurySummaryParts(record)), 'Hamstring · Questionable · 2 games missed in 2026 · 5 career');
  assert.equal(compactSummaryText(injurySummaryParts({ ...record, current: null, seasons: [], career_games_missed: 0 })), 'Healthy · No games missed on record');
});

test('history lists stints newest first with week ranges and an honest unspecified injury', () => {
  assert.deepEqual(
    injuryHistoryRows(record).map((r) => [r.season, r.injury, r.weeks, r.games]),
    [[2026, 'Injury (not specified)', 'Wk 9', '1 game'], [2026, 'Ankle', 'Wk 1', '1 game'], [2023, 'Foot', 'Wk 4–6', '3 games']],
  );
  assert.equal(weeksLabel({ start_week: null, end_week: null, games_missed: 1, injury: null }), '');
});

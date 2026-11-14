// Run with: node --experimental-strip-types --test src/lib/simToPrefs.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import type { SimToSummary } from './simGame.ts';
import { SIM_TO_DEFAULT_PREFS, SIM_TO_STOP_ROWS, simToCanForce, simToFixLabel, simToParsePrefs, simToReadout, simToRemaining, simToSerializePrefs, simToStopCount } from './simTo.ts';

const summary = (over: Partial<SimToSummary> = {}): SimToSummary => ({
  weeks: [], record: { before: '0-0', after: '2-0' }, rank: { before: 1, after: 1 }, pf: 200, injuries: [], claims: [], ai_trades: 0, standings: [], champion: null, season_complete: false, ...over,
});

test('defaults: auto-set on and every stop on; one row per stop', () => {
  assert.equal(SIM_TO_DEFAULT_PREFS.autoSet, true);
  assert.ok(Object.values(SIM_TO_DEFAULT_PREFS.stops).every(Boolean));
  assert.deepEqual(SIM_TO_STOP_ROWS.map((r) => r.key).sort(), Object.keys(SIM_TO_DEFAULT_PREFS.stops).sort());
  assert.deepEqual(simToParsePrefs(null), SIM_TO_DEFAULT_PREFS);
});

test('persisted choices round-trip and junk falls back per field', () => {
  const prefs = { autoSet: false, stops: { ...SIM_TO_DEFAULT_PREFS.stops, offers: false, deadline: false } };
  assert.deepEqual(simToParsePrefs(simToSerializePrefs(prefs)), prefs);
  assert.equal(simToStopCount(prefs.stops), 3);
  assert.deepEqual(simToParsePrefs('{nope'), SIM_TO_DEFAULT_PREFS);
  assert.deepEqual(simToParsePrefs(JSON.stringify({ autoSet: 'yes', stops: { offers: 0, injuries: false } })).stops, { ...SIM_TO_DEFAULT_PREFS.stops, injuries: false });
});

test('new stop codes get a fix button and can be simmed past', () => {
  assert.equal(simToFixLabel({ fix: 'inbox', code: 'trade_deadline' }), 'Open trades');
  assert.equal(simToFixLabel({ fix: 'roster', code: 'waiver_issue' }), 'Fix claims');
  assert.equal(simToFixLabel({ fix: 'lineup', code: 'starter_injured' }), 'Review lineup');
  assert.ok((['starter_injured', 'trade_deadline', 'waiver_issue'] as const).every((c) => simToCanForce({ code: c })));
});

test('keep simming only plays the weeks that are left', () => {
  assert.equal(simToRemaining({ id: 'weeks', weeks: 4, label: '4 weeks' }, 1).weeks, 3);
  assert.equal(simToRemaining({ id: 'weeks', weeks: 4, label: '4 weeks' }, 9).weeks, 1);
  assert.deepEqual(simToRemaining({ id: 'season_end', label: 'x' }, 3), { id: 'season_end', label: 'x' });
});

test('the readout names lineup changes, offers, roster overage and injuries', () => {
  assert.deepEqual(simToReadout(summary()), []);
  assert.deepEqual(simToReadout(summary({ auto_set: true, lineup_changes: [] })), ['Lineup auto-set: no changes needed.']);
  const lines = simToReadout(
    summary({
      auto_set: true,
      lineup_changes: [{ week: 1, slot: 'RB', out: 'A', in: 'B' }, { week: 2, slot: 'WR', out: 'C', in: 'D' }],
      offers_pending: 2, offers_new: 1, roster: { size: 20, limit: 18, over: 2 },
      injuries: [{ week: 2, player: { id: '1', name: 'X', pos: 'RB' }, weeks: 3 }],
    }),
  );
  assert.deepEqual(lines, ['Lineup auto-set: 2 changes over 2 weeks.', '2 trade offers waiting (1 new).', 'Over the limit by 2: cut or trade to add players.', '1 injury to your players.']);
});

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { SIM_WATCH_DEFAULTS, normalizeWatchReport, simWatchGradeMove, simWatchPlaybackLine, simWatchRerunBody, simWatchSliders } from './simWatch.ts';
import { simSetupBody, simSetupDefaults } from './simGame.ts';

test('defaults are Balanced waivers and Light trades', () => {
  assert.deepEqual(SIM_WATCH_DEFAULTS, { waivers: 'balanced', trades: 'light' });
  assert.equal(simSetupDefaults(null).watch, false);
});

test('setup body sends watch only for a fresh redraft and forces auto lineup', () => {
  const base = { ...simSetupDefaults(null), watch: true, watchWaivers: 'aggressive', watchTrades: 'off', auto: false };
  const body = simSetupBody(base) as Record<string, unknown>;
  assert.equal(body.watch, true);
  assert.equal(body.auto_lineup, true);
  assert.equal('watch' in (simSetupBody({ ...base, watch: false }) as Record<string, unknown>), false);
  assert.equal('watch' in (simSetupBody({ ...base, mode: 'dynasty' }) as Record<string, unknown>), false);
});

test('sliders, rerun body and playback lines', () => {
  assert.equal(simWatchSliders({}), null);
  assert.deepEqual(simWatchSliders({ watch_v: 1, watch_waivers: 'hands_off', watch_trades: 'active' }), { waivers: 'hands_off', trades: 'active' });
  const settings = { watch_v: 1, teams: 10, user_slot: 4 };
  assert.equal(simWatchRerunBody(settings, true).user_slot, 4);
  assert.equal(simWatchRerunBody(settings, false).user_slot, null);
  const line = simWatchPlaybackLine({ week: 3, kind: 'regular', your_game: { result: 'win', your_pts: 112.4, opp_pts: 98.1, opponent_name: 'Harbor Hawks' }, standings: [{ is_you: true, rank: 2 }] });
  assert.equal(line?.text, 'Wk 3 · W 112.4-98.1 vs Harbor Hawks · 2nd');
  assert.equal(line?.score, '112.4 - 98.1');
});

test('grade move and report parsing', () => {
  assert.equal(simWatchGradeMove('B', 'A-'), 'up');
  assert.equal(simWatchGradeMove(null, 'C'), 'same');
  assert.equal(normalizeWatchReport({}), null);
});

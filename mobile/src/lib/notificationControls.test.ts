// Run with: node --experimental-strip-types --test src/lib/notificationControls.test.ts
// Same assertions as web-next/src/lib/notificationControls.test.ts (parity).
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DIGEST_CATEGORIES,
  activeCapPreset,
  digestEnabled,
  digestPatch,
  hourLabel,
  leagueMode,
  quietSummary,
} from './notificationControls.ts';

const PRESETS = [
  { key: 'light', label: 'Light', cap: 2 },
  { key: 'standard', label: 'Standard', cap: 4 },
  { key: 'frequent', label: 'Frequent', cap: 7 },
];

test('formats hours on a 12-hour clock', () => {
  assert.deepEqual([0, 7, 12, 13, 22].map(hourLabel), ['12 AM', '7 AM', '12 PM', '1 PM', '10 PM']);
});

test('matches the effective cap to a preset; null cap means the server default', () => {
  assert.equal(activeCapPreset({ weekly_cap: null }, PRESETS, 4), 'standard');
  assert.equal(activeCapPreset({ weekly_cap: 2 }, PRESETS, 4), 'light');
  assert.equal(activeCapPreset({ weekly_cap: 5 }, PRESETS, 4), null);
});

test('digest switch round-trips and never touches critical categories', () => {
  assert.equal(digestEnabled({ category_modes: {} }), false);
  const on = digestPatch(true).category_modes ?? {};
  assert.deepEqual(Object.keys(on).sort(), [...DIGEST_CATEGORIES].sort());
  assert.equal(digestEnabled({ category_modes: on }), true);
  assert.ok(!('injury' in on) && !('lineup_lock' in on));
  assert.ok(Object.values(digestPatch(false).category_modes ?? {}).every((mode) => mode === 'instant'));
});

test('defaults a league to All and summarizes quiet hours', () => {
  assert.equal(leagueMode({ league_overrides: { L1: 'mute' } }, 'L1'), 'mute');
  assert.equal(leagueMode({ league_overrides: {} }, 'L2'), 'all');
  assert.equal(quietSummary({ quiet_hours_enabled: true, quiet_start: 22, quiet_end: 8 }), '10 PM to 8 AM');
  assert.equal(quietSummary({ quiet_hours_enabled: false, quiet_start: 22, quiet_end: 8 }), 'Off');
});

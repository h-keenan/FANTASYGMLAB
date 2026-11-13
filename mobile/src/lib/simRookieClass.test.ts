// Run with: node --experimental-strip-types --test src/lib/simRookieClass.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SIM_GENERATED_CLASS_LABEL,
  SIM_GENERATED_CLASS_NOTICE,
  simGeneratedClassLabel,
  simPlayerIsGenerated,
  simRookieClassChip,
  simRookieNoticeKey,
  simSetupDynastyNote,
} from './simGame.ts';

test('notice and chip label copy', () => {
  assert.equal(SIM_GENERATED_CLASS_NOTICE, 'These rookies are simulated, not the real NFL draft class. Names and talent are generated for the game.');
  assert.equal(SIM_GENERATED_CLASS_LABEL, 'Generated class');
});

test('strength flavor only for a known strength', () => {
  assert.equal(simGeneratedClassLabel('strong'), 'Generated class - strong');
  assert.equal(simGeneratedClassLabel('bogus'), 'Generated class');
  assert.equal(simGeneratedClassLabel(null), 'Generated class');
});

test('chip from the offseason payload, null for older saves', () => {
  assert.equal(simRookieClassChip({ rookie_class: { generated: true, strength: 'weak', size: 40 } }), 'Generated class - weak');
  assert.equal(simRookieClassChip({ rookie_class: { generated: false, strength: 'weak' } }), null);
  assert.equal(simRookieClassChip({}), null);
});

test('generated row flag and per-game key', () => {
  assert.equal(simPlayerIsGenerated({ generated: true }), true);
  assert.equal(simPlayerIsGenerated({}), false);
  assert.notEqual(simRookieNoticeKey('a'), simRookieNoticeKey('b'));
});

test('dynasty setup note mentions simulated classes', () => {
  assert.match(simSetupDynastyNote({ start: 'fresh', mode: 'dynasty' }) ?? '', /rookie classes are simulated/);
  assert.equal(simSetupDynastyNote({ start: 'fresh', mode: 'redraft' }), null);
});

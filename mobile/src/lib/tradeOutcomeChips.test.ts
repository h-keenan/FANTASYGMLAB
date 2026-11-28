// Run with: node --experimental-strip-types --test src/lib/tradeOutcomeChips.test.ts
import assert from 'node:assert/strict';
import test from 'node:test';

import { isPickAsset, tradeOutcomeChips, tradeValueDelta, tradeVerdictBadge } from './tradeOutcomeChips.ts';

test('a gain is a success chip, a loss is muted (never red)', () => {
  assert.equal(tradeOutcomeChips({ outcomeLabel: 'Made it', netPts: 34 })[0].label, 'You gained +34');
  const loss = tradeOutcomeChips({ outcomeLabel: 'Made it', netPts: -12 });
  assert.equal(loss[0].label, 'Down 12');
  assert.equal(loss[0].tone, 'muted');
});

test('falls back to the outcome label without points', () => {
  assert.deepEqual(tradeOutcomeChips({ outcomeLabel: "Didn't send", netPts: null }), [{ key: 'outcome', label: "Didn't send", tone: 'muted' }]);
});

test('the value trend moved out of the chips into the single delta number', () => {
  assert.deepEqual(tradeOutcomeChips({ outcomeLabel: 'Made it', netPts: 34 }).map((c) => c.key), ['pts']);
  assert.deepEqual(tradeValueDelta(12), { label: '+12%', tone: 'success' });
  assert.deepEqual(tradeValueDelta(-4), { label: '-4%', tone: 'muted' });
  assert.equal(tradeValueDelta(0.2), null);
  assert.equal(tradeValueDelta(null), null);
});

test('only a worked-out verdict is green; nothing is red', () => {
  assert.deepEqual(tradeVerdictBadge('worked_out', 'Worked out'), { key: 'verdict', label: 'Worked out', tone: 'success' });
  assert.equal(tradeVerdictBadge('didnt_pan_out', "Didn't pan out")?.tone, 'muted');
  assert.equal(tradeVerdictBadge(null, 'x'), null);
});

test('detects pick assets', () => {
  assert.equal(isPickAsset({ name: '2027 Round 1', position: '' }), true);
  assert.equal(isPickAsset({ name: '2026 1st Round Pick', position: 'PICK' }), true);
  assert.equal(isPickAsset({ name: 'Test Sender', position: 'WR', player_id: '100' }), false);
  assert.equal(isPickAsset({ name: 'Test Sender', position: 'WR' }), false);
});

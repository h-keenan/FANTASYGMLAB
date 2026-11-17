// Run with: node --experimental-strip-types --test src/lib/tradeOutcomeChips.test.ts
import assert from 'node:assert/strict';
import test from 'node:test';

import { tradeOutcomeChips } from './tradeOutcomeChips.ts';

test('a gain is a success chip, a loss is muted (never red)', () => {
  assert.equal(tradeOutcomeChips({ outcomeLabel: 'Made it', netPts: 34, netPct: 10 })[0].label, 'You gained +34');
  const loss = tradeOutcomeChips({ outcomeLabel: 'Made it', netPts: -12, netPct: -4 });
  assert.equal(loss[0].label, 'Down 12');
  assert.equal(loss[0].tone, 'muted');
});

test('falls back to the outcome label without points', () => {
  assert.deepEqual(tradeOutcomeChips({ outcomeLabel: "Didn't send", netPts: null, netPct: null }), [{ key: 'outcome', label: "Didn't send", tone: 'muted' }]);
});

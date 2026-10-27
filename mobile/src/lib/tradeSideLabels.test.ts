import assert from 'node:assert/strict';
import { test } from 'node:test';

import { SIDE_TINT_ALPHA, TRADE_SIDE_LABEL, withAlpha } from './tradeSideLabels.ts';

test('withAlpha appends a two-digit alpha to 6-digit hex only', () => {
  assert.equal(withAlpha('#ef4444', SIDE_TINT_ALPHA), '#ef44440f');
  assert.equal(withAlpha('#22c55e', 1), '#22c55eff');
  assert.equal(withAlpha('rgba(1,2,3,0.5)', 0.5), 'rgba(1,2,3,0.5)');
});

test('side labels match the web strings', () => {
  assert.deepEqual(TRADE_SIDE_LABEL, { send: 'You send', get: 'You get', receive: 'You receive' });
});

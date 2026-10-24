import assert from 'node:assert/strict';
import test from 'node:test';

import { injuryShortCode } from './tradeAssetDisplay.ts';

test('injuryShortCode maps known statuses', () => {
  assert.equal(injuryShortCode('Questionable'), 'Q');
  assert.equal(injuryShortCode(' Doubtful '), 'D');
  assert.equal(injuryShortCode('Out'), 'O');
  assert.equal(injuryShortCode('IR'), 'IR');
  assert.equal(injuryShortCode('Injured Reserve'), 'IR');
});

test('injuryShortCode passes unknown statuses through', () => {
  assert.equal(injuryShortCode('Suspended'), 'Suspended');
});

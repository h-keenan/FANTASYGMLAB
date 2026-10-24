import assert from 'node:assert/strict';
import test from 'node:test';

import { SAMPLE_ROSTER, SAMPLE_TRADE, sampleTradeVerdict } from './sampleLeague.ts';

test('sample trade verdict is deterministic', () => {
  const v = sampleTradeVerdict(SAMPLE_TRADE);
  assert.equal(v.giveTotal, 92);
  assert.equal(v.getTotal, 90);
  assert.equal(v.label, 'Fair');
});

test('sample roster ids are unique', () => {
  const ids = SAMPLE_ROSTER.map((p) => p.id);
  assert.equal(new Set(ids).size, ids.length);
});

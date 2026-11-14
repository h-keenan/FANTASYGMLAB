import assert from 'node:assert/strict';
import test from 'node:test';

import { waiversHeaderParts } from './waiversHeader.ts';

test('waivers header summary', () => {
  assert.deepEqual(waiversHeaderParts({ available: 394, faabLabel: 'FAAB', faab: '$81', need: 'QB' }).map((p) => p.text), ['394 available', '$81 FAAB', 'Need QB']);
  assert.deepEqual(waiversHeaderParts({ available: null, faabLabel: 'FAAB', faab: '—', need: '—' }), []);
  assert.equal(waiversHeaderParts({ available: 3, faabLabel: 'FAAB', faab: '$1', need: 'Covered' })[2].text, 'Needs covered');
});

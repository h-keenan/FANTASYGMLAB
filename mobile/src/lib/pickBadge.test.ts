import assert from 'node:assert/strict';
import test from 'node:test';

import { pickBadge, roundFromLabel } from './pickBadge.ts';

test('pick badge text', () => {
  assert.deepEqual(pickBadge({ round: 1, pickNo: 3 }), { top: 'R1', bottom: '#3', year: null, a11y: 'Round 1 pick 3' });
  assert.equal(pickBadge({ label: '2027 Round 1 (note)' }).top, 'R1');
  assert.equal(pickBadge({ label: '2027 Round 1 (note)' }).year, '2027');
  assert.equal(roundFromLabel('2028 R2'), '2');
  assert.equal(roundFromLabel('2026 2nd round'), '2');
  assert.equal(pickBadge({}).top, 'PICK');
  assert.equal(pickBadge({ pickNo: 7 }).top, '#7');
});

// Run with: node --experimental-strip-types --test src/lib/playerByePresentation.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { byePills } from './playerByePresentation.ts';

test('no bye week shows nothing, even if flagged', () => {
  assert.deepEqual(byePills(null, true), { label: null, thisWeek: false });
  assert.deepEqual(byePills(undefined, undefined), { label: null, thisWeek: false });
});
test('bye week shows the pill only', () => {
  assert.deepEqual(byePills(9, false), { label: 'Bye: Wk 9', thisWeek: false });
});
test('current-week bye adds the this-week flag', () => {
  assert.deepEqual(byePills(9, true), { label: 'Bye: Wk 9', thisWeek: true });
});

// Run with: node --experimental-strip-types --test src/lib/pqvContext.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { pqvBioForContext, pqvRealWorld } from './pqvContext.ts';

test('the real Player Quick View shows everything', () => {
  assert.deepEqual(pqvRealWorld(false), { fetchNews: true, showNews: true, showAvailability: true, showDepthChartNote: true, showBye: true, showContract: true });
  const bio = { bye_week: 'Week 8', contract_status: 'Through 2028' };
  assert.equal(pqvBioForContext(bio, false), bio);
});

test('inside Fantasy Sim nothing from the real world is fetched or shown', () => {
  assert.ok(Object.values(pqvRealWorld(true)).every((v) => v === false));
  assert.deepEqual(pqvBioForContext({ bye_week: 'Week 8', contract_status: 'Through 2028' }, true), { bye_week: '', contract_status: '' });
});

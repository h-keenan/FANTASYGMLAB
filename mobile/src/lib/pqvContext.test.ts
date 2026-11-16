// Run with: node --experimental-strip-types --test src/lib/pqvContext.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { pqvBioForContext, pqvRealWorld } from './pqvContext.ts';

test('the real Player Quick View shows everything', () => {
  assert.deepEqual(pqvRealWorld(false), { fetchNews: true, showNews: true, showAvailability: true, showDepthChartNote: true, showDepthChart: true, showInjuryHistory: true, fetchDepthChart: true, fetchInjuryHistory: true, showBye: true, showContract: true });
  const bio = { bye_week: 'Week 8', contract_status: 'Through 2028' };
  assert.equal(pqvBioForContext(bio, false), bio);
});

test('inside Fantasy Sim nothing from the real world is fetched or shown', () => {
  const { showDepthChart, showInjuryHistory, ...rest } = pqvRealWorld(true);
  assert.deepEqual([showDepthChart, showInjuryHistory], [true, true]);
  assert.ok(Object.values(rest).every((v) => v === false));
  assert.deepEqual(pqvBioForContext({ bye_week: 'Week 8', contract_status: 'Through 2028' }, true), { bye_week: '', contract_status: '' });
});

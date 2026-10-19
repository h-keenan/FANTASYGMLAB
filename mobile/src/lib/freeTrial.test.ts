import { test } from 'node:test';
import assert from 'node:assert/strict';

import { freeTrialFor } from './freeTrial.ts';

test('App Store free intro offer resolves to its length', () => {
  assert.deepEqual(
    freeTrialFor({ introPrice: { price: 0, periodUnit: 'DAY', periodNumberOfUnits: 7 } }),
    { lengthLabel: '7-day' },
  );
});

test('a paid intro price is not a free trial', () => {
  assert.equal(freeTrialFor({ introPrice: { price: 0.99, periodUnit: 'MONTH', periodNumberOfUnits: 1 } }), null);
});

test('Google Play free phase resolves when introPrice is null', () => {
  assert.deepEqual(
    freeTrialFor({ introPrice: null, defaultOption: { freePhase: { billingPeriod: { unit: 'WEEK', value: 1 } } } }),
    { lengthLabel: '1-week' },
  );
});

test('no trial data, unknown units, and missing product all resolve null', () => {
  assert.equal(freeTrialFor({ introPrice: null, defaultOption: null }), null);
  assert.equal(freeTrialFor({ introPrice: { price: 0, periodUnit: 'UNKNOWN', periodNumberOfUnits: 7 } }), null);
  assert.equal(freeTrialFor(null), null);
});

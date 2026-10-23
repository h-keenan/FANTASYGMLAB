import { test } from 'node:test';
import assert from 'node:assert/strict';

import { freeTrialFor, freeTrialForUser, thenPriceLine, trialCtaLabel, trialEndLabel } from './freeTrial.ts';

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

const IOS_TRIAL = { introPrice: { price: 0, periodUnit: 'DAY', periodNumberOfUnits: 3 } };
const PLAY_TRIAL = { introPrice: null, defaultOption: { freePhase: { billingPeriod: { unit: 'DAY', value: 3 } } } };

test('iOS shows the trial only when RevenueCat reports the user eligible', () => {
  assert.deepEqual(freeTrialForUser(IOS_TRIAL, 'eligible', 'ios'), { lengthLabel: '3-day' });
  assert.equal(freeTrialForUser(IOS_TRIAL, 'ineligible', 'ios'), null);
  assert.equal(freeTrialForUser(IOS_TRIAL, 'unknown', 'ios'), null);
  assert.equal(freeTrialForUser(IOS_TRIAL, undefined, 'ios'), null);
});

test('Android trusts the eligible free phase unless explicitly ineligible', () => {
  assert.deepEqual(freeTrialForUser(PLAY_TRIAL, 'unknown', 'android'), { lengthLabel: '3-day' });
  assert.deepEqual(freeTrialForUser(PLAY_TRIAL, undefined, 'android'), { lengthLabel: '3-day' });
  assert.equal(freeTrialForUser(PLAY_TRIAL, 'ineligible', 'android'), null);
});

test('no trial for a product without a free intro offer, whatever eligibility says', () => {
  assert.equal(freeTrialForUser({ introPrice: null, defaultOption: null }, 'eligible', 'ios'), null);
});

test('CTA and price line copy', () => {
  assert.equal(trialCtaLabel({ lengthLabel: '3-day' }), 'Start 3-day free trial');
  assert.equal(thenPriceLine('$19.99', '/yr'), 'Then $19.99/yr. Cancel anytime.');
});

test('trialEndLabel shows only a future end', () => {
  const now = new Date('2026-10-22T12:00:00Z');
  assert.equal(trialEndLabel('2026-10-25T12:00:00Z', now), 'Trial ends Oct 25');
  assert.equal(trialEndLabel('2026-10-20T12:00:00Z', now), '');
  assert.equal(trialEndLabel(null, now), '');
});

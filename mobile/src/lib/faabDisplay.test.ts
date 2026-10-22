import assert from 'node:assert/strict';
import { test } from 'node:test';

import { faabDisplayText } from './faabDisplay.ts';

const BASE = {
  low_bid: 8,
  high_bid: 14,
  pct_low: 8,
  pct_high: 14,
  remaining: 100,
  dollars_known: true,
  label: '$8–$14 of $100 remaining',
};

test('FAAB league with a known budget shows dollars', () => {
  assert.deepEqual(faabDisplayText(BASE), {
    isBid: true,
    primary: '$8–$14',
    secondary: 'of $100 remaining',
  });
});

test('unknown budget falls back to a percent range', () => {
  const text = faabDisplayText({ ...BASE, remaining: null, dollars_known: false });
  assert.equal(text.primary, '8–14%');
});

test('non-FAAB league never shows dollars or percents', () => {
  const text = faabDisplayText({
    ...BASE,
    low_bid: 0,
    high_bid: 0,
    pct_low: 0,
    pct_high: 0,
    remaining: null,
    dollars_known: false,
    applicable: false,
    waiver_mode: 'rolling',
  });
  assert.equal(text.isBid, false);
  assert.equal(text.primary, 'Waiver claim');
  assert.equal(text.secondary, 'Rolling waivers · no FAAB');
  assert.doesNotMatch(text.primary + text.secondary, /\$|%/);
});

test('a missing bid renders as a claim, not a crash', () => {
  assert.equal(faabDisplayText(null).primary, 'Waiver claim');
  assert.equal(faabDisplayText(undefined).secondary, 'No FAAB bid');
});

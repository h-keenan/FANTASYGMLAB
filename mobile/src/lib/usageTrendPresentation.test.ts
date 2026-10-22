// Run with: node --experimental-strip-types --test src/lib/usageTrendPresentation.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { sentenceCase, usageConfidenceBars, usageTrendTone } from './usageTrendPresentation.ts';

const RISING = { direction: 'up' as const, trend_pct: 13, confidence_label: 'high confidence' };
const FALLING = { direction: 'down' as const, trend_pct: -37, confidence_label: 'high confidence' };

test('rising usage is positive', () => {
  assert.equal(usageTrendTone(RISING), 'positive');
});

test('a confirmed decline (high confidence or a 20%+ drop) is danger', () => {
  assert.equal(usageTrendTone(FALLING), 'danger');
  assert.equal(usageTrendTone({ ...FALLING, confidence_label: 'moderate confidence', trend_pct: -24 }), 'danger');
});

test('a mild moderate-confidence decline is neutral, never green', () => {
  assert.equal(usageTrendTone({ ...FALLING, confidence_label: 'moderate confidence', trend_pct: -8 }), 'neutral');
});

test('confidence maps to signal bars', () => {
  assert.equal(usageConfidenceBars('high confidence'), 3);
  assert.equal(usageConfidenceBars('moderate confidence'), 2);
  assert.equal(usageConfidenceBars(''), 1);
});

test('sentenceCase capitalizes the first letter only', () => {
  assert.equal(sentenceCase('high confidence'), 'High confidence');
  assert.equal(sentenceCase('  '), '');
});

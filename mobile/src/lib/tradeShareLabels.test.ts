// Run with: node --experimental-strip-types --test src/lib/tradeShareLabels.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { analyzerHeadline, partnerForLine } from './tradeShareLabels.ts';

test('partnerForLine names the picked partner, trimmed', () => {
  assert.equal(partnerForLine('  Rival GM '), 'For Rival GM');
});

test('partnerForLine is null when no partner was picked', () => {
  assert.equal(partnerForLine(''), null);
  assert.equal(partnerForLine('   '), null);
  assert.equal(partnerForLine(undefined), null);
});

test('analyzerHeadline passes the four grades and rejects the rest', () => {
  assert.equal(analyzerHeadline('counter'), 'COUNTER');
  assert.equal(analyzerHeadline('ACCEPT'), 'ACCEPT');
  assert.equal(analyzerHeadline('IDEA'), null);
  assert.equal(analyzerHeadline(undefined), null);
});

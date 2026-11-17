import test from 'node:test';
import assert from 'node:assert/strict';

import { bandCompactTone, bandSimTone, deltaBand, percentBand, probabilityBand, verdictBand } from './verdictTone.ts';
import { simOddsTone } from './simPresentation.ts';
import { statusRingTone } from './statusHeader.ts';

test('probability bands use the shared cut points', () => {
  assert.equal(probabilityBand(0.6), 'good');
  assert.equal(probabilityBand(0.5), 'neutral');
  assert.equal(probabilityBand(0.25), 'caution');
  assert.equal(probabilityBand(0.03), 'bad');
  assert.equal(probabilityBand(null), 'neutral');
  assert.equal(percentBand(60), 'good');
});

test('the same percent reads the same tone on every page', () => {
  assert.equal(simOddsTone(0.6), 'success');
  assert.equal(statusRingTone(60), 'success');
  assert.equal(simOddsTone(0.21), 'warning');
  assert.equal(statusRingTone(21), 'warning');
});

test('verdict words and deltas', () => {
  assert.equal(verdictBand('accept'), 'good');
  assert.equal(verdictBand('decline'), 'bad');
  assert.equal(verdictBand('counter'), 'caution');
  assert.equal(deltaBand(-14.6), 'neutral');
  assert.equal(bandCompactTone('bad'), 'danger');
  assert.equal(bandSimTone('neutral'), 'accent');
});

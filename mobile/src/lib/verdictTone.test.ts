import test from 'node:test';
import assert from 'node:assert/strict';

import { bandCompactTone, bandSimTone, deltaBand, percentBand, percentWord, probabilityBand, probabilityWord, verdictBand } from './verdictTone.ts';
import { marginNowLabel, matchupCardModel } from './matchupModules.ts';
import { simHeadline, simOddsTone } from './simPresentation.ts';
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

test('a win percentage and its word come from the same band', () => {
  assert.equal(probabilityWord(0.57), 'Toss-up');
  assert.equal(probabilityWord(0.6), 'Favored');
  assert.equal(probabilityWord(0.39), 'Underdog');
  assert.equal(probabilityWord(null), '');
  for (const pct of [3, 20, 39, 40, 57, 59, 60, 100]) {
    const band = percentBand(pct);
    assert.equal(percentWord(pct) === 'Favored', band === 'good');
    assert.equal(percentWord(pct) === 'Toss-up', band === 'neutral');
  }
});

test('the Matchup chip and margin badge agree with the win band', () => {
  const model = (winPercent: number) =>
    matchupCardModel({ week: 10, live: false, final: false, myName: 'You', opponentName: 'Opp', myScore: null, opponentScore: null, myProjected: 118.3, opponentProjected: 109.7, winPercent, kickedOff: false, playersLeft: null, swing: [] });
  assert.equal(model(57).win?.label, '57% win · Toss-up');
  assert.equal(model(62).win?.label, '62% win · Favored');
  assert.equal(marginNowLabel(0, '0.0'), 'Even now');
  assert.equal(marginNowLabel(3.2, '+3.2'), '+3.2 now');
});

test('the sim playoff sentence cuts at the same 40% edge as the band', () => {
  const f = (playoffs: number) => simHeadline({ odds: { playoffs, title: 0.04, playoff_spots: 6 } } as never);
  assert.match(f(0.4), /coin flip/);
  assert.doesNotMatch(f(0.39), /coin flip/);
});

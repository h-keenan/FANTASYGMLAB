import test from 'node:test';
import assert from 'node:assert/strict';
import {
  teamSheetNextGameLine,
  teamSheetPositionLine,
  teamSheetSeasonLine,
  teamSheetStrengthNeedLine,
  teamSheetStreakTone,
  tradeStyleFromSignals,
} from './teamSheet.ts';

test('position line and strengths/needs read like the Sim sheet', () => {
  assert.equal(teamSheetPositionLine({ rank: 3, teams: 12, depth: 2 }), '#3 of 12 · depth 2');
  assert.equal(teamSheetStrengthNeedLine(['RB', 'WR'], ['TE']), 'Strong at RB, WR. Needs TE.');
  assert.equal(teamSheetStrengthNeedLine([], undefined), '');
});

test('next game, streak tone and season lines', () => {
  assert.equal(teamSheetNextGameLine({ week: 13, opponent: 'Rival' }), 'Week 13 vs Rival');
  assert.equal(teamSheetNextGameLine(null), '');
  assert.equal(teamSheetStreakTone('W12'), 'success');
  assert.equal(teamSheetStreakTone('L2'), 'danger');
  assert.equal(teamSheetSeasonLine({ wins: 9, losses: 3, ties: 0, place: 2, of: 12 }), '9-3 · #2 of 12');
});

test('a trade style is named only from a real, sufficiently sampled signal', () => {
  assert.equal(tradeStyleFromSignals(null), null);
  assert.equal(tradeStyleFromSignals({ posture: { status: 'insufficient_data', label: null } }), null);
  assert.deepEqual(
    tradeStyleFromSignals({
      posture: { status: 'ok', label: 'contending', summary: 'Win-now.' },
      pick_behavior: { status: 'ok', label: 'buys_picks', summary: 'Hoards picks.' },
    }),
    { tag: 'CONTENDER', blurb: 'Win-now.' },
  );
});

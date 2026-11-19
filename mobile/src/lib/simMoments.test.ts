import assert from 'node:assert/strict';
import { test } from 'node:test';

import { simCelebrationsParse, simCelebrationsSerialize, simPickMomentGrade, simStreakNumber, simWeekStamp } from './simMoments.ts';

test('Celebrations defaults to on', () => {
  assert.equal(simCelebrationsParse(null), true);
  assert.equal(simCelebrationsParse(simCelebrationsSerialize(false)), false);
});

test('pick grade and week stamp', () => {
  assert.equal(simPickMomentGrade(6).letter, 'A-');
  assert.equal(simPickMomentGrade(-80).letter, 'C-');
  const stamp = simWeekStamp({
    your_game: { result: 'win', your_pts: 112.4, opp_pts: 98.1, starters: [{ player: { name: 'Jalen Pruitt' }, pts: 31.4, flag: null }] },
    standings: [{ is_you: true, wins: 4, losses: 2, rank: 3, rank_prev: 5 }],
  });
  assert.equal(stamp?.caption, '4-2, up to 3rd');
  assert.equal(stamp?.note, 'J. Pruitt led you with 31.4');
});

test('streak badge number', () => {
  assert.equal(simStreakNumber({ key: 'win_streak', detail: '5 wins in a row (through week 7).' }), 5);
  assert.equal(simStreakNumber({ key: 'closest_win', detail: 'Won by 0.4' }), null);
});

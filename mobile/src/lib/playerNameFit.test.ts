// Run with: node --experimental-strip-types --test src/lib/playerNameFit.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { playerNameStage, playerNameStages, PLAYER_NAME_LAST_STAGE } from './playerNameFit.ts';

test('ladder: full, initial + whole surname, two font steps, wrapped', () => {
  const stages = playerNameStages('Jonathan Brisker');
  assert.deepEqual(stages.map((s) => s.text), ['Jonathan Brisker', 'J. Brisker', 'J. Brisker', 'J. Brisker', 'J. Brisker', 'J. Brisker']);
  assert.deepEqual(stages.map((s) => s.scale), [1, 1, 0.92, 0.85, 0.85, 0.85]);
  assert.deepEqual(stages.map((s) => s.wrap), [false, false, false, false, false, true]);
});

test('never an ellipsis; suffixes and multi-word surnames stay whole', () => {
  for (const n of ['Rhamondre Stevenson', 'Amon-Ra St. Brown', 'Michael Penix Jr.', 'Neymar', 'Ravens D/ST']) {
    for (const s of playerNameStages(n)) assert.doesNotMatch(s.text, /\.\.\.|…/);
  }
  assert.equal(playerNameStage('Michael Penix Jr.', 1).text, 'M. Penix Jr.');
  assert.equal(playerNameStage('Amon-Ra St. Brown', 1).text, 'A. St. Brown');
  assert.equal(playerNameStage('Neymar', 9).index, PLAYER_NAME_LAST_STAGE);
});

test('a generational suffix is shed before the name may wrap', () => {
  assert.equal(playerNameStage('Marvin Harrison Jr.', 3).text, 'M. Harrison Jr.');
  assert.equal(playerNameStage('Marvin Harrison Jr.', 4).text, 'M. Harrison');
  assert.equal(playerNameStage('Marvin Harrison Jr.', 4).wrap, false);
  assert.equal(playerNameStage('Marvin Harrison Jr.', 5).wrap, true);
});

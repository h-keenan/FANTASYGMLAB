import assert from 'node:assert/strict';
import { test } from 'node:test';

import { holdFactorLabel, holdIdeasNote } from './tradeHubHold.ts';
import { BEGINNER_HELP } from './experienceCopy.ts';

test('holdFactorLabel names the known factors and passes unknown ones through', () => {
  assert.equal(holdFactorLabel('competition'), 'Competition');
  assert.equal(holdFactorLabel('posture'), 'Posture');
  assert.equal(holdFactorLabel('other'), 'other');
});

test('holdIdeasNote only labels ideas optional when some are shown', () => {
  assert.equal(holdIdeasNote({ ideas_optional: true }, 3), 'Ideas below are optional.');
  assert.equal(holdIdeasNote({ ideas_optional: true }, 0), '');
  assert.equal(holdIdeasNote({ ideas_optional: false }, 3), '');
  assert.equal(holdIdeasNote(null, 3), '');
});

test('beginner copy explains posture and hold', () => {
  assert.match(BEGINNER_HELP.tradeHubPosture, /Posture is how you're building/);
  assert.match(BEGINNER_HELP.tradeHubHold, /no trade/);
});

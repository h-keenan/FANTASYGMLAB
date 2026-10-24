import assert from 'node:assert/strict';
import { test } from 'node:test';

import { LEAGUE_CAP_MESSAGE, leagueCapMessage, saveSucceeded } from './leagueCap.ts';

test('cap copy is the honest Free/Pro statement', () => {
  assert.equal(leagueCapMessage(), 'Free includes 1 league. Upgrade to add more.');
  assert.equal(LEAGUE_CAP_MESSAGE, leagueCapMessage());
});

test('an at_cap or any other refused save is never a success', () => {
  assert.equal(saveSucceeded({ ok: false }), false);
  assert.equal(saveSucceeded(null), false);
  assert.equal(saveSucceeded(undefined), false);
  assert.equal(saveSucceeded({}), false);
  assert.equal(saveSucceeded({ ok: true }), true);
});

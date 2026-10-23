import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  formatDelta,
  formatOdds,
  gamesReasonAction,
  gamesReasonMessage,
  matchPlayersByName,
  recordLabel,
  seedChangeLabel,
  whatIfSummary,
  whatIfTone,
  withPick,
} from './gamesPresentation.ts';

test('reasons map to short messages and a next step', () => {
  assert.match(gamesReasonMessage('offseason'), /regular season/);
  assert.match(gamesReasonMessage('brand_new_code'), /Not available/);
  assert.equal(gamesReasonAction('no_sleeper_username_linked'), 'account');
  assert.equal(gamesReasonAction('offseason'), 'home');
});

test('odds, deltas and seed moves format honestly', () => {
  assert.equal(formatOdds(61.4), '61%');
  assert.equal(formatOdds(null), '-');
  assert.equal(formatDelta(4.23), '+4.2');
  assert.equal(formatDelta(-1), '-1.0');
  assert.equal(formatDelta(0.01), '0.0');
  assert.equal(seedChangeLabel(-2), '2 seeds higher');
  assert.equal(seedChangeLabel(1), '1 seed lower');
  assert.equal(seedChangeLabel(0), 'Seed unchanged');
});

test('a change inside simulation noise is neutral', () => {
  assert.equal(whatIfTone({ playoff_probability: 1, within_noise: true }), 'neutral');
  assert.match(whatIfSummary({ playoff_probability: 1, within_noise: true }), /noise/);
  assert.equal(whatIfTone({ playoff_probability: 5, within_noise: false }), 'positive');
  assert.equal(whatIfSummary({ playoff_probability: -5.5, within_noise: false }), 'Lowers your playoff odds by 5.5 points.');
});

test('optimistic pick touches one matchup only', () => {
  const next = withPick(
    [
      { matchup_id: '1', my_pick: null },
      { matchup_id: '2', my_pick: '3' },
    ],
    '1',
    '2',
  );
  assert.deepEqual(next, [
    { matchup_id: '1', my_pick: '2' },
    { matchup_id: '2', my_pick: '3' },
  ]);
});

test('record and player search', () => {
  assert.equal(recordLabel({ correct: 7, graded: 10 }), '7-3');
  assert.equal(recordLabel(undefined), '0-0');
  const pool = [{ name: 'Travis Kelce' }, { name: 'Kelvin Harmon' }, { name: 'Jake Elliott' }];
  assert.deepEqual(
    matchPlayersByName(pool, 'kel').map((p) => p.name),
    ['Kelvin Harmon', 'Travis Kelce'],
  );
  assert.deepEqual(matchPlayersByName(pool, 'k'), []);
});

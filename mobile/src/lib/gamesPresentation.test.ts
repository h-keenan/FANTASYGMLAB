import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  formatDelta,
  formatOdds,
  gamesReasonAction,
  gamesReasonMessage,
  matchPlayersByName,
  recordLabel,
  tradeOddsView,
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

test('tradeOddsView states the change with margin and sample size, omits when thin', () => {
  const base = {
    reason: '',
    baseline: { playoff_probability: 40, title_probability: 5 },
    scenario: { playoff_probability: 52, title_probability: 8 },
    change: { playoff_probability: 12, title_probability: 3, within_noise: false, title_within_noise: false },
    margin_points: 2.5,
    trials: 3000,
    slope_fitted: true,
    weeks_remaining: 6,
  };
  const view = tradeOddsView(base)!;
  assert.equal(view.headline, 'Playoff odds 40% to 52% (+12.0 pts)');
  assert.equal(view.titleLine, 'Title odds 5% to 8% (+3.0 pts)');
  assert.match(view.detail, /3,000 simulated seasons/);
  const noisy = tradeOddsView({
    ...base,
    scenario: { playoff_probability: 41, title_probability: null },
    change: { playoff_probability: 1, title_probability: null, within_noise: true },
  })!;
  assert.match(noisy.headline, /no measurable change/);
  assert.equal(noisy.titleLine, null);
  assert.equal(tradeOddsView({ ...base, picks_excluded: true, slope_fitted: false })!.notes.length, 2);
  assert.equal(tradeOddsView({ ...base, reason: 'no_games_left' }), null);
});

test('seasonOddsLine shows playoff and title odds with the sample size, hides when not ready', async () => {
  const { seasonOddsLine } = await import('./gamesPresentation.ts');
  const line = seasonOddsLine({
    reason: '',
    my_team: { playoff_probability: 61.4, title_probability: 0.4 },
    title_odds: { available: true, reason: '' },
    weeks_remaining: 6,
    trials: 3000,
    slope_fitted: true,
  })!;
  assert.equal(line.headline, 'Playoff odds 61% · Title odds <1%');
  assert.match(line.caption, /3,000 simulated seasons/);
  const noTitle = seasonOddsLine({
    my_team: { playoff_probability: 61.4, title_probability: 2 },
    title_odds: { available: false, reason: 'playoffs_underway' },
  })!;
  assert.equal(noTitle.headline, 'Playoff odds 61%');
  assert.equal(seasonOddsLine({ reason: 'offseason', my_team: null }), null);
  assert.equal(seasonOddsLine(undefined), null);
});

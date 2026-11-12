// Run with: node --experimental-strip-types --test src/lib/simPresentation.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  isSimOffError,
  simFactorImpact,
  simFactorKindLabel,
  simFactorsIntro,
  simFinishRange,
  simFormatPercent,
  simFormatPointsSwing,
  simGate,
  simHeadline,
  simNoteMessages,
  simOddsTone,
  simOrdinal,
  simReasonMessage,
  simScopeLine,
  simWinsRange,
  type SimForecast,
} from './simPresentation.ts';

function forecast(overrides: Partial<SimForecast> = {}): SimForecast {
  return {
    samples: 80,
    start_week: 10,
    regular_season_end: 14,
    weeks_remaining: 5,
    team: { team_id: '1', name: 'Mine' },
    current: { wins: 5, losses: 4, ties: 0 },
    odds: { playoffs: 0.62, finals: 0.2, title: 0.09, playoff_spots: 6 },
    record: { wins: 8.6, losses: 5.4, wins_low: 7, wins_high: 10, projected: '9-5', games: 14 },
    finish: { median: 4, low: 2, high: 7, teams: 12, distribution: [] },
    swing_factors: [],
    ...overrides,
  };
}

test('gate: Pro upsell, unavailable, and ready', () => {
  assert.deepEqual(simGate({ ok: true, reason: 'premium_required', is_premium: false, upsell: { title: 't', body: 'b' } }), {
    kind: 'premium',
    upsell: { title: 't', body: 'b' },
  });
  assert.equal(simGate(null).kind, 'unavailable');
  assert.equal(simGate({ ok: true, enabled: false }).kind, 'unavailable');
  assert.equal(simGate({ ok: true, reason: '', is_premium: true }).kind, 'ready');
});

test('a 404 means the forecast is not switched on', () => {
  assert.equal(isSimOffError({ status: 404 }), true);
  assert.equal(isSimOffError({ status: 500 }), false);
  assert.equal(isSimOffError(null), false);
});

test('reason codes get customer-safe copy; success is empty', () => {
  assert.equal(simReasonMessage(''), '');
  assert.match(simReasonMessage('season_complete'), /regular season is over/);
  assert.match(simReasonMessage('who_knows'), /could not build/);
});

test('notes become plain caveats and unknown ones are dropped', () => {
  assert.deepEqual(simNoteMessages(['bye_weeks_unavailable', 'schedule_estimated_weeks:9,10', 'mystery']), [
    'Bye weeks could not be loaded, so no player is on bye.',
    'The schedule for weeks 9,10 is estimated.',
  ]);
});

test('percent never shows a false 0% or 100%', () => {
  assert.equal(simFormatPercent(0.004), '<1%');
  assert.equal(simFormatPercent(0.996), '>99%');
  assert.equal(simFormatPercent(0.62), '62%');
  assert.equal(simFormatPercent(0), '0%');
  assert.equal(simFormatPercent(undefined), '-');
});

test('odds tone follows how comfortable the position is', () => {
  assert.equal(simOddsTone(0.8), 'success');
  assert.equal(simOddsTone(0.4), 'accent');
  assert.equal(simOddsTone(0.2), 'warning');
  assert.equal(simOddsTone(0.02), 'danger');
});

test('ordinals, ranges and swings read naturally', () => {
  assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 22].map(simOrdinal), ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd']);
  assert.equal(simFinishRange(forecast().finish), '2nd to 7th');
  assert.equal(simFinishRange({ ...forecast().finish, low: 3, high: 3, median: 3 }), '3rd');
  assert.equal(simWinsRange(forecast().record), '7 to 10 wins');
  assert.equal(simWinsRange({ ...forecast().record, wins_low: 9, wins_high: 9 }), '9 wins');
  assert.equal(simFormatPointsSwing(0.153), '+15 pts');
  assert.equal(simFormatPointsSwing(-0.04), '-4 pts');
});

test('headline matches the playoff odds band', () => {
  assert.match(simHeadline(forecast({ odds: { playoffs: 0.95, finals: 0.4, title: 0.2, playoff_spots: 6 } })), /near lock/);
  assert.match(simHeadline(forecast()), /good shape.*62%/);
  assert.match(simHeadline(forecast({ odds: { playoffs: 0.4, finals: 0.1, title: 0.04, playoff_spots: 6 } })), /coin flip/);
  assert.match(simHeadline(forecast({ odds: { playoffs: 0.15, finals: 0.01, title: 0, playoff_spots: 6 } })), /outside looking in/);
  assert.match(simHeadline(forecast({ odds: { playoffs: 0.02, finals: 0, title: 0, playoff_spots: 6 } })), /long shot/);
});

test('scope line always says as-of, current rosters and rest of season', () => {
  const line = simScopeLine(forecast(), 'remaining', '2026-11-12T12:00:00+00:00');
  assert.match(line, /As of Nov 1[12]/);
  assert.match(line, /on current rosters, rest of season \(5 games left\)/);
  assert.match(simScopeLine(forecast({ weeks_remaining: 1 })), /\(1 game left\)/);
  assert.match(simScopeLine(forecast(), 'full'), /offseason/);
});

test('swing factors: labels, impact and the empty-state intro', () => {
  assert.equal(simFactorKindLabel('game'), 'Key game');
  assert.equal(simFactorKindLabel('waiver'), 'Waiver wire');
  assert.equal(simFactorKindLabel('trade'), 'Trade');
  const game = { kind: 'game' as const, title: 't', detail: 'd', playoff_delta: 0.35, title_delta: 0.05 };
  assert.equal(simFactorImpact(game), '+35 pts playoff odds, +5 pts title odds');
  assert.equal(simFactorImpact({ ...game, title_delta: 0 }), '+35 pts playoff odds');
  assert.match(simFactorsIntro([]), /Nothing stands out/);
  assert.match(simFactorsIntro([game]), /move your odds most/);
});

// Run with: node --experimental-strip-types --test src/lib/guessThePlayerPrompt.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { guessThePlayerStreakCaption, shouldShowGuessThePlayerPrompt } from './guessThePlayerPrompt.ts';
import type { GuessThePlayerPrompt, GuessThePlayerResponse } from './api.ts';

function makePrompt(overrides: Partial<GuessThePlayerPrompt> = {}): GuessThePlayerPrompt {
  return {
    pick_id: 'pick-today',
    season: 2026,
    week: 7,
    position: 'WR',
    tier: 'contributor',
    stat_line: [{ label: 'Targets', value: 9 }],
    fantasy_points_ppr: 21.4,
    options: [
      { player_id: 'p1', name: 'Real Answer' },
      { player_id: 'p2', name: 'Distractor One' },
      { player_id: 'p3', name: 'Distractor Two' },
      { player_id: 'p4', name: 'Distractor Three' },
    ],
    ...overrides,
  };
}

function makeResponse(overrides: Partial<GuessThePlayerResponse> = {}): GuessThePlayerResponse {
  return {
    ok: true,
    available: true,
    reason: '',
    prompt: makePrompt(),
    already_answered: false,
    last_result: null,
    correct_player: null,
    streak: { current_streak: 0, best_streak: 0 },
    ...overrides,
  };
}

test('shouldShowGuessThePlayerPrompt: shows when available, unanswered, and never dismissed', () => {
  assert.equal(shouldShowGuessThePlayerPrompt(makeResponse(), null), true);
});

test('shouldShowGuessThePlayerPrompt: hides when the backend has no pick available today', () => {
  assert.equal(
    shouldShowGuessThePlayerPrompt(makeResponse({ available: false, prompt: null }), null),
    false,
  );
});

test('shouldShowGuessThePlayerPrompt: hides when the response is null (still loading / fetch failed)', () => {
  assert.equal(shouldShowGuessThePlayerPrompt(null, null), false);
});

test('shouldShowGuessThePlayerPrompt: hides once the user has already answered today, even with no local dismiss recorded', () => {
  assert.equal(shouldShowGuessThePlayerPrompt(makeResponse({ already_answered: true }), null), false);
});

test("shouldShowGuessThePlayerPrompt: hides when this device already dismissed TODAY'S pick_id without answering", () => {
  assert.equal(shouldShowGuessThePlayerPrompt(makeResponse(), 'pick-today'), false);
});

test('shouldShowGuessThePlayerPrompt: still shows when the local dismiss is for a STALE pick_id (a prior day)', () => {
  assert.equal(shouldShowGuessThePlayerPrompt(makeResponse(), 'pick-yesterday'), true);
});

test('guessThePlayerStreakCaption: no streak at all', () => {
  assert.equal(guessThePlayerStreakCaption({ current_streak: 0, best_streak: 0 }), 'Start a streak');
});

test('guessThePlayerStreakCaption: current streak is also the best (no separate best shown)', () => {
  assert.equal(guessThePlayerStreakCaption({ current_streak: 3, best_streak: 3 }), '3 in a row');
});

test('guessThePlayerStreakCaption: a lapsed streak still shows the real best alongside the reset current', () => {
  assert.equal(
    guessThePlayerStreakCaption({ current_streak: 0, best_streak: 5 }),
    '0 in a row · Best 5',
  );
});

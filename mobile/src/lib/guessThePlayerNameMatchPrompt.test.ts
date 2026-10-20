// Run with: node --experimental-strip-types --test src/lib/guessThePlayerNameMatchPrompt.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { guessThePlayerStreakCaption, shouldShowGuessThePlayerNameMatchPrompt } from './guessThePlayerNameMatchPrompt.ts';
import type { GuessThePlayerNameMatchPrompt, GuessThePlayerNameMatchResponse } from './api.ts';

function makePrompt(overrides: Partial<GuessThePlayerNameMatchPrompt> = {}): GuessThePlayerNameMatchPrompt {
  return {
    pick_id: 'pair-today',
    season: 2026,
    week: 7,
    famous_player: { player_id: 'p-famous', name: 'Known Name', team: 'KC', position: 'RB', tier: 'elite' },
    obscure_player: { player_id: 'p-obscure', name: 'Unknown Name', team: 'NYJ', position: 'RB', tier: 'depth' },
    slots: {
      A: { stat_line: [{ label: 'Rush Attempts', value: 14 }], fantasy_points_ppr: 18 },
      B: { stat_line: [{ label: 'Rush Attempts', value: 22 }], fantasy_points_ppr: 30 },
    },
    ...overrides,
  };
}

function makeResponse(
  overrides: Partial<GuessThePlayerNameMatchResponse> = {},
): GuessThePlayerNameMatchResponse {
  return {
    ok: true,
    available: true,
    reason: '',
    prompt: makePrompt(),
    already_answered: false,
    last_result: null,
    correct_pairing: null,
    streak: { current_streak: 0, best_streak: 0 },
    ...overrides,
  };
}

test('shouldShowGuessThePlayerNameMatchPrompt: shows when available, unanswered, and never dismissed', () => {
  assert.equal(shouldShowGuessThePlayerNameMatchPrompt(makeResponse(), null), true);
});

test('shouldShowGuessThePlayerNameMatchPrompt: hides when the backend has no pairing available today', () => {
  assert.equal(
    shouldShowGuessThePlayerNameMatchPrompt(makeResponse({ available: false, prompt: null }), null),
    false,
  );
});

test('shouldShowGuessThePlayerNameMatchPrompt: hides when the response is null (still loading / fetch failed)', () => {
  assert.equal(shouldShowGuessThePlayerNameMatchPrompt(null, null), false);
});

test('shouldShowGuessThePlayerNameMatchPrompt: hides once the user has already answered today, even with no local dismiss recorded', () => {
  assert.equal(
    shouldShowGuessThePlayerNameMatchPrompt(makeResponse({ already_answered: true }), null),
    false,
  );
});

test("shouldShowGuessThePlayerNameMatchPrompt: hides when this device already dismissed TODAY'S pick_id without answering", () => {
  assert.equal(shouldShowGuessThePlayerNameMatchPrompt(makeResponse(), 'pair-today'), false);
});

test('shouldShowGuessThePlayerNameMatchPrompt: still shows when the local dismiss is for a STALE pick_id (a prior day)', () => {
  assert.equal(shouldShowGuessThePlayerNameMatchPrompt(makeResponse(), 'pair-yesterday'), true);
});

// Same exact function as the original game's own test file (lib/
// guessThePlayerPrompt.test.ts) -- this mode reuses it unchanged, it is
// not reimplemented here.
test('guessThePlayerStreakCaption: no streak at all', () => {
  assert.equal(guessThePlayerStreakCaption({ current_streak: 0, best_streak: 0 }), 'Start a streak');
});

test('guessThePlayerStreakCaption: a lapsed streak still shows the real best alongside the reset current', () => {
  assert.equal(
    guessThePlayerStreakCaption({ current_streak: 0, best_streak: 5 }),
    '0 in a row · Best 5',
  );
});

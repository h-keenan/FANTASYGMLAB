import type { GuessThePlayerResponse, GuessThePlayerStreak } from './api';

/**
 * Pure "should the popup show" decision, pulled out of
 * components/GuessThePlayerPrompt.tsx so it's testable under plain
 * `node --test` without mounting a React Native component (see
 * lib/queryClient.test.ts for the same "keep the storage-dependent wrapper
 * thin, test the real decision logic directly" split).
 *
 * `already_answered` alone covers "don't show it again today" for a real
 * submitted guess — the backend already knows that. `dismissedPickId` only
 * covers the one case the backend can't see: closed without answering (see
 * lib/guessThePlayerDismissed.ts).
 */
export function shouldShowGuessThePlayerPrompt(
  response: GuessThePlayerResponse | null | undefined,
  dismissedPickId: string | null | undefined,
): boolean {
  if (!response || !response.available || !response.prompt) return false;
  if (response.already_answered) return false;
  if (dismissedPickId && dismissedPickId === response.prompt.pick_id) return false;
  return true;
}

/** Same caption wording as web-next's GuessThePlayerCard.tsx streakCaption —
 * kept as one plain function here too so a future copy change only has to
 * happen in one place per platform, and so it's testable in isolation. */
export function guessThePlayerStreakCaption(streak: GuessThePlayerStreak): string {
  if (streak.current_streak <= 0 && streak.best_streak <= 0) return 'Start a streak';
  const current = `${streak.current_streak} in a row`;
  if (streak.best_streak <= streak.current_streak) return current;
  return `${current} · Best ${streak.best_streak}`;
}

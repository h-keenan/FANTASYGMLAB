import type { GuessThePlayerNameMatchResponse } from './api';
import { guessThePlayerStreakCaption } from './guessThePlayerPrompt.ts';

/**
 * Pure "should the popup show" decision for the "Who is who?" name-match
 * mode — same split as lib/guessThePlayerPrompt.ts's own
 * shouldShowGuessThePlayerPrompt (testable under plain `node --test`
 * without mounting a React Native component), kept as its own small
 * function here (rather than a shared generic) because the two response
 * shapes genuinely differ: this mode's `prompt` carries both real
 * identities plus unlabeled `slots`, not a hidden-identity `options` list.
 *
 * `already_answered` alone covers "don't show it again today" for a real
 * submitted guess — the backend already knows that. `dismissedPickId`
 * only covers the one case the backend can't see: closed without
 * answering (see lib/guessThePlayerNameMatchDismissed.ts).
 */
export function shouldShowGuessThePlayerNameMatchPrompt(
  response: GuessThePlayerNameMatchResponse | null | undefined,
  dismissedPickId: string | null | undefined,
): boolean {
  if (!response || !response.available || !response.prompt) return false;
  if (response.already_answered) return false;
  if (dismissedPickId && dismissedPickId === response.prompt.pick_id) return false;
  return true;
}

/** Re-exported rather than reimplemented: the streak shape
 * ({current_streak, best_streak}) is identical to the original game's, so
 * guessThePlayerStreakCaption already works here unchanged — same exact
 * caption copy/logic coridian_'s spec asked this mode to reuse. */
export { guessThePlayerStreakCaption };

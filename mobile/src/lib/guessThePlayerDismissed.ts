import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'fgl:guess-the-player-dismissed-pick-id';

/**
 * Which day's "Guess the Player" pick this device already closed WITHOUT
 * answering — same single-key, "store the identifier, compare on next
 * load" shape as lib/trialLapsedSeen.ts. Keyed by `pick_id` (today's
 * featured (player, week), see modules/guess_the_player.py's
 * compute_pick_id) rather than a plain boolean, so a new day's pick (a new
 * pick_id) is never suppressed by a stale dismiss from a previous day.
 *
 * This is deliberately separate from the backend's `already_answered` flag:
 * that only tracks a real submitted guess (GuessThePlayerPrompt.tsx already
 * treats `already_answered` as "don't show the popup again today," no
 * local state needed for that case). This key exists purely for "closed
 * it without answering" — the one case the backend has no way to know
 * about.
 */
export async function getDismissedGuessThePlayerPickId(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export async function setDismissedGuessThePlayerPickId(pickId: string): Promise<void> {
  if (!pickId) return;
  try {
    await AsyncStorage.setItem(KEY, pickId);
  } catch {
    // Best-effort — worst case the popup shows again next launch.
  }
}

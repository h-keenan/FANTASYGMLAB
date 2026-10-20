import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'fgl:guess-the-player-name-match-dismissed-pick-id';

/**
 * "Who is who?" name-match mode's own "closed without answering" record —
 * same single-key, pick_id-keyed shape as lib/guessThePlayerDismissed.ts,
 * but under its OWN distinct AsyncStorage key so a dismiss of one game's
 * popup can never suppress the other's (this mode has its own daily
 * pick_id namespace — modules/guess_the_player.py's
 * compute_name_match_pick_id — so even if both picks' raw ids ever
 * happened to coincide, the keys themselves still can't collide).
 *
 * This is deliberately separate from the backend's `already_answered`
 * flag: that only tracks a real submitted guess (the popup component
 * already treats `already_answered` as "don't show again today," no local
 * state needed for that case). This key exists purely for "closed it
 * without answering" — the one case the backend has no way to know about.
 */
export async function getDismissedGuessThePlayerNameMatchPickId(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export async function setDismissedGuessThePlayerNameMatchPickId(pickId: string): Promise<void> {
  if (!pickId) return;
  try {
    await AsyncStorage.setItem(KEY, pickId);
  } catch {
    // Best-effort — worst case the popup shows again next launch.
  }
}

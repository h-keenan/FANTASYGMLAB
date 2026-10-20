const KEY = "fd:guess-the-player-name-match-dismissed-pick-id";

/**
 * "Who is who?" name-match mode's own dismiss-persistence, built from the
 * start with the real fix lib/guessThePlayerDismissed.ts needed to be
 * retrofitted with (coridian_: "if you exit that module out, it shouldn't
 * pop back up" — a plain page-view-scoped useState resets on every fresh
 * mount). Same pick_id-keyed shape, but under its OWN distinct storage
 * key — this mode has its own daily pick_id namespace
 * (modules/guess_the_player.py's compute_name_match_pick_id), so it can
 * never collide with the original game's dismissed-pick storage key even
 * if both picks' raw ids ever happened to coincide.
 *
 * Every localStorage access is wrapped in try/catch — it can throw in a
 * private window or with site data cleared, and worst case here is just
 * the card showing again, never a broken page.
 */
export function getDismissedGuessThePlayerNameMatchPickId(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setDismissedGuessThePlayerNameMatchPickId(pickId: string): void {
  if (!pickId) return;
  try {
    window.localStorage.setItem(KEY, pickId);
  } catch {
    // Best-effort — worst case the card shows again next page view.
  }
}

const KEY = "fd:guess-the-player-dismissed-pick-id";

/**
 * coridian_, 2026-10-19: "if you exit that module out, it shouldn't pop
 * back up" — real bug. GuessThePlayerCard.tsx's dismiss used to be plain
 * `useState`, explicitly scoped to "this page view" only (see that
 * component's own prior doc comment), so navigating away from Dashboard
 * and back (a fresh mount) reset it and the card reappeared immediately.
 *
 * Same shape as mobile's lib/guessThePlayerDismissed.ts: keyed by `pick_id`
 * (today's featured player, see modules/guess_the_player.py's
 * compute_pick_id) rather than a plain boolean, so a new day's pick is
 * never suppressed by a stale dismiss from a previous day. Deliberately
 * separate from the backend's `already_answered` flag, which already
 * covers "don't show again today" for a real submitted guess — this only
 * covers "closed it without answering," the one case the backend has no
 * way to know about.
 *
 * Every localStorage access is wrapped in try/catch — it can throw in a
 * private window or with site data cleared, and worst case here is just
 * the card showing again, never a broken page.
 */
export function getDismissedGuessThePlayerPickId(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setDismissedGuessThePlayerPickId(pickId: string): void {
  if (!pickId) return;
  try {
    window.localStorage.setItem(KEY, pickId);
  } catch {
    // Best-effort — worst case the card shows again next page view.
  }
}

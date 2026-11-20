import { simRookieNoticeKey } from "@/lib/simGame";
import { userGet, userSet } from "@/lib/userStorage";

/**
 * Per-game "the generated rookie class popup was already dismissed" flag.
 * Web keeps it in localStorage (the app uses AsyncStorage). Every access is in
 * try/catch: storage can throw in a private window, and the worst case is the
 * popup showing once more.
 */
export function isSimRookieNoticeSeen(gameId: string): boolean {
  try {
    return userGet(simRookieNoticeKey(gameId)) === "1";
  } catch {
    return false;
  }
}

export function setSimRookieNoticeSeen(gameId: string): void {
  try {
    userSet(simRookieNoticeKey(gameId), "1");
  } catch {
    // Best-effort.
  }
}

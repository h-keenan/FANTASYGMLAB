/**
 * Forced sign-out detection, one definition for web and app (byte-identical lib twin; pure, no imports).
 * Audit: docs/audits/2026-11-auth-offline-error-paths.md.
 *
 * A session can end without the user asking: the refresh token was revoked (signed out on another device, password change),
 * the account was deleted, or another tab signed out. auth-js reports each as a SIGNED_OUT event. Before this, pages saw
 * `session === null` and silently bounced to the landing page (web) or swapped to the login stack (app) with no word why.
 * The user now gets a plain "your session ended" note on the sign-in form, and the web remembers where they were.
 */

export const SESSION_ENDED_NOTICE = "Your session ended, so we signed you out. Sign in again to pick up where you left off.";

export interface SignOutEventInput {
  event: string;
  /** Whether this provider had a session before the event. */
  hadSession: boolean;
  /** True while the user's own sign-out (or account deletion) is in flight. */
  userInitiated: boolean;
}

/** True when a SIGNED_OUT event ended a session the user did not end themselves. */
export function isForcedSignOut({ event, hadSession, userInitiated }: SignOutEventInput): boolean {
  return event === "SIGNED_OUT" && hadSession && !userInitiated;
}

const SESSION_ENDED_KEY = "fd_session_ended_at";
const SESSION_ENDED_TTL_MS = 60 * 60 * 1000;

/** Remembers (for a reload between the sign-out and the sign-in form) that the last sign-out was forced. */
export function markSessionEnded(storage: Pick<Storage, "setItem"> | null | undefined, now: number = Date.now()): void {
  try {
    storage?.setItem(SESSION_ENDED_KEY, String(now));
  } catch {
    /* storage unavailable: the in-memory flag still shows the note */
  }
}

export function readSessionEnded(storage: Pick<Storage, "getItem"> | null | undefined, now: number = Date.now()): boolean {
  try {
    const at = Number(storage?.getItem(SESSION_ENDED_KEY));
    return Number.isFinite(at) && at > 0 && now >= at && now - at <= SESSION_ENDED_TTL_MS;
  } catch {
    return false;
  }
}

export function clearSessionEnded(storage: Pick<Storage, "removeItem"> | null | undefined): void {
  try {
    storage?.removeItem(SESSION_ENDED_KEY);
  } catch {
    /* ignore */
  }
}

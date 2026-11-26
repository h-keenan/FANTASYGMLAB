/**
 * Real account-creation analytics for EVERY sign-up path (email, Google, Apple, guest), deduped per account.
 *
 * Before 2026-11 only the email form emitted signup_completed, so Google/Apple/guest sign-ups never appeared in the
 * funnel and email users who confirmed by link were never counted as completed. Now AuthContext reports the verified
 * Supabase user here whenever a session appears; this decides (purely, from the user object + a per-account local
 * marker) whether it is a brand-new registered account, a new guest session, or nothing.
 *
 * Reconciled server-side against real account creation (modules.account_acquisition +
 * docs/supabase_account_acquisition_2026_11.sql); the metrics layer also dedupes per person. No email, name or
 * provider id is ever put in an event: only signup_method (email | google | apple | other).
 */

export type SignupMethod = "email" | "google" | "apple" | "other";

export interface SignupUser {
  id?: string;
  is_anonymous?: boolean;
  created_at?: string;
  email_confirmed_at?: string | null;
  app_metadata?: { provider?: string; providers?: string[] } | null;
  identities?: Array<{ provider?: string }> | null;
}

export interface MarkerStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

/** A confirmation link or OAuth return counts as "just now" within this window. */
export const RECENT_MS = 15 * 60 * 1000;

const DONE = "fd_acct_event_v1:";
const GUEST = "fd_guest_seen_v1:";

export function signupMethodOf(user: SignupUser): SignupMethod {
  const candidates = [
    ...(user.identities ?? []).map((i) => i.provider),
    user.app_metadata?.provider,
    ...(user.app_metadata?.providers ?? []),
  ];
  for (const raw of candidates) {
    const p = String(raw ?? "").toLowerCase();
    if (p === "google" || p === "apple" || p === "email") return p;
  }
  return "other";
}

function recent(iso: string | null | undefined, nowMs: number): boolean {
  if (!iso) return false;
  const t = Date.parse(iso);
  return Number.isFinite(t) && nowMs - t >= -60_000 && nowMs - t <= RECENT_MS;
}

export type AccountEvent =
  | { kind: "signup"; event: "signup_completed"; method: SignupMethod }
  | { kind: "guest"; event: "guest_session_started" };

/**
 * Pure-ish decision (touches only `storage` markers). Returns the event to emit, or null. Each account yields at most
 * ONE account event per browser: a guest first reports guest_session_started, and later (same user id, after the
 * guest is upgraded) signup_completed.
 */
export function detectAccountEvent(
  user: SignupUser | null | undefined,
  storage: MarkerStorage | null,
  nowMs: number = Date.now(),
): AccountEvent | null {
  const id = String(user?.id ?? "");
  if (!user || !id || !storage) return null;
  try {
    if (user.is_anonymous) {
      if (storage.getItem(GUEST + id)) return null;
      storage.setItem(GUEST + id, "1");
      return recent(user.created_at, nowMs) ? { kind: "guest", event: "guest_session_started" } : null;
    }
    if (storage.getItem(DONE + id)) return null;
    const method = signupMethodOf(user);
    const wasGuest = Boolean(storage.getItem(GUEST + id));
    const isNew =
      wasGuest ||
      recent(user.created_at, nowMs) ||
      // Email sign-up confirmed by link: the account is older than the click, the confirmation is not.
      (method === "email" && recent(user.email_confirmed_at, nowMs));
    if (!isNew) return null;
    storage.setItem(DONE + id, "1");
    storage.removeItem(GUEST + id);
    return { kind: "signup", event: "signup_completed", method };
  } catch {
    return null;
  }
}

/**
 * Claim the one signup_completed for this account from the email form. Returns false when the auth listener already
 * reported it (so the two paths never double-count); true when the caller should emit. A user without an id (never
 * happens with a real session) is always claimable.
 */
export function claimSignup(user: SignupUser | null | undefined, storage: MarkerStorage | null): boolean {
  const id = String(user?.id ?? "");
  if (!id || !storage) return true;
  try {
    if (storage.getItem(DONE + id)) return false;
    storage.setItem(DONE + id, "1");
    storage.removeItem(GUEST + id);
  } catch {
    // storage blocked: emit; the metrics layer dedupes per person
  }
  return true;
}

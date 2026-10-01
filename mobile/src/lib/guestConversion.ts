/**
 * Guest -> account conversion (Fix 3, welcome/signup audit).
 *
 * Mobile's "Continue as Guest" (LoginScreen.tsx) signs in via Supabase
 * anonymous auth (`supabase.auth.signInAnonymously()` — AuthContext.tsx's
 * `signInAsGuest`), which creates a REAL `auth.users` row with its own
 * stable `user.id`. Every saved league, GM Target, trade-outcome row, etc.
 * is already RLS-scoped to `auth.uid() = user_id` against THAT id.
 *
 * This is a materially different starting point from web's guest model
 * (modules.guest_conversion): a web guest has no Supabase session at all,
 * so web's conversion has to snapshot in-memory workspace state
 * (capture_guest_resume) and manually re-apply it after a brand-new
 * account is created (finish_auth_from_guest) — the old and new identities
 * are unrelated. A mobile guest already has a durable identity; the
 * correct, minimal fix is Supabase's own anonymous -> permanent upgrade
 * (`supabase.auth.updateUser({ email, password })` called on the SAME,
 * still-signed-in anonymous session) rather than a sign-out + sign-up,
 * which would silently abandon the anonymous user's id and strand every
 * row already keyed to it — exactly the "dead end" this fix closes.
 * Because the user id never changes, no snapshot/restore step is needed:
 * saved_leagues and everything else tied to that id simply stays reachable
 * once the identity carries real credentials.
 *
 * This module holds only the pure, framework-free pieces (mobile has no
 * jest/RN testing harness configured — see backgroundRetry.test.ts — so
 * anything that needs a live Supabase session lives in AuthContext.tsx
 * instead, untested the same way the rest of that context already is).
 */

export interface GuestSessionLike {
  user?: {
    is_anonymous?: boolean | null;
  } | null;
}

/**
 * True only for a real, currently-anonymous Supabase session — never for
 * signed-out (`session` null/undefined) or an already-permanent account.
 * Conversion only ever makes sense in that one state.
 */
export function canConvertGuestToAccount(session: GuestSessionLike | null | undefined): boolean {
  return Boolean(session?.user?.is_anonymous);
}

/**
 * Returns a user-facing error string, or null when the input is acceptable
 * to send to `supabase.auth.updateUser`. Mirrors the same minimal bar
 * LoginScreen's existing sign-up submit button enforces (non-empty email
 * and password) rather than inventing stricter rules — Supabase itself is
 * still the real validator (password length/breach rules, email format).
 */
export function validateGuestConversionInput(email: string, password: string): string | null {
  const trimmedEmail = email.trim();
  if (!trimmedEmail || !trimmedEmail.includes('@')) {
    return 'Enter a valid email address.';
  }
  if (!password || password.length < 6) {
    return 'Password must be at least 6 characters.';
  }
  return null;
}

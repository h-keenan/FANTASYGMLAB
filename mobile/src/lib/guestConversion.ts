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

/**
 * Owner decision (coridian_, 2026-10-25): guests may not buy. Mirrors web
 * (#1521: TrialAccountGate + server 403 account_required). A guest must
 * create an account (in-place upgrade, same user id) before any
 * purchase/trial button is shown. Restore Purchases is NOT gated (Apple).
 */
export const GUEST_PURCHASE_CTA = 'Create an account to start your free trial';
export const GUEST_PURCHASE_HINT =
  'Free trials and subscriptions need an account so your Premium follows you across devices.';

export function guestMustCreateAccountToBuy(session: GuestSessionLike | null | undefined): boolean {
  return canConvertGuestToAccount(session);
}

// ---------------------------------------------------------------------------
// In-place linking for every sign-up path (email, Apple, Google).
//
// `signInWithIdToken` on an anonymous session signs in as a DIFFERENT user and
// strands the guest's id/data; `linkIdentity({ provider, token })` attaches the
// provider identity to the CURRENT user instead (needs "Allow manual linking"
// in the Supabase project). Web already does the OAuth equivalent
// (web-next/src/lib/guestUpgrade.ts).
// ---------------------------------------------------------------------------

export type GuestLinkFailure = 'email-exists' | 'identity-exists' | 'link-unavailable' | 'other';

interface ErrorLike {
  code?: string | null;
  message?: string | null;
}

export function classifyGuestLinkError(err: ErrorLike | null | undefined): GuestLinkFailure {
  if (!err) return 'other';
  const code = err.code ?? '';
  const message = (err.message ?? '').toLowerCase();
  if (code === 'manual_linking_disabled' || message.includes('manual linking is disabled')) return 'link-unavailable';
  if (code === 'identity_already_exists' || message.includes('identity is already linked')) return 'identity-exists';
  if (
    code === 'email_exists' ||
    code === 'user_already_exists' ||
    message.includes('already been registered') ||
    message.includes('already registered') ||
    message.includes('email address has already')
  ) {
    return 'email-exists';
  }
  return 'other';
}

export const GUEST_EMAIL_EXISTS_MESSAGE =
  "That email already has an account. Sign in to it instead — note that what you set up as a guest won't carry over.";
export const GUEST_IDENTITY_EXISTS_MESSAGE =
  "That Apple/Google account is already in use. Sign in to it instead — note that what you set up as a guest won't carry over.";
export const GUEST_LINK_UNAVAILABLE_MESSAGE =
  "We couldn't link this sign-in to your guest session right now. Try email instead, or try again later.";

export function guestLinkFailureMessage(failure: GuestLinkFailure, fallback: string): string {
  switch (failure) {
    case 'email-exists':
      return GUEST_EMAIL_EXISTS_MESSAGE;
    case 'identity-exists':
      return GUEST_IDENTITY_EXISTS_MESSAGE;
    case 'link-unavailable':
      return GUEST_LINK_UNAVAILABLE_MESSAGE;
    default:
      return fallback;
  }
}

export interface AuthResult {
  error: string | null;
  failure?: GuestLinkFailure;
}

interface IdTokenAuthClient {
  signInWithIdToken(c: { provider: 'apple' | 'google'; token: string; nonce?: string }): Promise<{ error: ErrorLike | null }>;
  linkIdentity(c: { provider: 'apple' | 'google'; token: string; nonce?: string }): Promise<{ error: ErrorLike | null }>;
}

/**
 * Exchanges a native Apple/Google id token. With `linkGuest` the identity is
 * LINKED to the current anonymous user (same user id); otherwise it is a plain
 * sign-in. A guest is never silently replaced: on a link failure the caller
 * gets a plain-language error and a `failure` kind, and no sign-in happens.
 */
export async function exchangeIdToken(
  client: IdTokenAuthClient,
  args: { provider: 'apple' | 'google'; token: string; nonce?: string; linkGuest: boolean },
): Promise<AuthResult> {
  const { linkGuest, ...credentials } = args;
  const { error } = linkGuest ? await client.linkIdentity(credentials) : await client.signInWithIdToken(credentials);
  if (!error) return { error: null };
  if (!linkGuest) return { error: error.message ?? 'Sign-in failed.' };
  const failure = classifyGuestLinkError(error);
  return { error: guestLinkFailureMessage(failure, error.message ?? 'Sign-in failed.'), failure };
}

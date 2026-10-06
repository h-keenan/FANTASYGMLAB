/**
 * Pure, RN-free home for "which authenticated Supabase user does the
 * in-memory/persisted React Query cache currently belong to."
 *
 * Deliberately decoupled from supabase.ts/AuthContext.tsx (both pull in
 * RN-only modules — AsyncStorage's native bridge, react-native's AppState —
 * that aren't importable by this repo's plain `node --test` unit tests; see
 * backgroundRetry.ts's own doc comment for the same constraint) so that
 * per-user query-key scoping (queryKeys.ts) and the "did the authenticated
 * user change" check (AuthContext.tsx, requirement 5 of the cache/auth
 * fix) stay unit-testable without a RN/Metro runtime.
 *
 * AuthContext.tsx is the single writer: it calls `setCurrentAuthScopeUserId`
 * every time Supabase reports a session — both the initial
 * `getSession()` resolution and every `onAuthStateChange` event — using
 * that session's `user.id`, or `null` for signed-out/no-session.
 */

export const ANONYMOUS_QUERY_SCOPE = 'anonymous';

/** The AsyncStorage key under which the last-known authenticated user id is
 * persisted across app restarts — a small, separate marker, NOT part of
 * the React Query persisted-cache blob itself (see queryClient.ts). */
export const AUTH_SCOPE_STORAGE_KEY = 'fgl:auth-scope-user-id';

let currentUserId: string | null = null;

/** Records the currently-authenticated Supabase user id (or `null` when
 * signed out) so `userScopeKey()` below can scope new query keys correctly. */
export function setCurrentAuthScopeUserId(userId: string | null): void {
  currentUserId = userId;
}

export function getCurrentAuthScopeUserId(): string | null {
  return currentUserId;
}

/**
 * The stable scope root prefixed onto every persisted, user-specific query
 * key — see queryKeys.ts. `['user', <supabase user id>]` for a signed-in
 * user, or `['user', 'anonymous']` pre-auth/signed-out so a key is always
 * well-formed (never `undefined`) even before the first session resolves.
 *
 * This is what makes `['user', userId, 'league', leagueId, 'dashboard']`
 * (requirement 2) actually different for two different Supabase users who
 * happen to share a league id — one user's cached response for a key is
 * structurally a different cache entry than another user's, so switching
 * accounts can never read the previous account's cached data just because
 * the league id matches.
 */
export function userScopeKey(): readonly [string, string] {
  return ['user', currentUserId ?? ANONYMOUS_QUERY_SCOPE] as const;
}

/**
 * Pure comparison powering requirement 5 (auth session change hardening):
 * should the authenticated query cache be cleared because the
 * authenticated user actually changed?
 *
 * - `nextUserId` null (an ordinary sign-out) is NOT a "change" here —
 *   normal sign-out already clears the cache explicitly via
 *   `clearAuthenticatedQueryCache` (see AuthContext.tsx's `signOut`), so
 *   this path exists only to catch a *different concrete user* becoming
 *   authenticated without that explicit flow having run (e.g. an
 *   interrupted/incomplete prior sign-out, or a persisted session restored
 *   for an account other than the one the cache was last confirmed for).
 * - `previousUserId` null means "nothing recorded to compare against yet"
 *   (a fresh install, or the marker was cleared by a prior, proper
 *   sign-out) — there is nothing stale to protect against, so this is also
 *   not a "change."
 * - Only a concrete `previousUserId` -> a *different* concrete `nextUserId`
 *   counts. In particular, an ordinary Supabase access-token refresh for
 *   the SAME user calls back with the same `user.id`, so this correctly
 *   returns `false` and must never thrash the cache or create a login loop.
 */
export function didAuthenticatedUserChange(
  previousUserId: string | null,
  nextUserId: string | null,
): boolean {
  if (!previousUserId || !nextUserId) return false;
  return previousUserId !== nextUserId;
}

/** Minimal async key-value storage shape `read/writeStoredAuthScopeUserId`
 * need — narrower than AsyncStorage's full interface so tests can supply a
 * trivial in-memory fake instead of the real, RN-only module. */
export interface AuthScopeStorage {
  getItem: (key: string) => Promise<string | null> | string | null;
  setItem: (key: string, value: string) => Promise<void> | void;
  removeItem: (key: string) => Promise<void> | void;
}

/** Reads the last-known authenticated user id recorded at the end of the
 * previous process (if any). Best-effort: any storage failure reads as
 * "nothing recorded," never throws. */
export async function readStoredAuthScopeUserId(
  storage: AuthScopeStorage,
): Promise<string | null> {
  try {
    const value = await storage.getItem(AUTH_SCOPE_STORAGE_KEY);
    return value ?? null;
  } catch {
    return null;
  }
}

/** Records the current authenticated user id for comparison on the next
 * process start, or clears the marker for `null` (signed out). Best-effort:
 * never throws — a storage failure here must never block sign-in/out. */
export async function writeStoredAuthScopeUserId(
  storage: AuthScopeStorage,
  userId: string | null,
): Promise<void> {
  try {
    if (userId) {
      await storage.setItem(AUTH_SCOPE_STORAGE_KEY, userId);
    } else {
      await storage.removeItem(AUTH_SCOPE_STORAGE_KEY);
    }
  } catch {
    // Best-effort — worst case we simply don't detect a cross-restart user
    // swap on the next launch; this must never block auth.
  }
}

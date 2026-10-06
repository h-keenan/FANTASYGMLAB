import AsyncStorage from '@react-native-async-storage/async-storage';
import { QueryClient } from '@tanstack/react-query';
import { createAsyncStoragePersister } from '@tanstack/query-async-storage-persister';

/**
 * Shared React Query client — the app-wide replacement for one-off
 * "show cached data instantly, refresh in background" helpers like the
 * now-retired dashboardCache.ts. Every screen that adopts `useQuery` gets
 * that behavior for free: cached data (in-memory, then AsyncStorage-backed
 * across app restarts via the persister below) paints immediately on
 * mount/focus while a background refetch keeps it current.
 *
 * staleTime (30s): most of this app's server responses are real per-request
 * computation (roster pulls, lineup optimization, trade/waiver search) over
 * data that changes on the order of minutes (injury reports, waiver claims,
 * live scores), not seconds. 30s is short enough that a user bouncing
 * between tabs/screens still gets a background refresh soon after their
 * last one, but long enough that rapid re-focusing (e.g. flipping between
 * Dashboard and Matchup) doesn't re-hit the backend on every single nav.
 *
 * gcTime (24h): this must be >= the persister's own maxAge (also 24h,
 * below) or a persisted query can be evicted from the in-memory cache
 * before its persisted copy would've been considered stale — defeating the
 * "survives app restarts" goal. 24h comfortably covers "closed the app
 * overnight, reopened the next day and still got an instant paint."
 */
const STALE_TIME_MS = 30 * 1000;
const GC_TIME_MS = 24 * 60 * 60 * 1000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: STALE_TIME_MS,
      gcTime: GC_TIME_MS,
      // The one common transient failure (RN's fetch throwing after the OS
      // tears down a backgrounded connection) is already absorbed once,
      // synchronously, inside api.ts's authorizedRequest (see
      // backgroundRetry.ts). A real 4xx/5xx or ApiError reaching here is a
      // genuine failure, not a backoff candidate, so query-level retries
      // are kept minimal rather than React Query's default of 3.
      retry: 1,
      // Refocusing a screen (React Navigation focus, not OS foreground) is
      // this app's existing refresh trigger (the old per-screen
      // useFocusEffect pattern) — keep that behavior rather than opting
      // into RN's (inactive by default) window-focus listener.
      refetchOnReconnect: true,
    },
  },
});

/**
 * AsyncStorage-backed persister — the mechanism that lets cached query
 * results survive a full app restart, not just in-memory navigation.
 * `@react-native-async-storage/async-storage` is already a dependency
 * elsewhere in this app (dashboardCache.ts, sinceLastCheckIn.ts, etc.).
 */
export const asyncStoragePersister = createAsyncStoragePersister({
  storage: AsyncStorage,
  key: 'fgl:react-query-cache',
});

export const PERSIST_MAX_AGE_MS = GC_TIME_MS;

/**
 * Persisted React Query cache schema version — passed as
 * `PersistQueryClientProvider`'s `buster` (see App.tsx). The persister
 * compares this string against the one baked into whatever was last
 * written to AsyncStorage and, on a mismatch, discards the old persisted
 * cache entirely (then refetches normally) instead of trying to read
 * data shaped for an older version of the app.
 *
 * INCREMENT THIS (e.g. '2' -> '3') whenever a change would make an
 * already-persisted cache entry incompatible with what the app currently
 * expects, for example:
 *  - a backend API response shape changes in a way an existing screen
 *    can't safely parse/render (a renamed/removed/retyped field a screen
 *    reads without an undefined-check)
 *  - a query's `queryKey` shape changes (e.g. the `['user', userId, ...]`
 *    scoping added alongside this constant) such that stale,
 *    differently-shaped entries would otherwise sit in storage forever
 *    instead of being swept
 *  - the persisted-client wrapper shape itself changes (rare — a
 *    TanStack Query major version bump)
 *
 * Must stay a plain, constant, intentionally-chosen string — NEVER a
 * random value or a timestamp. A random/changing-every-run value would
 * invalidate the cache on every single app launch, defeating the entire
 * point of persisting it. Bump it only as an explicit, reviewed change
 * committed together with the incompatible change that requires it.
 */
export const PERSISTED_QUERY_CACHE_VERSION = '2';

/**
 * Minimal shape `clearAuthenticatedQueryCache` needs from a persister —
 * deliberately narrower than the full `Persister` interface so a test can
 * supply a trivial in-memory fake instead of a real AsyncStorage-backed one.
 */
interface RemovableClientPersister {
  removeClient: () => void | PromiseLike<void>;
}

/**
 * The one centralized place that tears down authenticated/persisted server
 * state — every "this app no longer speaks for the previously-authenticated
 * user" transition (sign-out, delete-account, or discovering the
 * authenticated Supabase user id changed — see AuthContext.tsx) must funnel
 * through this, rather than each call site hand-rolling its own subset.
 *
 * Order matters:
 *  1. Cancel active queries first so an in-flight fetch for the outgoing
 *     user can't resolve *after* the clear below and silently repopulate
 *     the cache with that user's data.
 *  2. Clear the in-memory `QueryClient` — every query/mutation observer
 *     reset, nothing left for a screen to read stale data out of.
 *  3. Remove the persisted copy from AsyncStorage via the persister's own
 *     `removeClient()` — this touches only the one storage key the
 *     persister owns (`fgl:react-query-cache`), never anything else this
 *     app keeps in AsyncStorage (display density, theme, onboarding
 *     flags, etc.), so normal, non-authenticated app preferences survive
 *     a sign-out untouched.
 *
 * Each step is independently best-effort: a failure in one (e.g.
 * AsyncStorage briefly unavailable) must never block the next, and this
 * function itself never throws — a cache-clear failure must never leave
 * the user unable to sign out.
 */
export async function clearAuthenticatedQueryCache(
  client: QueryClient = queryClient,
  persister: RemovableClientPersister = asyncStoragePersister,
): Promise<void> {
  try {
    await client.cancelQueries();
  } catch (err) {
    console.warn('[queryClient] cancelQueries failed during auth cache clear', err);
  }
  try {
    client.clear();
  } catch (err) {
    console.warn('[queryClient] clear() failed during auth cache clear', err);
  }
  try {
    await persister.removeClient();
  } catch (err) {
    console.warn('[queryClient] persister.removeClient() failed during auth cache clear', err);
  }
}

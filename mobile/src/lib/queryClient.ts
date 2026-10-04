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

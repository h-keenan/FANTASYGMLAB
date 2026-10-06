// NOTE: the `.ts` extension here is required, not stylistic — this file is
// also imported by backgroundRetry.test.ts, which runs directly under
// plain Node's own module loader (no bundler to resolve an extensionless
// specifier). See tsconfig.json's `allowImportingTsExtensions` comment.
import { isTransportErrorMessage } from './transportError.ts';

/**
 * Absorbs a very specific, very common failure: iOS (and, more loosely,
 * Android) suspends a backgrounded app's in-flight network connections and
 * JS timers almost immediately — no ~1hr grace period like a Supabase
 * access token's lifetime (see mobile/src/lib/supabase.ts's own AppState
 * listener for that *different*, already-fixed bug: a long background
 * period racing a stale JWT). A request that's merely mid-flight when the
 * user backgrounds the app for even a few seconds and returns typically
 * resolves as a bare transport failure — React Native's fetch throws a
 * plain `TypeError` (no HTTP status, e.g. "Network request failed") once
 * the app resumes and the OS tears down the suspended connection.
 *
 * That failure is transient, not a real connectivity problem: the retry
 * below almost always succeeds immediately, once, back in the foreground.
 * This is the one shared place that absorbs it — see api.ts's
 * authorizedRequest, the sole caller — so no individual screen has to learn
 * about AppState. (Screens already only re-fetch on `useFocusEffect`, which
 * is React Navigation focus, not OS foreground/background — backgrounding
 * the whole app and returning does not blur/refocus the current screen, so
 * without this, a request that failed this way would leave the screen
 * stuck on that one attempt's error forever.)
 *
 * Pure and RN-free on purpose: `wasBackgroundedDuring` is injected so this
 * can be unit tested without importing react-native's AppState (which isn't
 * runnable outside the Metro/RN runtime).
 */

/**
 * A real HTTP error (4xx/5xx, or this app's own `ApiError`) already carries
 * a status and resolves through the normal response-handling path — it is
 * never a background-transition artifact and must never be retried here.
 * Only a bare transport failure (RN's fetch rejects with a plain
 * `TypeError`, no `.status`) is a candidate.
 *
 * Deliberately narrower than "any `TypeError`": an ordinary JS programming
 * bug (e.g. `Cannot read properties of undefined (reading 'is_premium')`)
 * throws a `TypeError` too, and blindly retrying *that* would just run the
 * same buggy code path twice instead of surfacing it. Only a `TypeError`
 * whose message actually matches a known RN/iOS/Android fetch-failure
 * signature (see transportError.ts, shared with errorMessages.ts so the
 * two classifications can't drift apart) is treated as transient.
 */
export function isTransientNetworkError(err: unknown): boolean {
  return err instanceof TypeError && isTransportErrorMessage(err.message);
}

/**
 * Runs `attempt` once. If it throws a transient network error AND the app
 * was backgrounded at some point since the attempt started (per
 * `wasBackgroundedDuring`), retries `attempt` exactly one more time before
 * giving up — a single retry, no backoff loop, so a genuine connectivity
 * problem still surfaces as an error instead of hanging.
 */
export async function withBackgroundRetry<T>(
  attempt: () => Promise<T>,
  wasBackgroundedDuring: () => boolean,
): Promise<T> {
  try {
    return await attempt();
  } catch (err) {
    if (!isTransientNetworkError(err) || !wasBackgroundedDuring()) {
      throw err;
    }
    return attempt();
  }
}

/**
 * Read-request coalescing for lib/api.ts's authorizedRequest.
 *
 * Two independent behaviors, both only for plain GETs that carry no caller
 * AbortSignal (a shared request must not be cancellable by one of its
 * consumers):
 *
 * 1. In-flight dedupe: while a GET for a given user + path is on the wire,
 *    every other caller for the same key awaits that one request instead of
 *    sending a duplicate. Always on. Before this, each page load sent
 *    `GET /v1/preferences` twice (ExperienceLevelContext and
 *    DisplayPreferencesContext both read it on mount).
 * 2. A very short result cache (REFERENCE_TTL_MS) for a small allowlist of
 *    league reference reads that several pages request back to back
 *    (rankings, draft picks, rosters, IDP values: Players and Trade
 *    Analyzer both pull all four). Any non-GET request clears it, so a
 *    change the user just made is never hidden behind a cached read.
 *
 * Every consumer gets its own copy of the body, so one page mutating its
 * response (sorting in place, say) can never leak into another's.
 */

/** How long an allowlisted reference read is reused. Mobile's React Query
 * layer uses 30 s of staleness; the web stays well under that. */
export const REFERENCE_TTL_MS = 10_000;

/** League reference reads worth reusing across pages: pure functions of the
 * league + query string, identical for every page that asks. */
const CACHEABLE_PATH = /^\/v1\/leagues\/[^/?]+\/(rankings|draft-picks|rosters|idp\/values)(\?|$)/;

const inflight = new Map<string, Promise<unknown>>();
const recent = new Map<string, { at: number; value: unknown }>();
/** Bumped by clearRequestCache so a read that was already in flight when a
 * write landed is not stored as if it were fresh. */
let generation = 0;

export function cloneBody<T>(value: T): T {
  if (value === null || typeof value !== "object") return value;
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value)) as T;
}

export function isCacheablePath(path: string): boolean {
  return CACHEABLE_PATH.test(path);
}

/** Drops every cached/in-flight record. Called on any mutation and in tests. */
export function clearRequestCache(): void {
  generation += 1;
  inflight.clear();
  recent.clear();
}

/**
 * Runs `load` for `key`, sharing one request between concurrent callers and
 * (for `reusable` keys) reusing a successful result for REFERENCE_TTL_MS.
 */
export function coalesceRead<T>(key: string, reusable: boolean, load: () => Promise<T>, now: () => number = Date.now): Promise<T> {
  if (reusable) {
    const hit = recent.get(key);
    if (hit) {
      if (now() - hit.at < REFERENCE_TTL_MS) return Promise.resolve(cloneBody(hit.value as T));
      recent.delete(key);
    }
  }
  const pending = inflight.get(key);
  if (pending) return (pending as Promise<T>).then(cloneBody);

  const startedIn = generation;
  const request = load().then(
    (value) => {
      if (inflight.get(key) === request) inflight.delete(key);
      if (reusable && startedIn === generation) recent.set(key, { at: now(), value });
      return value;
    },
    (error: unknown) => {
      if (inflight.get(key) === request) inflight.delete(key);
      throw error;
    },
  );
  inflight.set(key, request);
  // The first caller keeps the original object; followers and later hits get copies.
  return reusable ? request.then(cloneBody) : request;
}

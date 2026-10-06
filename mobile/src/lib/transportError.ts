/**
 * Shared transport-level failure detection, used by both errorMessages.ts
 * (what string to show the user) and backgroundRetry.ts (whether a caught
 * error is worth one silent retry). Kept in one place so the two can't
 * drift into recognizing different sets of errors as "network trouble" —
 * see each of those files for how they use it.
 *
 * Substrings below show up in the `message` of a genuine transport-level
 * failure across the RN/JS environments this app runs in (iOS/Android
 * fetch, Hermes, Safari's WebKit fetch shim in dev). None of these are
 * meant for a user — they're implementation details of *how* a request
 * failed to even reach (or come back from) the server, as opposed to a
 * real `ApiError` the backend sent back with a genuine, human-readable
 * reason, or an ordinary JS programming bug.
 */
const TRANSPORT_ERROR_MESSAGE_PATTERNS: readonly RegExp[] = [
  /network request failed/i,
  /failed to fetch/i,
  /load failed/i, // WebKit's fetch failure message on iOS
  /connection (?:appears to be )?offline/i,
  /network connection (?:was )?lost/i,
  /hostname could not be found/i,
  /could not connect to the server/i,
  /network error/i,
  /nsurlerrordomain/i,
  /timed? ?out/i,
  /json parse error/i,
  /unexpected (?:end of input|token) .* json/i,
  /unexpected character/i,
];

/** True if `message` matches one of the known transport-failure signatures above. */
export function isTransportErrorMessage(message: string): boolean {
  return TRANSPORT_ERROR_MESSAGE_PATTERNS.some((pattern) => pattern.test(message));
}

/**
 * A caught AbortController abort, or a fetch-timeout wrapper's own
 * TimeoutError. Neither carries a message worth pattern-matching, but both
 * are unambiguously transport-level by construction (the request was
 * deliberately cut off, not answered with a programming error).
 */
export function isAbortOrTimeoutError(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false;
  const name = (err as { name?: unknown }).name;
  return name === 'AbortError' || name === 'TimeoutError';
}

/**
 * Recognizes a transport-level failure: a request that never made it to (or
 * back from) the server in a way the backend could describe — dropped
 * connection, DNS failure, timeout, abort, or a response body that wasn't
 * valid JSON.
 *
 * Deliberately NOT "any TypeError" — `fetch` throwing a plain `TypeError`
 * is *also* exactly what happens for an ordinary JS programming bug
 * anywhere downstream of a fetch call (e.g. `Cannot read properties of
 * undefined (reading 'is_premium')`). Treating every `TypeError` as "the
 * network is down" turned real app/data-shape bugs into a misleading
 * "Couldn't connect — check your connection and try again," and (via
 * backgroundRetry.ts) pointlessly retried them. Only an `Error` (whether a
 * `TypeError` or not) whose *message* actually matches one of the known
 * signatures above counts. Anything else falls through to the caller's own
 * fallback/error handling instead of risking a misleading classification.
 */
export function isTransportError(err: unknown): boolean {
  if (isAbortOrTimeoutError(err)) return true;
  if (err instanceof Error) {
    return isTransportErrorMessage(err.message);
  }
  return false;
}

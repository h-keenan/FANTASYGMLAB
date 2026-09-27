import { ApiError } from './api';

/**
 * Substrings that show up in the `message` of a transport-level failure
 * across the RN/JS environments this app runs in (iOS/Android fetch,
 * Hermes, Safari's WebKit fetch shim in dev). None of these are meant for a
 * user — they're implementation details of *how* the request failed to
 * even reach (or come back from) the server, as opposed to a real
 * `ApiError` the backend sent back with a genuine, human-readable reason.
 */
const TRANSPORT_ERROR_PATTERNS = [
  /network request failed/i,
  /failed to fetch/i,
  /load failed/i, // WebKit's fetch failure message on iOS
  /the internet connection appears to be offline/i,
  /the network connection was lost/i,
  /a server with the specified hostname could not be found/i,
  /could not connect to the server/i,
  /timed? ?out/i,
  /nsurlerrordomain/i,
  /json parse error/i,
  /unexpected (?:end of input|token) .* json/i,
  /unexpected character/i,
];

function isAbortOrTimeout(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false;
  const name = (err as { name?: unknown }).name;
  return name === 'AbortError' || name === 'TimeoutError';
}

/**
 * Recognizes a transport-level failure: a request that never made it to (or
 * back from) the server in a way the backend could describe — dropped
 * connection, DNS failure, timeout, abort, or a response body that wasn't
 * valid JSON. Deliberately conservative: anything not matched here falls
 * through to the caller's own fallback string rather than risk showing raw
 * exception text.
 */
function isTransportError(err: unknown): boolean {
  if (isAbortOrTimeout(err)) return true;
  // A bare TypeError is what `fetch` itself throws for a network failure
  // (as opposed to an HTTP error status, which resolves normally).
  if (err instanceof TypeError) return true;
  if (err instanceof Error) {
    return TRANSPORT_ERROR_PATTERNS.some((pattern) => pattern.test(err.message));
  }
  return false;
}

/**
 * Turns a caught error into a string safe to render to the user.
 *
 * - A real `ApiError` (backend responded, just not with a 2xx) already
 *   carries a human-written, customer-safe message — use it as-is.
 * - A recognizable transport-level failure (network down, timeout, abort,
 *   a non-JSON/garbled response) gets a generic, friendly message instead
 *   of the raw `TypeError`/parse-error text.
 * - Anything else falls back to the caller's own fallback string, same as
 *   before — this only changes behavior for the specific cases above.
 */
export function toUserErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return err.message || fallback;
  }
  if (isTransportError(err)) {
    return "Couldn't connect — check your connection and try again.";
  }
  return fallback;
}

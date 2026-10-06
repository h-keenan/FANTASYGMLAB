import { ApiError } from './api';
import { isTransportError } from './transportError';

/**
 * Turns a caught error into a string safe to render to the user.
 *
 * - A real `ApiError` (backend responded, just not with a 2xx) already
 *   carries a human-written, customer-safe message — use it as-is.
 * - A recognizable transport-level failure (network down, timeout, abort,
 *   a non-JSON/garbled response — see transportError.ts) gets a generic,
 *   friendly message instead of the raw `TypeError`/parse-error text.
 * - Anything else — including an ordinary JS programming error, which can
 *   also surface as a bare `TypeError` — falls back to the caller's own
 *   fallback string, same as before. A real bug must never masquerade as
 *   a connectivity problem; see transportError.ts's own doc comment.
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

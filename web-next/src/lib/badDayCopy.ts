/**
 * Bad-day copy and classification, one definition for web and app (byte-identical lib twin): what a user reads when the
 * network is gone, a request is slow, the server errors, the session ended or the league is gone. Pure, no imports.
 * Audit: docs/audits/2026-11-bad-day-and-words.md. Wording follows docs/ui-patterns.md "Copy casing and shared copy":
 * sentence case, no em-dashes.
 */

/** A page that is still loading after this long says so (skeleton stays, nothing spins forever). */
export const SLOW_LOAD_AFTER_MS = 8_000;
/** After this long the skeleton offers a retry; the request itself gives up at 30s and shows the shared error state. */
export const SLOW_LOAD_RETRY_AFTER_MS = 15_000;

export const OFFLINE_BANNER_TEXT = "You are offline. Showing what we last loaded.";
export const BACK_ONLINE_TEXT = "Back online";
export const SLOW_LOAD_TEXT = "Still loading. This is taking longer than usual.";
export const SLOW_LOAD_RETRY_LABEL = "Try again";

export const SESSION_EXPIRED_TITLE = "Your session ended";
export const SESSION_EXPIRED_BODY = "Sign in again to pick up where you left off. Your leagues and settings are saved.";
export const SESSION_EXPIRED_ACTION = "Sign in again";

export const LEAGUE_GONE_TITLE = "This league is not available";
export const LEAGUE_GONE_BODY = "It may have been deleted or archived on Sleeper. Choose another league to keep going.";
export const LEAGUE_GONE_ACTION = "Choose another league";

export const SERVER_ERROR_MESSAGE = "Our servers hit a snag. Try again in a moment.";
export const SERVICE_BUSY_MESSAGE = "We are busy right now. Try again in a moment.";
export const OFFLINE_ERROR_MESSAGE = "Could not reach the server. Check your connection and try again.";

export type ErrorKind = "session" | "league_gone" | "offline" | "server" | "other";

/** What kind of bad day a user-facing error message describes (messages are all the shared ErrorState receives). */
export function classifyErrorMessage(message: string): ErrorKind {
  const text = message.trim();
  if (/^not signed in\.?$/i.test(text) || /\b(session (has )?expired|invalid (or expired )?token|jwt expired)\b/i.test(text)) return "session";
  if (/^league not found\.?$/i.test(text)) return "league_gone";
  if (/could not reach the server|couldn'?t connect|network request failed|failed to fetch|you are offline/i.test(text)) return "offline";
  if (/^request failed( with status |\s*\()\s*5\d\d/i.test(text) || /^our servers hit a snag/i.test(text)) return "server";
  return "other";
}

/**
 * A message for a failed response. A server-written `detail` is kept; the generic fallback a client builds ("Request
 * failed with status 502.") is replaced, since a bare status code tells a user nothing.
 */
export function friendlyStatusMessage(status: number, detail: string): string {
  const text = detail.trim();
  const generic = !text || /^request failed( with status |\s*\()\s*\d{3}/i.test(text);
  if (!generic) return text;
  if (status === 401) return "Not signed in.";
  if (status === 429 || status === 503) return SERVICE_BUSY_MESSAGE;
  if (status >= 500) return SERVER_ERROR_MESSAGE;
  // 4xx keeps the client's generic fallback: callers (Sim mutations) detect it to substitute their own sentence.
  return text || `Request failed with status ${status}.`;
}

/** "As of 3:42 PM" today, "As of Mon 3:42 PM" within a week, otherwise "As of Nov 9". `now` is injectable for tests. */
export function asOfLabel(updatedAtMs: number, now: number = Date.now()): string {
  if (!Number.isFinite(updatedAtMs) || updatedAtMs <= 0) return "";
  const then = new Date(updatedAtMs);
  const today = new Date(now);
  const time = then.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  if (then.toDateString() === today.toDateString()) return `As of ${time}`;
  if (now - updatedAtMs < 7 * 24 * 60 * 60 * 1000) return `As of ${then.toLocaleDateString("en-US", { weekday: "short" })} ${time}`;
  return `As of ${then.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
}

/** The one stale-content note: shown only when the data on screen is older than `staleAfterMs` or the device is offline. */
export function staleNote(updatedAtMs: number, opts: { offline?: boolean; now?: number; staleAfterMs?: number } = {}): string {
  const now = opts.now ?? Date.now();
  const stale = now - updatedAtMs > (opts.staleAfterMs ?? 10 * 60 * 1000);
  if (!opts.offline && !stale) return "";
  return asOfLabel(updatedAtMs, now);
}

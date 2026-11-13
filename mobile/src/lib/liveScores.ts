/**
 * Live-score polling + freshness rules for the Matchup screen. Pure, no
 * platform imports; byte-identical twin of mobile/src/lib/liveScores.ts.
 *
 * The server (modules/live_policy.py) says when games are live and how often
 * to refresh (`poll_after_seconds`); its shared matchups cache is at most 20 s
 * old, so polling every 30 s keeps the screen within ~50 s of Sleeper.
 */

export const MIN_POLL_SECONDS = 30;
export const MAX_POLL_SECONDS = 120;
export const MAX_BACKOFF_SECONDS = 300;

export interface PollPlan {
  /** Server says NFL games are in progress. */
  live: boolean;
  /** Server's recommended interval (matchup `poll_after_seconds`). */
  pollAfterSeconds?: number | null;
  /** Screen/tab visible and app in the foreground. */
  visible: boolean;
  online: boolean;
}

/** Poll only while a game is live, the screen is visible and the device is online. */
export function shouldPoll(plan: PollPlan): boolean {
  return plan.live && plan.visible && plan.online;
}

/**
 * Delay before the next refresh: the server's interval clamped to 30-120 s (never faster than the server's adaptive TTL, which it reports);
 * after `failures` consecutive errors it doubles each time (capped at 5 min),
 * and never undercuts a server `Retry-After` (busyRetry.ts).
 */
export function nextPollDelayMs(
  pollAfterSeconds: number | null | undefined,
  failures = 0,
  retryAfterSeconds?: number,
  random: () => number = Math.random,
): number {
  const base = Math.min(MAX_POLL_SECONDS, Math.max(MIN_POLL_SECONDS, pollAfterSeconds ?? MIN_POLL_SECONDS));
  let seconds = base;
  if (failures > 0) seconds = Math.min(MAX_BACKOFF_SECONDS, base * 2 ** Math.min(failures, 6));
  if (retryAfterSeconds && retryAfterSeconds > 0) seconds = Math.max(seconds, retryAfterSeconds);
  return Math.round(seconds * 1000 * (1 + 0.1 * random()));
}

/** Age of the data now: its age when received plus time since it arrived (client-clock safe). */
export function dataAgeSeconds(ageAtReceiptSeconds: number, receivedAtMs: number, nowMs: number): number {
  return Math.max(0, Math.round(ageAtReceiptSeconds + (nowMs - receivedAtMs) / 1000));
}

/** "Updated 12s ago" / "Updated 3m ago". */
export function freshnessLabel(ageSeconds: number): string {
  if (ageSeconds < 5) return "Updated just now";
  if (ageSeconds < 60) return `Updated ${ageSeconds}s ago`;
  if (ageSeconds < 3600) return `Updated ${Math.floor(ageSeconds / 60)}m ago`;
  return `Updated ${Math.floor(ageSeconds / 3600)}h ago`;
}

/** "Proj final 18.4" for a starter whose game is in progress. */
export function projFinalLabel(projectedFinal: number | null | undefined): string | null {
  return typeof projectedFinal === "number" && Number.isFinite(projectedFinal)
    ? `Proj final ${projectedFinal.toFixed(1)}`
    : null;
}

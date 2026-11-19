/**
 * Latest-request gate and single-flight guard, one definition for web and app (byte-identical lib twin, imports nothing).
 * Audit: docs/audits/2026-11-client-data-races.md.
 *
 * A screen that loads by key (league, lens, player, week, search text) takes a ticket from the gate before it sends the
 * request and checks the ticket before it applies the answer. Starting a newer request, or cancelling, retires every
 * older ticket, so a slow answer for the previous key can never land on top of the current one. The request itself is
 * never aborted here: only its result is ignored, so shared in-flight reads (lib/requestCache.ts) keep working.
 */

/**
 * Kill switch. `false` restores the previous behaviour exactly: every ticket is always current (no stale response is
 * ignored) and the single-flight guard lets every call through. The repo has no client flag mechanism, so this is one
 * constant; flip it and ship.
 */
export const RACE_GUARDS_ENABLED = true;

export interface LatestGate {
  /** Takes a ticket and retires all earlier ones. Call `isCurrent()` before applying a response. */
  begin(): () => boolean;
  /** Retires every outstanding ticket (unmount, key change with no new request). */
  cancel(): void;
}

export function createLatestGate(enabled: boolean = RACE_GUARDS_ENABLED): LatestGate {
  let latest = 0;
  return {
    begin() {
      const mine = ++latest;
      return () => !enabled || mine === latest;
    },
    cancel() {
      latest += 1;
    },
  };
}

export interface SingleFlight {
  /** True while a call started by `run` has not settled. */
  readonly pending: boolean;
  /**
   * Runs `task` unless one is already pending, in which case it returns `undefined` without calling it. The pending flag
   * clears when the task settles, whether it resolves or throws. Use for taps that send a write (trade send, claim, save).
   */
  run<T>(task: () => Promise<T>): Promise<T> | undefined;
}

export function createSingleFlight(enabled: boolean = RACE_GUARDS_ENABLED): SingleFlight {
  let pending = false;
  return {
    get pending() {
      return pending;
    },
    run<T>(task: () => Promise<T>) {
      if (enabled && pending) return undefined;
      pending = true;
      let promise: Promise<T>;
      try {
        promise = Promise.resolve(task());
      } catch (error) {
        pending = false;
        return Promise.reject(error);
      }
      return promise.finally(() => {
        pending = false;
      });
    },
  };
}

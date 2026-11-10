/**
 * Client side of the API's load shedding (modules/admission.py). When the
 * server is saturated it answers an expensive route with 503
 * `{ code: "server_busy", retry_after }` plus a `Retry-After` header instead
 * of letting the request time out. Idempotent reads are retried a couple of
 * times with that hint (jittered, capped) so a brief spike resolves itself;
 * if it is still busy the error surfaces with its friendly message.
 *
 * Kept free of fetch/ApiError imports so it is unit-testable on its own.
 * mobile/src/lib/busyRetry.ts is the same logic for the Expo app.
 */

export const SERVER_BUSY_CODE = "server_busy";
export const MAX_BUSY_RETRIES = 2;
export const MAX_BUSY_WAIT_MS = 10_000;

export interface BusyErrorLike {
  status?: number;
  code?: string;
  retryAfterSeconds?: number;
}

export function isServerBusyError(error: unknown): error is BusyErrorLike {
  if (!error || typeof error !== "object") return false;
  const e = error as BusyErrorLike;
  return e.status === 503 && e.code === SERVER_BUSY_CODE;
}

/** Parse a Retry-After header value (delta-seconds form) to whole seconds. */
export function parseRetryAfterSeconds(value: string | null | undefined): number | undefined {
  if (!value) return undefined;
  const n = Number(value.trim());
  return Number.isFinite(n) && n > 0 ? Math.ceil(n) : undefined;
}

export function busyDelayMs(retryAfterSeconds: number | undefined, attempt: number, random: () => number = Math.random): number {
  const base = retryAfterSeconds && retryAfterSeconds > 0 ? retryAfterSeconds * 1000 : 2000 * (attempt + 1);
  const jittered = base * (1 + 0.2 * random());
  return Math.min(MAX_BUSY_WAIT_MS, Math.round(jittered));
}

// Plain Error (not DOMException): React Native's Hermes has no DOMException.
function abortError(): Error {
  const e = new Error("Aborted");
  e.name = "AbortError";
  return e;
}

function abortableSleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(abortError());
    const id = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(id);
      reject(abortError());
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export interface BusyRetryOptions {
  /** Only idempotent reads are retried. */
  canRetry: boolean;
  signal?: AbortSignal;
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>;
  random?: () => number;
}

export async function withServerBusyRetry<T>(run: () => Promise<T>, options: BusyRetryOptions): Promise<T> {
  const sleep = options.sleep ?? abortableSleep;
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await run();
    } catch (error) {
      if (!options.canRetry || attempt >= MAX_BUSY_RETRIES || !isServerBusyError(error) || options.signal?.aborted) {
        throw error;
      }
      await sleep(busyDelayMs(error.retryAfterSeconds, attempt, options.random), options.signal);
    }
  }
}

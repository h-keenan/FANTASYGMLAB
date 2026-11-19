/**
 * Client request timeouts, one definition for web and app (byte-identical lib twin, imports nothing). The shared fetch layers
 * (lib/supabase.ts on both platforms, lib/billingClient.ts on web) call into this; no call site sets its own timeout.
 * Audit: docs/audits/2026-11-auth-offline-error-paths.md ("Not fixed": no client timeout on PostgREST or billing).
 */
/**
 * Kill switch. `false` restores the previous behaviour exactly: PostgREST reads use the platform default (no client
 * timeout) and billing keeps its single 30s abort with the old copy. The repo has no client flag mechanism, so this is
 * one constant; flip it and ship.
 */
export const REQUEST_TIMEOUTS_ENABLED = true;

/** A PostgREST read (GET/HEAD to /rest/v1/) that gets no response in this long fails with SLOW_REQUEST_MESSAGE. */
export const POSTGREST_READ_TIMEOUT_MS = 15_000;
/** Billing reads (plan list). */
export const BILLING_READ_TIMEOUT_MS = 15_000;
/** Billing writes (checkout session, portal link, account deletion): unchanged from the old single value, never shortened. */
export const BILLING_WRITE_TIMEOUT_MS = 30_000;

/** Body code on the synthetic response returned when a read times out. */
export const CLIENT_TIMEOUT_CODE = "client_timeout";

/** Reads only: a write that is aborted client-side may still have landed, so writes are never timed out here. */
export function isPostgrestRead(input: RequestInfo | URL, init?: RequestInit): boolean {
  const requestMethod = typeof input === "object" && "method" in input ? input.method : undefined;
  const method = (init?.method ?? requestMethod ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") return false;
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  return url.includes("/rest/v1/");
}

/**
 * `opts.message` is SLOW_REQUEST_MESSAGE from badDayCopy.ts (this file imports nothing, so the twins stay byte-identical).
 * Wrap a fetch so PostgREST reads give up after `timeoutMs`. On timeout it resolves a 408 JSON response
 * ({message, code}) instead of throwing, which postgrest-js turns into `{ data: null, error: { message } }`: callers
 * already handle `error` and show it, so the shared ErrorState + retry path needs no per-call-site change. A caller's
 * own abort is passed through untouched. Everything that is not a PostgREST read (auth, writes) goes straight through.
 */
export function withReadTimeout(
  baseFetch: typeof fetch,
  opts: { message: string; timeoutMs?: number; enabled?: boolean },
): typeof fetch {
  const timeoutMs = opts.timeoutMs ?? POSTGREST_READ_TIMEOUT_MS;
  const enabled = opts.enabled ?? REQUEST_TIMEOUTS_ENABLED;
  return async (input, init) => {
    if (!enabled || !isPostgrestRead(input, init)) return baseFetch(input, init);
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    const caller = init?.signal;
    const onCallerAbort = () => controller.abort();
    if (caller) {
      if (caller.aborted) controller.abort();
      else caller.addEventListener("abort", onCallerAbort, { once: true });
    }
    try {
      return await baseFetch(input, { ...init, signal: controller.signal });
    } catch (error) {
      if (timedOut && !caller?.aborted) {
        return new Response(JSON.stringify({ message: opts.message, code: CLIENT_TIMEOUT_CODE }), {
          status: 408,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw error;
    } finally {
      clearTimeout(timer);
      caller?.removeEventListener("abort", onCallerAbort);
    }
  };
}

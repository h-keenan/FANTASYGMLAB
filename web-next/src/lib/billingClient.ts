import { ApiError } from "./api";
import { env } from "./env";

/**
 * Single client for the Stripe web-billing endpoints (plans, checkout,
 * portal). These run as Supabase Edge Functions
 * (supabase/functions/billing-plans, create-checkout-session,
 * billing-portal-session); see docs/billing-on-supabase.md.
 *
 * Request: the user's Supabase JWT as Authorization, the anon key as apikey.
 * Response bodies are identical to the old FastAPI /v1/billing/* routes; only
 * the error envelope differs ({ok:false, error} vs {detail}), which is
 * normalized here into the same ApiError the rest of the app already handles.
 *
 * ROLLBACK: the FastAPI routes still exist (deprecated). Set
 * NEXT_PUBLIC_BILLING_BACKEND=fastapi at build time to send these calls back
 * to `${NEXT_PUBLIC_API_BASE_URL}/v1/billing/*` instead.
 */
export type BillingBackend = "supabase" | "fastapi";

export const BILLING_BACKEND: BillingBackend =
  process.env.NEXT_PUBLIC_BILLING_BACKEND === "fastapi" ? "fastapi" : "supabase";

export type BillingFunction = "billing-plans" | "create-checkout-session" | "billing-portal-session";

/** Deprecated FastAPI route for each function (rollback path only). */
const FASTAPI_PATHS: Record<BillingFunction, string> = {
  "billing-plans": "/v1/billing/plans",
  "create-checkout-session": "/v1/billing/checkout",
  "billing-portal-session": "/v1/billing/portal",
};

const REQUEST_TIMEOUT_MS = 30_000;

export function billingEndpoint(name: BillingFunction, backend: BillingBackend = BILLING_BACKEND): string {
  if (backend === "fastapi") return `${env.apiBaseUrl}${FASTAPI_PATHS[name]}`;
  return `${env.supabaseUrl.replace(/\/+$/, "")}/functions/v1/${name}`;
}

export async function billingRequest<T>(
  name: BillingFunction,
  accessToken: string,
  init?: { method?: "GET" | "POST"; jsonBody?: unknown; backend?: BillingBackend },
): Promise<T> {
  const backend = init?.backend ?? BILLING_BACKEND;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(billingEndpoint(name, backend), {
      method: init?.method ?? "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        ...(backend === "supabase" ? { apikey: env.supabaseAnonKey } : {}),
        ...(init?.jsonBody !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      ...(init?.jsonBody !== undefined ? { body: JSON.stringify(init.jsonBody) } : {}),
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(0, "The request timed out. Check your connection and try again.");
    }
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  } finally {
    clearTimeout(timeoutId);
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const record = body && typeof body === "object" ? (body as { detail?: unknown; error?: unknown; msg?: unknown; message?: unknown; code?: unknown }) : {};
    // Edge Functions: {ok:false,error}; FastAPI: {detail}; Supabase gateway (e.g. bad JWT): {msg|message}.
    const detail = String(record.detail ?? record.error ?? record.msg ?? record.message ?? "");
    const code = typeof record.code === "string" ? record.code : undefined;
    throw new ApiError(response.status, detail || `Request failed with status ${response.status}.`, code);
  }
  return body as T;
}

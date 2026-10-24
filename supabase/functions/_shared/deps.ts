import { Env, errorResponse } from "./util.ts";
import { FetchFn } from "./supabase_rest.ts";

/** Everything a handler touches from the outside, injectable for tests. */
export interface Deps {
  env: Env;
  fetch: FetchFn;
  now?: () => Date;
}

/** Browser callers (web-next) hit checkout/portal cross-origin. Origin allowlist = APP_BASE_URL (+ CORS_ALLOWED_ORIGINS). */
export function corsHeaders(env: Env, origin: string | null): Record<string, string> {
  const allowed = new Set<string>();
  const base = (env("APP_BASE_URL") ?? "").trim().replace(/\/+$/, "");
  if (base) allowed.add(base);
  for (const o of (env("CORS_ALLOWED_ORIGINS") ?? "").split(",")) {
    const t = o.trim().replace(/\/+$/, "");
    if (t) allowed.add(t);
  }
  const headers: Record<string, string> = {
    "Access-Control-Allow-Headers": "authorization, content-type, apikey, x-client-info",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    Vary: "Origin",
  };
  if (origin && allowed.has(origin)) headers["Access-Control-Allow-Origin"] = origin;
  return headers;
}

export function methodNotAllowed(): Response {
  return errorResponse(405, "Method not allowed.");
}

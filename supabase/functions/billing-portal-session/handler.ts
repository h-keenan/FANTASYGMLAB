// POST /billing-portal-session  (port of POST /v1/billing/portal)
// Authenticated with the caller's Supabase JWT. The Stripe customer id is read
// from the verified user's own profile row, never from the request.

import { loadStripeConfig, loadSupabaseConfig } from "../_shared/config.ts";
import { corsHeaders, Deps } from "../_shared/deps.ts";
import { createPortalSession } from "../_shared/stripe_api.ts";
import { fetchBillingProfile, verifyUserJwt } from "../_shared/supabase_rest.ts";
import { errorResponse, HttpError, jsonResponse, st } from "../_shared/util.ts";

export async function handle(req: Request, deps: Deps): Promise<Response> {
  const cors = corsHeaders(deps.env, req.headers.get("origin"));
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
  if (req.method !== "POST") return errorResponse(405, "Method not allowed.", cors);

  const config = loadStripeConfig(deps.env);
  const supabase = loadSupabaseConfig(deps.env);
  try {
    if (!supabase.url || !supabase.serviceRoleKey) throw new HttpError(500, "Supabase is not configured.");
    const user = await verifyUserJwt(supabase, deps.fetch, req.headers.get("authorization") ?? "");
    const profile = await fetchBillingProfile(supabase, deps.fetch, user.id);
    const customerId = st(profile?.stripe_customer_id);
    if (!customerId) return errorResponse(404, "No billing account found for this user yet.", cors);
    const portal = await createPortalSession(deps.fetch, config, customerId);
    const url = st(portal.url);
    if (!url) return errorResponse(502, "Could not open billing portal.", cors);
    return jsonResponse({ ok: true, portal_url: url }, 200, cors);
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.status, e.message, cors);
    console.error("billing-portal-session failed", (e as Error).message);
    return errorResponse(502, "Could not open billing portal.", cors);
  }
}

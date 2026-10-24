// POST /create-checkout-session  (port of POST /v1/billing/checkout + create_checkout_session)
// Authenticated with the caller's Supabase JWT (verify_jwt stays ON at the
// gateway AND we re-verify via GoTrue to obtain the verified id + email).
// Body: { tier?: "pro"|"front_office", interval?: "monthly"|"annual",
//         return_to?: "/path", ui_mode?: "embedded"|"hosted" }

import { loadStripeConfig, loadSupabaseConfig, TIER_PRO, MONTHLY } from "../_shared/config.ts";
import { corsHeaders, Deps } from "../_shared/deps.ts";
import { createCheckoutSession, trialEligible } from "../_shared/stripe_api.ts";
import { fetchBillingProfile, verifyUserJwt } from "../_shared/supabase_rest.ts";
import { errorResponse, HttpError, isObj, jsonResponse, st } from "../_shared/util.ts";

export async function handle(req: Request, deps: Deps): Promise<Response> {
  const cors = corsHeaders(deps.env, req.headers.get("origin"));
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
  if (req.method !== "POST") return errorResponse(405, "Method not allowed.", cors);

  const config = loadStripeConfig(deps.env);
  const supabase = loadSupabaseConfig(deps.env);
  try {
    if (!supabase.url || !supabase.serviceRoleKey) throw new HttpError(500, "Supabase is not configured.");
    const user = await verifyUserJwt(supabase, deps.fetch, req.headers.get("authorization") ?? "");

    let body: Record<string, unknown> = {};
    try {
      const parsed = await req.json();
      if (isObj(parsed)) body = parsed;
    } catch { /* empty body -> defaults */ }
    const tier = st(body.tier) || TIER_PRO;
    const interval = st(body.interval) || MONTHLY;

    const profile = await fetchBillingProfile(supabase, deps.fetch, user.id);
    const trialOk = await trialEligible(config, deps.fetch, {
      tier,
      email: user.email,
      profile,
      profileReadable: profile !== null,
    });

    const session = await createCheckoutSession(deps.fetch, {
      config,
      userId: user.id,
      email: user.email, // verified JWT email only
      customerId: st(profile?.stripe_customer_id),
      tier,
      interval,
      uiMode: st(body.ui_mode) || "embedded",
      returnTo: st(body.return_to) || "/premium",
      trialEligible: trialOk,
      now: deps.now?.(),
    });

    const embedded = (st(body.ui_mode) || "embedded").toLowerCase() === "embedded";
    if (embedded) {
      const clientSecret = st(session.client_secret);
      if (!clientSecret) return errorResponse(502, "Could not start checkout.", cors);
      return jsonResponse({ ok: true, client_secret: clientSecret, trial_days: trialOk ? config.trialDays : 0 }, 200, cors);
    }
    const url = st(session.url);
    if (!url) return errorResponse(502, "Could not start checkout.", cors);
    return jsonResponse({ ok: true, checkout_url: url, trial_days: trialOk ? config.trialDays : 0 }, 200, cors);
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.status, e.message, cors);
    console.error("create-checkout-session failed", (e as Error).message);
    return errorResponse(502, "Could not start checkout.", cors);
  }
}

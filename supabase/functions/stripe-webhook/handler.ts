// POST /stripe-webhook  (port of services/stripe_webhook_service.py)
// Deployed with --no-verify-jwt: Stripe cannot send a Supabase JWT; the
// Stripe-Signature HMAC is the authentication.

import { loadStripeConfig, loadSupabaseConfig } from "../_shared/config.ts";
import { Deps, methodNotAllowed } from "../_shared/deps.ts";
import { processStripeEvent, assertStripeRuntime } from "../_shared/stripe_events.ts";
import { SignatureError, verifyStripeSignature } from "../_shared/stripe_signature.ts";
import { stripeStore } from "../_shared/supabase_rest.ts";
import { errorResponse, jsonResponse, st } from "../_shared/util.ts";

export async function handle(req: Request, deps: Deps): Promise<Response> {
  if (req.method !== "POST") return methodNotAllowed();
  const signature = req.headers.get("stripe-signature");
  if (!signature) return errorResponse(400, "Missing Stripe signature.");

  // RAW body: signature is over the exact bytes, never re-serialized JSON.
  const payload = await req.text();
  const config = loadStripeConfig(deps.env);
  const supabase = loadSupabaseConfig(deps.env);
  const runtimeProblem = assertStripeRuntime(config);
  if (runtimeProblem) return errorResponse(runtimeProblem.status, runtimeProblem.error);
  if (!supabase.url || !supabase.serviceRoleKey) {
    return errorResponse(500, "Supabase service-role update is not configured.");
  }

  let event: Record<string, unknown>;
  try {
    event = await verifyStripeSignature(payload, signature, config.webhookSecret, {
      nowSeconds: deps.now ? Math.floor(deps.now().getTime() / 1000) : undefined,
    });
  } catch (e) {
    if (e instanceof SignatureError) return errorResponse(400, e.message);
    return errorResponse(500, "Webhook processing failed.");
  }
  if (!!event.livemode !== (config.billingMode === "live")) {
    return errorResponse(400, "Stripe event mode does not match the configured billing mode.");
  }

  try {
    const result = await processStripeEvent(event, config, stripeStore(supabase, deps.fetch), {
      now: deps.now?.(),
    });
    if (!result.ok) {
      const message = st(result.error) || "Stripe webhook processing failed.";
      const status = message.toLowerCase().includes("signature") || message.toLowerCase().includes("user id") ? 400 : 500;
      return errorResponse(status, message);
    }
    const action = result.action;
    return jsonResponse({
      received: true,
      event_id: result.event_id,
      entitlement: action.entitlement ?? "",
      subscription_status: action.stripe_subscription_status ?? "",
      skipped: !!result.skipped,
    });
  } catch (e) {
    console.error("stripe-webhook failed", (e as Error).message);
    return errorResponse(500, "Webhook processing failed.");
  }
}

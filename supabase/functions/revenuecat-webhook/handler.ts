// POST /revenuecat-webhook  (port of services/revenuecat_webhook_service.py)
// Deployed with --no-verify-jwt: RevenueCat authenticates with the fixed
// Authorization header value we configure in its dashboard.

import { loadRevenueCatConfig, loadSupabaseConfig } from "../_shared/config.ts";
import { Deps, methodNotAllowed } from "../_shared/deps.ts";
import {
  parseWebhookPayload,
  processRevenueCatEvent,
  RevenueCatAuthError,
  RevenueCatPayloadError,
  RevenueCatUpstreamError,
  verifyWebhookAuthorization,
} from "../_shared/revenuecat_events.ts";
import { revenueCatStore } from "../_shared/supabase_rest.ts";
import { errorResponse, HttpError, jsonResponse, st } from "../_shared/util.ts";

export async function handle(req: Request, deps: Deps): Promise<Response> {
  if (req.method !== "POST") return methodNotAllowed();
  const authorization = req.headers.get("authorization");
  if (!authorization) return errorResponse(400, "Missing Authorization header.");

  const payload = await req.text();
  const config = loadRevenueCatConfig(deps.env);
  const supabase = loadSupabaseConfig(deps.env);
  if (!config.webhookAuthToken) return errorResponse(500, "RevenueCat webhook auth token is not configured.");
  if (!supabase.url || !supabase.serviceRoleKey) {
    return errorResponse(500, "Supabase service-role update is not configured.");
  }

  try {
    verifyWebhookAuthorization(authorization, config);
    const event = parseWebhookPayload(payload);
    const result = await processRevenueCatEvent(event, config, revenueCatStore(supabase, deps.fetch), deps.fetch, {
      now: deps.now?.(),
    });
    if (!result.ok) {
      const message = st(result.error) || "RevenueCat webhook processing failed.";
      return errorResponse(message.toLowerCase().includes("user id") ? 400 : 500, message);
    }
    const action = result.action as Record<string, string>;
    return jsonResponse({
      received: true,
      event_id: result.event_id,
      entitlement: action.entitlement ?? "",
      event_type: action.event_type ?? "",
      skipped: !!result.skipped,
    });
  } catch (e) {
    if (e instanceof RevenueCatAuthError) return errorResponse(401, e.message);
    if (e instanceof RevenueCatPayloadError) return errorResponse(400, e.message);
    if (e instanceof HttpError) return errorResponse(e.status, e.message);
    // Upstream RevenueCat read failure: 502 (Python returned 400); RevenueCat retries either way.
    if (e instanceof RevenueCatUpstreamError) return errorResponse(502, e.message);
    console.error("revenuecat-webhook failed", (e as Error).message);
    return errorResponse(500, "Webhook processing failed.");
  }
}

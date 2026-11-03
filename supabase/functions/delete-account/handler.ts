// POST /delete-account
// Server-side account deletion: cancel the caller's Stripe subscription(s)
// FIRST, and only if that succeeds delete the account (public.delete_user()
// RPC, run with the caller's own JWT so it stays auth.uid()-scoped).
//
// Failure-safe: if Stripe cannot be reached or a cancel fails, nothing is
// deleted and the client gets an error to show (retry is safe: canceling is
// idempotent). Store (App Store / Google Play) subscriptions cannot be
// canceled from a server; `store_subscription` tells the client to say so.

import { loadStripeConfig, loadSupabaseConfig, secretModeConfigured } from "../_shared/config.ts";
import { corsHeaders, Deps } from "../_shared/deps.ts";
import { cancelSubscriptionsForDeletion } from "../_shared/stripe_cancel.ts";
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
    const authorization = req.headers.get("authorization") ?? "";
    const user = await verifyUserJwt(supabase, deps.fetch, authorization);

    // null => billing columns unreadable: we cannot prove there is no subscription, so do not delete.
    const profile = await fetchBillingProfile(supabase, deps.fetch, user.id);
    if (profile === null && !user.isAnonymous) {
      return errorResponse(502, "Could not check your subscription, so your account was not deleted. Try again.", cors, "billing_unreadable");
    }
    const customerId = st(profile?.stripe_customer_id);
    const subscriptionId = st(profile?.stripe_subscription_id);
    const storeSubscription = !!st(profile?.revenuecat_app_user_id);

    let canceled: string[] = [];
    if (customerId || subscriptionId) {
      if (!secretModeConfigured(config)) {
        return errorResponse(502, "Could not cancel your subscription, so your account was not deleted. Try again or contact support.", cors, "cancel_failed");
      }
      try {
        canceled = await cancelSubscriptionsForDeletion(deps.fetch, config.secretKey, { customerId, subscriptionId });
      } catch (e) {
        console.error("delete-account cancel failed", (e as Error).message);
        return errorResponse(502, "Could not cancel your subscription, so your account was not deleted. Try again or contact support.", cors, "cancel_failed");
      }
    }

    // The caller's own JWT, so delete_user() deletes only auth.uid().
    const rpc = await deps.fetch(`${supabase.url}/rest/v1/rpc/delete_user`, {
      method: "POST",
      headers: {
        apikey: supabase.anonKey || supabase.serviceRoleKey,
        Authorization: authorization,
        "Content-Type": "application/json",
      },
      body: "{}",
    });
    if (rpc.status >= 400) {
      console.error("delete-account rpc failed", rpc.status);
      return errorResponse(502, "Your subscription was canceled but the account could not be deleted. Try again.", cors, "delete_failed");
    }
    return jsonResponse({ ok: true, canceled_subscriptions: canceled.length, store_subscription: storeSubscription }, 200, cors);
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.status, e.message, cors, e.code);
    console.error("delete-account failed", (e as Error).message);
    return errorResponse(502, "Could not delete your account. Try again.", cors);
  }
}

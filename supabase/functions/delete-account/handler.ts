// POST /delete-account
// Authenticated with the caller's Supabase JWT; deletes ONLY that user.
// Order is deliberate so a failure never leaves a deleted-but-still-billed user:
//   1. cancel Stripe subscriptions   (any failure aborts; nothing deleted; user can retry)
//   2. revoke Sign in with Apple     (best effort: needs APPLE_* secrets + a fresh code from the client)
//   3. anonymize kept records        (Stripe customer name/email, referral links, analytics, billing events)
//   4. delete the auth user          (cascades app tables; the profiles delete trigger flags any billing left
//                                     uncancelled, so a path that bypasses this function cannot skip it silently)
// Every step is idempotent, so a retry after a partial failure is safe.
// RevenueCat/App Store subscriptions cannot be canceled server-side; the client
// must tell iOS/Android users to cancel in the store (see docs/account-deletion.md).

import { loadStripeConfig, loadSupabaseConfig } from "../_shared/config.ts";
import { corsHeaders, Deps } from "../_shared/deps.ts";
import { accountRefs, anonymizeStripeCustomer, cancelUserSubscriptions, loadAppleConfig, revokeAppleGrant } from "../_shared/account_deletion.ts";
import { anonymizeDeletedUser, deleteAuthUser, deleteNonCascadingUserRows, fetchBillingProfile, markBillingHandled, verifyUserJwt } from "../_shared/supabase_rest.ts";
import { errorResponse, HttpError, isObj, jsonResponse, st } from "../_shared/util.ts";

export async function handle(req: Request, deps: Deps): Promise<Response> {
  const cors = corsHeaders(deps.env, req.headers.get("origin"));
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
  if (req.method !== "POST") return errorResponse(405, "Method not allowed.", cors);

  const stripe = loadStripeConfig(deps.env);
  const supabase = loadSupabaseConfig(deps.env);
  try {
    if (!supabase.url || !supabase.serviceRoleKey) throw new HttpError(500, "Supabase is not configured.");
    const user = await verifyUserJwt(supabase, deps.fetch, req.headers.get("authorization") ?? "");

    let appleCode = "";
    try {
      const body = await req.json();
      if (isObj(body)) appleCode = st(body.apple_authorization_code);
    } catch { /* body is optional */ }

    // Unreadable profile => we cannot prove there is nothing to cancel: fail closed.
    const profile = await fetchBillingProfile(supabase, deps.fetch, user.id);
    if (profile === null) throw new HttpError(503, "Could not verify billing status, so the account was not deleted. Please try again.", "billing_unavailable");

    const subs = await cancelUserSubscriptions(deps.fetch, stripe, {
      userId: user.id,
      customerId: st(profile.stripe_customer_id),
      subscriptionId: st(profile.stripe_subscription_id),
    });

    // Payment records are kept, but the Stripe customer must stop carrying a name/email.
    const customerAnonymized = st(profile.stripe_customer_id)
      ? await anonymizeStripeCustomer(deps.fetch, stripe, st(profile.stripe_customer_id))
      : true;

    let appleRevoked: boolean | null = null; // null = not attempted
    const apple = loadAppleConfig(deps.env);
    if (apple && appleCode) {
      try {
        appleRevoked = await revokeAppleGrant(deps.fetch, apple, appleCode, Math.floor((deps.now ?? (() => new Date()))().getTime() / 1000));
      } catch (e) {
        console.error("delete-account: apple revoke failed", (e as Error).message);
        appleRevoked = false;
      }
      if (!appleRevoked) console.error("delete-account: apple revocation not confirmed");
    }

    const cleanupFailed = await deleteNonCascadingUserRows(supabase, deps.fetch, user.id);
    if (cleanupFailed.length) console.error("delete-account: could not clear rows in", cleanupFailed.join(","));

    // Keep-but-anonymize: referral links, analytics rows, feedback context, billing-event user ids.
    const refs = await accountRefs(user.id, deps.env);
    const anonymized = await anonymizeDeletedUser(supabase, deps.fetch, user.id, refs);
    if (!anonymized) console.error("delete-account: anonymize_deleted_user not applied (run docs/supabase_account_deletion_2026_11.sql)");

    await deleteAuthUser(supabase, deps.fetch, user.id);
    // The profiles delete trigger snapshotted billing ids into deleted_account_billing (flagged as unhandled);
    // record that this path cancelled the subscription and anonymized the customer.
    await markBillingHandled(supabase, deps.fetch, refs.billingRef, { stripeCanceled: true, customerAnonymized });
    return jsonResponse({
      ok: true,
      data_anonymized: anonymized,
      stripe_subscriptions_canceled: subs.canceled.length,
      apple_revoked: appleRevoked,
    }, 200, cors);
  } catch (e) {
    if (e instanceof HttpError) return errorResponse(e.status, e.message, cors, e.code);
    console.error("delete-account failed", (e as Error).message);
    return errorResponse(502, "Could not cancel billing, so the account was not deleted. Please try again or contact support.", cors, "billing_cancel_failed");
  }
}

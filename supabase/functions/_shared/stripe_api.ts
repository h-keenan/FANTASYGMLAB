// Minimal Stripe REST client (form-encoded, no SDK) + checkout/portal logic
// ported from modules/stripe_billing.py (price_id_for_plan, launch week,
// trial eligibility, create_checkout_session, create_customer_portal_session).

import {
  ANNUAL,
  MONTHLY,
  secretModeConfigured,
  StripeConfig,
  TIER_FRONT_OFFICE,
  TIER_PRO,
} from "./config.ts";
import { FetchFn } from "./supabase_rest.ts";
import { HttpError, isObj, Json, st } from "./util.ts";

const STRIPE_API = "https://api.stripe.com/v1";

/** Stripe's bracket-notation form encoding for nested objects/arrays. */
export function encodeForm(params: Json, prefix = ""): string[] {
  const out: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined) continue;
    const key = prefix ? `${prefix}[${k}]` : k;
    if (Array.isArray(v)) {
      v.forEach((item, i) => {
        if (isObj(item)) out.push(...encodeForm(item, `${key}[${i}]`));
        else out.push(`${encodeURIComponent(`${key}[${i}]`)}=${encodeURIComponent(String(item))}`);
      });
    } else if (isObj(v)) out.push(...encodeForm(v, key));
    else out.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(v))}`);
  }
  return out;
}

export async function stripeRequest(
  fetchFn: FetchFn,
  secretKey: string,
  method: "GET" | "POST",
  path: string,
  params: Json = {},
  idempotencyKey = "",
): Promise<Json> {
  const body = encodeForm(params).join("&");
  const headers: Record<string, string> = { Authorization: `Bearer ${secretKey}` };
  if (method === "POST") headers["Content-Type"] = "application/x-www-form-urlencoded";
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  const url = method === "GET" && body ? `${STRIPE_API}${path}?${body}` : `${STRIPE_API}${path}`;
  const res = await fetchFn(url, { method, headers, body: method === "POST" ? body : undefined });
  const data = await res.json().catch(() => ({}));
  if (res.status >= 400) {
    // Log the Stripe error type server-side only; never echo Stripe text to clients.
    console.error("stripe api error", path, res.status, isObj(data) && isObj(data.error) ? st(data.error.type) : "");
    throw new Error(`Stripe ${path} failed (${res.status})`);
  }
  return isObj(data) ? data : {};
}

// ---- Launch Week promo: Oct 12 00:00 CT .. Oct 18 23:59:59 CT 2026 (CDT = UTC-5) ----
export const LAUNCH_WEEK_START = Date.parse("2026-10-12T00:00:00-05:00");
export const LAUNCH_WEEK_END = Date.parse("2026-10-18T23:59:59-05:00");
export function launchWeekActive(now: Date = new Date()): boolean {
  const t = now.getTime();
  return t >= LAUNCH_WEEK_START && t <= LAUNCH_WEEK_END;
}

/** Fails closed; never falls through to a different tier's/interval's price. */
export function priceIdForPlan(config: StripeConfig, tier: string, interval: string, now?: Date): string {
  const tierKey = st(tier).toLowerCase() || TIER_PRO;
  const intervalKey = st(interval).toLowerCase();
  if (tierKey === TIER_FRONT_OFFICE) {
    if (intervalKey !== "" && intervalKey !== ANNUAL) throw new HttpError(503, "Front Office billing is annual-only.");
    if (!config.priceFrontOfficeAnnual) throw new HttpError(503, "Front Office annual price is not configured.");
    return config.priceFrontOfficeAnnual;
  }
  if (tierKey !== TIER_PRO) throw new HttpError(503, `Unknown billing tier: '${tierKey}'.`);
  if (intervalKey === MONTHLY) {
    if (!config.priceMonthly) throw new HttpError(503, "GM Pro monthly price is not configured.");
    return config.priceMonthly;
  }
  if (intervalKey === ANNUAL) {
    if (launchWeekActive(now) && config.priceProAnnualLaunchWeek) return config.priceProAnnualLaunchWeek;
    if (!config.priceAnnual) throw new HttpError(503, "GM Pro annual price is not configured.");
    return config.priceAnnual;
  }
  throw new HttpError(503, "Unknown billing interval.");
}

export function profileHasBillingHistory(profile: Json | null): boolean {
  if (!profile) return false;
  return [
    "stripe_customer_id",
    "stripe_subscription_id",
    "stripe_subscription_status",
    "revenuecat_app_user_id",
    "trial_ends_at",
  ].some((k) => st(profile[k]));
}

async function stripeCustomerHadSubscription(config: StripeConfig, fetchFn: FetchFn, email: string): Promise<boolean> {
  const clean = st(email);
  if (!clean) return false;
  const customers = await stripeRequest(fetchFn, config.secretKey, "GET", "/customers", { email: clean, limit: 10 });
  for (const c of Array.isArray(customers.data) ? customers.data : []) {
    const id = isObj(c) ? st(c.id) : "";
    if (!id) continue;
    const subs = await stripeRequest(fetchFn, config.secretKey, "GET", "/subscriptions", { customer: id, status: "all", limit: 1 });
    if (Array.isArray(subs.data) && subs.data.length) return true;
  }
  return false;
}

/** One free trial per account, Pro only, only when enabled. Fails closed on any doubt. */
export async function trialEligible(
  config: StripeConfig,
  fetchFn: FetchFn,
  opts: { tier: string; email: string; profile: Json | null; profileReadable: boolean },
): Promise<boolean> {
  if (config.trialDays <= 0) return false;
  if ((st(opts.tier).toLowerCase() || TIER_PRO) !== TIER_PRO) return false;
  if (!opts.profileReadable) return false;
  if (profileHasBillingHistory(opts.profile)) return false;
  if (secretModeConfigured(config) && st(opts.email)) {
    try {
      if (await stripeCustomerHadSubscription(config, fetchFn, opts.email)) return false;
    } catch {
      return false;
    }
  }
  return true;
}

/** Same rule as services/mobile_api_service.py `_safe_return_path`: site-relative path only. */
export function safeReturnPath(path: unknown): string {
  const clean = st(path);
  if (!clean.startsWith("/") || clean.startsWith("//") || clean.length > 200 || /[\\\r\n]/.test(clean)) {
    return "/premium";
  }
  return clean;
}

function fingerprint(text: string): string {
  let h = 0x811c9dc5;
  for (let n = 0; n < text.length; n++) {
    h ^= text.charCodeAt(n);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16);
}

export interface CheckoutInput {
  config: StripeConfig;
  userId: string;
  email: string;
  customerId: string;
  tier: string;
  interval: string;
  uiMode: string;
  returnTo: string;
  trialEligible: boolean;
  now?: Date;
}

export async function createCheckoutSession(fetchFn: FetchFn, i: CheckoutInput): Promise<Json> {
  const { config } = i;
  if (!secretModeConfigured(config)) throw new HttpError(503, "Stripe billing mode and secret key do not match.");
  const tierKey = st(i.tier).toLowerCase() || TIER_PRO;
  const intervalKey = st(i.interval).toLowerCase();
  const priceId = priceIdForPlan(config, tierKey, i.interval, i.now);
  const embedded = st(i.uiMode).toLowerCase() === "embedded";
  const trialDays = tierKey === TIER_PRO && i.trialEligible ? config.trialDays : 0;

  const subscriptionData: Json = { metadata: { supabase_user_id: i.userId } };
  if (trialDays > 0) {
    subscriptionData.trial_period_days = trialDays;
    subscriptionData.trial_settings = { end_behavior: { missing_payment_method: "cancel" } };
  }
  const path = safeReturnPath(i.returnTo);
  const urls: Json = embedded
    ? { ui_mode: "embedded", return_url: `${config.appBaseUrl}${path}?billing=complete` }
    : {
      success_url: `${config.appBaseUrl}${path}?billing=success`,
      cancel_url: `${config.appBaseUrl}${path}?billing=cancel`,
    };
  const params: Json = {
    mode: "subscription",
    // Reuse the existing Stripe customer when we have one; otherwise prefill
    // the VERIFIED JWT email (never a client-supplied one).
    ...(i.customerId ? { customer: i.customerId } : { customer_email: st(i.email) || undefined }),
    line_items: [{ price: priceId, quantity: 1 }],
    allow_promotion_codes: true,
    client_reference_id: i.userId,
    payment_method_collection: "always",
    metadata: {
      supabase_user_id: i.userId,
      billing_interval: intervalKey,
      plan_interval: intervalKey,
      billing_tier: tierKey,
    },
    subscription_data: subscriptionData,
    ...urls,
  };
  // Same key shape as Python, plus a fingerprint of the full params: Stripe
  // rejects a reused key whose params differ (e.g. different return path).
  const idempotencyKey = `fgl-checkout-${i.userId}-${intervalKey}-${priceId}-${embedded ? "embedded" : "hosted"}-t${trialDays}-${fingerprint(encodeForm(params).join("&"))}`.slice(0, 255);
  return await stripeRequest(fetchFn, config.secretKey, "POST", "/checkout/sessions", params, idempotencyKey);
}

export async function createPortalSession(fetchFn: FetchFn, config: StripeConfig, customerId: string): Promise<Json> {
  if (!secretModeConfigured(config)) throw new HttpError(503, "Stripe billing mode and secret key do not match.");
  if (!st(customerId)) throw new HttpError(404, "No billing account found for this user yet.");
  return await stripeRequest(fetchFn, config.secretKey, "POST", "/billing_portal/sessions", {
    customer: customerId,
    return_url: `${config.appBaseUrl}/premium`,
  });
}
